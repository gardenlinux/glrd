import argparse
import json
import logging
import os
import sys
from datetime import datetime

import requests
import tabulate
import yaml

from glrd.util import *
from python_gardenlinux_lib.flavors.parse_flavors import *
from python_gardenlinux_lib.s3.s3 import *

DEFAULTS = dict(DEFAULTS, **{
    'POSSIBLE_FIELDS_MAP': {
        "Name": lambda r: r.get('name', 'N/A'),
        "Version": lambda r: get_version_string(r['version'], r.get('type')),
        "Type": lambda r: r.get('type', 'N/A'),
        "GitCommit": lambda r: r.get('git', {}).get('commit', 'N/A'),
        "GitCommitShort": lambda r: r.get('git', {}).get('commit_short', 'N/A'),
        "ReleaseDate": lambda r: r['lifecycle']['released'].get('isodate', 'N/A'),
        "ReleaseTime": lambda r: timestamp_to_isotime(r['lifecycle']['released'].get('timestamp')),
        "ExtendedMaintenance": lambda r: get_extended_maintenance(r),
        "EndOfMaintenance": lambda r: r['lifecycle'].get('eol', {}).get('isodate', 'N/A'),
        "Flavors": lambda r: ','.join(r.get('flavors', [])) or 'N/A',  # Simple comma-separated list for shell output
        "OCI": lambda r: get_oci_url(r),
        "AttributesSourceRepo": lambda r: str(r.get('attributes', {}).get('source_repo', 'N/A'))
    }
})

def get_version_string(version, release_type=None):
    """Return a version string from a version object. Show major only for stable and next releases."""
    if release_type in ['stable', 'next']:
        return str(version['major'])  # Stable releases show only major version
    return f"{version['major']}.{version.get('minor', 0)}"

def is_active_release(release, current_timestamp):
    """Check if the release is still active based on its EOL timestamp."""
    eol_timestamp = release.get('lifecycle', {}).get('eol', {}).get('timestamp')
    return eol_timestamp and eol_timestamp > current_timestamp

def filter_active_releases(releases):
    """Filter and return only active releases."""
    current_timestamp = get_current_timestamp()
    return [release for release in releases if is_active_release(release, current_timestamp)]

def is_archived_release(release, current_timestamp):
    """Check if the release archived based on its EOL timestamp."""
    eol_timestamp = release.get('lifecycle', {}).get('eol', {}).get('timestamp')
    return eol_timestamp and eol_timestamp < current_timestamp

def filter_archived_releases(releases):
    """Filter and return only archived releases."""
    current_timestamp = get_current_timestamp()
    return [release for release in releases if is_archived_release(release, current_timestamp)]

def filter_releases(releases, release_types=None, version=None):
    """Filter releases by type and/or version."""
    if version:
        version_parts = version.split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else None
        releases = [
            r for r in releases
            if r['version']['major'] == major and (minor is None or r['version'].get('minor', 0) == minor)
        ]
    if release_types:
        release_types = release_types.split(',')
        releases = [r for r in releases if r.get('type') in release_types]
    return releases

def find_latest_release(releases):
    """Find the latest release by version."""
    return max(releases, key=lambda r: (r['version']['major'], r['version'].get('minor', 0)), default=None)

def get_extended_maintenance(release):
    """Return the extended maintenance date for a release, if available."""
    extended = release['lifecycle'].get('extended', {})
    if extended.get('isodate'):
        return extended['isodate']
    # Default to N/A if extended is missing
    return 'N/A'

def duration_in_months(start_date, end_date):
    """Compute the number of months between two dates."""
    delta = end_date - start_date
    months = delta.days / 30.44  # Approximate average days in a month
    return round(months)

def prepare_structured_output(release):
    """Prepare a release object for JSON/YAML output by adding URLs and organizing fields."""
    release_copy = {}

    # Add core fields first in specific order
    core_fields = ['name', 'type', 'version', 'lifecycle', 'git', 'github']
    for field in core_fields:
        if field in release:
            release_copy[field] = release[field]

    # Add flavors with URLs
    release_copy['flavors'] = format_flavors_with_urls(release)

    # Add OCI URL
    release_copy['oci'] = get_oci_url(release)

    # Add attributes last
    if 'attributes' in release:
        release_copy['attributes'] = release['attributes']

    return release_copy

def format_structured_output(releases, output_format):
    """Format releases as JSON or YAML."""
    releases_with_urls = [prepare_structured_output(r) for r in releases]
    data = {"releases": releases_with_urls}

    if output_format == 'json':
        return json.dumps(data, indent=2)
    else:  # yaml
        return yaml.dump(data, default_flow_style=False, sort_keys=False, Dumper=NoAliasDumper)

def format_tabular_output(releases, fields, no_header, output_format):
    """Format releases as a table for shell or markdown output."""
    # Get the requested fields or use defaults
    selected_fields = fields.split(',') if fields else DEFAULTS['QUERY_FIELDS'].split(',')

    # Get all available fields for validation
    all_fields = list(DEFAULTS['POSSIBLE_FIELDS_MAP'].keys())

    # Validate and filter the fields
    selected_fields, _ = filter_fields(all_fields, [], selected_fields)

    # Generate rows using only the selected fields
    rows = [
        [DEFAULTS['POSSIBLE_FIELDS_MAP'][field](r) for field in selected_fields]
        for r in releases
    ]

    headers = selected_fields if not no_header else ()

    if output_format == 'shell':
        return tabulate.tabulate(rows, headers, tablefmt="plain", disable_numparse=True)
    elif output_format == 'markdown':
        return tabulate.tabulate(rows, headers, tablefmt="pipe", disable_numparse=True)

def filter_fields(headers, rows, requested_fields):
    """Filter columns in tabular data based on requested fields."""
    # Validate requested fields
    invalid_fields = [f for f in requested_fields if f not in headers]
    if invalid_fields:
        logging.error(f"Invalid field(s): {', '.join(invalid_fields)}")
        logging.error(f"Available fields: {', '.join(headers)}")
        sys.exit(ERROR_CODES['invalid_field'])

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
        name = get_version_string(release['version'], release.get('type'))
        # name = release['name']
        output.append(f"    section {name}")

        # Extract dates
        released_date_str = release['lifecycle']['released'].get('isodate')
        extended_date_str = release['lifecycle'].get('extended', {}).get('isodate')
        eol_date_str = release['lifecycle'].get('eol', {}).get('isodate')  # End of life

        # Convert dates to datetime objects
        date_format = '%Y-%m-%d'
        released_date = datetime.strptime(released_date_str, date_format) if released_date_str else None
        extended_date = datetime.strptime(extended_date_str, date_format) if extended_date_str else None
        eol_date = datetime.strptime(eol_date_str, date_format) if eol_date_str else None

        # Add 'Release' milestone
        if released_date:
            released_date_formatted = released_date.strftime('%Y-%m-%d')
            output.append(f"        Release:                milestone, {released_date_formatted}, 0m")

        # Standard maintenance
        if released_date and extended_date:
            duration_months = duration_in_months(released_date, extended_date)
            duration_str = f"{duration_months}M"
            start_date_str = released_date.strftime('%Y-%m-%d')
            output.append(f"        Standard maintenance:       task, {start_date_str}, {duration_str}")

        # Extended maintenance
        if extended_date and eol_date:
            # Extended maintenance start as a milestone
            extended_date_formatted = extended_date.strftime('%Y-%m-%d')
            output.append(f"        Extended maintenance:       milestone, {extended_date_formatted}, 0m")
            duration_months = duration_in_months(extended_date, eol_date)
            duration_str = f"{duration_months}M"
            start_date_str = extended_date.strftime('%Y-%m-%d')
            output.append(f"        Extended maintenance:       task, {start_date_str}, {duration_str}")
            # End of maintenance milestone
            eol_date_formatted = eol_date.strftime('%Y-%m-%d')
            output.append(f"        End of maintenance:         milestone, {eol_date_formatted}, 0m")
        elif eol_date:
            # No extended maintenance, but have eol_date
            eol_date_formatted = eol_date.strftime('%Y-%m-%d')
            output.append(f"        End of maintenance:         milestone, {eol_date_formatted}, 0m")

    return "\n".join(output)

def format_output(args, releases, output_format, fields=None, no_header=False):
    """Format and print release data in the specified format."""
    formatted_output = None

    if output_format in ['json', 'yaml']:
        formatted_output = format_structured_output(releases, output_format)
    elif output_format in ['shell', 'markdown']:
        formatted_output = format_tabular_output(releases, fields, no_header, output_format)
    elif output_format == 'mermaid_gantt':
        formatted_output = format_mermaid_gantt(args, releases)

    if formatted_output is not None:
        print(formatted_output)

def sort_releases(releases):
    """Sort releases by major and minor version, handling non-integer majors like 'next'."""
    def parse_version_part(part):
        if isinstance(part, int):
            return part
        elif isinstance(part, str):
            if part.lower() == 'next':
                # Assign a special value to place 'next' releases appropriately
                return float('inf')  # Place at the end
            else:
                # Handle other string versions if necessary
                return -1
        else:
            return -1  # Default value for unexpected types

    def sort_key(r):
        major = parse_version_part(r['version'].get('major'))
        minor = parse_version_part(r['version'].get('minor', -1))
        return (major, minor)

    return sorted(releases, key=sort_key)

def load_releases(input_source, is_url=False):
    """Load the releases from a file or a URL."""
    if is_url:
        try:
            response = requests.get(input_source)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f"Error fetching data from URL: {e}")
            sys.exit(ERROR_CODES['http_error'])
    else:
        if not os.path.exists(input_source):
            logging.error(f"Error: File {input_source} does not exist.")
            sys.exit(ERROR_CODES['file_not_found'])
        with open(input_source, 'r') as file:
            return json.load(file)

def load_split_releases(release_type, input_type, input_url, input_file_prefix, input_format):
    """Load and split releases based on type."""
    releases_next, releases_stable, releases_patch, releases_nightly, releases_dev = [], [], [], [], []
    types = release_type.split(',')
    is_url = (input_type == 'url')

    if 'next' in types:
        input_file = input_file_prefix + '-next' + '.' + input_format
        if is_url:
            input_file = input_url + '/' + input_file
        releases_next = load_releases(input_file, is_url=is_url).get('releases', [])

    if 'stable' in types:
        input_file = input_file_prefix + '-stable' + '.' + input_format
        if is_url:
            input_file = input_url + '/' + input_file
        releases_stable = load_releases(input_file, is_url=is_url).get('releases', [])

    if 'patch' in types:
        input_file = input_file_prefix + '-patch' + '.' + input_format
        if is_url:
            input_file = input_url + '/' + input_file
        releases_patch = load_releases(input_file, is_url=is_url).get('releases', [])

    if 'nightly' in types:
        input_file = input_file_prefix + '-nightly' + '.' + input_format
        if is_url:
            input_file = input_url + '/' + input_file
        releases_nightly = load_releases(input_file, is_url=is_url).get('releases', [])

    if 'dev' in types:
        input_file = input_file_prefix + '-dev' + '.' + input_format
        if is_url:
            input_file = input_url + '/' + input_file
        releases_dev = load_releases(input_file, is_url=is_url).get('releases', [])

    return releases_next + releases_stable + releases_patch + releases_nightly + releases_dev

# def load_all_releases(args):
def load_all_releases(release_type, input_type, input_url, input_file_prefix, input_format, no_input_split=False):
    """Load releases either from a single source or split by type."""
    # if args.no_input_split:
    if no_input_split:
        # return load_releases(args.input, is_url=(args.input_type == 'url')).get('releases', [])
        return load_releases(input_source, is_url=(input_type == 'url')).get('releases', [])
    else:
        # return load_split_releases(input)
        return load_split_releases(release_type, input_type, input_url, input_file_prefix, input_format)

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Process and filter releases data from a file or URL.")

    parser.add_argument('--input-format', type=str, choices=['yaml', 'json'],
                       default=DEFAULTS['QUERY_INPUT_FORMAT'],
                       help="Input format: 'yaml' or 'json' (default: json).")

    parser.add_argument('--input-file-prefix', type=str,
                       default=DEFAULTS['QUERY_INPUT_FILE_PREFIX'],
                       help="The prefix to get input files (default: releases).")

    parser.add_argument('--input-type', choices=['file', 'url'],
                       default=DEFAULTS['QUERY_INPUT_TYPE'],
                       help="Specify if the input type (default: url).")

    parser.add_argument('--input-url', type=str,
                       default=DEFAULTS['QUERY_INPUT_URL'],
                       help="Input URL to the releases data. Defaults to gardenlinux-glrd S3 URL.")

    parser.add_argument('--no-input-split', action='store_true',
                       help="Do not split Input into stable+patch and nightly. No additional input-files *-nightly and *-dev will be parsed.")

    parser.add_argument('--output-format',
                       choices=['json', 'yaml', 'markdown', 'mermaid_gantt', 'shell'],
                       default=DEFAULTS['QUERY_OUTPUT_TYPE'],
                       help="Output format: json, yaml, markdown, mermaid_gantt, shell (default).")

    parser.add_argument('--output-description', type=str,
                       default=DEFAULTS['QUERY_OUTPUT_DESCRIPTION'],
                       help="Description, added to certain outputs, e.g. mermaid (default: 'Garden Linux Releases').")

    parser.add_argument('--active', action='store_true',
                       help="Show only active releases.")

    parser.add_argument('--archived', action='store_true',
                       help="Show only archived releases.")

    parser.add_argument('--latest', action='store_true',
                       help="Show the latest active major.minor release.")

    parser.add_argument('--type', type=str,
                       default=DEFAULTS['QUERY_TYPE'],
                       help="Filter by release types (comma-separated list, default: stable,patch). E.g., --type stable,patch,nightly,dev,next")

    parser.add_argument('--version', type=str,
                       help="Filter by a specific version (major or major.minor). E.g., --version 1312 or --version 1312.0")

    parser.add_argument('--fields', type=str,
                       help=("Comma-separated list of fields to output. Possible fields: " +
                            ",".join(DEFAULTS['POSSIBLE_FIELDS_MAP'].keys()) +
                            " (default: " + DEFAULTS['QUERY_FIELDS'] + ")"))

    parser.add_argument('--no-header', action='store_true',
                       help="Omit the header in shell output.")

    parser.add_argument('-V', action='version', version=f'%(prog)s {get_version()}')

    return parser.parse_args()

def get_platform_from_flavor(flavor):
    """Extract platform from flavor string."""
    try:
        return flavor.split('-')[0]
    except Exception as e:
        logging.error(f"Error extracting platform from flavor {flavor}: {e}")
        sys.exit(ERROR_CODES['format_error'])

def prepare_oci_flavor_url(flavor, version, platform):
    """Create OCI URL for container/bare platforms."""
    try:
        if platform == "container":
            return {
                'oci': f"{DEFAULTS['CONTAINER_REGISTRY']}:{version}"
            }
        elif platform == "bare":
            flavor_base = '-'.join(flavor.split('-')[:-1])
            return {
                'oci': f"{DEFAULTS['CONTAINER_REGISTRY']}/{flavor_base}:{version}"
            }
    except Exception as e:
        logging.error(f"Error creating URLs for container/bare platforms: {e}")
        sys.exit(ERROR_CODES['format_error'])

def prepare_regular_flavor_urls(flavor, version, commit_short, platform):
    """Create metadata and image URLs for regular platforms."""
    try:
        image_ext = DEFAULTS['PLATFORM_EXTENSIONS'].get(platform, "raw")
        base_url = (f"{DEFAULTS['ARTIFACTS_S3_BASE_URL']}/"
                   f"{DEFAULTS['ARTIFACTS_S3_PREFIX']}"
                   f"{flavor}-{version}-{commit_short}")
        base_filename = f"{flavor}-{version}-{commit_short}"

        return {
            'metadata': f"{base_url}/{base_filename}.manifest",
            'image': f"{base_url}/{base_filename}.{image_ext}"
        }
    except Exception as e:
        logging.error(f"Error creating URLs for flavor {flavor}: {e}")
        sys.exit(ERROR_CODES['format_error'])

def format_flavors_with_urls(release):
    """Format flavors as a map with metadata and image URLs."""
    """Return empty dict if no flavors in release."""
    if not release.get('flavors'):
        return {}

    try:
        version = f"{release['version']['major']}.{release['version'].get('minor', 0)}"
        commit_short = release['git'].get('commit_short', '')

        regular_flavors = {}
        oci_flavors = {}

        for flavor in sorted(release['flavors']):
            platform = get_platform_from_flavor(flavor)

            # Handle OCI-based platforms
            if platform in ["container", "bare"]:
                urls = prepare_oci_flavor_url(flavor, version, platform)
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
        sys.exit(ERROR_CODES['format_error'])

def get_oci_url(release):
    """Return the OCI image URL for a release."""
    try:
        if release['type'] in ['stable', 'next']:
            version = str(release['version']['major'])
        else:
            version = f"{release['version']['major']}.{release['version'].get('minor', 0)}"
        return f"{DEFAULTS['CONTAINER_REGISTRY']}:{version}"
    except Exception as e:
        logging.error(f"Error getting OCI URL: {e}")
        sys.exit(ERROR_CODES['format_error'])

def process_query(args):
    """Process the query based on command line arguments."""
    # Load releases
    releases = load_all_releases(
        args.type,
        args.input_type,
        args.input_url,
        args.input_file_prefix,
        args.input_format,
        args.no_input_split
    )

    if not releases:
        logging.error("No releases found.")
        sys.exit(ERROR_CODES["no_releases"])

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
    parser = argparse.ArgumentParser(description='Garden Linux Release Database Query Tool')
    parser.add_argument('--version', action='version', version=f'%(prog)s {get_version()}')
    args = parse_arguments()

    process_query(args)

if __name__ == "__main__":
    main()
