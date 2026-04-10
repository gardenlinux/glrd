"""
S3 operations for GLRD.

This module provides functions for interacting with AWS S3 buckets
for storing and retrieving release data.
"""

import fnmatch
import json
import logging
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from glrd.util import DEFAULTS, ERROR_CODES


def save_output_file(data: Dict[str, Any], filename: str, format: str = "yaml") -> None:
    """Save the data to a file in the specified format."""
    import yaml
    from glrd.util import NoAliasDumper

    with open(filename, "w") as file:
        if format == "yaml":
            yaml.dump(
                data,
                file,
                default_flow_style=False,
                sort_keys=False,
                Dumper=NoAliasDumper,
            )
        else:
            # Optimize JSON by removing unnecessary spaces
            json.dump(data, file, separators=(",", ":"), ensure_ascii=False)


def create_s3_bucket(args, bucket_name: Optional[str] = None, region: Optional[str] = None):
    """Create an S3 bucket for storing releases data."""
    if not bucket_name:
        bucket_name = args.s3_bucket_name
    if not region:
        region = args.s3_bucket_region
    try:
        s3_client = boto3.client("s3", region_name=region)
        location = {"LocationConstraint": region}
        s3_client.create_bucket(Bucket=bucket_name, CreateBucketConfiguration=location)
        logging.info(f"Bucket '{bucket_name}' created successfully.")
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                "TagSet": [
                    {
                        "Key": "sec-by-def-public-storage-exception",
                        "Value": "enabled",
                    },
                    {
                        "Key": "sec-by-def-objectversioning-exception",
                        "Value": "enabled",
                    },
                    {
                        "Key": "sec-by-def-encrypt-storage-exception",
                        "Value": "enabled",
                    },
                ]
            },
        )
        logging.info(f"Tags added to bucket '{bucket_name}'.")
        s3_client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        logging.info(
            f"Public access block settings disabled for bucket '{bucket_name}'."
        )
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                # Allow public read access to all objects in the bucket
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*",
                },
                # Deny non-SSL access
                {
                    "Sid": "AllowSSLRequestsOnly",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [
                        "arn:aws:s3:::gardenlinux-glrd",
                        "arn:aws:s3:::gardenlinux-glrd/*",
                    ],
                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                },
            ],
        }
        s3_client.put_bucket_policy(
            Bucket=bucket_name, Policy=json.dumps(bucket_policy)
        )
        logging.info(
            f"Bucket '{bucket_name}' made public and denied non-SSL access with a bucket policy."
        )
    except ClientError as e:
        logging.error(f"Error creating bucket: {e}")
        sys.exit(ERROR_CODES["s3_output_error"])


def upload_to_s3(file_path: str, bucket_name: str, bucket_key: str) -> None:
    """Upload a file to an S3 bucket."""
    s3_client = boto3.client("s3")
    try:
        s3_client.upload_file(file_path, bucket_name, bucket_key)
        logging.debug(f"Uploaded '{file_path}' to 's3://{bucket_name}/{bucket_key}'.")
    except ClientError as e:
        logging.error(f"Error uploading {file_path} to S3: {e}")
        sys.exit(ERROR_CODES["s3_output_error"])


def download_from_s3(bucket_name: str, bucket_key: str, local_file: str) -> None:
    """Download a file from an S3 bucket to a local file."""
    s3_client = boto3.client("s3")
    try:
        s3_client.download_file(bucket_name, bucket_key, local_file)
        logging.debug(
            f"Downloaded 's3://{bucket_name}/{bucket_key}' to '{local_file}'."
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logging.warning(
                f"No existing file found at 's3://{bucket_name}/{bucket_key}', "
                f"starting with a fresh file."
            )
            return None  # No existing file, so we return None
        logging.error(f"Error downloading from S3: {e}")
        sys.exit(ERROR_CODES["s3_output_error"])


def merge_existing_s3_data(
    bucket_name: str, bucket_key: str, local_file: str, new_data: Any
) -> List[Dict[str, Any]]:
    """Download, merge, and return the merged data using a temporary file."""
    from glrd.manage import merge_input_data

    # Use a temporary file that will be automatically deleted when closed
    with tempfile.NamedTemporaryFile(delete=True, mode="w+") as temp_file:
        # Download existing releases.json from S3 if it exists
        download_from_s3(bucket_name, bucket_key, temp_file.name)

        # Load existing data if the file was successfully downloaded
        try:
            temp_file.seek(0)  # Go to the start of the file to read the contents
            with open(temp_file.name, "r") as f:
                file_contents = f.read()  # Read file contents as a string
                existing_data = json.loads(file_contents)  # Load JSON from string
                # Ensure we're working with a list
                existing_releases = (
                    existing_data
                    if isinstance(existing_data, list)
                    else existing_data.get("releases", [])
                )
        except (json.JSONDecodeError, FileNotFoundError):
            logging.warning(
                "Could not decode the existing JSON from S3 or no file "
                "exists. Starting with a fresh file."
            )
            existing_releases = []

        # Ensure new_data is treated as a list
        new_releases = (
            new_data if isinstance(new_data, list) else new_data.get("releases", [])
        )

        # Use the merge function to merge new and existing releases
        merged_releases = merge_input_data(existing_releases, new_releases)

        # Return the merged data as a list
        return merged_releases


def download_all_s3_files(bucket_name: str, bucket_prefix: str) -> None:
    """Download all release files from S3 bucket."""
    s3_client = boto3.client("s3")

    try:
        # List all objects in the bucket with the given prefix
        paginator = s3_client.get_paginator("list_objects_v2")
        found_files = False

        logging.info(f"Looking for files in s3://{bucket_name}/{bucket_prefix}")

        for page in paginator.paginate(Bucket=bucket_name, Prefix=bucket_prefix):
            if "Contents" in page:
                found_files = True
                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.endswith(".json"):
                        local_file = os.path.basename(key)
                        download_from_s3(bucket_name, key, local_file)

        if not found_files:
            logging.warning(
                f"No release files found in s3://{bucket_name}/{bucket_prefix}"
            )
            # Create empty files for each release type
            for release_type in DEFAULTS["RELEASE_TYPES"]:
                filename = f"releases-{release_type}.json"
                save_output_file({"releases": []}, filename, "json")

    except Exception as e:
        logging.error(f"Error downloading files from S3: {e}")


def upload_all_local_files(bucket_name: str, bucket_prefix: str) -> None:
    """Upload all local release files to S3."""
    s3_client = boto3.client("s3")

    try:
        # First find all matching local files
        matching_files = []
        for file in os.listdir("."):
            for release_type in DEFAULTS["RELEASE_TYPES"]:
                filename = f"releases-{release_type}.json"
                if fnmatch.fnmatch(file, filename):
                    matching_files.append(file)

        if not matching_files:
            logging.warning("No release files found to upload")
            return

        # Show what will be uploaded and ask for confirmation
        print("\nThe following files will be uploaded to S3:")
        for file in matching_files:
            bucket_key = f"{bucket_prefix}{file}"
            print(f"  {file} -> s3://{bucket_name}/{bucket_key}")

        response = input(
            "\nDo you really want to upload these files to S3? [y/N] "
        ).lower()
        if response != "y":
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
