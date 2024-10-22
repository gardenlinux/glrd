import os
import re
import signal
import sys
from datetime import datetime

DEFAULTS = {
    'DEFAULT_QUERY_INPUT_FORMAT': 'json',
    'DEFAULT_QUERY_INPUT_FILE_PREFIX': 'releases',
    'DEFAULT_QUERY_INPUT_TYPE': 'url',
    'DEFAULT_QUERY_INPUT_URL': 'https://gardenlinux-glrd.s3.eu-central-1.amazonaws.com',
    'DEFAULT_QUERY_OUTPUT_TYPE': 'shell',
    'DEFAULT_QUERY_OUTPUT_DESCRIPTION': 'Garden Linux Releases',
    'DEFAULT_QUERY_TYPE': 'stable,patch',
    'DEFAULT_MANAGE_INPUT_FILE': 'releases-input.yaml',
    'DEFAULT_MANAGE_OUTPUT_FILE_PREFIX': 'releases',
    'DEFAULT_MANAGE_OUTPUT_FORMAT': 'json',
    'DEFAULT_S3_BUCKET_NAME': 'gardenlinux-glrd',
    'DEFAULT_S3_BUCKET_PREFIX': '',
    'DEFAULT_S3_BUCKET_REGION': 'eu-central-1'
}

# Definition of error codes
ERROR_CODES = {
    "generic_error": 1,
    "parameter_missing": 2,
    "subprocess_output_error": 100,
    "subprocess_output_missing": 110,
    "input_parameter_error": 101,
    "input_parameter_missing": 111,
    "s3_output_error": 102,
    "s3_output_missing": 112,
    "validation_error": 200,
    "query_error": 201,
}

def extract_version_data(tag_name):
    """Extract major and minor version numbers from a tag."""
    version_regex = re.compile(r'^(\d+)\.?(\d+)?$')
    match = version_regex.match(tag_name)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)

def get_current_timestamp():
    """Return the current timestamp."""
    return int(datetime.now().timestamp())

def timestamp_to_isotime(timestamp):
    """Convert timestamp to ISO time."""
    dt = datetime.utcfromtimestamp(float(timestamp))
    return dt.strftime("%H:%M:%S")

def isodate_to_timestamp(isodate):
    """Convert ISO date to timestamp."""
    return int(datetime.strptime(isodate, "%Y-%m-%d").timestamp())

def timestamp_to_isodate(timestamp):
    """Convert timestamp to ISO date."""
    dt = datetime.utcfromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d")

def timestamp_to_isotime(timestamp):
    """Convert timestamp to ISO time."""
    dt = datetime.utcfromtimestamp(timestamp)
    return dt.strftime("%H:%M:%S")

# Handle SIGPIPE and BrokenPipeError
def handle_broken_pipe_error(signum, frame):
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)

signal.signal(signal.SIGPIPE, handle_broken_pipe_error)
