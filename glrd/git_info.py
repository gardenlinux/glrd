"""
GitInfo dataclass for GLRD releases.
"""

from dataclasses import dataclass
from typing import Any, Dict


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
