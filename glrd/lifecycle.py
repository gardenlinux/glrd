"""
Lifecycle dataclasses for GLRD releases.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .util import (
    get_current_timestamp,
    isodate_to_timestamp,
    timestamp_to_isodate,
)


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
        ts = (
            current_timestamp
            if current_timestamp is not None
            else get_current_timestamp()
        )
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
        ts = (
            current_timestamp
            if current_timestamp is not None
            else get_current_timestamp()
        )
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
