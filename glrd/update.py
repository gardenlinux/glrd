import argparse
import json
import logging
import os
import sys

import boto3

from glrd.manage import download_all_s3_files, upload_all_local_files
from glrd.util import DEFAULTS, ERROR_CODES, get_version

from python_gardenlinux_lib.flavors.parse_flavors import parse_flavors_commit
from python_gardenlinux_lib.s3.s3 import get_s3_artifacts

logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Update existing releases with fields that were added to the schema."
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level",
    )

    parser.add_argument(
        "--s3-download",
        action="store_true",
        help="Download files from S3 first",
    )

    parser.add_argument(
        "--s3-update",
        action="store_true",
        help="Upload files to S3 after processing",
    )

    parser.add_argument(
        "--s3-bucket-name",
        type=str,
        default=DEFAULTS["GLRD_S3_BUCKET_NAME"],
        help="Name of S3 bucket for artifacts",
    )

    parser.add_argument(
        "--s3-bucket-region",
        type=str,
        default=DEFAULTS["GLRD_S3_BUCKET_REGION"],
        help="Region for S3 bucket",
    )

    parser.add_argument(
        "--s3-bucket-prefix",
        type=str,
        default=DEFAULTS["GLRD_S3_BUCKET_PREFIX"],
        help="Prefix for S3 bucket objects",
    )

    parser.add_argument(
        "--version",
        type=str,
        help="Only process releases with this version (format: major.minor.patch)",
    )

    parser.add_argument(
        "--fix-patch-versions",
        action="store_true",
        default=True,
        help="Fix missing patch version fields in release names and version "
        "objects (default: True)",
    )

    parser.add_argument(
        "--no-fix-patch-versions",
        action="store_true",
        help="Disable fixing of missing patch version fields",
    )

    parser.add_argument("-V", action="version", version=f"%(prog)s {get_version()}")

    args = parser.parse_args()

    # Convert log level to uppercase if provided in lowercase
    args.log_level = args.log_level.upper()

    # Parse version if provided
    if args.version:
        try:
            parts = args.version.split(".")
            if len(parts) != 3:
                raise ValueError("Version must be in format major.minor.patch")
            args.version_major = int(parts[0])
            args.version_minor = int(parts[1])
            args.version_patch = int(parts[2])
        except (ValueError, IndexError) as e:
            logging.error(f"Invalid version format: {e}")
            sys.exit(ERROR_CODES["parameter_missing"])

    # Handle patch version fixing flags
    if args.no_fix_patch_versions:
        args.fix_patch_versions = False

    return args


def load_releases_from_file(json_file):
    """Load releases from a JSON file."""
    try:
        with open(json_file, "r") as file:
            data = json.load(file)
            return data.get("releases", [])
    except Exception as e:
        logging.error(f"Error loading releases from {json_file}: {e}")
        sys.exit(ERROR_CODES["file_not_found"])


def save_releases(releases, json_file):
    """Save releases to a JSON file."""
    try:
        with open(json_file, "w") as file:
            json.dump(
                {"releases": releases},
                file,
                separators=(",", ":"),
                ensure_ascii=False,
            )
    except Exception as e:
        logging.error(f"Error saving releases to {json_file}: {e}")
        sys.exit(ERROR_CODES["output_error"])


def fetch_s3_bucket_contents(args):
    """Fetch all objects from S3 bucket once and return them."""
    try:
        s3_client = boto3.client("s3", region_name=args.s3_bucket_region)
        bucket_name = args.s3_bucket_name
        prefix = args.s3_bucket_prefix

        logging.info(f"Fetching objects from s3://{bucket_name}/{prefix}")

        paginator = s3_client.get_paginator("list_objects_v2")
        all_objects = []

        for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
            if "Contents" in page:
                all_objects.extend(page["Contents"])

        logging.info(f"Found {len(all_objects)} objects")
        return all_objects

    except Exception as e:
        logging.error(f"Error fetching S3 bucket contents: {e}")
        sys.exit(ERROR_CODES["s3_error"])


def update_flavors(release):
    """Update flavors for a release."""
    if "git" not in release:
        logger.debug(f"Skipping flavor update for {release['name']} - no git info")
        return release

    commit = release["git"]["commit"]
    version = release["version"]

    # First try flavors.yaml
    flavors = parse_flavors_commit(
        commit, version=version, query_s3=False, logger=logger
    )

    # If no flavors found, try S3
    if not flavors:
        logger.info(
            f"No flavors found in flavors.yaml for {release['name']}, checking S3..."
        )
        artifacts_data = get_s3_artifacts(
            DEFAULTS["ARTIFACTS_S3_BUCKET_NAME"],
            DEFAULTS["ARTIFACTS_S3_PREFIX"],
            logger=logger,
        )

        if artifacts_data:
            flavors = parse_flavors_commit(
                commit,
                version=version,
                query_s3=True,
                s3_objects=artifacts_data,
                logger=logger,
            )
        else:
            logger.warning(f"No artifacts data available from S3 for {release['name']}")

    if flavors:
        release["flavors"] = flavors
        logger.info(
            f"Updated flavors for {release['name']}: found {len(flavors)} flavors"
        )
    else:
        logger.warning(f"No flavors found for {release['name']}")

    return release


def update_source_repo_attribute(releases):
    """Update source repo attribute for releases."""
    for release in releases:
        major = int(release["version"].get("major", 0))
        minor = int(release["version"].get("minor", 0))
        patch = int(release["version"].get("patch", 0))

        if (major > 1592) or (major == 1592 and minor >= 4 and patch >= 0):
            release["attributes"] = {"source_repo": True}
        else:
            release["attributes"] = {"source_repo": False}


def fix_patch_version_fields(releases):
    """Fix missing patch version fields in releases based on versioned schemas."""
    fixed_count = 0

    for release in releases:
        release_type = release.get("type")
        version = release.get("version", {})

        # Only fix minor, nightly, and dev releases
        if release_type in ["minor", "nightly", "dev"]:
            major = version.get("major")
            minor = version.get("minor")
            patch = version.get("patch")

            # Only add patch field for versions >= 2000.0.0 (v2 schema)
            if major is not None and major >= 2000:
                # If patch is missing, set it to 0
                if patch is None:
                    version["patch"] = 0
                    patch = 0
                    fixed_count += 1

                # Fix the name if it's missing the patch version
                current_name = release.get("name", "")
                expected_name = f"{release_type}-{major}.{minor}.{patch}"

                if current_name != expected_name:
                    release["name"] = expected_name
                    fixed_count += 1
                    logging.debug(f"Fixed name: {current_name} -> {expected_name}")
            else:
                # For versions < 2000.0.0 (v1 schema), ensure patch field is NOT present
                if "patch" in version:
                    del version["patch"]
                    fixed_count += 1
                    logging.debug(
                        f"Removed patch field for v1 schema release: {release.get('name', '')}"
                    )

                # Ensure name doesn't have patch version for v1 schema
                current_name = release.get("name", "")
                expected_name = f"{release_type}-{major}.{minor}"

                if current_name != expected_name:
                    release["name"] = expected_name
                    fixed_count += 1
                    logging.debug(
                        f"Fixed name for v1 schema: {current_name} -> {expected_name}"
                    )

    return fixed_count


def process_releases(args):
    """Process all release files."""
    # Download files from S3 if requested
    if args.s3_download:
        try:
            logging.info(f"Downloading files from S3 bucket {args.s3_bucket_name}")
            download_all_s3_files(
                bucket_name=args.s3_bucket_name,
                bucket_prefix=args.s3_bucket_prefix,
            )
            logging.info("Successfully downloaded files from S3")
        except Exception as e:
            logging.error(f"Error downloading files from S3: {e}")
            sys.exit(ERROR_CODES["s3_error"])

    # Get artifacts from artifacts bucket
    logging.info(
        f"Fetching artifacts data from S3 bucket {DEFAULTS['ARTIFACTS_S3_BUCKET_NAME']}"
    )
    artifacts_data = get_s3_artifacts(
        DEFAULTS["ARTIFACTS_S3_BUCKET_NAME"], DEFAULTS["ARTIFACTS_S3_PREFIX"]
    )

    if not artifacts_data or not artifacts_data.get("artifacts"):
        logging.error("Failed to fetch artifacts data from S3")
        return
    logging.info(
        f"Successfully fetched {len(artifacts_data.get('artifacts', []))} artifacts"
    )

    # Get list of JSON files to process
    json_files = [
        f for f in os.listdir(".") if f.endswith(".json") and f.startswith("releases-")
    ]
    if not json_files:
        logging.warning("No JSON files found to process")
        return
    logging.info(
        f"Found {len(json_files)} JSON files to process: {', '.join(json_files)}"
    )

    # Process each file
    successful_files = []
    total_releases_processed = 0
    total_releases_updated = 0
    total_patch_fixes = 0

    for json_file in json_files:
        try:
            logging.info(f"\nProcessing file: {json_file}")
            with open(json_file, "r") as f:
                releases = json.load(f)
                if isinstance(releases, dict) and "releases" in releases:
                    releases = releases["releases"]
                logging.info(f"Found {len(releases)} releases in {json_file}")

            # Fix patch version fields first (if enabled)
            patch_fixes = 0
            if args.fix_patch_versions:
                patch_fixes = fix_patch_version_fields(releases)
                if patch_fixes > 0:
                    logging.info(
                        f"Fixed {patch_fixes} patch version fields in {json_file}"
                    )
                    total_patch_fixes += patch_fixes

            # Process each release
            modified = patch_fixes > 0  # File is modified if patch versions were fixed
            releases_processed = 0
            releases_updated = 0

            for release in releases:
                releases_processed += 1
                total_releases_processed += 1

                release_name = release.get("name", "unknown")
                release_type = release.get("type", "unknown")

                # Only process minor, nightly, and dev releases
                if release_type not in ["minor", "nightly", "dev"]:
                    logging.debug(
                        f"Skipping {release_type} release {release_name}: "
                        f"not a minor/nightly/dev release"
                    )
                    continue

                version = release.get("version", {})
                version_info = (
                    f"{version.get('major', '?')}."
                    f"{version.get('minor', '?')}."
                    f"{version.get('patch', '?')}"
                )

                # Skip if version filter is active and doesn't match
                if args.version:
                    if (
                        version.get("major") != args.version_major
                        or version.get("minor") != args.version_minor
                        or version.get("patch") != args.version_patch
                    ):
                        logging.debug(
                            f"Skipping {release_type} release {release_name}: "
                            f"version {version_info} doesn't match filter {args.version}"
                        )
                        continue

                if "git" not in release:
                    logging.debug(
                        f"Skipping {release_type} release {release_name}: no git information"
                    )
                    continue

                commit = release["git"].get("commit")
                if not commit:
                    logging.debug(
                        f"Skipping {release_type} release {release_name}: no commit hash"
                    )
                    continue

                logging.info(
                    f"Processing {release_type} release {release_name} "
                    f"(version {version_info}, commit {commit[:8]})"
                )

                # Update source repo attribute
                update_source_repo_attribute([release])

                # Get flavors for this commit using artifacts data
                flavors = parse_flavors_commit(
                    commit,
                    version=version,
                    query_s3=True,
                    s3_objects=artifacts_data,
                )
                if flavors:
                    release["flavors"] = flavors
                    modified = True
                    releases_updated += 1
                    total_releases_updated += 1
                    logging.info(
                        f"Added {len(flavors)} flavors for {release_name} "
                        f"(version {version_info}, commit {commit[:8]})"
                    )
                else:
                    logging.info(
                        f"No flavors found for {release_name} "
                        f"(version {version_info}, commit {commit[:8]})"
                    )

            # Save if modified
            if modified:
                with open(json_file, "w") as f:
                    json.dump({"releases": releases}, f, indent=2)
                successful_files.append(json_file)
                logging.info(
                    f"Updated {json_file} "
                    f"({releases_updated}/{releases_processed} releases updated)"
                )
            else:
                logging.info(
                    f"No updates needed for {json_file} ({releases_processed} releases checked)"
                )

        except Exception as e:
            logging.error(f"Error processing {json_file}: {e}", exc_info=True)
            sys.exit(ERROR_CODES["input_error"])

    # Upload to S3 if requested and files were modified
    if args.s3_update and successful_files:
        try:
            logging.info(f"Uploading {len(successful_files)} modified files to S3")
            upload_all_local_files(args.s3_bucket_name, args.s3_bucket_prefix)
            logging.info("Successfully uploaded files to S3")
        except Exception as e:
            logging.error(f"Error uploading files to S3: {e}")
            sys.exit(ERROR_CODES["s3_error"])

    # Log summary
    logging.info("\nUpdate Summary:")
    logging.info(
        f"Files processed successfully: {len(successful_files)} out of {len(json_files)}"
    )
    logging.info(f"Total releases processed: {total_releases_processed}")
    logging.info(f"Total releases updated with flavors: {total_releases_updated}")
    logging.info(f"Total patch version fields fixed: {total_patch_fixes}")


def main():
    args = parse_arguments()

    # Configure logging with the already uppercase level
    logging.basicConfig(level=args.log_level, format="%(levelname)s: %(message)s")
    process_releases(args)


if __name__ == "__main__":
    main()
