import argparse
import json
import logging
import os
import sys
from datetime import datetime

import boto3
import pytz
import yaml
from dateutil.relativedelta import relativedelta
from deepdiff.diff import DeepDiff

from glrd.git import (
    get_github_releases,
    get_git_commit_at_time,
    get_garden_version_for_date,
    create_initial_releases,
    create_initial_nightly_releases,
)
from glrd.query import load_all_releases
from glrd.release import (
    GitInfo,
    Lifecycle,
    LifecyclePhase,
    Release,
    ReleaseType,
    Version,
    parse_release_name as model_parse_release_name,
)
from glrd.s3 import (
    create_s3_bucket,
    download_all_s3_files,
    merge_existing_s3_data,
    save_output_file,
    upload_all_local_files,
    upload_to_s3,
)
from glrd.validation import validate_input_version_format, validate_all_releases
from glrd.util import (
    DEFAULTS,
    ERROR_CODES,
    get_version,
    merge_input_data,
    resolve_flavors,
    split_releases_by_type,
)

# silence boto3 logging
boto3.set_stream_logger(name="botocore.credentials", level=logging.ERROR)


# Global variable to store the path of the cloned gardenlinux repository (cached)
repo_clone_path = None


def glrd_query_type(args, release_type):
    """Retrieve releases of a specific type."""
    try:
        releases = load_all_releases(
            release_type,
            getattr(args, "input_type", None) or DEFAULTS["QUERY_INPUT_TYPE"],
            getattr(args, "input_url", None) or DEFAULTS["QUERY_INPUT_URL"],
            getattr(args, "input_file_prefix", None)
            or DEFAULTS["QUERY_INPUT_FILE_PREFIX"],
            getattr(args, "query_input_format", None) or DEFAULTS["QUERY_INPUT_FORMAT"],
        )
        if not releases:
            logging.warning(
                f"No releases found for type '{release_type}', returning empty list"
            )
            return []
        return releases
    except SystemExit:
        # If load_all_releases exits due to S3 access issues (like in tests),
        # return empty list instead of propagating the exit
        logging.warning(
            f"Could not retrieve releases for type '{release_type}', returning empty list"
        )
        return []


def ensure_isodate_and_timestamp(lifecycle):
    """
    Ensure both isodate and timestamp are set for all lifecycle fields
    (released, extended, eol). If only one is present, the other is
    computed.

    This operates on the raw lifecycle dict (the JSON boundary) but delegates
    the isodate<->timestamp conversion to the release model's
    ``LifecyclePhase.ensure_complete`` so there is a single source of truth for
    that logic.
    """
    for key in ["released", "extended", "eol"]:
        entry = lifecycle.get(key)
        if not entry:
            continue
        phase = LifecyclePhase(
            isodate=entry.get("isodate"),
            timestamp=entry.get("timestamp"),
        )
        phase.ensure_complete()
        if entry.get("isodate") and not entry.get("timestamp"):
            entry["timestamp"] = phase.timestamp
        elif entry.get("timestamp") and not entry.get("isodate"):
            entry["isodate"] = phase.isodate


def create_single_release(release_type, args, existing_releases):
    """Create a single release of the specified type."""
    if release_type not in DEFAULTS["RELEASE_TYPES"]:
        logging.error(f"Invalid release type: {release_type}")
        sys.exit(ERROR_CODES["parameter_missing"])

    # Check if a manual lifecycle-released-isodatetime is provided, otherwise use the current date
    if args.lifecycle_released_isodatetime:
        try:
            release_date = datetime.strptime(
                args.lifecycle_released_isodatetime, "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=pytz.UTC)
        except ValueError:
            logging.error(
                "Error: Invalid --date-time-release format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
            sys.exit(ERROR_CODES["validation_error"])
    else:
        tz = pytz.timezone("UTC")
        release_date = tz.localize(datetime.now())

    lifecycle_released_isodate = release_date.strftime("%Y-%m-%d")
    lifecycle_released_timestamp = int(release_date.timestamp())

    if args.lifecycle_extended_isodatetime:
        try:
            extended_date = datetime.strptime(
                args.lifecycle_extended_isodatetime, "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=pytz.UTC)
            lifecycle_extended_isodate = extended_date.strftime("%Y-%m-%d")
            lifecycle_extended_timestamp = int(extended_date.timestamp())
        except ValueError:
            logging.error(
                "Error: Invalid --lifecycle-extended-isodatetime format. "
                "Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
            sys.exit(ERROR_CODES["validation_error"])
    else:
        # for major - default extended maintenance date is release date + 6 months
        if release_type == "major":
            extended_date = release_date + relativedelta(months=6)
            lifecycle_extended_isodate = extended_date.strftime("%Y-%m-%d")
            lifecycle_extended_timestamp = int(extended_date.timestamp())
        # minor releases will use set_latest_minor_eol_to_major() to set lifecycle fields
        # other release types to not have extended lifecycle fields
        else:
            lifecycle_extended_isodate = None
            lifecycle_extended_timestamp = None

    if args.lifecycle_eol_isodatetime:
        try:
            eol_date = datetime.strptime(
                args.lifecycle_eol_isodatetime, "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=pytz.UTC)
            lifecycle_eol_isodate = eol_date.strftime("%Y-%m-%d")
            lifecycle_eol_timestamp = int(eol_date.timestamp())
        except ValueError:
            logging.error(
                "Error: Invalid --lifecycle-eol-isodatetime format. "
                "Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
            sys.exit(ERROR_CODES["validation_error"])
    else:
        # for major - default eol date is release date + 9 months
        if release_type == "major":
            eol_date = release_date + relativedelta(months=9)
            lifecycle_eol_isodate = eol_date.strftime("%Y-%m-%d")
            lifecycle_eol_timestamp = int(eol_date.timestamp())
        # minor releases will use set_latest_minor_eol_to_major() to set lifecycle fields
        # other release types to not have extended lifecycle fields
        else:
            lifecycle_eol_isodate = None
            lifecycle_eol_timestamp = None

    # Resolve the git commit only for release types that store it
    # (minor, nightly, dev). 'next' and 'major' releases do not carry a commit,
    # so we avoid the network lookup (git clone) entirely for them.
    commit = None
    commit_short = None
    if release_type in ("minor", "nightly", "dev"):
        if args.commit:
            commit = args.commit
            if len(commit) != 40:
                logging.error("Error: Invalid commit hash. Must be 40 characters.")
                sys.exit(ERROR_CODES["validation_error"])
            commit_short = commit[:8]
        else:
            commit, commit_short = get_git_commit_at_time(lifecycle_released_isodate)

    # Check if a manual version is provided, otherwise use garden version for the date
    if args.create == "next":
        major = "next"
        minor = None
        patch = None
    elif args.version and args.create == "major":
        # For 'major' releases, version should not contain '.'
        if "." in args.version:
            logging.error(
                "Error: Invalid --version format for major release. "
                "Use format: major (integer without '.')"
            )
            sys.exit(ERROR_CODES["validation_error"])
        try:
            major = int(args.version)
            minor = None
            patch = None
        except ValueError:
            logging.error(
                "Error: Invalid --version format. Major version must be an integer."
            )
            sys.exit(ERROR_CODES["validation_error"])
    elif args.version and args.create != "major":
        try:
            is_valid, error_message = validate_input_version_format(
                args.version, args.create
            )
            if not is_valid:
                logging.error(f"Error: {error_message}")
                sys.exit(ERROR_CODES["validation_error"])

            version_parts = args.version.split(".")
            major, minor = map(int, version_parts[:2])
            if len(version_parts) == 2:
                patch = 0
            else:
                patch = int(version_parts[2])

        except ValueError:
            logging.error(
                "Error: Invalid --version format. Use format: "
                "major.minor (for versions < 2017.0.0) or "
                "major.minor.patch (for versions >= 2017.0.0)"
            )
            sys.exit(ERROR_CODES["validation_error"])
    else:
        major, minor, patch = get_garden_version_for_date(
            release_type, release_date, existing_releases
        )

    # Create version object
    version = {"major": major, "minor": minor, "patch": patch}

    # Flavors only apply to release types that carry a git commit.
    flavors = []
    if release_type in ("minor", "nightly", "dev"):
        flavors = resolve_flavors(
            commit, version, skip=getattr(args, "no_flavors", False)
        )
        if not flavors:
            logging.info(
                f"No flavors found anywhere for version {version} "
                f"(commit {commit_short})"
            )

    # Build the release using the domain model (single source of truth for
    # name generation, version shape, and serialization).
    rtype = ReleaseType(release_type)
    version_obj = Version(major, minor, patch)

    released_phase = LifecyclePhase(
        isodate=lifecycle_released_isodate,
        timestamp=lifecycle_released_timestamp,
    )

    if rtype in (ReleaseType.NEXT, ReleaseType.MAJOR):
        lifecycle = Lifecycle(
            released=released_phase,
            extended=LifecyclePhase(
                isodate=lifecycle_extended_isodate,
                timestamp=lifecycle_extended_timestamp,
            ),
            eol=LifecyclePhase(
                isodate=lifecycle_eol_isodate,
                timestamp=lifecycle_eol_timestamp,
            ),
        )
        release_obj = Release(
            name=Release.default_name(rtype, version_obj),
            type=rtype,
            version=version_obj,
            lifecycle=lifecycle,
        )
    elif rtype == ReleaseType.MINOR:
        lifecycle = Lifecycle(
            released=released_phase,
            eol=LifecyclePhase(
                isodate=lifecycle_eol_isodate,
                timestamp=lifecycle_eol_timestamp,
            ),
        )
        release_obj = Release(
            name=Release.default_name(rtype, version_obj),
            type=rtype,
            version=version_obj,
            lifecycle=lifecycle,
            git=GitInfo(commit=commit, commit_short=commit_short),
            github={"release": Release.github_release_url(version_obj, rtype)},
            flavors=flavors,
            attributes={"source_repo": True},
        )
    else:  # dev, nightly
        release_obj = Release(
            name=Release.default_name(rtype, version_obj),
            type=rtype,
            version=version_obj,
            lifecycle=Lifecycle(released=released_phase),
            git=GitInfo(commit=commit, commit_short=commit_short),
            flavors=flavors,
            attributes={"source_repo": True},
        )

    release = release_obj.to_dict()
    logging.debug(f"Release '{release['name']}' created.")
    return release


def delete_release(
    args,
    next_releases,
    major_releases,
    minor_releases,
    nightly_releases,
    dev_releases,
):
    """Delete a release by name from the appropriate release list."""
    release_type, major, minor, patch = parse_release_name(args.delete)

    # Select the appropriate list based on release_type
    if release_type == "next":
        release_list = next_releases
    elif release_type == "major":
        release_list = major_releases
    elif release_type == "minor":
        release_list = minor_releases
    elif release_type == "nightly":
        release_list = nightly_releases
    elif release_type == "dev":
        release_list = dev_releases
    else:
        logging.error(f"Error: Unknown release type '{release_type}' in release name.")
        sys.exit(ERROR_CODES["validation_error"])

    # Find and remove the release
    release_found = False
    for release in release_list:
        if release["name"] == args.delete:
            release_found = True
            release_list.remove(release)

    if not release_found:
        logging.error(f"Error: Release '{args.delete}' not found in the existing data.")
        sys.exit(ERROR_CODES["validation_error"])

    logging.debug(f"Release '{args.delete}' will be deleted.")


def update_release(
    args,
    next_releases,
    major_releases,
    minor_releases,
    nightly_releases,
    dev_releases,
):
    """Update an existing release by name, modifying specified fields in-place."""
    release_type, major, minor, patch = parse_release_name(args.update)

    # Select the appropriate list based on release_type
    if release_type == "next":
        release_list = next_releases
    elif release_type == "major":
        release_list = major_releases
    elif release_type == "minor":
        release_list = minor_releases
    elif release_type == "nightly":
        release_list = nightly_releases
    elif release_type == "dev":
        release_list = dev_releases
    else:
        logging.error(f"Error: Unknown release type '{release_type}' in release name.")
        sys.exit(ERROR_CODES["validation_error"])

    # Validate field applicability for the release type
    if args.lifecycle_extended_isodatetime and release_type not in ["major", "next"]:
        logging.error(
            f"Error: '--lifecycle-extended-isodatetime' is only valid for "
            f"'major' and 'next' release types, not '{release_type}'."
        )
        sys.exit(ERROR_CODES["validation_error"])

    if args.lifecycle_eol_isodatetime and release_type not in [
        "next",
        "major",
        "minor",
    ]:
        logging.error(
            f"Error: '--lifecycle-eol-isodatetime' is only valid for "
            f"'next', 'major', and 'minor' release types, not '{release_type}'."
        )
        sys.exit(ERROR_CODES["validation_error"])

    if args.commit and release_type not in ["minor", "nightly", "dev"]:
        logging.error(
            f"Error: '--commit' is only valid for 'minor', 'nightly', and "
            f"'dev' release types, not '{release_type}'."
        )
        sys.exit(ERROR_CODES["validation_error"])

    # Find the release by name
    release = None
    for r in release_list:
        if r["name"] == args.update:
            release = r
            break

    if release is None:
        logging.error(f"Error: Release '{args.update}' not found in the existing data.")
        sys.exit(ERROR_CODES["validation_error"])

    # Apply lifecycle.released update
    if args.lifecycle_released_isodatetime:
        try:
            released_date = datetime.strptime(
                args.lifecycle_released_isodatetime, "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=pytz.UTC)
        except ValueError:
            logging.error(
                "Error: Invalid --lifecycle-released-isodatetime format. "
                "Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
            sys.exit(ERROR_CODES["validation_error"])
        if "released" not in release["lifecycle"]:
            release["lifecycle"]["released"] = {}
        release["lifecycle"]["released"]["isodate"] = released_date.strftime("%Y-%m-%d")
        release["lifecycle"]["released"]["timestamp"] = int(released_date.timestamp())
        logging.info(
            f"Updated lifecycle.released for '{args.update}' to "
            f"{released_date.strftime('%Y-%m-%d')}."
        )

    # Apply lifecycle.extended update (only for major/next)
    if args.lifecycle_extended_isodatetime:
        try:
            extended_date = datetime.strptime(
                args.lifecycle_extended_isodatetime, "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=pytz.UTC)
        except ValueError:
            logging.error(
                "Error: Invalid --lifecycle-extended-isodatetime format. "
                "Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
            sys.exit(ERROR_CODES["validation_error"])
        if "extended" not in release["lifecycle"]:
            release["lifecycle"]["extended"] = {}
        release["lifecycle"]["extended"]["isodate"] = extended_date.strftime("%Y-%m-%d")
        release["lifecycle"]["extended"]["timestamp"] = int(extended_date.timestamp())
        logging.info(
            f"Updated lifecycle.extended for '{args.update}' to "
            f"{extended_date.strftime('%Y-%m-%d')}."
        )

    # Apply lifecycle.eol update (only for next/major/minor)
    if args.lifecycle_eol_isodatetime:
        try:
            eol_date = datetime.strptime(
                args.lifecycle_eol_isodatetime, "%Y-%m-%dT%H:%M:%S"
            ).replace(tzinfo=pytz.UTC)
        except ValueError:
            logging.error(
                "Error: Invalid --lifecycle-eol-isodatetime format. "
                "Use ISO format: YYYY-MM-DDTHH:MM:SS"
            )
            sys.exit(ERROR_CODES["validation_error"])
        if "eol" not in release["lifecycle"]:
            release["lifecycle"]["eol"] = {}
        release["lifecycle"]["eol"]["isodate"] = eol_date.strftime("%Y-%m-%d")
        release["lifecycle"]["eol"]["timestamp"] = int(eol_date.timestamp())
        logging.info(
            f"Updated lifecycle.eol for '{args.update}' to "
            f"{eol_date.strftime('%Y-%m-%d')}."
        )

    # Apply commit update (only for minor/nightly/dev)
    if args.commit:
        commit = args.commit
        if len(commit) != 40:
            logging.error("Error: Invalid commit hash. Must be 40 characters.")
            sys.exit(ERROR_CODES["validation_error"])
        if "git" not in release:
            release["git"] = {}
        release["git"]["commit"] = commit
        release["git"]["commit_short"] = commit[:8]
        logging.info(f"Updated git.commit for '{args.update}' to {commit[:8]}.")

    logging.debug(f"Release '{args.update}' will be updated.")


def set_latest_minor_eol_to_major(major_releases, minor_releases):
    """Set the EOL of each minor version to the next higher minor version,
    and the EOL of the latest minor version to match the major release."""
    releases_by_major = {}

    # Group releases by major version
    for release in minor_releases:
        major = release["version"]["major"]
        # minor = release.get("version", {}).get("minor")  # unused
        # patch = release.get("version", {}).get("patch")  # unused
        releases_by_major.setdefault(major, []).append(release)

    # For each major version, sort the minor releases and set the EOL
    for major, minor_releases in releases_by_major.items():
        # Sort the minor releases by the 'minor' version number
        minor_releases.sort(key=lambda r: r.get("version", {}).get("minor", 0))

        # Find the corresponding major release for this major version
        major_release = next(
            (r for r in major_releases if r["version"]["major"] == major),
            None,
        )

        # Loop through all minor releases
        for i, release in enumerate(minor_releases):
            # If it's the last minor release, set its EOL to the major release's EOL
            if i == len(minor_releases) - 1:
                if major_release:
                    release["lifecycle"]["eol"] = major_release["lifecycle"]["eol"]
                else:
                    logging.warning(
                        f"No major release found for major version {major}, skipping EOL update."
                    )
            else:
                # Set the EOL to the "released" date of the next minor release
                next_release = minor_releases[i + 1]
                release["lifecycle"]["eol"] = next_release["lifecycle"]["released"]


def load_input(filename):
    """Load manual input from a file if it exists."""
    try:
        input_data = yaml.safe_load(open(filename, "r"))
        merged_releases = input_data.get("releases", [])
        if len(merged_releases) == 0:
            logging.error("Error, no releases found in JSON from file")
            sys.exit(ERROR_CODES["input_parameter_missing"])
        by_type = split_releases_by_type(merged_releases)
        return (
            by_type["next"],
            by_type["major"],
            by_type["minor"],
            by_type["nightly"],
            by_type["dev"],
        )
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON from file: {str(e)}")
        sys.exit(ERROR_CODES["validation_error"])
    except Exception as e:
        logging.error(f"Error reading input from file: {str(e)}")
        sys.exit(ERROR_CODES["input_parameter_error"])


def load_input_stdin():
    """Load input from stdin as JSON data."""
    try:
        stdin_data = sys.stdin.read()
        input_data = json.loads(stdin_data)
        logging.debug(f"Input data from stdin: {input_data}")
        merged_releases = input_data.get("releases", [])
        if len(merged_releases) == 0:
            logging.error("Error, no releases found in JSON from stdin")
            sys.exit(ERROR_CODES["input_parameter_missing"])
        by_type = split_releases_by_type(merged_releases)
        logging.debug(
            f"Parsed releases from stdin - "
            f"next: {len(by_type['next'])}, major: {len(by_type['major'])}, "
            f"minor: {len(by_type['minor'])}, nightly: {len(by_type['nightly'])}, "
            f"dev: {len(by_type['dev'])}"
        )
        return (
            by_type["next"],
            by_type["major"],
            by_type["minor"],
            by_type["nightly"],
            by_type["dev"],
        )
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON from stdin: {str(e)}")
        sys.exit(ERROR_CODES["validation_error"])
    except Exception as e:
        logging.error(f"Error reading input from stdin: {str(e)}")
        sys.exit(ERROR_CODES["input_parameter_error"])


def parse_release_name(release_name):
    """Parse a release name into (type, major, minor, patch).

    Thin wrapper around :func:`glrd.release.parse_release_name` that converts
    the model's ``ValueError`` into the CLI's error-exit behavior. The release
    model is the single source of truth for name parsing.
    """
    try:
        release_type, major, minor, patch = model_parse_release_name(release_name)
    except ValueError as exc:
        logging.error(f"Error: {exc}")
        sys.exit(ERROR_CODES["validation_error"])
    return release_type.value, major, minor, patch


def diff_releases(existing_merged_releases, merged_releases):
    """Show which releases will be created, deleted, or updated."""
    existing_releases_by_name = {r["name"]: r for r in existing_merged_releases}
    new_releases_by_name = {r["name"]: r for r in merged_releases}

    existing_merged_release_names = set(existing_releases_by_name.keys())
    merged_release_names = set(new_releases_by_name.keys())

    releases_to_create = merged_release_names - existing_merged_release_names
    releases_to_delete = existing_merged_release_names - merged_release_names
    releases_to_check = merged_release_names & existing_merged_release_names

    for release_name in releases_to_create:
        logging.info(f"{release_name} - release will be created.")

    for release_name in releases_to_delete:
        logging.info(f"{release_name} - release will be deleted.")

    for release_name in releases_to_check:
        existing_release = existing_releases_by_name[release_name]
        new_release = new_releases_by_name[release_name]

        # Perform deep comparison
        diff = DeepDiff(existing_release, new_release, ignore_order=True)

        if diff:
            logging.info(f"{release_name} - release will be updated.")
            for change_type, changes in diff.items():
                if change_type == "values_changed":
                    for path, change in changes.items():
                        formatted_path = path.replace("root", "")
                        logging.info(
                            f"{release_name} - {change_type}: {formatted_path} "
                            f"changed from '{change['old_value']}' to '{change['new_value']}'"
                        )
                elif change_type == "type_changes":
                    for path, change in changes.items():
                        formatted_path = path.replace("root", "")
                        logging.info(
                            f"{release_name} - {change_type}: {formatted_path} "
                            f"type changed from '{change['old_type']}' to '{change['new_type']}'"
                        )
                elif change_type in [
                    "dictionary_item_added",
                    "dictionary_item_removed",
                    "iterable_item_added",
                    "iterable_item_removed",
                ]:
                    changes_list = sorted(list(changes))
                    for change in changes_list:
                        formatted_change = str(change).replace("root", "")
                        logging.info(
                            f"{release_name} - {change_type}: {formatted_change}"
                        )


def handle_releases(args):
    """Handle the creation and deletion of initial or single releases."""
    if args.input_all:
        upload_all_local_files(args.s3_bucket_name, args.s3_bucket_prefix)
        return

    if args.output_all:
        download_all_s3_files(args.s3_bucket_name, args.s3_bucket_prefix)
        return

    if args.s3_create_bucket:
        create_s3_bucket(args)
        return

    if not args.s3_update:
        logging.warning("'--s3-update' was not passed, skipping S3 update.")

    create_initial_major, create_initial_minor, create_initial_nightly = (
        False,
        False,
        False,
    )
    (
        next_releases,
        major_releases,
        minor_releases,
        nightly_releases,
        dev_releases,
    ) = (
        [],
        [],
        [],
        [],
        [],
    )

    if args.create_initial_releases:
        create_initial_list = args.create_initial_releases.split(",")
        create_initial_major = "major" in create_initial_list
        create_initial_minor = "minor" in create_initial_list
        create_initial_nightly = "nightly" in create_initial_list

    # Variables to store inputs, dev/major/minor releases and nightly releases
    existing_next_releases = []
    existing_major_releases = []
    existing_minor_releases = []
    existing_nightly_releases = []
    existing_dev_releases = []
    existing_merged_releases = []
    next_releases = []
    major_releases = []
    minor_releases = []
    nightly_releases = []
    dev_releases = []
    merged_releases = []

    if not args.no_query:
        # Execute glrd command to fill major, minor, nightly, and dev releases
        existing_next_releases = glrd_query_type(args, "next")
        existing_major_releases = glrd_query_type(args, "major")
        existing_minor_releases = glrd_query_type(args, "minor")
        existing_nightly_releases = glrd_query_type(args, "nightly")
        existing_merged_releases = (
            existing_next_releases
            + existing_major_releases
            + existing_minor_releases
            + existing_nightly_releases
            + existing_dev_releases
        )
        next_releases.extend(existing_next_releases)
        major_releases.extend(existing_major_releases)
        minor_releases.extend(existing_minor_releases)
        nightly_releases.extend(existing_nightly_releases)
        dev_releases.extend(existing_dev_releases)

    if args.delete:
        if args.no_query:
            logging.error("Error: '--delete' cannot run with '--no-query'.")
            sys.exit(ERROR_CODES["parameter_missing"])
        delete_release(
            args,
            next_releases,
            major_releases,
            minor_releases,
            nightly_releases,
            dev_releases,
        )

    elif args.update:
        if args.no_query:
            logging.error("Error: '--update' cannot run with '--no-query'.")
            sys.exit(ERROR_CODES["parameter_missing"])
        # Validate at least one modifier is provided
        if not any(
            [
                args.lifecycle_released_isodatetime,
                args.lifecycle_extended_isodatetime,
                args.lifecycle_eol_isodatetime,
                args.commit,
            ]
        ):
            logging.error(
                "Error: '--update' requires at least one of: "
                "--lifecycle-released-isodatetime, --lifecycle-extended-isodatetime, "
                "--lifecycle-eol-isodatetime, --commit."
            )
            sys.exit(ERROR_CODES["parameter_missing"])

        # Add stdin input or file input data if provided (existing releases will be overwritten)
        if args.input_stdin or args.input:
            if args.input_stdin:
                (
                    input_next,
                    input_major,
                    input_minor,
                    input_nightly,
                    input_dev,
                ) = load_input_stdin()
            elif args.input:
                (
                    input_next,
                    input_major,
                    input_minor,
                    input_nightly,
                    input_dev,
                ) = load_input(args.input_file)
            next_releases = merge_input_data(next_releases, input_next)
            major_releases = merge_input_data(major_releases, input_major)
            minor_releases = merge_input_data(minor_releases, input_minor)
            nightly_releases = merge_input_data(nightly_releases, input_nightly)
            dev_releases = merge_input_data(dev_releases, input_dev)

        update_release(
            args,
            next_releases,
            major_releases,
            minor_releases,
            nightly_releases,
            dev_releases,
        )

    else:
        if create_initial_major or create_initial_minor:
            github_releases = get_github_releases()
            (
                major_releases,
                minor_releases,
                latest_minor_versions,
                latest_patch_versions,
            ) = create_initial_releases(github_releases)

        # Add stdin input or file input data if provided (existing releases will be overwritten)
        if args.input_stdin or args.input:
            if args.input_stdin:
                (
                    input_next,
                    input_major,
                    input_minor,
                    input_nightly,
                    input_dev,
                ) = load_input_stdin()
            elif args.input:
                (
                    input_next,
                    input_major,
                    input_minor,
                    input_nightly,
                    input_dev,
                ) = load_input(args.input_file)
            next_releases = merge_input_data(next_releases, input_next)
            major_releases = merge_input_data(major_releases, input_major)
            minor_releases = merge_input_data(minor_releases, input_minor)
            nightly_releases = merge_input_data(nightly_releases, input_nightly)
            dev_releases = merge_input_data(dev_releases, input_dev)

        # we define major releases in input file, therefore this has to be run past defining inputs
        # Create initial nightly releases if requested (needs major releases)
        if create_initial_nightly:
            nightly_releases = create_initial_nightly_releases(major_releases)

        # Create a next release if requested
        if args.create == "next":
            release = create_single_release("next", args, next_releases)
            next_releases = merge_input_data(next_releases, [release])

        # Create a major release if requested
        if args.create == "major":
            release = create_single_release("major", args, major_releases)
            major_releases = merge_input_data(major_releases, [release])

        # Create a minor release if requested
        if args.create == "minor":
            release = create_single_release("minor", args, minor_releases)
            minor_releases = merge_input_data(minor_releases, [release])

        # Create a nightly release if requested
        if args.create == "nightly":
            release = create_single_release("nightly", args, nightly_releases)
            nightly_releases = merge_input_data(nightly_releases, [release])

        # Create a development release if requested
        if args.create == "dev":
            release = create_single_release("dev", args, dev_releases)
            dev_releases = merge_input_data(dev_releases, [release])

    # Set EOL for minor releases based on latest minor versions
    set_latest_minor_eol_to_major(major_releases, minor_releases)

    # Merge all releases into a single list
    merged_releases = (
        next_releases
        + major_releases
        + minor_releases
        + nightly_releases
        + dev_releases
    )

    # Ensure timestamps for all releases
    for release in merged_releases:
        ensure_isodate_and_timestamp(release["lifecycle"])

    # Validate all releases
    validate_all_releases(merged_releases)

    # split all releases again
    next_releases = [r for r in merged_releases if r["type"] == "next"]
    major_releases = [r for r in merged_releases if r["type"] == "major"]
    minor_releases = [r for r in merged_releases if r["type"] == "minor"]
    nightly_releases = [r for r in merged_releases if r["type"] == "nightly"]
    dev_releases = [r for r in merged_releases if r["type"] == "dev"]

    diff_releases(existing_merged_releases, merged_releases)

    store_releases(args, merged_releases)


def store_releases(args, merged_releases):
    """Store releases in splitted or not splitted output."""
    if args.no_output_split:
        handle_output(args, args.s3_bucket_name, args.s3_bucket_prefix, merged_releases)
    else:
        handle_splitted_output(
            args, args.s3_bucket_name, args.s3_bucket_prefix, merged_releases
        )


def handle_splitted_output(args, bucket_name, bucket_prefix, releases):
    """Handle output of splitted releases (next, major, minor, nightly, dev) to disk and S3."""
    for release_type in DEFAULTS["RELEASE_TYPES"]:
        releases_filtered = [r for r in releases if r["type"] == release_type]
        if releases_filtered:
            # Always use json format for S3 storage
            s3_output_file = f"{args.output_file_prefix}-{release_type}.json"
            # Use requested format for local file
            local_output_file = (
                f"{args.output_file_prefix}-{release_type}.{args.output_format}"
            )

            # Save local file in requested format
            save_output_file(
                {"releases": releases_filtered},
                filename=local_output_file,
                format=args.output_format,
            )

            # Handle S3 upload if the argument is provided
            if args.s3_update:
                # For S3, always use JSON format
                save_output_file(
                    {"releases": releases_filtered},
                    filename=s3_output_file,
                    format="json",
                )
                releases_filtered = merge_existing_s3_data(
                    bucket_name,
                    f"{bucket_prefix}{s3_output_file}",
                    s3_output_file,
                    releases_filtered,
                )
                upload_to_s3(
                    s3_output_file,
                    bucket_name,
                    f"{bucket_prefix}{s3_output_file}",
                )

                # Clean up temporary JSON file if local format is different
                if args.output_format != "json":
                    try:
                        os.remove(s3_output_file)
                    except OSError:
                        pass


def handle_output(args, bucket_name, bucket_prefix, releases):
    """Handle output of not splitted releases to disk and S3."""
    output_file = f"{args.output_file_prefix}.{args.output_format}"
    save_output_file(
        {"releases": releases}, filename=output_file, format=args.output_format
    )
    logging.debug(f"Release data saved to '{output_file}'.")

    # Handle S3 upload if the argument is provided
    if args.s3_update:
        # merged_releases = merge_existing_s3_data(  # unused
        merge_existing_s3_data(
            bucket_name,
            f"{bucket_prefix}{os.path.basename(output_file)}",
            output_file,
            releases,
        )
        upload_to_s3(
            output_file,
            bucket_name,
            f"{bucket_prefix}{os.path.basename(output_file)}",
        )


def parse_arguments():
    parser = argparse.ArgumentParser(description="Manage Garden Linux releases data.")

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level",
    )

    parser.add_argument(
        "--input-file",
        type=str,
        default=DEFAULTS["MANAGE_INPUT_FILE"],
        help="The name of the input file (default: releases-input.yaml).",
    )

    parser.add_argument(
        "--input-type",
        choices=["file", "url"],
        default=DEFAULTS["QUERY_INPUT_TYPE"],
        help="Where existing releases are queried from when not using "
        "--no-query: 'file' (local) or 'url' (default). Use 'file' to run "
        "fully offline.",
    )

    parser.add_argument(
        "--input-url",
        type=str,
        default=DEFAULTS["QUERY_INPUT_URL"],
        help="Base URL used to query existing releases (default: "
        "gardenlinux-glrd S3 URL). Only used with '--input-type url'.",
    )

    parser.add_argument(
        "--input-file-prefix",
        type=str,
        default=DEFAULTS["QUERY_INPUT_FILE_PREFIX"],
        help="Prefix used to query existing releases from local files "
        "(default: releases). Only used with '--input-type file'.",
    )

    parser.add_argument(
        "--query-input-format",
        choices=["yaml", "json"],
        default=DEFAULTS["QUERY_INPUT_FORMAT"],
        help="Format of the existing releases queried when not using "
        "--no-query (default: json).",
    )

    parser.add_argument(
        "--output-format",
        type=str,
        choices=["yaml", "json"],
        default=DEFAULTS["MANAGE_OUTPUT_FORMAT"],
        help="Output format: yaml or json (default: yaml).",
    )

    parser.add_argument(
        "--output-file-prefix",
        type=str,
        default=DEFAULTS["MANAGE_OUTPUT_FILE_PREFIX"],
        help="The prefix for output files (default: releases).",
    )

    parser.add_argument(
        "--s3-bucket-name",
        type=str,
        default=DEFAULTS["GLRD_S3_BUCKET_NAME"],
        help="Name of S3 bucket. Defaults to 'gardenlinux-glrd'.",
    )

    parser.add_argument(
        "--s3-bucket-region",
        type=str,
        default=DEFAULTS["GLRD_S3_BUCKET_REGION"],
        help="Region for S3 bucket. Defaults to 'eu-central-1'.",
    )

    parser.add_argument(
        "--s3-bucket-prefix",
        type=str,
        default=DEFAULTS["GLRD_S3_BUCKET_PREFIX"],
        help="Prefix for S3 bucket objects. Defaults to empty string.",
    )

    parser.add_argument(
        "--delete",
        type=str,
        help="Delete a release by name (format: type-major.minor or "
        "type-major.minor.patch). Requires --s3-update.",
    )
    parser.add_argument(
        "--update",
        type=str,
        help="Update an existing release by name (format: type-major.minor or "
        "type-major.minor.patch or type-major). Requires at least one of: "
        "--lifecycle-released-isodatetime, --lifecycle-extended-isodatetime, "
        "--lifecycle-eol-isodatetime, --commit.",
    )
    parser.add_argument(
        "--create-initial-releases",
        type=str,
        help="Comma-separated list of initial releases to retrieve and "
        "generate: 'major,minor,nightly'.",
    )
    parser.add_argument(
        "--create",
        type=str,
        help="Create a release for this type using the current timestamp "
        "and git information (choose one of: major,minor,nightly,dev,next)'.",
    )
    parser.add_argument(
        "--version",
        type=str,
        help="Manually specify the version (format: major.minor for "
        "versions < 2017.0.0, or major.minor.patch for versions >= 2017.0.0).",
    )
    parser.add_argument(
        "--commit",
        type=str,
        help="Manually specify the git commit hash (40 characters).",
    )
    parser.add_argument(
        "--no-flavors",
        action="store_true",
        help="Do not resolve flavors (skips the Git clone and S3 lookup). "
        "Useful for offline use and tests. Can also be enabled via the "
        "GLRD_SKIP_FLAVORS environment variable.",
    )
    parser.add_argument(
        "--lifecycle-released-isodatetime",
        type=str,
        help="Manually specify the release date and time in ISO format "
        "(YYYY-MM-DDTHH:MM:SS).",
    )
    parser.add_argument(
        "--lifecycle-extended-isodatetime",
        type=str,
        help="Manually specify the extended maintenance date and time in "
        "ISO format (YYYY-MM-DDTHH:MM:SS).",
    )
    parser.add_argument(
        "--lifecycle-eol-isodatetime",
        type=str,
        help="Manually specify the EOL date and time in ISO format "
        "(YYYY-MM-DDTHH:MM:SS).",
    )
    parser.add_argument(
        "--no-query",
        action="store_true",
        help="Do not query and use existing releases using glrd command. "
        "Be careful, this can delete your releases.",
    )
    parser.add_argument(
        "--input-stdin",
        action="store_true",
        help="Process a single input from stdin (JSON data).",
    )
    parser.add_argument(
        "--input", action="store_true", help="Process input from --input-file."
    )
    parser.add_argument(
        "--no-output-split",
        action="store_true",
        help="Do not split Output into major+minor and nightly. Additional "
        "output-files *-nightly and *-dev will not be created.",
    )
    parser.add_argument(
        "--s3-create-bucket", action="store_true", help="Create an S3 bucket."
    )
    parser.add_argument(
        "--s3-update",
        action="store_true",
        help="Update (merge) the generated files with S3.",
    )
    parser.add_argument(
        "--output-all",
        action="store_true",
        help="Download and write all release files found in S3 to " "local disk",
    )
    parser.add_argument(
        "--input-all",
        action="store_true",
        help="Upload all local release files to S3",
    )
    parser.add_argument("-V", action="version", version=f"%(prog)s {get_version()}")

    args = parser.parse_args()

    # Convert log level to uppercase if provided in lowercase
    args.log_level = args.log_level.upper()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(ERROR_CODES["parameter_missing"])

    return args


def main():
    args = parse_arguments()

    # Configure logging with the already uppercase level
    logging.basicConfig(level=args.log_level, format="%(levelname)s: %(message)s")

    handle_releases(args)


if __name__ == "__main__":
    main()
