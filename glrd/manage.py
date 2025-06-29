import argparse
import atexit
import base64
import fnmatch
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta

import boto3
import pytz
import yaml
from botocore.exceptions import ClientError
from dateutil.relativedelta import relativedelta
from deepdiff import DeepDiff
from jsonschema import validate, ValidationError

from glrd.query import load_all_releases
from glrd.util import *
from python_gardenlinux_lib.flavors.parse_flavors import *
from python_gardenlinux_lib.s3.s3 import *

# silence boto3 logging
boto3.set_stream_logger(name="botocore.credentials", level=logging.ERROR)

# JSON schema for stable, patch, and nightly releases
SCHEMAS = {
    "next": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["next"]},
            "version": {
                "type": "object",
                "properties": { "major": {"enum": ["next"]}},
                "required": ["major"]
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {"type": "object", "properties": {
                        "isodate": {"type": "string", "format": "date"},
                        "timestamp": {"type": "integer"}},
                        "required": ["isodate", "timestamp"]},
                    "extended": {
                        "type": "object",
                        "properties": {
                            "isodate": {"type": ["string"], "format": "date"},
                            "timestamp": {"type": ["integer"]}
                        }
                    },
                    "eol": {
                        "type": "object",
                        "properties": {
                            "isodate": {"type": ["string"], "format": "date"},
                            "timestamp": {"type": ["integer"]}
                        }
                    }
                },
                "required": ["released", "extended", "eol"]
            }
        },
        "required": ["name", "type", "version", "lifecycle"]
    },
    "stable": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["stable"]},
            "version": {
                "type": "object",
                "properties": {"major": {"type": "integer"}},
                "required": ["major"]
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {"type": "object", "properties": {
                        "isodate": {"type": "string", "format": "date"},
                        "timestamp": {"type": "integer"}},
                        "required": ["isodate", "timestamp"]},
                    "extended": {
                        "type": "object",
                        "properties": {
                            "isodate": {"type": ["string"], "format": "date"},
                            "timestamp": {"type": ["integer"]}
                        }
                    },
                    "eol": {
                        "type": "object",
                        "properties": {
                            "isodate": {"type": ["string"], "format": "date"},
                            "timestamp": {"type": ["integer"]}
                        }
                    }
                },
                "required": ["released", "extended", "eol"]
            }
        },
        "required": ["name", "type", "version", "lifecycle"]
    },
    "patch": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["patch"]},
            "version": {
                "type": "object",
                "properties": {
                    "major": {"type": "integer"},
                    "minor": {"type": "integer"}
                },
                "required": ["major", "minor"]
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {"type": "object", "properties": {
                        "isodate": {"type": "string", "format": "date"},
                        "timestamp": {"type": "integer"}},
                        "required": ["isodate", "timestamp"]},
                    "eol": {
                        "type": "object",
                        "properties": {
                            "isodate": {"type": ["string"], "format": "date"},
                            "timestamp": {"type": ["integer"]}
                        }
                    }
                },
                "required": ["released", "eol"]
            },
            "git": {
                "type": "object",
                "properties": {
                    "commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                    "commit_short": {"type": "string", "pattern": "^[0-9a-f]{7,8}$"}
                },
                "required": ["commit", "commit_short"]
            },
            "github": {
                "type": "object",
                "properties": {"release": {"type": "string", "format": "uri"}},
                "required": ["release"]
            },
            "flavors": {
                "type": "array",
                "items": {"type": "string"}
            },
            "attributes": {
                "type": "object",
                "properties": {
                    "source_repo": {
                        "type": "boolean",
                        "default": True
                    }
                },
                "required": ["source_repo"]
            }
        },
        "required": ["name", "type", "version", "lifecycle", "git", "github"]
    },
    "nightly": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["nightly"]},
            "version": {
                "type": "object",
                "properties": {"major": {"type": "integer"}, "minor": {"type": "integer"}},
                "required": ["major", "minor"]
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {"type": "object", "properties": {
                        "isodate": {"type": "string", "format": "date"},
                        "timestamp": {"type": "integer"}},
                        "required": ["isodate", "timestamp"]}
                },
                "required": ["released"]
            },
            "git": {
                "type": "object",
                "properties": {
                    "commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                    "commit_short": {"type": "string", "pattern": "^[0-9a-f]{7,8}$"}
                },
                "required": ["commit", "commit_short"]
            },
            "flavors": {
                "type": "array",
                "items": {"type": "string"}
            },
            "attributes": {
                "type": "object",
                "properties": {
                    "source_repo": {
                        "type": "boolean",
                        "default": True
                    }
                },
                "required": ["source_repo"]
            }
        },
        "required": ["name", "type", "version", "lifecycle", "git"]
    },
    "dev": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["dev"]},
            "version": {
                "type": "object",
                "properties": {"major": {"type": "integer"}, "minor": {"type": "integer"}},
                "required": ["major", "minor"]
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {"type": "object", "properties": {
                        "isodate": {"type": "string", "format": "date"},
                        "timestamp": {"type": "integer"}},
                        "required": ["isodate", "timestamp"]}
                },
                "required": ["released"]
            },
            "git": {
                "type": "object",
                "properties": {
                    "commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                    "commit_short": {"type": "string", "pattern": "^[0-9a-f]{7,8}$"}
                },
                "required": ["commit", "commit_short"]
            },
            "flavors": {
                "type": "array",
                "items": {"type": "string"}
            },
            "attributes": {
                "type": "object",
                "properties": {
                    "source_repo": {
                        "type": "boolean",
                        "default": True
                    }
                },
                "required": ["source_repo"]
            }
        },
        "required": ["name", "type", "version", "lifecycle", "git"]
    }
}

# Global variable to store the path of the cloned gardenlinux repository (cached)
repo_clone_path = None

def cleanup_temp_repo():
    """Cleanup function to delete the temporary directory at the end of the script."""
    global repo_clone_path
    if repo_clone_path and os.path.exists(repo_clone_path):
        shutil.rmtree(repo_clone_path)

def glrd_query_type(args, release_type):
    """Retrieve releases of a specific type."""
    releases = load_all_releases(release_type, DEFAULTS['QUERY_INPUT_TYPE'],
                               DEFAULTS['QUERY_INPUT_URL'],
                               DEFAULTS['QUERY_INPUT_FILE_PREFIX'],
                               DEFAULTS['QUERY_INPUT_FORMAT'])
    if not releases:
        logging.error(f"Error retrieving releases: {result.stderr}")
        sys.exit(ERROR_CODES["query_error"])
    return releases

def get_github_releases():
    """Fetch releases from the GitHub API using the 'gh' command."""
    command = ["gh", "api", "--paginate", f"/repos/{DEFAULTS['GL_REPO_OWNER']}/{DEFAULTS['GL_REPO_NAME']}/releases"]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logging.error(f"Error fetching GitHub releases: {result.stderr}")
        sys.exit(ERROR_CODES["subprocess_output_error"])
    return json.loads(result.stdout)

def get_git_commit_from_tag(tag):
    """
    Fetch the git commit hash for a given tag using the GitHub API.
    """
    try:
        # Use the GitHub API to get the commit hash from the tag name
        command = ["gh", "api", f"/repos/{DEFAULTS['GL_REPO_OWNER']}/{DEFAULTS['GL_REPO_NAME']}/git/refs/tags/{tag}", "--jq", ".object.sha"]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            logging.error(f"Error fetching git commit for tag: {tag}, {result.stderr}")
            sys.exit(ERROR_CODES["subprocess_output_missing"])

        commit = result.stdout.strip()
        return commit, commit[:8]  # Return full commit and shortened version
    except Exception as e:
        logging.error(f"Error fetching git commit for tag {tag}: {e}")
        sys.exit(ERROR_CODES["subprocess_output_error"])

def ensure_isodate_and_timestamp(lifecycle):
    """
    Ensure both isodate and timestamp are set for all lifecycle fields (released, extended, eol).
    If only one is present, the other is computed.
    """
    for key in ['released', 'extended', 'eol']:
        if key in lifecycle and lifecycle[key]:
            entry = lifecycle[key]
            # Ensure if 'isodate' exists, 'timestamp' is computed
            if 'isodate' in entry and entry['isodate'] and not entry.get('timestamp'):
                entry['timestamp'] = isodate_to_timestamp(entry['isodate'])
            # Ensure if 'timestamp' exists, 'isodate' is computed
            elif 'timestamp' in entry and entry['timestamp'] and not entry.get('isodate'):
                entry['isodate'] = timestamp_to_isodate(entry['timestamp'])

def get_git_commit_at_time(date, time="06:00", branch="main", remote_repo=DEFAULTS['GL_REPO_URL']):
    """Fetch the git commit that was at a specific date and time in the main branch, using a temporary cached git clone."""
    global repo_clone_path

    # Convert the input date and time to the target timezone (UTC) and then to UTC
    target_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").astimezone(pytz.timezone('UTC'))
    target_time_utc = target_time.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

    # If the repository hasn't been cloned yet, clone it to a dynamically created temp directory
    if not repo_clone_path:
        # Create a temporary directory for cloning the repository
        temp_dir = tempfile.mkdtemp(prefix="glrd_temp_repo_")

        # Perform the shallow clone
        clone_command = ["git", "clone", "--depth", "1", "--branch", branch, remote_repo, temp_dir]
        clone_result = subprocess.run(clone_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if clone_result.returncode != 0:
            logging.error(f"Error cloning remote repository: {clone_result.stderr}")
            sys.exit(ERROR_CODES["subprocess_output_error"])

        # Fetch full history to enable searching through commits by time
        fetch_command = ["git", "fetch", "--unshallow"]
        fetch_result = subprocess.run(fetch_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=temp_dir)

        if fetch_result.returncode != 0:
            logging.error(f"Error fetching full history from remote repository: {fetch_result.stderr}")
            sys.exit(ERROR_CODES["subprocess_output_error"])

        # Cache the clone path to reuse it later
        repo_clone_path = temp_dir

    # Use `git rev-list` to find the commit before the specified time
    rev_list_command = ["git", "rev-list", "-n", "1", "--before", target_time_utc, branch]
    rev_list_result = subprocess.run(rev_list_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=repo_clone_path)

    if rev_list_result.returncode != 0:
        logging.error(f"Error fetching git commit for {date} at {time}: {rev_list_result.stderr}")
        sys.exit(ERROR_CODES["subprocess_output_error"])

    commit = rev_list_result.stdout.strip()

    # Example of a debug message
    logging.debug(f"Found commit {commit} for {date} at {time}")

    if not commit:
        logging.error(f"No commit found for {date} at {time}")
        sys.exit(ERROR_CODES["subprocess_output_missing"])

    return commit, commit[:8]

def get_garden_version_for_date(release_type, date, existing_releases):
    """
    Create major and minor version based on the Garden Linux base_date.
    Logic is taken from `gardenlinux/bin/garden-version`.

    Major: days since base date.
    Minor: Next available minor version based on existing releases.
    """
    # Calculate major version
    base_date = datetime(2020, 3, 31, tzinfo=pytz.UTC)
    major = (date - base_date).days

    if release_type == 'next':
        minor = 0
    elif release_type == 'stable':
        minor = 0
    else:
        # Collect existing minor versions for the given major version and release type
        existing_minor_versions = [
            release['version'].get('minor', -1)
            for release in existing_releases
            if release['type'] == release_type and release['version']['major'] == major
        ]

        logging.debug(f"Existing minor versions for major {major}: {existing_minor_versions}")

        if existing_minor_versions:
            minor = max(existing_minor_versions) + 1
        else:
            minor = 0

    logging.debug(f"New {release_type} version for {date} is {major}.{minor}")

    return major, minor

def create_initial_releases(releases):
    """Generate initial stable and patch releases."""
    release_data_stable = []
    release_data_patch = []
    latest_minor_versions = {}

    releases.sort(key=lambda r: extract_version_data(r['tag_name']))

    for release in releases:
        tag_name = release.get('tag_name')
        major, minor = extract_version_data(tag_name)
        if major is None:
            continue

        # Determine release type: "patch" if minor exists, otherwise "stable"
        release_type = "patch" if minor is not None else "stable"

        release_info = {
            "name": f"{release_type}-{tag_name}",
            "type": release_type,
            "version": {"major": major},
            "lifecycle": {
                "released": {
                    "isodate": release['published_at'][:10],
                    "timestamp": isodate_to_timestamp(release['published_at'])
                },
                "eol": {
                    "isodate": None,
                    "timestamp": None
                }
            }
        }
        if release_type == "stable":
            release_data_stable.append(release_info)
            logging.debug(f"Initial stable release '{release_info['name']}' created.")
        else:
            # For patch releases, add git and github data
            if release_type == "patch":
                commit, commit_short = get_git_commit_from_tag(tag_name)
                release_info['version']['minor'] = minor
                release_info['git'] = {
                    "commit": commit,
                    "commit_short": commit_short
                }
                release_info['github'] = {
                    "release": release['html_url']
                }
                release_data_patch.append(release_info)
                logging.debug(f"Initial patch release '{release_info['name']}' created.")

        if major not in latest_minor_versions or (minor is not None and minor > latest_minor_versions[major]['minor']):
            latest_minor_versions[major] = {
                'index': len(release_data_patch if release_type == "patch" else release_data_stable) - 1,
                'minor': minor
            }

    return release_data_stable, release_data_patch, latest_minor_versions

def create_initial_nightly_releases(stable_releases):
    """Generate initial nightly releases from the earliest stable release."""
    release_data = []
    release_type = "nightly"

    # Set the default start date to 2020-06-09 06:00 UTC
    start_date_default = datetime(2020, 6, 9, 6, 0, 0, tzinfo=pytz.UTC)

    if stable_releases:
        # Get the earliest stable release timestamp
        first_stable_release = min(stable_releases, key=lambda r: r['lifecycle']['released']['timestamp'])
        # Convert the timestamp to a datetime object and set the time to 06:00 UTC
        start_date = datetime.utcfromtimestamp(first_stable_release['lifecycle']['released']['timestamp']).replace(hour=7, minute=0, second=0, tzinfo=pytz.UTC)
    else:
        logging.info("No stable releases found in the generated data. Using default start date.")
        # Use the default start date if no stable releases are available
        start_date = start_date_default

    # Ensure current_date is set to 06:00 UTC as well
    tz = pytz.timezone('UTC')
    current_date = datetime.now(tz).replace(hour=6, minute=0, second=0, microsecond=0)

    date = start_date

    while date <= current_date:
        major, minor = get_garden_version_for_date(release_type, date, [])
        commit, commit_short = get_git_commit_at_time(date.strftime('%Y-%m-%d'))
        nightly_name = f"nightly-{major}.{minor}"
        release_info = {
            "name": nightly_name,
            "type": "nightly",
            "version": {"major": major, "minor": minor},
            "lifecycle": {
                "released": {"isodate": date.strftime('%Y-%m-%d'), "timestamp": int(date.timestamp())}
            },
            "git": {"commit": commit, "commit_short": commit_short}
        }
        release_data.append(release_info)
        logging.debug(f"Initial nightly release '{release_info['name']}' created.")
        date += timedelta(days=1)

    return release_data

def create_single_release(release_type, args, existing_releases):
    """Create a single release of the specified type."""
    if release_type not in DEFAULTS['RELEASE_TYPES']:
        logging.error(f"Invalid release type: {release_type}")
        sys.exit(ERROR_CODES["parameter_missing"])

    # Check if a manual lifecycle-released-isodatetime is provided, otherwise use the current date
    if args.lifecycle_released_isodatetime:
        try:
            release_date = datetime.strptime(args.lifecycle_released_isodatetime, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.UTC)
        except ValueError:
            logging.error("Error: Invalid --date-time-release format. Use ISO format: YYYY-MM-DDTHH:MM:SS")
            sys.exit(ERROR_CODES["validation_error"])
    else:
        tz = pytz.timezone('UTC')
        release_date = tz.localize(datetime.now())

    lifecycle_released_isodate = release_date.strftime('%Y-%m-%d')
    lifecycle_released_timestamp = int(release_date.timestamp())

    if args.lifecycle_extended_isodatetime:
        try:
            extended_date = datetime.strptime(args.lifecycle_extended_isodatetime, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.UTC)
            lifecycle_extended_isodate = extended_date.strftime('%Y-%m-%d')
            lifecycle_extended_timestamp = int(extended_date.timestamp())
        except ValueError:
            logging.error("Error: Invalid --lifecycle-extended-isodatetime format. Use ISO format: YYYY-MM-DDTHH:MM:SS")
            sys.exit(ERROR_CODES["validation_error"])
    else:
        # for stable - default extended maintenance date is release date + 6 months
        if release_type == "stable":
            extended_date = release_date + relativedelta(months=6)
            lifecycle_extended_isodate = extended_date.strftime('%Y-%m-%d')
            lifecycle_extended_timestamp = int(extended_date.timestamp())
        # patch releases will use set_latest_minor_eol_to_major() to set lifecycle fields
        # other release types to not have extended lifecycle fields
        else:
            lifecycle_extended_isodate = None
            lifecycle_extended_timestamp = None

    if args.lifecycle_eol_isodatetime:
        try:
            eol_date = datetime.strptime(args.lifecycle_eol_isodatetime, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.UTC)
            lifecycle_eol_isodate = eol_date.strftime('%Y-%m-%d')
            lifecycle_eol_timestamp = int(eol_date.timestamp())
        except ValueError:
            logging.error("Error: Invalid --lifecycle-eol-isodatetime format. Use ISO format: YYYY-MM-DDTHH:MM:SS")
            sys.exit(ERROR_CODES["validation_error"])
    else:
        # for stable - default eol date is release date + 9 months
        if release_type == "stable":
            eol_date = release_date + relativedelta(months=9)
            lifecycle_eol_isodate = eol_date.strftime('%Y-%m-%d')
            lifecycle_eol_timestamp = int(eol_date.timestamp())
        # patch releases will use set_latest_minor_eol_to_major() to set lifecycle fields
        # other release types to not have extended lifecycle fields
        else:
            lifecycle_eol_isodate = None
            lifecycle_eol_timestamp = None

    # Check if a manual commit is provided, otherwise use git commit at the given time
    if args.commit:
        commit = args.commit
        if len(commit) != 40:
            logging.error("Error: Invalid commit hash. Must be 40 characters.")
            sys.exit(ERROR_CODES["validation_error"])
        commit_short = commit[:8]
    else:
        commit, commit_short = get_git_commit_at_time(lifecycle_released_isodate)

    # Check if a manual version is provided, otherwise use garden version for the date
    if args.create == 'next':
        major = 'next'
        minor = None
    elif args.version and args.create == 'stable':
        # For 'stable' releases, version should not contain '.'
        if '.' in args.version:
            logging.error("Error: Invalid --version format for stable release. Use format: major (integer without '.')")
            sys.exit(ERROR_CODES["validation_error"])
        try:
            major = int(args.version)
            minor = None
        except ValueError:
            logging.error("Error: Invalid --version format. Major version must be an integer.")
            sys.exit(ERROR_CODES["validation_error"])
    elif args.version and args.create != 'stable':
        # For other releases, version should be 'major.minor'
        try:
            major, minor = map(int, args.version.split('.'))
        except ValueError:
            logging.error("Error: Invalid --version format. Use format: major.minor")
            sys.exit(ERROR_CODES["validation_error"])
    else:
        major, minor = get_garden_version_for_date(release_type, release_date, existing_releases)

    # Create version object
    version = {'major': major, 'minor': minor}

    # First try to get flavors from flavors.yaml
    flavors = parse_flavors_commit(commit, version=version, query_s3=False, logger=logging.getLogger())

    # Only if no flavors found in flavors.yaml, try S3
    if not flavors:
        logging.info("No flavors found in flavors.yaml, checking S3 artifacts...")
        # Get artifacts data from S3 with caching
        artifacts_data = get_s3_artifacts(
            DEFAULTS['ARTIFACTS_S3_BUCKET_NAME'],
            DEFAULTS['ARTIFACTS_S3_PREFIX'],
            logger=logging.getLogger()
        )

        if artifacts_data:
            flavors = parse_flavors_commit(
                commit,
                version=version,
                query_s3=True,
                s3_objects=artifacts_data,
                logger=logging.getLogger()
            )
        else:
            logging.warning("No artifacts data available from S3")

    if not flavors:
        logging.info(f"No flavors found anywhere for version {version} (commit {commit_short})")

    # Create release data
    release = {}
    release['type'] = f"{release_type}"
    release['version'] = {}
    release['version']['major'] = major
    release['lifecycle'] = {}
    release['lifecycle']['released'] = {}
    release['lifecycle']['released']['isodate'] = lifecycle_released_isodate
    release['lifecycle']['released']['timestamp'] = lifecycle_released_timestamp

    if release_type in ['dev', 'nightly']:
        release['name'] = f"{release_type}-{major}.{minor}"
        release['version']['minor'] = minor
        release['git'] = {}
        release['git']['commit'] = commit
        release['git']['commit_short'] = commit_short
        release['flavors'] = flavors
        release['attributes'] = {}
        release['attributes']['source_repo'] = True
    elif release_type == "next":
        release['name'] = f"{release_type}"
        release['lifecycle']['extended'] = {}
        release['lifecycle']['extended']['isodate'] = lifecycle_extended_isodate
        release['lifecycle']['extended']['timestamp'] = lifecycle_extended_timestamp
        release['lifecycle']['eol'] = {}
        release['lifecycle']['eol']['isodate'] = lifecycle_eol_isodate
        release['lifecycle']['eol']['timestamp'] = lifecycle_eol_timestamp
    elif release_type == "stable":
        release['name'] = f"{release_type}-{major}"
        release['lifecycle']['extended'] = {}
        release['lifecycle']['extended']['isodate'] = lifecycle_extended_isodate
        release['lifecycle']['extended']['timestamp'] = lifecycle_extended_timestamp
        release['lifecycle']['eol'] = {}
        release['lifecycle']['eol']['isodate'] = lifecycle_eol_isodate
        release['lifecycle']['eol']['timestamp'] = lifecycle_eol_timestamp
    elif release_type == "patch":
        release['name'] = f"{release_type}-{major}.{minor}"
        release['version']['minor'] = minor
        release['lifecycle']['eol'] = {}
        release['lifecycle']['eol']['isodate'] = lifecycle_eol_isodate
        release['lifecycle']['eol']['timestamp'] = lifecycle_eol_timestamp
        release['git'] = {}
        release['git']['commit'] = commit
        release['git']['commit_short'] = commit_short
        release['github'] = {}
        release['github']['release'] = f"https://github.com/gardenlinux/gardenlinux/releases/tag/{major}.{minor}"
        release['flavors'] = flavors
        release['attributes'] = {}
        release['attributes']['source_repo'] = True

    logging.debug(f"Release '{release['name']}' created.")
    return release

def delete_release(args, next_releases, stable_releases, patch_releases, nightly_releases, dev_releases):
    """Delete a release by name from the appropriate release list."""
    release_type, major, minor = parse_release_name(args.delete)

    # Select the appropriate list based on release_type
    if release_type == 'next':
        release_list = next_releases
    elif release_type == 'stable':
        release_list = stable_releases
    elif release_type == 'patch':
        release_list = patch_releases
    elif release_type == 'nightly':
        release_list = nightly_releases
    elif release_type == 'dev':
        release_list = dev_releases
    else:
        logging.error(f"Error: Unknown release type '{release_type}' in release name.")
        sys.exit(ERROR_CODES["validation_error"])

    # Find and remove the release
    release_found = False
    for release in release_list:
        if release['name'] == args.delete:
            release_found = True
            release_list.remove(release)

    if not release_found:
        logging.error(f"Error: Release '{args.delete}' not found in the existing data.")
        sys.exit(ERROR_CODES["validation_error"])

    logging.debug(f"Release '{args.delete}' will be deleted.")

def merge_input_data(existing_releases, new_releases):
    """Merge two lists of releases, updating existing releases with new releases."""
    # Create a dictionary of releases by name from existing_releases
    releases_by_name = {release['name']: release for release in existing_releases}

    # Update or add releases from new_data
    for new_release in new_releases:
        releases_by_name[new_release['name']] = new_release

    # Return the merged list of releases
    return list(releases_by_name.values())

def set_latest_minor_eol_to_major(stable_releases, patch_releases):
    """Set the EOL of each minor version to the next higher minor version,
    and the EOL of the latest minor version to match the stable release."""
    releases_by_major = {}

    # Group releases by major version
    for release in patch_releases:
        major = release['version']['major']
        minor = release.get('version', {}).get('minor')
        releases_by_major.setdefault(major, []).append(release)

    # For each major version, sort the minor releases and set the EOL
    for major, minor_releases in releases_by_major.items():
        # Sort the minor releases by the 'minor' version number
        minor_releases.sort(key=lambda r: r.get('version', {}).get('minor', 0))

        # Find the corresponding stable release for this major version
        stable_release = next((r for r in stable_releases if r['version']['major'] == major), None)

        # Loop through all minor releases
        for i, release in enumerate(minor_releases):
            # If it's the last minor release, set its EOL to the stable release's EOL
            if i == len(minor_releases) - 1:
                if stable_release:
                    release['lifecycle']['eol'] = stable_release['lifecycle']['eol']
                else:
                    logging.warning(f"No stable release found for major version {major}, skipping EOL update.")
            else:
                # Set the EOL to the "released" date of the next minor release
                next_release = minor_releases[i + 1]
                release['lifecycle']['eol'] = next_release['lifecycle']['released']

def load_input(filename):
    """Load manual input from a file if it exists."""
    try:
        input_data = yaml.safe_load(open(filename, 'r'))

        merged_releases = input_data.get('releases', [])
        if  len(merged_releases) == 0:
            logging.error(f"Error, no releases found in JSON from file")
            sys.exit(ERROR_CODES["input_parameter_missing"])
        next_releases = [r for r in merged_releases if r['type'] == 'next']
        stable_releases = [r for r in merged_releases if r['type'] == 'stable']
        patch_releases = [r for r in merged_releases if r['type'] == 'patch']
        nightly_releases = [r for r in merged_releases if r['type'] == 'nightly']
        dev_releases = [r for r in merged_releases if r['type'] == 'dev']
        return next_releases, stable_releases, patch_releases, nightly_releases, dev_releases
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

        merged_releases = input_data.get('releases', [])
        if len(merged_releases) == 0:
            logging.error(f"Error, no releases found in JSON from stdin")
            sys.exit(ERROR_CODES["input_parameter_missing"])
        next_releases = [r for r in merged_releases if r['type'] == 'next']
        stable_releases = [r for r in merged_releases if r['type'] == 'stable']
        patch_releases = [r for r in merged_releases if r['type'] == 'patch']
        nightly_releases = [r for r in merged_releases if r['type'] == 'nightly']
        dev_releases = [r for r in merged_releases if r['type'] == 'dev']

        logging.debug(f"Parsed releases from stdin - next: {len(next_releases)}, stable: {len(stable_releases)}, patch: {len(patch_releases)}, nightly: {len(nightly_releases)}, dev: {len(dev_releases)}")

        return next_releases, stable_releases, patch_releases, nightly_releases, dev_releases
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON from stdin: {str(e)}")
        sys.exit(ERROR_CODES["validation_error"])
    except Exception as e:
        logging.error(f"Error reading input from stdin: {str(e)}")
        sys.exit(ERROR_CODES["input_parameter_error"])

def parse_release_name(release_name):
    """Parse the release name in the format 'type-major.minor' or 'type-major'."""
    valid_types = ['next', 'stable', 'patch', 'nightly', 'dev']
    type_and_version = release_name.split('-', 1)
    if len(type_and_version) != 2:
        logging.error("Error: Invalid release name format. Expected 'type-major.minor' or 'type-major'")
        sys.exit(ERROR_CODES["validation_error"])
    release_type = type_and_version[0]
    if release_type not in valid_types:
        logging.error(f"Error: Invalid release type '{release_type}'. Must be one of {', '.join(valid_types)}.")
        sys.exit(ERROR_CODES["validation_error"])
    version = type_and_version[1]
    version_parts = version.split('.')
    try:
        if len(version_parts) == 2:
            major = int(version_parts[0])
            minor = int(version_parts[1])
        elif len(version_parts) == 1:
            major = int(version_parts[0])
            minor = None
        else:
            logging.error("Error: Invalid version format in release name.")
            sys.exit(ERROR_CODES["validation_error"])
    except ValueError:
        logging.error("Error: Major and minor versions must be integers.")
        sys.exit(ERROR_CODES["validation_error"])
    return release_type, major, minor

def validate_release_data(release, errors):
    """Validate release data using the appropriate JSON schema."""
    schema = SCHEMAS.get(release['type'])
    if not schema:
        error_message = f"Unknown release type: {release['type']}"
        logging.error(error_message)
        errors.append(error_message)
        return False
    try:
        validate(instance=release, schema=schema)
        return True
    except ValidationError as e:
        # Construct the field path that caused the validation error
        field_path = '.'.join([str(p) for p in e.absolute_path])
        error_message = f"Validation error for release '{release['name']}' at '{field_path}': {e.message}"
        logging.error(error_message)
        errors.append(error_message)
        return False

def validate_all_releases(releases):
    """Validate all releases and exit if any validation errors are found."""
    errors = []
    for release in releases:
        validate_release_data(release, errors)
    if errors:
        logging.error(f"Validation failed for {len(errors)} release(s). Exiting.")
        sys.exit(ERROR_CODES["validation_error"])

def diff_releases(existing_merged_releases, merged_releases):
    """Show which releases will be created, deleted, or updated."""
    existing_releases_by_name = {r['name']: r for r in existing_merged_releases}
    new_releases_by_name = {r['name']: r for r in merged_releases}

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
                if change_type == 'values_changed':
                    for path, change in changes.items():
                        formatted_path = path.replace("root", "")
                        logging.info(f"{release_name} - {change_type}: {formatted_path} changed from '{change['old_value']}' to '{change['new_value']}'")
                elif change_type == 'type_changes':
                    for path, change in changes.items():
                        formatted_path = path.replace("root", "")
                        logging.info(f"{release_name} - {change_type}: {formatted_path} type changed from '{change['old_type']}' to '{change['new_type']}'")
                elif change_type in ['dictionary_item_added', 'dictionary_item_removed', 'iterable_item_added', 'iterable_item_removed']:
                    changes_list = sorted(list(changes))
                    for change in changes_list:
                        formatted_change = change.replace("root", "")

def save_output_file(data, filename, format="yaml"):
    """Save the data to a file in the specified format."""
    with open(filename, 'w') as file:
        if format == 'yaml':
            yaml.dump(data, file, default_flow_style=False, sort_keys=False, Dumper=NoAliasDumper)
        else:
            # Optimize JSON by removing unnecessary spaces
            json.dump(data, file, separators=(',', ':'), ensure_ascii=False)

def create_s3_bucket(args, bucket_name=None, region=None):
    """Create an S3 bucket for storing releases data."""
    if not bucket_name:
        bucket_name = args.s3_bucket_name
    if not region:
        region = args.s3_bucket_region
    try:
        s3_client = boto3.client('s3', region_name=region)
        location = {'LocationConstraint': region}
        s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration=location)
        logging.info(f"Bucket '{bucket_name}' created successfully.")
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                'TagSet': [
                    {'Key': 'sec-by-def-public-storage-exception', 'Value': 'enabled'},
                    {'Key': 'sec-by-def-objectversioning-exception', 'Value': 'enabled'},
                    {'Key': 'sec-by-def-encrypt-storage-exception', 'Value': 'enabled'}
                ]
            }
        )
        logging.info(f"Tags added to bucket '{bucket_name}'.")
        s3_client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': False,
                'IgnorePublicAcls': False,
                'BlockPublicPolicy': False,
                'RestrictPublicBuckets': False
            }
        )
        logging.info(f"Public access block settings disabled for bucket '{bucket_name}'.")
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                # Allow public read access to all objects in the bucket
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*"
                },
                # Deny non-SSL access
                {
                    "Sid": "AllowSSLRequestsOnly",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [
                        "arn:aws:s3:::gardenlinux-glrd",
                        "arn:aws:s3:::gardenlinux-glrd/*"
                    ],
                    "Condition": {
                        "Bool": {
                            "aws:SecureTransport": "false"
                        }
                    }
                }
            ]
        }
        s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(bucket_policy))
        logging.info(f"Bucket '{bucket_name}' made public and denied non-SSL access with a bucket policy.")
    except ClientError as e:
        logging.error(f"Error creating bucket: {e}")
        sys.exit(ERROR_CODES["s3_output_error"])

def upload_to_s3(file_path, bucket_name, bucket_key):
    """Upload a file to an S3 bucket."""
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_path, bucket_name, bucket_key)
        logging.debug(f"Uploaded '{file_path}' to 's3://{bucket_name}/{bucket_key}'.")
    except ClientError as e:
        logging.error(f"Error uploading {file_path} to S3: {e}")
        sys.exit(ERROR_CODES["s3_output_error"])

def download_from_s3(bucket_name, bucket_key, local_file):
    """Download a file from an S3 bucket to a local file."""
    s3_client = boto3.client('s3')
    try:
        s3_client.download_file(bucket_name, bucket_key, local_file)
        logging.debug(f"Downloaded 's3://{bucket_name}/{bucket_key}' to '{local_file}'.")
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logging.warning(f"No existing file found at 's3://{bucket_name}/{bucket_key}', starting with a fresh file.")
            return None  # No existing file, so we return None
        logging.error(f"Error downloading from S3: {e}")
        sys.exit(ERROR_CODES["s3_output_error"])

def merge_existing_s3_data(bucket_name, bucket_key, local_file, new_data):
    """Download, merge, and return the merged data using a temporary file."""
    # Use a temporary file that will be automatically deleted when closed
    with tempfile.NamedTemporaryFile(delete=True, mode='w+') as temp_file:
        # Download existing releases.json from S3 if it exists
        download_from_s3(bucket_name, bucket_key, temp_file.name)

        # Load existing data if the file was successfully downloaded
        try:
            temp_file.seek(0)  # Go to the start of the file to read the contents
            with open(temp_file.name, 'r') as f:
                file_contents = f.read()  # Read file contents as a string
                existing_data = json.loads(file_contents)  # Load JSON from string
                # Ensure we're working with a list
                existing_releases = existing_data if isinstance(existing_data, list) else existing_data.get('releases', [])
        except (json.JSONDecodeError, FileNotFoundError):
            logging.warning("Could not decode the existing JSON from S3 or no file exists. Starting with a fresh file.")
            existing_releases = []

        # Ensure new_data is treated as a list
        new_releases = new_data if isinstance(new_data, list) else new_data.get('releases', [])

        # Use the merge function to merge new and existing releases
        merged_releases = merge_input_data(existing_releases, new_releases)

        # Return the merged data as a list
        return merged_releases

def download_all_s3_files(bucket_name, bucket_prefix):
    """Download all release files from S3 bucket."""
    s3_client = get_s3_client()

    try:
        # List all objects in the bucket with the given prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        found_files = False

        logging.info(f"Looking for files in s3://{bucket_name}/{bucket_prefix}")

        for page in paginator.paginate(Bucket=bucket_name, Prefix=bucket_prefix):
            if 'Contents' in page:
                found_files = True
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.endswith('.json'):
                        local_file = os.path.basename(key)
                        download_from_s3(bucket_name, key, local_file)

        if not found_files:
            logging.warning(f"No release files found in s3://{bucket_name}/{bucket_prefix}")
            # Create empty files for each release type
            for release_type in DEFAULTS['RELEASE_TYPES']:
                filename = f"releases-{release_type}.json"
                save_output_file({'releases': []}, filename, 'json')

    except Exception as e:
        logging.error(f"Error downloading files from S3: {e}")

def upload_all_local_files(bucket_name, bucket_prefix):
    """Upload all local release files to S3."""
    s3_client = boto3.client('s3')

    try:
        # First find all matching local files
        matching_files = []
        for file in os.listdir('.'):
            for release_type in DEFAULTS['RELEASE_TYPES']:
                filename = f"releases-{release_type}.json"
                if fnmatch.fnmatch(file, filename):
                    matching_files.append(file)

        if not matching_files:
            logging.warning(f"No release files found to upload")
            return

        # Show what will be uploaded and ask for confirmation
        print("\nThe following files will be uploaded to S3:")
        for file in matching_files:
            bucket_key = f"{bucket_prefix}{file}"
            print(f"  {file} -> s3://{bucket_name}/{bucket_key}")

        response = input("\nDo you really want to upload these files to S3? [y/N] ").lower()
        if response != 'y':
            print("Upload cancelled.")
            return

        # Proceed with upload
        files_uploaded = 0
        for file in matching_files:
            bucket_key = f"{bucket_prefix}{file}"
            try:
                s3_client.upload_file(file, bucket_name, bucket_key)
                files_uploaded += 1
            except Exception as e:
                logging.error(f"Error uploading {file}: {e}")

        logging.info(f"Successfully uploaded {files_uploaded} release files")

    except Exception as e:
        logging.error(f"Error accessing S3: {e}")
        sys.exit(ERROR_CODES["s3_error"])

def handle_releases(args):
    """Handle the creation and deletion of initial or single releases."""
    if args.input_all:
        upload_all_local_files(args.s3_bucket_name, args.s3_bucket_prefix)
        return

    if args.output_all:
        download_all_s3_files(args.s3_bucket_name, args.s3_bucket_prefix)
        return

    if not args.s3_update:
        logging.warning(f"'--s3-update' was not passed, skipping S3 update.")

    create_initial_stable, create_initial_patch, create_initial_nightly = False, False, False
    next_releases, stable_releases, patch_releases, nightly_releases, dev_releases = [], [], [], [], []

    if args.create_initial_releases:
        create_initial_list = args.create_initial_releases.split(',')
        create_initial_stable = 'stable' in create_initial_list
        create_initial_patch = 'patch' in create_initial_list
        create_initial_nightly = 'nightly' in create_initial_list

    # Variables to store inputs, dev/stable/patch releases and nightly releases
    existing_next_releases = []
    existing_stable_releases = []
    existing_patch_releases = []
    existing_nightly_releases = []
    existing_dev_releases = []
    existing_merged_releases = []
    next_releases = []
    stable_releases = []
    patch_releases = []
    nightly_releases = []
    dev_releases = []
    merged_releases = []

    if not args.no_query:
        # Execute glrd command to fill stable, patch, nightly, and dev releases
        existing_next_releases = glrd_query_type(args, "next")
        existing_stable_releases = glrd_query_type(args, "stable")
        existing_patch_releases = glrd_query_type(args, "patch")
        existing_nightly_releases = glrd_query_type(args, "nightly")
        existing_merged_releases = existing_next_releases + existing_stable_releases + existing_patch_releases + existing_nightly_releases + existing_dev_releases
        next_releases.extend(existing_next_releases)
        stable_releases.extend(existing_stable_releases)
        patch_releases.extend(existing_patch_releases)
        nightly_releases.extend(existing_nightly_releases)
        dev_releases.extend(existing_dev_releases)

    if args.delete:
        if args.no_query:
            logging.error("Error: '--delete' cannot run with '--no-query'.")
            sys.exit(ERROR_CODES["parameter_missing"])
        delete_release(args, next_releases, stable_releases, patch_releases, nightly_releases, dev_releases)

    else:
        if create_initial_stable or create_initial_patch:
            github_releases = get_github_releases()
            stable_releases, patch_releases, latest_minor_versions = create_initial_releases(github_releases)

        # Add stdin input or file input data if provided (existing releases will be overwritten)
        if args.input_stdin or args.input:
            if args.input_stdin:
                input_next, input_stable, input_patch, input_nightly, input_dev = load_input_stdin()
            elif args.input:
                input_next, input_stable, input_patch, input_nightly, input_dev = load_input(args.input_file)
            next_releases = merge_input_data(next_releases, input_next)
            stable_releases = merge_input_data(stable_releases, input_stable)
            patch_releases = merge_input_data(patch_releases, input_patch)
            nightly_releases = merge_input_data(nightly_releases, input_nightly)
            dev_releases = merge_input_data(dev_releases, input_dev)

        # we define stable releases in input file, therefore this has to be run past defining inputs
        # Create initial nightly releases if requested (needs stable releases)
        if create_initial_nightly:
            nightly_releases = create_initial_nightly_releases(stable_releases)

        # Create a next release if requested
        if args.create == 'next':
            release = create_single_release('next', args, next_releases)
            next_releases = merge_input_data(next_releases, [release])

        # Create a stable release if requested
        if args.create == 'stable':
            release = create_single_release('stable', args, stable_releases)
            stable_releases = merge_input_data(stable_releases, [release])

        # Create a patch release if requested
        if args.create == 'patch':
            release = create_single_release('patch', args, patch_releases)
            patch_releases = merge_input_data(patch_releases, [release])

        # Create a nightly release if requested
        if args.create == 'nightly':
            release = create_single_release('nightly', args, nightly_releases)
            nightly_releases = merge_input_data(nightly_releases, [release])

        # Create a development release if requested
        if args.create == 'dev':
            release = create_single_release('dev', args, dev_releases)
            dev_releases = merge_input_data(dev_releases, [release])

    # Set EOL for patch releases based on latest minor versions
    set_latest_minor_eol_to_major(stable_releases, patch_releases)

    # Merge all releases into a single list
    merged_releases = next_releases + stable_releases + patch_releases + nightly_releases + dev_releases

    # Ensure timestamps for all releases
    for release in merged_releases:
        ensure_isodate_and_timestamp(release['lifecycle'])

    # Validate all releases
    validate_all_releases(merged_releases)

    # split all releases again
    next_releases = [r for r in merged_releases if r['type'] == 'next']
    stable_releases = [r for r in merged_releases if r['type'] == 'stable']
    patch_releases = [r for r in merged_releases if r['type'] == 'patch']
    nightly_releases = [r for r in merged_releases if r['type'] == 'nightly']
    dev_releases = [r for r in merged_releases if r['type'] == 'dev']

    diff_releases(existing_merged_releases, merged_releases)

    store_releases(args, merged_releases)

def store_releases(args, merged_releases):
    """Store releases in splitted or not splitted output."""
    if args.no_output_split:
        handle_output(args, args.s3_bucket_name, args.s3_bucket_prefix, merged_releases)
    else:
        handle_splitted_output(args, args.s3_bucket_name, args.s3_bucket_prefix, merged_releases)

def handle_splitted_output(args, bucket_name, bucket_prefix, releases):
    """Handle output of splitted releases (next, stable, patch, nightly, dev) to disk and S3."""
    for release_type in DEFAULTS['RELEASE_TYPES']:
        releases_filtered = [r for r in releases if r['type'] == release_type]
        if releases_filtered:
            # Always use json format for S3 storage
            s3_output_file = f"{args.output_file_prefix}-{release_type}.json"
            # Use requested format for local file
            local_output_file = f"{args.output_file_prefix}-{release_type}.{args.output_format}"

            # Save local file in requested format
            save_output_file({'releases': releases_filtered}, filename=local_output_file, format=args.output_format)

            # Handle S3 upload if the argument is provided
            if args.s3_update:
                # For S3, always use JSON format
                save_output_file({'releases': releases_filtered}, filename=s3_output_file, format='json')
                releases_filtered = merge_existing_s3_data(bucket_name, f"{bucket_prefix}{s3_output_file}", s3_output_file, releases_filtered)
                upload_to_s3(s3_output_file, bucket_name, f"{bucket_prefix}{s3_output_file}")

                # Clean up temporary JSON file if local format is different
                if args.output_format != 'json':
                    try:
                        os.remove(s3_output_file)
                    except OSError:
                        pass

def handle_output(args, bucket_name, bucket_prefix, releases):
    """Handle output of not splitted releases to disk and S3."""
    output_file = f"{args.output_file_prefix}.{args.output_format}"
    save_output_file({'releases': releases}, filename=output_file, format=args.output_format)
    logging.debug(f"Release data saved to '{output_file}'.")

    # Handle S3 upload if the argument is provided
    if args.s3_update:
        merged_releases = merge_existing_s3_data(bucket_name, f"{bucket_prefix}{os.path.basename(output_file)}", output_file, releases)
        upload_to_s3(output_file, bucket_name, f"{bucket_prefix}{os.path.basename(output_file)}")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Manage Garden Linux releases data.")

    parser.add_argument('--log-level', type=str,
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                      default='INFO', help="Set the logging level")

    parser.add_argument('--input-file', type=str, default=DEFAULTS['MANAGE_INPUT_FILE'],
                      help="The name of the input file (default: releases-input.yaml).")

    parser.add_argument('--output-format', type=str, choices=['yaml', 'json'],
                      default=DEFAULTS['MANAGE_OUTPUT_FORMAT'],
                      help="Output format: yaml or json (default: yaml).")

    parser.add_argument('--output-file-prefix', type=str,
                      default=DEFAULTS['MANAGE_OUTPUT_FILE_PREFIX'],
                      help="The prefix for output files (default: releases).")

    parser.add_argument('--s3-bucket-name', type=str,
                      default=DEFAULTS['GLRD_S3_BUCKET_NAME'],
                      help="Name of S3 bucket. Defaults to 'gardenlinux-glrd'.")

    parser.add_argument('--s3-bucket-region', type=str,
                      default=DEFAULTS['GLRD_S3_BUCKET_REGION'],
                      help="Region for S3 bucket. Defaults to 'eu-central-1'.")

    parser.add_argument('--s3-bucket-prefix', type=str,
                      default=DEFAULTS['GLRD_S3_BUCKET_PREFIX'],
                      help="Prefix for S3 bucket objects. Defaults to empty string.")

    parser.add_argument('--delete', type=str, help="Delete a release by name (format: type-major.minor). Requires --s3-update.")
    parser.add_argument('--create-initial-releases', type=str, help="Comma-separated list of initial releases to retrieve and generate: 'stable,patch,nightly'.")
    parser.add_argument('--create', type=str, help="Create a release for this type using the current timestamp and git information (choose one of: stable,patch,nightly,dev,next)'.")
    parser.add_argument('--version', type=str, help="Manually specify the version (format: major.minor).")
    parser.add_argument('--commit', type=str, help="Manually specify the git commit hash (40 characters).")
    parser.add_argument('--lifecycle-released-isodatetime', type=str, help="Manually specify the release date and time in ISO format (YYYY-MM-DDTHH:MM:SS).")
    parser.add_argument('--lifecycle-extended-isodatetime', type=str, help="Manually specify the extended maintenance date and time in ISO format (YYYY-MM-DDTHH:MM:SS).")
    parser.add_argument('--lifecycle-eol-isodatetime', type=str, help="Manually specify the EOL date and time in ISO format (YYYY-MM-DDTHH:MM:SS).")
    parser.add_argument('--no-query', action='store_true', help="Do not query and use existing releases using glrd command. Be careful, this can delete your releases.")
    parser.add_argument('--input-stdin', action='store_true', help="Process a single input from stdin (JSON data).")
    parser.add_argument('--input', action='store_true', help="Process input from --input-file.")
    parser.add_argument('--no-output-split', action='store_true', help="Do not split Output into stable+patch and nightly. Additional output-files *-nightly and *-dev will not be created.")
    parser.add_argument('--s3-create-bucket', action='store_true', help="Create an S3 bucket.")
    parser.add_argument('--s3-update', action='store_true', help="Update (merge) the generated files with S3.")
    parser.add_argument('--output-all', action='store_true',
                       help="Download and write all release files found in S3 to local disk")
    parser.add_argument('--input-all', action='store_true',
                       help="Upload all local release files to S3")
    parser.add_argument('-V', action='version', version=f'%(prog)s {get_version()}')

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
    logging.basicConfig(
        level=args.log_level,
        format='%(levelname)s: %(message)s'
    )

    handle_releases(args)

if __name__ == "__main__":
    main()
