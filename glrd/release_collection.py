"""
ReleaseCollection class for GLRD releases.
"""

from typing import Any, Dict, List, Optional

from glrd.release_model import Release
from glrd.release_type import ReleaseType


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

    def filter_version(
        self, major: int, minor: Optional[int] = None, patch: Optional[int] = None
    ) -> "ReleaseCollection":
        """
        Filter releases by version components.

        Missing minor/patch on a release are treated as 0 when a filter value
        is supplied, matching the query tool's historical semantics.
        """
        return ReleaseCollection(
            [
                r
                for r in self._releases
                if r.version.major == major
                and (minor is None or (r.version.minor or 0) == minor)
                and (patch is None or (r.version.patch or 0) == patch)
            ]
        )

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
