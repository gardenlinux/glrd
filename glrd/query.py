import argparse
import json
import requests
from datetime import datetime
import os
import yaml
import tabulate
from glrd.util import *

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

def format_output(args, releases, output_format, fields=None, include_extended=False, no_header=False):
    """Format release data for output."""
    all_fields = ["Name", "Version", "Type", "Git Commit", "Release date", "Release time", "Extended maintenance", "End of maintenance"]
    selected_fields = fields.split(',') if fields else all_fields
    rows = [
        [
            r.get('name', 'N/A'),
            get_version_string(r['version'], r.get('type')),
            r.get('type', 'N/A'),
            r.get('git', {}).get('commit_short', 'N/A'),
            r['lifecycle']['released'].get('isodate', 'N/A'),
            timestamp_to_isotime(r['lifecycle']['released'].get('timestamp')),
            get_extended_maintenance(r),
            r['lifecycle'].get('eol', {}).get('isodate', 'N/A')
        ]
        for r in releases
    ]
    headers, rows = filter_fields(all_fields, rows, selected_fields)
    
    if output_format == 'json':
        print(json.dumps({"releases": releases}, indent=2))
    elif output_format == 'yaml':
        print(yaml.dump({"releases": releases}, default_flow_style=False, sort_keys=False))
    elif output_format == 'markdown':
        print(tabulate.tabulate(rows, headers, tablefmt="pipe"))
    elif output_format == 'mermaid_gantt':
        format_mermaid_gantt(args, releases)
    elif output_format == 'shell':
        format_shell(rows, headers, no_header)

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

def format_mermaid_gantt(args, releases):
    """Format release data into Mermaid Gantt chart syntax."""
    print("gantt")
    print(f"    title {args.output_description}")
    print("    axisFormat %m.%y")
    
    for release in releases:
        name = get_version_string(release['version'], release.get('type'))
        # name = release['name']
        print(f"    section {name}")
        
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
            print(f"        Release:                milestone, {released_date_formatted}, 0m")
        
        # Standard maintenance
        if released_date and extended_date:
            duration_months = duration_in_months(released_date, extended_date)
            duration_str = f"{duration_months}M"
            start_date_str = released_date.strftime('%Y-%m-%d')
            print(f"        Standard maintenance:       task, {start_date_str}, {duration_str}")
        
        # Extended maintenance
        if extended_date and eol_date:
            # Extended maintenance start as a milestone
            extended_date_formatted = extended_date.strftime('%Y-%m-%d')
            print(f"        Extended maintenance:       milestone, {extended_date_formatted}, 0m")
            duration_months = duration_in_months(extended_date, eol_date)
            duration_str = f"{duration_months}M"
            start_date_str = extended_date.strftime('%Y-%m-%d')
            print(f"        Extended maintenance:       task, {start_date_str}, {duration_str}")
            # End of maintenance milestone
            eol_date_formatted = eol_date.strftime('%Y-%m-%d')
            print(f"        End of maintenance:         milestone, {eol_date_formatted}, 0m")
        elif eol_date:
            # No extended maintenance, but have eol_date
            eol_date_formatted = eol_date.strftime('%Y-%m-%d')
            print(f"        End of maintenance:         milestone, {eol_date_formatted}, 0m")

def format_shell(rows, headers, no_header):
    """Format release data for shell output."""
    if not no_header:
        print("\t".join([f"{header:<20}" for header in headers]))
    for row in rows:
        print("\t".join([f"{str(col) if col is not None else 'foo':<20}" for col in row]))

def filter_fields(headers, rows, fields):
    """Filter out the fields based on user input."""
    selected_indexes = [headers.index(field) for field in fields if field in headers]
    filtered_headers = [headers[i] for i in selected_indexes]
    filtered_rows = [[row[i] for i in selected_indexes] for row in rows]
    return filtered_headers, filtered_rows

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
            print(f"Error fetching data from URL: {e}")
            exit(1)
    else:
        if not os.path.exists(input_source):
            print(f"Error: File {input_source} does not exist.")
            exit(1)
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
    
    parser.add_argument('--input-format', type=str, choices=['yaml', 'json'], default=DEFAULTS['DEFAULT_QUERY_INPUT_FORMAT'], help="Input format: 'yaml' or 'json' (default: json).")
    parser.add_argument('--input-file-prefix', type=str, default=DEFAULTS['DEFAULT_QUERY_INPUT_FILE_PREFIX'], help="The prefix to get input files (default: releases).")
    parser.add_argument('--input-type', choices=['file', 'url'], default=DEFAULTS['DEFAULT_QUERY_INPUT_TYPE'], help="Specify if the input type (default: url).")
    parser.add_argument('--input-url', type=str, default=DEFAULTS['DEFAULT_QUERY_INPUT_URL'], help="Input URL to the releases data. Defaults to gardenlinux-glrd S3 URL.")
    parser.add_argument('--no-input-split', action='store_true', help="Do not split Input into stable+patch and nightly. No additional input-files *-nightly and *-dev will be parsed.")
    parser.add_argument('--output-format', choices=['json', 'yaml', 'markdown', 'mermaid_gantt', 'shell'], default=DEFAULTS['DEFAULT_QUERY_OUTPUT_TYPE'], help="Output format: json, yaml, markdown, mermaid_gantt, shell (default).")
    parser.add_argument('--output-description', type=str, default=DEFAULTS['DEFAULT_QUERY_OUTPUT_DESCRIPTION'], help="Description, added to certain outputs, e.g. mermaid (default: 'Garden Linux Releases').")
    parser.add_argument('--active', action='store_true', help="Show only active releases.")
    parser.add_argument('--archived', action='store_true', help="Show only archived releases.")
    parser.add_argument('--latest', action='store_true', help="Show the latest active major.minor release.")
    parser.add_argument('--type', type=str, default=DEFAULTS['DEFAULT_QUERY_TYPE'], help="Filter by release types (comma-separated list, default: stable,patch). E.g., --type stable,patch,nightly,dev,next")
    parser.add_argument('--version', type=str, help="Filter by a specific version (major or major.minor). E.g., --version 1312 or --version 1312.0")
    parser.add_argument(
        '--fields', 
        type=str, 
        help=(
            "Comma-separated list of fields to output. E.g., --fields "
            "\"Name, Version, Type, Git Commit, Release date, Release time, Extended maintenance, End of maintenance\""
        )
    )
    parser.add_argument('--no-header', action='store_true', help="Omit the header in shell output.")
    
    return parser.parse_args()
