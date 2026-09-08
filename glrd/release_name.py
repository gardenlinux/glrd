"""
parse_release_name function for GLRD releases.
"""

from typing import Optional, Tuple

from glrd.release_type import ReleaseType


def parse_release_name(
    release_name: str,
) -> Tuple[ReleaseType, int, Optional[int], Optional[int]]:
    """
    Parse a release name in the format 'type-major.minor.patch' or similar.

    Args:
        release_name: Release name like "minor-2017.0.0" or "major-1234"

    Returns:
        Tuple of (release_type, major, minor, patch)

    Raises:
        ValueError: If the release name format is invalid
    """
    valid_types = [rt.value for rt in ReleaseType]
    type_and_version = release_name.split("-", 1)

    if len(type_and_version) != 2:
        raise ValueError(
            "Invalid release name format. Expected "
            "'type-major.minor.patch' or 'type-major.minor' or 'type-major'"
        )

    release_type_str = type_and_version[0]
    if release_type_str not in valid_types:
        raise ValueError(
            f"Invalid release type '{release_type_str}'. "
            f"Must be one of {', '.join(valid_types)}."
        )

    release_type = ReleaseType(release_type_str)
    version = type_and_version[1]
    version_parts = version.split(".")

    try:
        if len(version_parts) == 3:
            major = int(version_parts[0])
            minor = int(version_parts[1])
            patch = int(version_parts[2])
        elif len(version_parts) == 2:
            major = int(version_parts[0])
            minor = int(version_parts[1])
            patch = None
        elif len(version_parts) == 1:
            major = int(version_parts[0])
            minor = None
            patch = None
        else:
            raise ValueError("Invalid version format in release name.")
    except ValueError:
        raise ValueError("Major, minor and patch versions must be integers.")

    return release_type, major, minor, patch
