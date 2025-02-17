import json
import logging
import os
import re
import signal
import sys
from datetime import datetime

import pytz
import yaml

ERROR_CODES = {
    "validation_error": 1,
    "subprocess_output_error": 2,
    "no_releases": 3,
    "s3_error": 4,
    "query_error": 5,
    "parameter_missing": 6,
}

DEFAULTS = {
    # Release types
    'RELEASE_TYPES': ['next', 'stable', 'patch', 'nightly', 'dev'],

    # Query defaults
    'QUERY_TYPE': 'stable,patch',
    'QUERY_FIELDS': 'Name,Version,Type,ReleaseDate,ExtendedMaintenance,EndOfMaintenance,Flavors',
    'QUERY_INPUT_TYPE': 'url',
    'QUERY_INPUT_URL': 'https://gardenlinux-glrd.s3.eu-central-1.amazonaws.com',
    'QUERY_INPUT_FILE_PREFIX': 'releases',
    'QUERY_INPUT_FORMAT': 'json',
    'QUERY_OUTPUT_TYPE': 'shell',
    'QUERY_OUTPUT_DESCRIPTION': 'Garden Linux Releases',
    
    # Manage defaults
    'MANAGE_INPUT_FILE': 'releases-input.yaml',
    'MANAGE_OUTPUT_FORMAT': 'yaml',
    'MANAGE_OUTPUT_FILE_PREFIX': 'releases',

    # S3 configuration for glrd storage
    'GLRD_S3_BUCKET_NAME': 'gardenlinux-glrd',
    'GLRD_S3_BUCKET_PREFIX': '',
    'GLRD_S3_BUCKET_REGION': 'eu-central-1',
    
    # S3 configuration for releases artifacts
    'ARTIFACTS_S3_BUCKET_NAME': 'gardenlinux-github-releases',
    'ARTIFACTS_S3_PREFIX': 'objects/',
    'ARTIFACTS_S3_BASE_URL': 'https://gardenlinux-github-releases.s3.amazonaws.com',

    # Garden Linux repository
    'GL_REPO_NAME': 'gardenlinux',
    'GL_REPO_OWNER': 'gardenlinux',
    'GL_REPO_URL': 'https://github.com/gardenlinux/gardenlinux',

    # Container registry configuration
    'CONTAINER_REGISTRY': 'ghcr.io/gardenlinux/gardenlinux',
    
    # Platform file extensions
    'PLATFORM_EXTENSIONS': {
        'ali': 'qcow2',
        'aws': 'raw',
        'azure': 'vhd',
        'gcp': 'gcpimage.tar.gz',
        'gdch': 'gcpimage.tar.gz',
        'kvm': 'raw',
        'metal': 'raw',
        'openstack': 'qcow2',
        'openstackbaremetal': 'qcow2',
        'vmware': 'ova',
    }
}

def extract_version_data(tag_name):
    """Extract major and minor version numbers from a tag."""
    version_regex = re.compile(r'^(\d+)\.?(\d+)?$')
    match = version_regex.match(tag_name)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)

def get_current_timestamp():
    """Get current timestamp in UTC."""
    return int(datetime.now(pytz.UTC).timestamp())

def timestamp_to_isotime(timestamp):
    """Convert timestamp to ISO time string."""
    if not timestamp:
        return 'N/A'
    try:
        dt = datetime.fromtimestamp(timestamp, pytz.UTC)
        return dt.strftime('%H:%M:%S')
    except (ValueError, TypeError):
        return 'N/A'

def isodate_to_timestamp(isodate):
    """
    Convert an ISO 8601 formatted date (with or without time) to a Unix timestamp.
    If only a date is provided, assume the time is 00:00:00 UTC.
    """
    try:
        # Try parsing with full ISO format (date and time with 'Z' timezone)
        return int(datetime.strptime(isodate, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC).timestamp())
    except ValueError:
        # If the time part is missing, assume time is 00:00:00 UTC
        return int(datetime.strptime(isodate, "%Y-%m-%d").replace(tzinfo=pytz.UTC).timestamp())

def timestamp_to_isodate(timestamp):
    """Convert timestamp to ISO date."""
    dt = datetime.utcfromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d")

# Handle SIGPIPE and BrokenPipeError
def handle_broken_pipe_error(signum, frame):
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(0)

signal.signal(signal.SIGPIPE, handle_broken_pipe_error)

def setup_logger(log_level, name='glrd'):
    """
    Configure and return a logger with the specified log level.
    
    Args:
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        name (str): Logger name (default: 'glrd')
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Get or create logger
    logger = logging.getLogger(name)
    
    # Remove any existing handlers to prevent duplicates
    logger.handlers = []
    
    # Prevent propagation to parent loggers
    logger.propagate = False
    
    # Set level
    logger.setLevel(log_level)
    
    # Create console handler with formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = logging.Formatter('%(message)s')  # Simplified format without prefix
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger
