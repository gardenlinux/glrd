"""
ReleaseType enum for GLRD releases.
"""

from enum import Enum


class ReleaseType(str, Enum):
    """Enum for release types."""

    NEXT = "next"
    MAJOR = "major"
    MINOR = "minor"
    NIGHTLY = "nightly"
    DEV = "dev"
