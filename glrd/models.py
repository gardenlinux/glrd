"""
Typed domain models for GLRD releases.

This module provides dataclasses for all domain objects, replacing the previous
dict-based approach with immutable, typed objects that are self-documenting
and easier to test.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from glrd.util import (
    V2_SCHEMA_THRESHOLD,
    isodate_to_timestamp,
    timestamp_to_isodate,
    get_current_timestamp,
)


class ReleaseType(str, Enum):
    """Enum for release types."""

    NEXT = "next"
    MAJOR = "major"
    MINOR = "minor"
    NIGHTLY = "nightly"
    DEV = "dev"


@dataclass(frozen=True)
class Version:
    """
    Immutable version object representing a release version.

    Handles both v1 schema (< 2017) and v2 schema (>= 2017) versions,
    centralizing the version threshold logic.
    """

    major: int
    minor: Optional[int] = None
    patch: Optional[int] = None

    @property
    def uses_patch(self) -> bool:
        """Check if this version requires the patch field (v2 schema)."""
        return self.major >= V2_SCHEMA_THRESHOLD

    def to_string(self, release_type: ReleaseType) -> str:
        """
        Return a version string appropriate for the release type.

        Args:
            release_type: The type of release (affects string format)

        Returns:
            Formatted version string
        """
        if release_type in (ReleaseType.NEXT, ReleaseType.MAJOR):
            return str(self.major)
        if self.uses_patch:
            return f"{self.major}.{self.minor}.{self.patch}"
        return f"{self.major}.{self.minor}"

    @classmethod
    def from_string(cls, version_string: str) -> "Version":
        """
        Parse a version string into a Version object.

        Args:
            version_string: Version string like "2017", "2017.0", or "2017.0.1"

        Returns:
            Version object
        """
        parts = version_string.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else None
        patch = int(parts[2]) if len(parts) > 2 else None
        return cls(major, minor, patch)

    def to_sort_key(self) -> Tuple[int, int, int]:
        """
        Get a sortable tuple for version comparison.

        For v1 schema versions (< 2017), patch is forced to 0 for comparison.

        Returns:
            Tuple of (major, minor, patch) suitable for sorting
        """
        if self.uses_patch:
            return (self.major, self.minor or 0, self.patch or 0)
        return (self.major, self.minor or 0, 0)

    def __lt__(self, other: "Version") -> bool:
        """Compare versions."""
        return self.to_sort_key() < other.to_sort_key()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.to_sort_key() == other.to_sort_key()

    def __hash__(self) -> int:
        return hash(self.to_sort_key())


@dataclass
class LifecyclePhase:
    """
    A single lifecycle phase (released, extended, or eol).
    """

    isodate: Optional[str] = None  # "YYYY-MM-DD"
    timestamp: Optional[int] = None  # Unix epoch

    @classmethod
    def from_isodate(cls, isodate: str) -> "LifecyclePhase":
        """Create a LifecyclePhase from an isodate string."""
        ts = isodate_to_timestamp(isodate)
        return cls(isodate=isodate, timestamp=ts)

    @classmethod
    def from_timestamp(cls, timestamp: int) -> "LifecyclePhase":
        """Create a LifecyclePhase from a timestamp."""
        iso = timestamp_to_isodate(timestamp)
        return cls(isodate=iso, timestamp=timestamp)

    def ensure_complete(self) -> None:
        """
        Ensure both isodate and timestamp are populated.

        Mutates in-place: fills in missing timestamp from isodate or vice versa.
        """
        if self.isodate and not self.timestamp:
            self.timestamp = isodate_to_timestamp(self.isodate)
        elif self.timestamp and not self.isodate:
            self.isodate = timestamp_to_isodate(self.timestamp)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {"isodate": self.isodate, "timestamp": self.timestamp}


@dataclass
class Lifecycle:
    """
    Lifecycle information for a release (released, extended, eol dates).
    """

    released: LifecyclePhase
    extended: Optional[LifecyclePhase] = None
    eol: Optional[LifecyclePhase] = None

    def is_active(self, current_timestamp: Optional[int] = None) -> bool:
        """
        Check if the release is still active based on its EOL timestamp.

        Args:
            current_timestamp: Optional timestamp to check against.
                              If None, uses get_current_timestamp().

        Returns:
            True if the release is active (EOL in the future)
        """
        ts = current_timestamp if current_timestamp is not None else get_current_timestamp()
        if self.eol and self.eol.timestamp:
            return self.eol.timestamp > ts
        return False

    def is_archived(self, current_timestamp: Optional[int] = None) -> bool:
        """
        Check if the release is archived based on its EOL timestamp.

        Args:
            current_timestamp: Optional timestamp to check against.
                              If None, uses get_current_timestamp().

        Returns:
            True if the release is archived (EOL in the past)
        """
        ts = current_timestamp if current_timestamp is not None else get_current_timestamp()
        if self.eol and self.eol.timestamp:
            return self.eol.timestamp < ts
        return False

    def ensure_complete(self) -> None:
        """
        Ensure timestamps/isodates are complete for all phases.

        Mutates in-place.
        """
        self.released.ensure_complete()
        if self.extended:
            self.extended.ensure_complete()
        if self.eol:
            self.eol.ensure_complete()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {"released": self.released.to_dict()}
        if self.extended:
            result["extended"] = self.extended.to_dict()
        if self.eol:
            result["eol"] = self.eol.to_dict()
        return result


@dataclass(frozen=True)
class GitInfo:
    """
    Git commit information for a release.
    """

    commit: str  # 40-char SHA
    commit_short: str  # 8-char prefix

    @classmethod
    def from_commit(cls, commit: str) -> "GitInfo":
        """Create GitInfo from a full commit SHA."""
        return cls(commit=commit, commit_short=commit[:8])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"commit": self.commit, "commit_short": self.commit_short}


@dataclass
class Release:
    """
    A complete release object representing a Garden Linux release.

    This is the main domain object, replacing the previous dict-based approach.
    """

    name: str  # e.g., "minor-2017.0.0"
    type: ReleaseType
    version: Version
    lifecycle: Lifecycle
    git: Optional[GitInfo] = None
    github: Optional[Dict[str, str]] = None  # {"release": "url"}
    flavors: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None  # {"source_repo": bool}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON/YAML serialization.

        Returns:
            Dictionary representation suitable for storage
        """
        result: Dict[str, Any] = {
            "name": self.name,
            "type": self.type.value,
            "version": {},
            "lifecycle": self.lifecycle.to_dict(),
        }

        # Version
        result["version"]["major"] = self.version.major
        if self.version.minor is not None:
            result["version"]["minor"] = self.version.minor
        if self.version.patch is not None and self.version.uses_patch:
            result["version"]["patch"] = self.version.patch

        # Git info
        if self.git:
            result["git"] = self.git.to_dict()

        # GitHub info
        if self.github:
            result["github"] = self.github

        # Flavors
        if self.flavors:
            result["flavors"] = self.flavors

        # Attributes
        if self.attributes:
            result["attributes"] = self.attributes

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Release":
        """
        Create a Release from a dictionary (deserialization).

        Handles both v1 and v2 dict shapes.

        Args:
            data: Dictionary with release data

        Returns:
            Release object
        """
        version_data = data["version"]
        version = Version(
            version_data["major"],
            version_data.get("minor"),
            version_data.get("patch"),
        )

        lifecycle_data = data["lifecycle"]
        lifecycle = Lifecycle(
            released=LifecyclePhase(**lifecycle_data["released"]),
            extended=(
                LifecyclePhase(**lifecycle_data["extended"])
                if "extended" in lifecycle_data
                else None
            ),
            eol=(
                LifecyclePhase(**lifecycle_data["eol"])
                if "eol" in lifecycle_data
                else None
            ),
        )

        git = None
        if "git" in data:
            git = GitInfo(
                data["git"]["commit"],
                data["git"]["commit_short"],
            )

        return cls(
            name=data["name"],
            type=ReleaseType(data["type"]),
            version=version,
            lifecycle=lifecycle,
            git=git,
            github=data.get("github"),
            flavors=data.get("flavors"),
            attributes=data.get("attributes"),
        )

    def is_active(self) -> bool:
        """Check if the release is active."""
        return self.lifecycle.is_active()

    def is_archived(self) -> bool:
        """Check if the release is archived."""
        return self.lifecycle.is_archived()


class ReleaseCollection:
    """
    A collection of releases with query and transformation methods.

    Provides a fluent interface for filtering, sorting, and transforming
    releases.
    """

    def __init__(self, releases: List[Release]):
        self._releases = releases

    def __iter__(self):
        return iter(self._releases)

    def __len__(self):
        return len(self._releases)

    def by_type(self, release_type: ReleaseType) -> "ReleaseCollection":
        """Filter releases by type."""
        return ReleaseCollection([r for r in self._releases if r.type == release_type])

    def by_types(self, release_types: List[ReleaseType]) -> "ReleaseCollection":
        """Filter releases by multiple types."""
        return ReleaseCollection([r for r in self._releases if r.type in release_types])

    def filter_active(self) -> "ReleaseCollection":
        """Filter to only active releases."""
        return ReleaseCollection([r for r in self._releases if r.is_active()])

    def filter_archived(self) -> "ReleaseCollection":
        """Filter to only archived releases."""
        return ReleaseCollection([r for r in self._releases if r.is_archived()])

    def filter_version(self, major: int, minor: Optional[int] = None, patch: Optional[int] = None) -> "ReleaseCollection":
        """Filter releases by version components."""
        return ReleaseCollection([
            r for r in self._releases
            if r.version.major == major
            and (minor is None or r.version.minor == minor)
            and (patch is None or r.version.patch == patch)
        ])

    def latest(self) -> Optional[Release]:
        """Find the latest release by version."""
        if not self._releases:
            return None
        return max(self._releases, key=lambda r: r.version.to_sort_key())

    def sorted(self) -> List[Release]:
        """Return releases sorted by version."""
        return sorted(self._releases, key=lambda r: r.version.to_sort_key())

    def to_list(self) -> List[Dict[str, Any]]:
        """Convert all releases to dictionaries."""
        return [r.to_dict() for r in self._releases]

    def to_dict_list(self) -> List[Release]:
        """Return list of Release objects."""
        return self._releases


def parse_release_name(release_name: str) -> Tuple[ReleaseType, int, Optional[int], Optional[int]]:
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
