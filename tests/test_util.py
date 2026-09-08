"""
Unit tests for glrd/util.py — split_releases_by_type / ReleasesByType.
"""

from glrd.util import ReleasesByType, split_releases_by_type


def _release(rtype: str) -> dict:
    return {"type": rtype, "name": f"{rtype}-1"}


class TestSplitReleasesByType:
    def test_returns_releases_by_type_instance(self):
        result = split_releases_by_type([])
        assert isinstance(result, ReleasesByType)

    def test_empty_input_gives_empty_lists(self):
        r = split_releases_by_type([])
        assert r.next == []
        assert r.major == []
        assert r.minor == []
        assert r.nightly == []
        assert r.dev == []

    def test_each_type_lands_in_correct_field(self):
        releases = [_release(t) for t in ("next", "major", "minor", "nightly", "dev")]
        r = split_releases_by_type(releases)
        assert len(r.next) == 1 and r.next[0]["type"] == "next"
        assert len(r.major) == 1 and r.major[0]["type"] == "major"
        assert len(r.minor) == 1 and r.minor[0]["type"] == "minor"
        assert len(r.nightly) == 1 and r.nightly[0]["type"] == "nightly"
        assert len(r.dev) == 1 and r.dev[0]["type"] == "dev"

    def test_unknown_type_is_silently_dropped(self):
        r = split_releases_by_type([{"type": "bogus", "name": "bogus-1"}])
        assert r.next == r.major == r.minor == r.nightly == r.dev == []

    def test_multiple_releases_of_same_type(self):
        releases = [_release("major"), _release("major"), _release("minor")]
        r = split_releases_by_type(releases)
        assert len(r.major) == 2
        assert len(r.minor) == 1

    def test_missing_type_key_is_dropped(self):
        r = split_releases_by_type([{"name": "no-type"}])
        assert r.next == r.major == r.minor == r.nightly == r.dev == []

    def test_result_fields_are_independent_lists(self):
        """Mutating one field must not affect others."""
        r = split_releases_by_type([_release("major")])
        r.major.append({"type": "major", "name": "extra"})
        assert len(r.minor) == 0
