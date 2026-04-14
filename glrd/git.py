"""
Git operations for GLRD.

This module provides functions for interacting with Git repositories
and GitHub APIs to retrieve commit information and release data.
"""

import json
import logging
import subprocess
import sys
import tempfile
from datetime import datetime
from typing import Optional, Tuple

import pytz

from glrd.util import DEFAULTS, ERROR_CODES, extract_version_data, isodate_to_timestamp

# Global variable to cache the repository clone path
_repo_clone_path: Optional[str] = None


def get_github_releases() -> list:
    """Fetch releases from the GitHub API using the 'gh' command."""
    command = [
        "gh",
        "api",
        "--paginate",
        f"/repos/{DEFAULTS['GL_REPO_OWNER']}/{DEFAULTS['GL_REPO_NAME']}/releases",
    ]
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode != 0:
        logging.error(f"Error fetching GitHub releases: {result.stderr}")
        sys.exit(ERROR_CODES["subprocess_output_error"])
    return json.loads(result.stdout)


def get_git_commit_from_tag(tag: str) -> Tuple[str, str]:
    """
    Fetch the git commit hash for a given tag using the GitHub API.

    Args:
        tag: Git tag name

    Returns:
        Tuple of (full_commit_sha, short_commit_sha)
    """
    try:
        # Use the GitHub API to get the commit hash from the tag name
        command = [
            "gh",
            "api",
            f"/repos/{DEFAULTS['GL_REPO_OWNER']}/"
            f"{DEFAULTS['GL_REPO_NAME']}/git/refs/tags/{tag}",
            "--jq",
            ".object.sha",
        ]
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            logging.error(f"Error fetching git commit for tag: {tag}, {result.stderr}")
            sys.exit(ERROR_CODES["subprocess_output_missing"])

        commit = result.stdout.strip()
        return (
            commit,
            commit[:8],
        )  # Return full commit and shortened version
    except Exception as e:
        logging.error(f"Error fetching git commit for tag {tag}: {e}")
        sys.exit(ERROR_CODES["subprocess_output_error"])


def get_git_commit_at_time(
    date: str,
    time: str = "06:00",
    branch: str = "main",
    remote_repo: str = DEFAULTS["GL_REPO_URL"],
) -> Tuple[str, str]:
    """
    Fetch the git commit that was at a specific date and time in the
    main branch, using a temporary cached git clone.

    Args:
        date: Date string in YYYY-MM-DD format
        time: Time string in HH:MM format (default: "06:00")
        branch: Git branch to check (default: "main")
        remote_repo: URL of the remote repository

    Returns:
        Tuple of (full_commit_sha, short_commit_sha)
    """
    global _repo_clone_path

    # Convert the input date and time to the target timezone (UTC) and
    # then to UTC
    target_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").astimezone(
        pytz.timezone("UTC")
    )
    target_time_utc = target_time.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # If the repository hasn't been cloned yet, clone it to a dynamically
    # created temp directory
    if not _repo_clone_path:
        # Create a temporary directory for cloning the repository
        temp_dir = tempfile.mkdtemp(prefix="glrd_temp_repo_")

        # Perform the shallow clone
        clone_command = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            remote_repo,
            temp_dir,
        ]
        clone_result = subprocess.run(
            clone_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if clone_result.returncode != 0:
            logging.error(f"Error cloning remote repository: {clone_result.stderr}")
            sys.exit(ERROR_CODES["subprocess_output_error"])

        # Fetch full history to enable searching through commits by time
        fetch_command = ["git", "fetch", "--unshallow"]
        fetch_result = subprocess.run(
            fetch_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=temp_dir,
        )

        if fetch_result.returncode != 0:
            logging.error(
                f"Error fetching full history from remote repository: {fetch_result.stderr}"
            )
            sys.exit(ERROR_CODES["subprocess_output_error"])

        # Cache the clone path to reuse it later
        _repo_clone_path = temp_dir

    # Use `git rev-list` to find the commit before the specified time
    rev_list_command = [
        "git",
        "rev-list",
        "-n",
        "1",
        "--before",
        target_time_utc,
        branch,
    ]
    rev_list_result = subprocess.run(
        rev_list_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=_repo_clone_path,
    )

    if rev_list_result.returncode != 0:
        logging.error(
            f"Error fetching git commit for {date} at {time}: {rev_list_result.stderr}"
        )
        sys.exit(ERROR_CODES["subprocess_output_error"])

    commit = rev_list_result.stdout.strip()

    # Example of a debug message
    logging.debug(f"Found commit {commit} for {date} at {time}")

    if not commit:
        logging.error(f"No commit found for {date} at {time}")
        sys.exit(ERROR_CODES["subprocess_output_missing"])

    return commit, commit[:8]


def cleanup_temp_repo() -> None:
    """
    Clean up the temporary repository clone.

    This function can be registered as an atexit handler.
    """
    global _repo_clone_path
    if _repo_clone_path:
        import shutil

        shutil.rmtree(_repo_clone_path, ignore_errors=True)
        _repo_clone_path = None


def get_garden_version_for_date(
    release_type: str, date: datetime, existing_releases: list
) -> Tuple[int, int, int]:
    """
    Create major.minor.patch version based on the Garden Linux base_date.
    Logic is taken from `gardenlinux/bin/garden-version`.

    Major: days since base date.
    Minor: Next available minor version based on existing releases.
    Patch: Next available patch version based on existing releases.

    Args:
        release_type: Type of release
        date: Release date
        existing_releases: List of existing release dicts

    Returns:
        Tuple of (major, minor, patch)
    """
    # Calculate major version
    base_date = datetime(2020, 3, 31, tzinfo=pytz.UTC)
    major = (date - base_date).days

    if release_type == "next":
        minor = 0
        patch = 0
    elif release_type == "major":
        minor = 0
        patch = 0
    else:
        # Collect existing minor versions for the given major version and
        # release type
        existing_minor_versions = [
            release["version"].get("minor", -1)
            for release in existing_releases
            if (
                release["type"] == release_type and release["version"]["major"] == major
            )
        ]

        # For patch versions, we need to find the latest minor first
        if existing_minor_versions:
            minor = max(existing_minor_versions)
        else:
            minor = 0

        existing_patch_versions = [
            release["version"].get("patch", -1)
            for release in existing_releases
            if (
                release["type"] == release_type
                and release["version"]["major"] == major
                and release["version"].get("minor") == minor
            )
        ]

        logging.debug(
            f"Existing patch versions for major {major} and minor "
            f"{minor}: {existing_patch_versions}"
        )

        if existing_minor_versions:
            # Increment minor if we have existing minor versions
            minor = max(existing_minor_versions) + 1
        else:
            minor = 0

        if existing_patch_versions:
            patch = max(existing_patch_versions) + 1
        else:
            patch = 0

    logging.debug(
        f"New {release_type} version for {date} is " f"{major}.{minor}.{patch}"
    )

    return major, minor, patch


def create_initial_releases(releases: list) -> Tuple[list, list, dict, dict]:
    """
    Generate initial major and minor releases from GitHub releases.

    Args:
        releases: List of GitHub release objects

    Returns:
        Tuple of (release_data_major, release_data_minor,
                  latest_minor_versions, latest_patch_versions)
    """
    release_data_major = []
    release_data_minor = []
    latest_minor_versions = {}
    latest_patch_versions = {}

    releases.sort(key=lambda r: extract_version_data(r["tag_name"]))

    for release in releases:
        tag_name = release.get("tag_name")
        major, minor, patch = extract_version_data(tag_name)
        if major is None:
            continue

        # Determine release type: "minor" if minor exists, otherwise "major"
        release_type = "minor" if minor is not None and patch is not None else "major"

        release_info = {
            "name": f"{release_type}-{tag_name}",
            "type": release_type,
            "version": {"major": major},
            "lifecycle": {
                "released": {
                    "isodate": release["published_at"][:10],
                    "timestamp": isodate_to_timestamp(release["published_at"]),
                },
                "eol": {"isodate": None, "timestamp": None},
            },
        }
        if release_type == "major":
            release_data_major.append(release_info)
            logging.debug(f"Initial major release '{release_info['name']}' created.")
        else:
            # For minor releases, add git and github data
            if release_type == "minor":
                commit, commit_short = get_git_commit_from_tag(tag_name)
                release_info["version"]["minor"] = minor
                release_info["version"]["patch"] = patch
                release_info["git"] = {
                    "commit": commit,
                    "commit_short": commit_short,
                }
                release_info["github"] = {"release": release["html_url"]}
                release_data_minor.append(release_info)
                logging.debug(
                    f"Initial minor release '{release_info['name']}' created."
                )

        if major not in latest_minor_versions or (
            (minor is not None and minor > latest_minor_versions[major]["minor"])
            and (patch is not None and patch > latest_minor_versions[major]["patch"])
        ):
            latest_minor_versions[major] = {
                "index": len(
                    release_data_minor
                    if release_type == "minor"
                    else release_data_major
                )
                - 1,
                "minor": minor,
                "patch": patch,
            }

    return (
        release_data_major,
        release_data_minor,
        latest_minor_versions,
        latest_patch_versions,
    )


def create_initial_nightly_releases(major_releases: list) -> list:
    """
    Create initial nightly releases based on major releases.

    Args:
        major_releases: List of major release dicts

    Returns:
        List of nightly release dicts
    """
    nightly_releases = []

    # Sort major releases by released timestamp
    if not major_releases:
        return nightly_releases

    sorted_major_releases = sorted(
        major_releases,
        key=lambda r: r["lifecycle"]["released"]["timestamp"],
    )

    # Use the first major release's timestamp to determine the start date
    first_major_release = sorted_major_releases[0]
    start_date = datetime.fromtimestamp(
        first_major_release["lifecycle"]["released"]["timestamp"], pytz.UTC
    ).replace(hour=7, minute=0, second=0, microsecond=0, tzinfo=pytz.UTC)

    # Calculate the number of nightly releases to create (one per day)
    for major_release in sorted_major_releases:
        current_date = start_date

        # Create nightly releases until the next major release
        while current_date < datetime.fromtimestamp(
            major_release["lifecycle"]["released"]["timestamp"], pytz.UTC
        ):
            major, minor, patch = get_garden_version_for_date(
                "nightly", current_date, nightly_releases
            )
            commit, commit_short = get_git_commit_at_time(
                current_date.strftime("%Y-%m-%d")
            )

            release = {
                "name": (
                    f"nightly-{major}.{minor}.{patch}"
                    if major >= 2017
                    else f"nightly-{major}.{minor}"
                ),
                "type": "nightly",
                "version": {"major": major, "minor": minor},
                "lifecycle": {
                    "released": {
                        "isodate": current_date.strftime("%Y-%m-%d"),
                        "timestamp": int(current_date.timestamp()),
                    }
                },
                "git": {"commit": commit, "commit_short": commit_short},
            }

            # Add patch field for v2 schema (>= 2017)
            if major >= 2017:
                release["version"]["patch"] = patch

            nightly_releases.append(release)
            logging.debug(f"Nightly release '{release['name']}' created.")
            # Move to next day
            from datetime import timedelta

            current_date = current_date + timedelta(days=1)

    return nightly_releases
