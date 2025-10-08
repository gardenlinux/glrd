import importlib.metadata
import logging
import os
import re
import signal
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Optional

import pytz
import yaml

from gardenlinux.constants import GL_REPOSITORY_URL
from gardenlinux.flavors import Parser
from gardenlinux.git import Repository
from gardenlinux.s3 import Bucket


ERROR_CODES = {
    "validation_error": 1,
    "subprocess_output_error": 2,
    "no_releases": 3,
    "s3_error": 4,
    "query_error": 5,
    "parameter_missing": 6,
    "invalid_field": 7,
    "http_error": 8,
    "file_not_found": 9,
    "format_error": 10,
    "input_error": 11,
}

DEFAULTS = {
    # Release types
    "RELEASE_TYPES": ["next", "major", "minor", "nightly", "dev"],
    # Query defaults
    "QUERY_TYPE": "major,minor",
    "QUERY_FIELDS": (
        "Name,Version,Type,GitCommitShort,ReleaseDate,"
        "ExtendedMaintenance,EndOfMaintenance"
    ),
    "QUERY_INPUT_TYPE": "url",
    "QUERY_INPUT_URL": ("https://gardenlinux-glrd.s3.eu-central-1.amazonaws.com"),
    "QUERY_INPUT_FILE_PREFIX": "releases",
    "QUERY_INPUT_FORMAT": "json",
    "QUERY_OUTPUT_TYPE": "shell",
    "QUERY_OUTPUT_DESCRIPTION": "Garden Linux Releases",
    # Manage defaults
    "MANAGE_INPUT_FILE": "releases-input.json",
    "MANAGE_OUTPUT_FORMAT": "json",
    "MANAGE_OUTPUT_FILE_PREFIX": "releases",
    # S3 configuration for glrd storage
    "GLRD_S3_BUCKET_NAME": "gardenlinux-glrd",
    "GLRD_S3_BUCKET_PREFIX": "",
    "GLRD_S3_BUCKET_REGION": "eu-central-1",
    # S3 configuration for releases artifacts
    "ARTIFACTS_S3_BUCKET_NAME": "gardenlinux-github-releases",
    "ARTIFACTS_S3_PREFIX": "objects/",
    "ARTIFACTS_S3_BASE_URL": ("https://gardenlinux-github-releases.s3.amazonaws.com"),
    "ARTIFACTS_S3_CACHE_FILE": "artifacts-cache.json",
    # Garden Linux repository
    "GL_REPO_NAME": "gardenlinux",
    "GL_REPO_OWNER": "gardenlinux",
    "GL_REPO_URL": "https://github.com/gardenlinux/gardenlinux",
    # Container registry configuration
    "CONTAINER_REGISTRY": "ghcr.io/gardenlinux/gardenlinux",
    # Platform file extensions
    "PLATFORM_EXTENSIONS": {
        "ali": "qcow2",
        "aws": "raw",
        "azure": "vhd",
        "gcp": "gcpimage.tar.gz",
        "gdch": "gcpimage.tar.gz",
        "kvm": "raw",
        "metal": "raw",
        "openstack": "qcow2",
        "openstackbaremetal": "qcow2",
        "vmware": "ova",
    },
}


def get_version():
    return importlib.metadata.version("glrd")


def extract_version_data(tag_name):
    """Extract major, minor and patch version numbers from a tag."""
    version_regex = re.compile(r"^(\d+)\.?(\d+)?\.?(\d+)?$")
    match = version_regex.match(tag_name)
    return (
        (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if match
        else (None, None, None)
    )


def get_current_timestamp():
    """Get current timestamp."""
    return int(datetime.now().timestamp())


def timestamp_to_isotime(timestamp):
    """Convert timestamp to ISO time string."""
    if not timestamp:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(timestamp, pytz.UTC)
        return dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        logging.error(f"Error converting timestamp to ISO time: " f"{timestamp}")
        sys.exit(ERROR_CODES["format_error"])


def isodate_to_timestamp(isodate):
    """
    Convert an ISO 8601 formatted date (with or without time) to a Unix
    timestamp. If only a date is provided, assume the time is 00:00:00 UTC.
    """
    try:
        # Try parsing with full ISO format (date and time with 'Z' timezone)
        return int(
            datetime.strptime(isodate, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=pytz.UTC)
            .timestamp()
        )
    except ValueError:
        # If the time part is missing, assume time is 00:00:00 UTC
        return int(
            datetime.strptime(isodate, "%Y-%m-%d").replace(tzinfo=pytz.UTC).timestamp()
        )


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


# Create a custom dumper class that doesn't generate anchors
class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


signal.signal(signal.SIGPIPE, handle_broken_pipe_error)


def get_flavors_from_git(commit: str) -> List[str]:
    """
    Get flavors from Git repository using gardenlinux library.

    Args:
        commit: Git commit hash (or 'latest')

    Returns:
        List of flavor strings
    """

    try:
        with TemporaryDirectory() as git_directory:
            # Use gardenlinux Repository class for sparse checkout with pygit2
            Repository.checkout_repo_sparse(
                git_directory=git_directory,
                repo_url=GL_REPOSITORY_URL,
                commit=commit if commit != "latest" else None,
                pathspecs=["flavors.yaml"],  # Only checkout the flavors.yaml file
            )

            flavors_file = Path(git_directory, "flavors.yaml")
            if flavors_file.exists():
                with flavors_file.open("r") as fp:
                    flavors_data = fp.read()
                    flavors_yaml = yaml.safe_load(flavors_data)
                    parser = Parser(flavors_yaml)
                    combinations = parser.filter()
                    all_flavors = set(combination for _, combination in combinations)
                    flavors = sorted(all_flavors)
                    logging.info(f"Found {len(flavors)} flavors in Git")
                    return flavors
            else:
                logging.warning("flavors.yaml not found in repository")
                return []
    except Exception as exc:
        logging.debug(f"Could not get flavors from Git: {exc}")
        return []


def get_s3_artifacts_data(
    bucket_name: str,
    prefix: str,
    cache_file: Optional[str] = None,
    cache_ttl: int = 3600,
) -> Optional[Dict]:
    """
    Get S3 artifacts data using gardenlinux library with caching support.

    Args:
        bucket_name: S3 bucket name
        prefix: S3 prefix
        cache_file: Optional cache file path for S3 object keys
        cache_ttl: Cache time-to-live in seconds (default: 1 hour)

    Returns:
        Dictionary containing S3 artifacts data with 'index' and 'artifacts' keys
    """

    try:
        bucket = Bucket(bucket_name)

        artifacts = bucket.read_cache_file_or_filter(
            cache_file, cache_ttl=cache_ttl, Prefix=prefix
        )

        index = {}
        for key in artifacts:
            try:
                parts = key.split("/")
                if len(parts) >= 3:
                    version_commit = parts[1]
                    if "-" in version_commit:
                        version_part, commit_part = version_commit.split("-", 1)
                        if version_part not in index:
                            index[version_part] = []
                        index[version_part].append(key)
            except Exception as e:
                logging.debug(f"Could not parse version from key {key}: {e}")

        result = {"index": index, "artifacts": artifacts}
        logging.info(f"Found {len(artifacts)} artifacts and {len(index)} index entries")
        return result
    except Exception as e:
        logging.error(f"Error getting S3 artifacts: {e}")
        return None


def get_flavors_from_s3_artifacts(
    artifacts_data: Dict, version: Dict[str, Any], commit: str
) -> List[str]:
    """
    Extract flavors from S3 artifacts data.

    Args:
        artifacts_data: S3 artifacts data dictionary
        version: Version dictionary with major, minor, micro
        commit: Git commit hash

    Returns:
        List of flavor strings
    """

    try:
        version_info = f"{version['major']}.{version.get('minor', 0)}"
        commit_short = commit[:8]

        # Try index lookup first
        search_key = f"{version_info}-{commit_short}"
        if search_key in artifacts_data.get("index", {}):
            flavors = artifacts_data["index"][search_key]
            logging.debug(f"Found flavors in S3 index for {search_key}")
            return flavors
        else:
            # Search through artifacts
            found_flavors = set()
            for key in artifacts_data.get("artifacts", []):
                if version_info in key and commit_short in key:
                    try:
                        parts = key.split("/")
                        if len(parts) >= 2:
                            flavor_with_version = parts[1]
                            flavor = flavor_with_version.rsplit(f"-{version_info}", 1)[
                                0
                            ]
                            if flavor:
                                found_flavors.add(flavor)
                    except Exception as e:
                        logging.debug(f"Error parsing artifact key {key}: {e}")
                        continue
            flavors = sorted(found_flavors)
            if flavors:
                logging.info(f"Found {len(flavors)} flavors in S3 artifacts")
            return flavors
    except Exception as e:
        logging.error(f"Error processing S3 artifacts: {e}")
        return []
