import argparse
import json
import logging
import os
import sys
from datetime import datetime

import requests
import tabulate
import yaml
from dateutil.relativedelta import relativedelta
import pytz

from .release_collection import ReleaseCollection
from .release_model import Release
from .release_type import ReleaseType
from .util import (
    DEFAULTS,
    ERROR_CODES,
    get_current_timestamp,
    timestamp_to_isotime,
    get_version,
    NoAliasDumper,
)

# Lifecycle compliance checks only apply to releases from this major version
# onwards. Older releases were created under different lifecycle rules
# (extended = released + 6 months, eol = released + 9 months) and are hard
# excluded from the check. See docs/explanation/release-lifecycle.md.
LIFECYCLE_CHECK_MIN_MAJOR = 1877

DEFAULTS = dict(
    DEFAULTS,
    **{
        "POSSIBLE_FIELDS_MAP": {
            "Name": lambda r: r.get("name", "N/A"),
            "Version": lambda r: get_version_string(r["version"], r.get("type")),
            "Type": lambda r: r.get("type", "N/A"),
            "GitCommit": lambda r: r.get("git", {}).get("commit", "N/A"),
            "GitCommitShort": lambda r: r.get("git", {}).get("commit_short", "N/A"),
            "ReleaseDate": lambda r: r["lifecycle"]["released"].get("isodate", "N/A"),
            "ReleaseTime": lambda r: timestamp_to_isotime(
                r["lifecycle"]["released"].get("timestamp")
            ),
            "ExtendedMaintenance": lambda r: get_extended_maintenance(r),
            "EndOfMaintenance": lambda r: r["lifecycle"]
            .get("eol", {})
            .get("isodate", "N/A"),
            "Flavors": lambda r: ",".join(r.get("flavors", []))
            or "N/A",  # Simple comma-separated list for shell output
            "OCI": lambda r: get_oci_url(r),
            "AttributesSourceRepo": lambda r: str(
                r.get("attributes", {}).get("source_repo", "N/A")
            ),
        }
    },
)


def get_version_string(version, release_type=None):
    """
    Return a version string from a version object, respecting versioned schemas.

    Args:
        version: Version object containing major, minor, and optionally patch fields
        release_type: Type of release (major, minor, nightly, dev, next)

    Returns:
        Formatted version string appropriate for the release type and version
    """
    if release_type in ["major", "next"]:
        return str(version["major"])  # Major releases show only major version

    # For minor, nightly, and dev releases, determine format based on version number
    major = version.get("major", 0)
    minor = version.get("minor", 0)
    patch = version.get("patch", 0)

    # Use v2 schema format (with patch) for versions >= 2017.0.0
    if major >= 2017:
        return f"{major}.{minor}.{patch}"
    else:
        # Use v1 schema format (without patch) for versions < 2017.0.0
        return f"{major}.{minor}"


def is_active_release(release, current_timestamp):
    """Check if the release is still active based on its EOL timestamp."""
    return Release.from_dict(release).lifecycle.is_active(current_timestamp)


def filter_active_releases(releases):
    """Filter and return only active releases."""
    current_timestamp = get_current_timestamp()
    return [
        release for release in releases if is_active_release(release, current_timestamp)
    ]


def is_archived_release(release, current_timestamp):
    """Check if the release archived based on its EOL timestamp."""
    return Release.from_dict(release).lifecycle.is_archived(current_timestamp)


def filter_archived_releases(releases):
    """Filter and return only archived releases."""
    current_timestamp = get_current_timestamp()
    return [
        release
        for release in releases
        if is_archived_release(release, current_timestamp)
    ]


def filter_releases(releases, release_types=None, version=None):
    """
    Filter releases by type and/or version, respecting versioned schemas.

    Args:
        releases: List of release objects (dicts) to filter
        release_types: Comma-separated string of release types to include
        version: Version string in format major.minor.patch (patch is optional)

    Returns:
        Filtered list of releases (dicts)
    """
    collection = ReleaseCollection([Release.from_dict(r) for r in releases])

    if version:
        version_parts = version.split(".")
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else None
        patch = int(version_parts[2]) if len(version_parts) > 2 else None
        collection = collection.filter_version(major, minor, patch)

    if release_types:
        valid = {rt.value for rt in ReleaseType}
        # Unknown types are ignored (they simply match nothing), preserving the
        # historical behavior where an invalid --type produced an empty result
        # rather than an error.
        types = [ReleaseType(t) for t in release_types.split(",") if t in valid]
        collection = collection.by_types(types)

    return collection.to_list()


def find_latest_release(releases):
    """
    Find the latest release by version, respecting versioned schemas.

    Args:
        releases: List of release objects (dicts) to search

    Returns:
        The latest release object (dict) or None if no releases found
    """
    collection = ReleaseCollection([Release.from_dict(r) for r in releases])
    latest = collection.latest()
    return latest.to_dict() if latest else None


def get_extended_maintenance(release):
    """Return the extended maintenance date for a release, if available."""
    extended = release["lifecycle"].get("extended", {})
    if extended.get("isodate"):
        return extended["isodate"]
    # Default to N/A if extended is missing
    return "N/A"


def duration_in_months(start_date, end_date):
    """Compute the number of months between two dates."""
    delta = end_date - start_date
    months = delta.days / 30.44  # Approximate average days in a month
    return round(months)


def prepare_structured_output(release):
    """Prepare a release object for JSON/YAML output by adding URLs and organizing fields."""
    release_copy = {}

    # Add core fields first in specific order
    core_fields = ["name", "type", "version", "lifecycle", "git", "github"]
    for field in core_fields:
        if field in release:
            release_copy[field] = release[field]

    # Add flavors with URLs
    release_copy["flavors"] = format_flavors_with_urls(release)

    # Add OCI URL
    release_copy["oci"] = get_oci_url(release)

    # Add attributes last
    if "attributes" in release:
        release_copy["attributes"] = release["attributes"]

    return release_copy


def format_structured_output(releases, output_format):
    """Format releases as JSON or YAML."""
    releases_with_urls = [prepare_structured_output(r) for r in releases]
    data = {"releases": releases_with_urls}

    if output_format == "json":
        return json.dumps(data, indent=2)
    else:  # yaml
        return yaml.dump(
            data,
            default_flow_style=False,
            sort_keys=False,
            Dumper=NoAliasDumper,
        )


def format_tabular_output(releases, fields, no_header, output_format):
    """Format releases as a table for shell or markdown output."""
    # Get the requested fields or use defaults
    selected_fields = (
        fields.split(",") if fields else DEFAULTS["QUERY_FIELDS"].split(",")
    )

    # Get all available fields for validation
    all_fields = list(DEFAULTS["POSSIBLE_FIELDS_MAP"].keys())

    # Validate and filter the fields
    selected_fields, _ = filter_fields(all_fields, [], selected_fields)

    # Generate rows using only the selected fields
    rows = [
        [DEFAULTS["POSSIBLE_FIELDS_MAP"][field](r) for field in selected_fields]
        for r in releases
    ]

    headers = selected_fields if not no_header else ()

    if output_format == "shell":
        return tabulate.tabulate(rows, headers, tablefmt="plain", disable_numparse=True)
    elif output_format == "markdown":
        return tabulate.tabulate(rows, headers, tablefmt="pipe", disable_numparse=True)


def filter_fields(headers, rows, requested_fields):
    """Filter columns in tabular data based on requested fields."""
    # Validate requested fields
    invalid_fields = [f for f in requested_fields if f not in headers]
    if invalid_fields:
        logging.error(f"Invalid field(s): {', '.join(invalid_fields)}")
        logging.error(f"Available fields: {', '.join(headers)}")
        sys.exit(ERROR_CODES["invalid_field"])

    # Get indices of requested fields
    indices = [headers.index(field) for field in requested_fields]

    # Filter headers and rows
    filtered_headers = [headers[i] for i in indices]
    filtered_rows = [[row[i] for i in indices] for row in rows]

    return filtered_headers, filtered_rows


def format_mermaid_gantt(args, releases):
    """Format releases as a Mermaid Gantt chart."""
    output = []
    output.append("gantt")
    output.append(f"    title {args.output_description}")
    output.append("    axisFormat %m.%y")

    for release in releases:
        name = get_version_string(release["version"], release.get("type"))
        # name = release['name']
        output.append(f"    section {name}")

        # Extract dates
        released_date_str = release["lifecycle"]["released"].get("isodate")
        extended_date_str = release["lifecycle"].get("extended", {}).get("isodate")
        eol_date_str = release["lifecycle"].get("eol", {}).get("isodate")  # End of life

        # Convert dates to datetime objects
        date_format = "%Y-%m-%d"
        released_date = (
            datetime.strptime(released_date_str, date_format)
            if released_date_str
            else None
        )
        extended_date = (
            datetime.strptime(extended_date_str, date_format)
            if extended_date_str
            else None
        )
        eol_date = (
            datetime.strptime(eol_date_str, date_format) if eol_date_str else None
        )

        # Add 'Release' milestone
        if released_date:
            released_date_formatted = released_date.strftime("%Y-%m-%d")
            output.append(
                f"        Release:                milestone, {released_date_formatted}, 0m"
            )

        # Standard maintenance
        if released_date and extended_date:
            duration_months = duration_in_months(released_date, extended_date)
            duration_str = f"{duration_months}M"
            start_date_str = released_date.strftime("%Y-%m-%d")
            output.append(
                f"        Standard maintenance:       task, {start_date_str}, {duration_str}"
            )

        # Extended maintenance
        if extended_date and eol_date:
            # Extended maintenance start as a milestone
            extended_date_formatted = extended_date.strftime("%Y-%m-%d")
            output.append(
                f"        Extended maintenance:       milestone, {extended_date_formatted}, 0m"
            )
            duration_months = duration_in_months(extended_date, eol_date)
            duration_str = f"{duration_months}M"
            start_date_str = extended_date.strftime("%Y-%m-%d")
            output.append(
                f"        Extended maintenance:       task, {start_date_str}, {duration_str}"
            )
            # End of maintenance milestone
            eol_date_formatted = eol_date.strftime("%Y-%m-%d")
            output.append(
                f"        End of maintenance:         milestone, {eol_date_formatted}, 0m"
            )
        elif eol_date:
            # No extended maintenance, but have eol_date
            eol_date_formatted = eol_date.strftime("%Y-%m-%d")
            output.append(
                f"        End of maintenance:         milestone, {eol_date_formatted}, 0m"
            )

    return "\n".join(output)


def format_output(args, releases, output_format, fields=None, no_header=False):
    """Format and print release data in the specified format."""
    formatted_output = None

    if output_format in ["json", "yaml"]:
        formatted_output = format_structured_output(releases, output_format)
    elif output_format in ["shell", "markdown"]:
        formatted_output = format_tabular_output(
            releases, fields, no_header, output_format
        )
    elif output_format == "mermaid_gantt":
        formatted_output = format_mermaid_gantt(args, releases)

    if formatted_output is not None:
        print(formatted_output)


def sort_releases(releases):
    """
    Sort releases by version, respecting versioned schemas.

    Args:
        releases: List of release objects (dicts) to sort

    Returns:
        Sorted list of releases (dicts)
    """
    collection = ReleaseCollection([Release.from_dict(r) for r in releases])
    return [r.to_dict() for r in collection.sorted()]


def load_releases(input_source, is_url=False):
    """Load the releases from a file or a URL."""
    if is_url:
        try:
            response = requests.get(input_source)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f"Error fetching data from URL: {e}")
            sys.exit(ERROR_CODES["http_error"])
    else:
        if not os.path.exists(input_source):
            logging.error(f"Error: File {input_source} does not exist.")
            sys.exit(ERROR_CODES["file_not_found"])
        with open(input_source, "r") as file:
            return json.load(file)


def load_split_releases(
    release_type, input_type, input_url, input_file_prefix, input_format
):
    """Load and split releases based on type."""
    (
        releases_next,
        releases_major,
        releases_minor,
        releases_nightly,
        releases_dev,
    ) = (
        [],
        [],
        [],
        [],
        [],
    )
    types = release_type.split(",")
    is_url = input_type == "url"

    if "next" in types:
        input_file = input_file_prefix + "-next" + "." + input_format
        if is_url:
            input_file = input_url + "/" + input_file
        releases_next = load_releases(input_file, is_url=is_url).get("releases", [])

    if "major" in types:
        input_file = input_file_prefix + "-major" + "." + input_format
        if is_url:
            input_file = input_url + "/" + input_file
        releases_major = load_releases(input_file, is_url=is_url).get("releases", [])

    if "minor" in types:
        input_file = input_file_prefix + "-minor" + "." + input_format
        if is_url:
            input_file = input_url + "/" + input_file
        releases_minor = load_releases(input_file, is_url=is_url).get("releases", [])

    if "nightly" in types:
        input_file = input_file_prefix + "-nightly" + "." + input_format
        if is_url:
            input_file = input_url + "/" + input_file
        releases_nightly = load_releases(input_file, is_url=is_url).get("releases", [])

    if "dev" in types:
        input_file = input_file_prefix + "-dev" + "." + input_format
        if is_url:
            input_file = input_url + "/" + input_file
        releases_dev = load_releases(input_file, is_url=is_url).get("releases", [])

    return (
        releases_next
        + releases_major
        + releases_minor
        + releases_nightly
        + releases_dev
    )


# def load_all_releases(args):
def load_all_releases(
    release_type,
    input_type,
    input_url,
    input_file_prefix,
    input_format,
    no_input_split=False,
):
    """Load releases either from a single source or split by type."""
    if no_input_split:
        return load_releases(input_url, is_url=(input_type == "url")).get(
            "releases", []
        )
    else:
        return load_split_releases(
            release_type,
            input_type,
            input_url,
            input_file_prefix,
            input_format,
        )


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Process and filter releases data from a file or URL."
    )

    parser.add_argument(
        "--input-format",
        type=str,
        choices=["yaml", "json"],
        default=DEFAULTS["QUERY_INPUT_FORMAT"],
        help="Input format: 'yaml' or 'json' (default: json).",
    )

    parser.add_argument(
        "--input-file-prefix",
        type=str,
        default=DEFAULTS["QUERY_INPUT_FILE_PREFIX"],
        help="The prefix to get input files (default: releases).",
    )

    parser.add_argument(
        "--input-type",
        choices=["file", "url"],
        default=DEFAULTS["QUERY_INPUT_TYPE"],
        help="Specify if the input type (default: url).",
    )

    parser.add_argument(
        "--input-url",
        type=str,
        default=DEFAULTS["QUERY_INPUT_URL"],
        help="Input URL to the releases data. Defaults to gardenlinux-glrd S3 URL.",
    )

    parser.add_argument(
        "--no-input-split",
        action="store_true",
        help="Do not split Input into major+minor and nightly. No additional "
        "input-files *-nightly and *-dev will be parsed.",
    )

    parser.add_argument(
        "--output-format",
        choices=["json", "yaml", "markdown", "mermaid_gantt", "shell"],
        default=DEFAULTS["QUERY_OUTPUT_TYPE"],
        help="Output format: json, yaml, markdown, mermaid_gantt, shell (default).",
    )

    parser.add_argument(
        "--output-description",
        type=str,
        default=DEFAULTS["QUERY_OUTPUT_DESCRIPTION"],
        help="Description, added to certain outputs, e.g. mermaid "
        "(default: 'Garden Linux Releases').",
    )

    parser.add_argument(
        "--active", action="store_true", help="Show only active releases."
    )

    parser.add_argument(
        "--archived", action="store_true", help="Show only archived releases."
    )

    parser.add_argument(
        "--latest",
        action="store_true",
        help="Show the latest active major.minor.patch release.",
    )

    parser.add_argument(
        "--type",
        type=str,
        default=DEFAULTS["QUERY_TYPE"],
        help="Filter by release types (comma-separated list, default: "
        "major,minor). E.g., --type major,minor,nightly,dev,next",
    )

    parser.add_argument(
        "--version",
        type=str,
        help="Filter by a specific version (major or major.minor.patch). "
        "E.g., --version 1312 or --version 1312.0 or --version 1312.0.0",
    )

    parser.add_argument(
        "--fields",
        type=str,
        help=(
            "Comma-separated list of fields to output. Possible fields: "
            + ",".join(DEFAULTS["POSSIBLE_FIELDS_MAP"].keys())
            + " (default: "
            + DEFAULTS["QUERY_FIELDS"]
            + ")"
        ),
    )

    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Omit the header in shell output.",
    )

    parser.add_argument(
        "--check-lifecycle",
        action="store_true",
        help="Check releases against lifecycles rules.",
    )

    parser.add_argument("-V", action="version", version=f"%(prog)s {get_version()}")

    return parser.parse_args()


def get_platform_from_flavor(flavor):
    """Extract platform from flavor string."""
    try:
        return flavor.split("-")[0]
    except Exception as e:
        logging.error(f"Error extracting platform from flavor {flavor}: {e}")
        sys.exit(ERROR_CODES["format_error"])


def get_container_registry(release_type):
    """Return the container registry URL for the given release type."""
    if release_type == "nightly":
        return DEFAULTS["CONTAINER_REGISTRY_NIGHTLY"]
    return DEFAULTS["CONTAINER_REGISTRY_MINOR"]


def prepare_oci_flavor_url(flavor, version, platform, release_type=None):
    """Create OCI URL for container/bare platforms."""
    try:
        if platform == "container":
            return {"oci": f"{get_container_registry(release_type)}:{version}"}
        elif platform == "bare":
            flavor_base = "-".join(flavor.split("-")[:-1])
            return {
                "oci": f"{get_container_registry(release_type)}/{flavor_base}:{version}"
            }
    except Exception as e:
        logging.error(f"Error creating URLs for container/bare platforms: {e}")
        sys.exit(ERROR_CODES["format_error"])


def prepare_regular_flavor_urls(flavor, version, commit_short, platform):
    """Create metadata and image URLs for regular platforms."""
    try:
        image_ext = DEFAULTS["PLATFORM_EXTENSIONS"].get(platform, "raw")
        base_url = (
            f"{DEFAULTS['ARTIFACTS_S3_BASE_URL']}/"
            f"{DEFAULTS['ARTIFACTS_S3_PREFIX']}"
            f"{flavor}-{version}-{commit_short}"
        )
        base_filename = f"{flavor}-{version}-{commit_short}"

        return {
            "metadata": f"{base_url}/{base_filename}.manifest",
            "image": f"{base_url}/{base_filename}.{image_ext}",
        }
    except Exception as e:
        logging.error(f"Error creating URLs for flavor {flavor}: {e}")
        sys.exit(ERROR_CODES["format_error"])


def format_flavors_with_urls(release):
    """Format flavors as a map with metadata and image URLs."""
    """Return empty dict if no flavors in release."""
    if not release.get("flavors"):
        return {}

    try:
        # Get version string respecting versioned schemas
        version = get_version_string(release["version"], release.get("type"))
        commit_short = release["git"].get("commit_short", "")

        regular_flavors = {}
        oci_flavors = {}

        for flavor in sorted(release["flavors"]):
            platform = get_platform_from_flavor(flavor)

            # Handle OCI-based platforms
            if platform in ["container", "bare"]:
                urls = prepare_oci_flavor_url(
                    flavor, version, platform, release.get("type")
                )
                if urls:
                    oci_flavors[flavor] = urls
                continue

            # Handle regular platforms
            urls = prepare_regular_flavor_urls(flavor, version, commit_short, platform)
            if urls:
                regular_flavors[flavor] = urls

        # Combine regular and OCI flavors, with OCI flavors at the end
        return {**regular_flavors, **oci_flavors}

    except Exception as e:
        logging.error(f"Error formatting flavors with URLs: {e}")
        sys.exit(ERROR_CODES["format_error"])


def get_oci_url(release):
    """Return the OCI image URL for a release."""
    try:
        # Get version string respecting versioned schemas
        version = get_version_string(release["version"], release.get("type"))
        return f"{get_container_registry(release.get('type'))}:{version}"
    except Exception as e:
        logging.error(f"Error getting OCI URL: {e}")
        sys.exit(ERROR_CODES["format_error"])


def check_releases_lifecycle(context_releases, query_releases):
    """
    Validate query_releases' dates against Garden Linux lifecycle rules.
    Returns True if all query_releases matched, False otherwise.
    """
    mismatches = []

    # Sort context minor releases by minor version inside major version groups
    # to facilitate Case 2a and Case 2b
    minors_by_major = {}
    for r in context_releases:
        if r.get("type") == "minor":
            major_num = r["version"]["major"]
            minors_by_major.setdefault(major_num, []).append(r)

    for major_num in minors_by_major:
        minors_by_major[major_num].sort(key=lambda x: x["version"].get("minor", 0))

    # Parent majors keyed by major number
    majors_by_num = {
        r["version"]["major"]: r for r in context_releases if r.get("type") == "major"
    }

    print("Checking release lifecycle compliance...")

    matched_count = 0
    mismatched_count = 0

    for r in query_releases:
        rtype = r.get("type")
        name = r.get("name")

        # Hard exclude releases older than LIFECYCLE_CHECK_MIN_MAJOR. These
        # predate the current lifecycle rules and must not be checked or
        # reported on.
        major_num = r.get("version", {}).get("major")
        if isinstance(major_num, int) and major_num < LIFECYCLE_CHECK_MIN_MAJOR:
            continue

        # Nightly and dev do not carry extended/eol dates
        if rtype in ("nightly", "dev"):
            print(f"  {name}: OK (ephemeral type)")
            matched_count += 1
            continue

        released_str = r.get("lifecycle", {}).get("released", {}).get("isodate")
        if not released_str:
            print(f"  {name}: FAIL (missing released date)")
            mismatches.append((name, "released", "YYYY-MM-DD", "N/A"))
            mismatched_count += 1
            continue

        try:
            released_dt = datetime.strptime(released_str, "%Y-%m-%d").replace(
                tzinfo=pytz.UTC
            )
        except ValueError:
            print(f"  {name}: FAIL (invalid released date format)")
            mismatches.append((name, "released", "YYYY-MM-DD", released_str))
            mismatched_count += 1
            continue

        if rtype == "major":
            # Check standard maintenance (extended) and end of life (eol)
            is_lts = r.get("attributes", {}).get("lts", False)

            # Expected extended is released + 9 months
            expected_extended_dt = released_dt + relativedelta(months=9)
            expected_extended = expected_extended_dt.strftime("%Y-%m-%d")

            # Expected EOL is released + 15 months (standard) or 5 years (LTS), aligned to end of month
            if is_lts:
                expected_eol_dt = (
                    released_dt + relativedelta(years=5) + relativedelta(day=31)
                )
            else:
                expected_eol_dt = (
                    released_dt + relativedelta(months=15) + relativedelta(day=31)
                )
            expected_eol = expected_eol_dt.strftime("%Y-%m-%d")

            actual_extended = (
                r.get("lifecycle", {}).get("extended", {}).get("isodate", "N/A")
            )
            actual_eol = r.get("lifecycle", {}).get("eol", {}).get("isodate", "N/A")

            release_ok = True
            if actual_extended != expected_extended:
                mismatches.append(
                    (name, "extended", expected_extended, actual_extended)
                )
                release_ok = False
            if actual_eol != expected_eol:
                mismatches.append((name, "eol", expected_eol, actual_eol))
                release_ok = False

            if release_ok:
                print(f"  {name}: OK")
                matched_count += 1
            else:
                print(f"  {name}: FAIL (date mismatch)")
                mismatched_count += 1

        elif rtype == "minor":
            major_num = r["version"]["major"]
            series = minors_by_major.get(major_num, [])

            # Find the index of current release in the series
            try:
                idx = next(i for i, x in enumerate(series) if x["name"] == name)
            except StopIteration:
                print(f"  {name}: FAIL (not found in series)")
                mismatches.append((name, "series", "found", "not found"))
                mismatched_count += 1
                continue

            # Case 2a: Intermediate minor release (not the last)
            if idx < len(series) - 1:
                next_minor = series[idx + 1]
                expected_eol = (
                    next_minor.get("lifecycle", {})
                    .get("released", {})
                    .get("isodate", "N/A")
                )
            else:
                # Case 2b: Latest minor release (last)
                parent_major = majors_by_num.get(major_num)
                if parent_major:
                    expected_eol = (
                        parent_major.get("lifecycle", {})
                        .get("eol", {})
                        .get("isodate", "N/A")
                    )
                else:
                    expected_eol = "N/A (missing parent major)"

            actual_eol = r.get("lifecycle", {}).get("eol", {}).get("isodate", "N/A")

            if actual_eol == expected_eol:
                print(f"  {name}: OK")
                matched_count += 1
            else:
                mismatches.append((name, "eol", expected_eol, actual_eol))
                print(f"  {name}: FAIL (date mismatch)")
                mismatched_count += 1

        else:
            print(f"  {name}: OK (type {rtype} bypassed)")
            matched_count += 1

    print("\nSummary:")
    print(f"  Total Checked: {matched_count + mismatched_count}")
    print(f"  Passed:        {matched_count}")
    print(f"  Failed:        {mismatched_count}")

    if mismatches:
        print("\nMismatches detailed:")
        for name, field, expected, actual in mismatches:
            print(f"  - {name}: {field} mismatch")
            print(f"    Expected: {expected}")
            print(f"    Actual:   {actual}")
        return False

    return True


def process_query(args):
    """Process the query based on command line arguments."""
    # Load releases
    releases = load_all_releases(
        args.type,
        args.input_type,
        args.input_url,
        args.input_file_prefix,
        args.input_format,
        args.no_input_split,
    )

    if not releases:
        logging.error("No releases found.")
        sys.exit(ERROR_CODES["no_releases"])

    if getattr(args, "check_lifecycle", False):
        # We need all releases as background context to resolve minor version relationships
        context_releases = []
        for t in ["major", "minor"]:
            if args.input_type == "file" and not args.no_input_split:
                input_file = f"{args.input_file_prefix}-{t}.{args.input_format}"
                if not os.path.exists(input_file):
                    continue
            try:
                type_releases = load_all_releases(
                    t,
                    args.input_type,
                    args.input_url,
                    args.input_file_prefix,
                    args.input_format,
                    args.no_input_split,
                )
                context_releases.extend(type_releases)
            except SystemExit as e:
                if e.code != ERROR_CODES["file_not_found"]:
                    raise
        # Apply the same filters on the query releases so we check what was queried
        query_releases = list(releases)
        if args.version:
            query_releases = filter_releases(query_releases, version=args.version)
        if args.type:
            query_releases = filter_releases(query_releases, release_types=args.type)
        if args.active:
            query_releases = filter_active_releases(query_releases)
        elif args.archived:
            query_releases = filter_archived_releases(query_releases)
        if args.latest:
            latest = find_latest_release(query_releases)
            query_releases = [latest] if latest else []

            query_releases = sort_releases(query_releases)

        ok = check_releases_lifecycle(context_releases, query_releases)
        if not ok:
            sys.exit(ERROR_CODES["validation_error"])
        sys.exit(0)

    # Filter by version if specified
    if args.version:
        releases = filter_releases(releases, version=args.version)

    # Filter by type if specified
    if args.type:
        releases = filter_releases(releases, release_types=args.type)

    # Filter active/archived releases
    if args.active:
        releases = filter_active_releases(releases)
    elif args.archived:
        releases = filter_archived_releases(releases)

    # Get latest release if requested
    if args.latest:
        latest = find_latest_release(releases)
        releases = [latest] if latest else []

    # Sort releases
    releases = sort_releases(releases)

    # Format and output the results
    format_output(args, releases, args.output_format, args.fields, args.no_header)


def main():
    parser = argparse.ArgumentParser(
        description="Garden Linux Release Database Query Tool"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {get_version()}"
    )
    args = parse_arguments()

    process_query(args)


if __name__ == "__main__":
    main()
