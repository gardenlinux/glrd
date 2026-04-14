"""
Validation functions for GLRD releases.

This module provides functions for validating release data against
JSON schemas and checking version format requirements.
"""

import logging
import sys
from typing import Dict, List, Optional, Tuple

from jsonschema import ValidationError, validate

from glrd.schema import SCHEMA_V1, SCHEMA_V2
from glrd.util import ERROR_CODES, V2_SCHEMA_THRESHOLD


def validate_input_version_format(
    version: str, release_type: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate that the input version format matches schema requirements.

    Args:
        version: Version string from user input (e.g., "2017.0.1")
        release_type: Type of release (major, minor, etc.)

    Returns:
        Tuple of (is_valid, error_message)
    """
    version_parts = version.split(".")

    if release_type in ["major", "next"]:
        # major and next don't use major.minor.patch
        return True, None

    if len(version_parts) == 2:
        major = int(version_parts[0])
        # Check if this version requires v2 schema (with patch field)
        if major >= V2_SCHEMA_THRESHOLD:
            return (
                False,
                f"Version {'.'.join(version_parts)} requires v2 schema "
                f"but missing patch version. Use format: major.minor.patch",
            )
        return True, None
    elif len(version_parts) == 3:
        major = int(version_parts[0])
        # Check if this version should use v1 schema (without patch field)
        if major < V2_SCHEMA_THRESHOLD:
            return (
                False,
                f"Version {'.'.join(version_parts)} uses v1 schema but "
                f"includes patch version. Use format: major.minor",
            )
        return True, None
    else:
        return (
            False,
            "Invalid version format. Expected major.minor or major.minor.patch",
        )


def get_schema_for_release(release: Dict) -> Optional[Dict]:
    """
    Get the appropriate schema version for a release based on its version number.

    Args:
        release: Release dictionary containing type and version information

    Returns:
        Schema dictionary appropriate for the release version, or None
    """
    release_type = release.get("type")
    version = release.get("version", {})

    # For major and next releases, always use v2 schema
    # (they don't have major.minor.patch version numbers >= 2017)
    if release_type in ["major", "next"]:
        return SCHEMA_V2[release_type]

    # For minor, nightly, and dev releases, determine schema version based
    # on version number
    if release_type in ["minor", "nightly", "dev"]:
        major = version.get("major", 0)

        # Use v2 schema (with patch field) for versions >= 2017.0.0
        if major >= V2_SCHEMA_THRESHOLD:
            return SCHEMA_V2[release_type]
        else:
            return SCHEMA_V1[release_type]

    return None


def validate_release_data(release: Dict, errors: List[str]) -> bool:
    """
    Validate release data using the appropriate JSON schema.

    Args:
        release: Release dictionary to validate
        errors: List to append error messages to (mutated in-place)

    Returns:
        True if valid, False otherwise
    """
    schema = get_schema_for_release(release)
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
        field_path = ".".join([str(p) for p in e.absolute_path])
        error_message = (
            f"Validation error for release '{release['name']}' "
            f"at '{field_path}': {e.message}"
        )
        logging.error(error_message)
        errors.append(error_message)
        return False


def validate_all_releases(releases: List[Dict]) -> None:
    """
    Validate all releases and exit if any validation errors are found.

    Args:
        releases: List of release dictionaries to validate
    """
    errors = []
    for release in releases:
        validate_release_data(release, errors)
    if errors:
        logging.error(f"Validation failed for {len(errors)} release(s). Exiting.")
        sys.exit(ERROR_CODES["validation_error"])
