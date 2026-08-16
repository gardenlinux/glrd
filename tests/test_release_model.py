"""
Unit tests for the release domain model (glrd/release.py).

The release model is the single source of truth for parsing, version handling,
name generation, and serialization. These tests are pure and fully offline.
"""

import pytest

from glrd.release import (
    GitInfo,
    Lifecycle,
    LifecyclePhase,
    Release,
    ReleaseCollection,
    ReleaseType,
    Version,
    parse_release_name,
)


@pytest.mark.unit
class TestVersion:
    """Tests for the Version value object."""

    def test_uses_patch_threshold(self):
        assert Version(2017, 0, 0).uses_patch is True
        assert Version(2016, 9).uses_patch is False
        # Exactly at the v2 threshold
        assert Version(2017).uses_patch is True

    def test_next_sentinel(self):
        v = Version("next")
        assert v.is_next is True
        assert v.uses_patch is False
        assert v.to_string(ReleaseType.NEXT) == "next"
        # 'next' sorts after every numeric version
        assert v.to_sort_key() > Version(9999, 9, 9).to_sort_key()

    def test_to_string_respects_type_and_schema(self):
        assert Version(2017, 0, 1).to_string(ReleaseType.MINOR) == "2017.0.1"
        assert Version(1990, 0).to_string(ReleaseType.NIGHTLY) == "1990.0"
        assert Version(27).to_string(ReleaseType.MAJOR) == "27"

    def test_from_string_roundtrip(self):
        assert Version.from_string("2017.0.1") == Version(2017, 0, 1)
        assert Version.from_string("1990.0") == Version(1990, 0)
        assert Version.from_string("next").is_next

    def test_sorting_v1_ignores_patch(self):
        # v1 versions (< 2017) compare without patch
        assert Version(1990, 0).to_sort_key() == Version(1990, 0).to_sort_key()


@pytest.mark.unit
class TestParseReleaseName:
    """Tests for release-name parsing."""

    def test_valid_names(self):
        assert parse_release_name("minor-2017.0.0") == (
            ReleaseType.MINOR,
            2017,
            0,
            0,
        )
        assert parse_release_name("major-27") == (ReleaseType.MAJOR, 27, None, None)
        assert parse_release_name("nightly-1990.0") == (
            ReleaseType.NIGHTLY,
            1990,
            0,
            None,
        )

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            parse_release_name("bogus-1.2.3")

    def test_missing_dash(self):
        with pytest.raises(ValueError):
            parse_release_name("next")

    def test_non_integer_version(self):
        with pytest.raises(ValueError):
            parse_release_name("minor-abc.def")


@pytest.mark.unit
class TestReleaseSerialization:
    """Tests for Release.from_dict/to_dict round-tripping."""

    def _minor(self):
        return {
            "name": "minor-2017.0.0",
            "type": "minor",
            "version": {"major": 2017, "minor": 0, "patch": 0},
            "lifecycle": {
                "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
                "eol": {"isodate": "2025-10-01", "timestamp": 1759276800},
            },
            "git": {
                "commit": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
                "commit_short": "a94a8fe5",
            },
            "github": {
                "release": (
                    "https://github.com/gardenlinux/gardenlinux/releases/tag/2017.0.0"
                )
            },
            "flavors": ["container-amd64"],
            "attributes": {"source_repo": True},
        }

    def test_minor_roundtrip(self):
        data = self._minor()
        assert Release.from_dict(data).to_dict() == data

    def test_v1_minor_omits_patch(self):
        data = {
            "name": "minor-1990.0",
            "type": "minor",
            "version": {"major": 1990, "minor": 0},
            "lifecycle": {
                "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
                "eol": {"isodate": "2025-10-01", "timestamp": 1759276800},
            },
            "git": {
                "commit": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
                "commit_short": "a94a8fe5",
            },
            "github": {
                "release": (
                    "https://github.com/gardenlinux/gardenlinux/releases/tag/1990.0"
                )
            },
            "flavors": ["container-amd64"],
            "attributes": {"source_repo": True},
        }
        out = Release.from_dict(data).to_dict()
        assert "patch" not in out["version"]
        assert out == data

    def test_next_roundtrip(self):
        data = {
            "name": "next",
            "type": "next",
            "version": {"major": "next"},
            "lifecycle": {
                "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
                "extended": {"isodate": "2025-07-01", "timestamp": 1751328000},
                "eol": {"isodate": "2025-10-01", "timestamp": 1759276800},
            },
        }
        assert Release.from_dict(data).to_dict() == data

    def test_empty_flavors_preserved(self):
        # A freshly created release with no flavors keeps the empty list.
        data = self._minor()
        data["flavors"] = []
        assert Release.from_dict(data).to_dict()["flavors"] == []


@pytest.mark.unit
class TestNameAndUrlGeneration:
    """Tests that the model owns name and URL generation."""

    def test_default_name(self):
        assert Release.default_name(ReleaseType.NEXT, Version("next")) == "next"
        assert Release.default_name(ReleaseType.MAJOR, Version(27)) == "major-27"
        assert (
            Release.default_name(ReleaseType.MINOR, Version(2017, 0, 0))
            == "minor-2017.0.0"
        )
        assert (
            Release.default_name(ReleaseType.NIGHTLY, Version(1990, 0))
            == "nightly-1990.0"
        )

    def test_github_url(self):
        assert Release.github_release_url(Version(2017, 0, 0), ReleaseType.MINOR) == (
            "https://github.com/gardenlinux/gardenlinux/releases/tag/2017.0.0"
        )
        assert Release.github_release_url(Version(1990, 0), ReleaseType.MINOR) == (
            "https://github.com/gardenlinux/gardenlinux/releases/tag/1990.0"
        )


@pytest.mark.unit
class TestLifecycle:
    """Tests for lifecycle active/archived logic."""

    def test_active_when_eol_in_future(self):
        lc = Lifecycle(
            released=LifecyclePhase("2025-01-01", 1735689600),
            eol=LifecyclePhase("2999-01-01", 32472144000),
        )
        assert lc.is_active(current_timestamp=1_800_000_000) is True
        assert lc.is_archived(current_timestamp=1_800_000_000) is False

    def test_archived_when_eol_in_past(self):
        lc = Lifecycle(
            released=LifecyclePhase("2020-01-01", 1577836800),
            eol=LifecyclePhase("2021-01-01", 1609459200),
        )
        assert lc.is_active(current_timestamp=1_800_000_000) is False
        assert lc.is_archived(current_timestamp=1_800_000_000) is True

    def test_no_eol_is_neither_active_nor_archived(self):
        lc = Lifecycle(released=LifecyclePhase("2020-01-01", 1577836800))
        assert lc.is_active(current_timestamp=1_800_000_000) is False
        assert lc.is_archived(current_timestamp=1_800_000_000) is False


@pytest.mark.unit
class TestReleaseCollection:
    """Tests for filtering, sorting, and latest selection."""

    def _make(self, name, rtype, major, minor=None, patch=None, eol_ts=None):
        return Release(
            name=name,
            type=ReleaseType(rtype),
            version=Version(major, minor, patch),
            lifecycle=Lifecycle(
                released=LifecyclePhase("2025-01-01", 1735689600),
                eol=LifecyclePhase("2999-01-01", eol_ts) if eol_ts else None,
            ),
            git=(
                GitInfo("a" * 40, "aaaaaaaa")
                if rtype in ("minor", "nightly", "dev")
                else None
            ),
        )

    def test_by_type(self):
        col = ReleaseCollection(
            [
                self._make("major-27", "major", 27),
                self._make("minor-2017.0.0", "minor", 2017, 0, 0),
            ]
        )
        assert len(col.by_type(ReleaseType.MAJOR)) == 1
        assert len(col.by_types([ReleaseType.MAJOR, ReleaseType.MINOR])) == 2

    def test_latest_and_sorted_put_next_last(self):
        col = ReleaseCollection(
            [
                self._make("minor-2017.0.0", "minor", 2017, 0, 0),
                self._make("next", "next", "next"),
                self._make("minor-2017.0.5", "minor", 2017, 0, 5),
            ]
        )
        latest = col.latest()
        assert latest.name == "next"  # next sorts to the end == "latest"
        names = [r.name for r in col.sorted()]
        assert names[-1] == "next"
        assert names.index("minor-2017.0.0") < names.index("minor-2017.0.5")

    def test_filter_version_treats_missing_minor_as_zero(self):
        col = ReleaseCollection([self._make("major-27", "major", 27)])
        # A major release (no minor) should match --version 27.0
        assert len(col.filter_version(27, 0)) == 1

    def test_sorted_v1_missing_minor_treated_as_zero(self):
        # Characterization: a major-only v1 version and a x.0 version share the
        # same normalized sort key (missing minor == 0), and both sort before
        # x.1. This pins the intended ordering after the model refactor.
        col = ReleaseCollection(
            [
                self._make("minor-1990.1", "minor", 1990, 1),
                self._make("major-1990", "major", 1990),
                self._make("minor-1990.0", "minor", 1990, 0),
            ]
        )
        names = [r.name for r in col.sorted()]
        assert names[-1] == "minor-1990.1"
        assert Version(1990).to_sort_key() == Version(1990, 0).to_sort_key()
