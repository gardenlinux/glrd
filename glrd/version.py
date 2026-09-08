"""
Version dataclass for GLRD releases.
"""

from dataclasses import dataclass
from typing import Any, Optional, Tuple

from glrd.release_type import ReleaseType
from glrd.util import V2_SCHEMA_THRESHOLD


@dataclass(frozen=True)
class Version:
    """
    Immutable version object representing a release version.

    Handles both v1 schema (< 2017) and v2 schema (>= 2017) versions,
    centralizing the version threshold logic. The ``major`` component may be
    the string ``"next"`` for the special ``next`` release; such versions never
    use a patch field and always sort after all numeric versions.
    """

    major: Any  # int, or the string "next"
    minor: Optional[int] = None
    patch: Optional[int] = None

    @property
    def is_next(self) -> bool:
        """True if this is the symbolic 'next' version."""
        return not isinstance(self.major, int)

    @property
    def uses_patch(self) -> bool:
        """Check if this version requires the patch field (v2 schema)."""
        if self.is_next:
            return False
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
            version_string: Version string like "2017", "2017.0", "2017.0.1",
                or "next".

        Returns:
            Version object
        """
        if version_string == "next":
            return cls("next")
        parts = version_string.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else None
        patch = int(parts[2]) if len(parts) > 2 else None
        return cls(major, minor, patch)

    def to_sort_key(self) -> Tuple[float, float, float]:
        """
        Get a sortable tuple for version comparison.

        For v1 schema versions (< 2017), patch is forced to 0 for comparison.
        The symbolic 'next' version sorts after all numeric versions. A missing
        minor or patch is treated as 0, so e.g. major ``2020`` and minor
        ``2020.0`` sort adjacently (this is also why equality/hashing use the
        same normalized key).

        Returns:
            Tuple of (major, minor, patch) suitable for sorting
        """
        if self.is_next:
            return (float("inf"), float("inf"), float("inf"))
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
