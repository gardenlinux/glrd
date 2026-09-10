"""
Release dataclass for GLRD releases.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .git_info import GitInfo
from .lifecycle import Lifecycle, LifecyclePhase
from .release_type import ReleaseType
from .version import Version


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

        # Flavors: preserved when set (including an empty list), so the
        # serialized shape matches what glrd-manage produces on creation.
        if self.flavors is not None:
            result["flavors"] = self.flavors

        # Attributes
        if self.attributes is not None:
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

    @staticmethod
    def default_name(release_type: ReleaseType, version: Version) -> str:
        """
        Generate the canonical release name for a type and version.

        Examples: ``next``, ``major-27``, ``minor-2017.0.0``, ``nightly-1990.0``.
        This is the single source of truth for release-name construction.
        """
        if release_type == ReleaseType.NEXT:
            return "next"
        if release_type == ReleaseType.MAJOR:
            return f"major-{version.major}"
        return f"{release_type.value}-{version.to_string(release_type)}"

    @staticmethod
    def github_release_url(version: Version, release_type: ReleaseType) -> str:
        """Build the GitHub release URL for a minor release."""
        return (
            "https://github.com/gardenlinux/gardenlinux/releases/tag/"
            f"{version.to_string(release_type)}"
        )
