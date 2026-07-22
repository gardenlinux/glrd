"""
Unit tests for glrd/git.py.

GitHub API calls are mocked at the gardenlinux.github.Client boundary.
pygit2 repository walks use a local in-memory fixture via pygit2.
Tests that require a live GITHUB_TOKEN are gated with pytest.mark.skipif.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pygit2
import pytest
import pytz

import glrd.git as git_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_release(tag_name: str, published_at: str, html_url: str):
    """Return a MagicMock that mimics a PyGithub GitRelease object."""
    r = MagicMock()
    r.tag_name = tag_name
    r.published_at = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    r.html_url = html_url
    return r


def _make_mock_ref(sha: str, obj_type: str = "commit"):
    """Return a MagicMock mimicking a PyGithub GitRef / GitRef.object."""
    ref = MagicMock()
    ref.object.sha = sha
    ref.object.type = obj_type
    return ref


# ---------------------------------------------------------------------------
# get_github_releases
# ---------------------------------------------------------------------------


class TestGetGithubReleases:
    def test_returns_dict_list_with_expected_keys(self):
        mock_releases = [
            _make_mock_release(
                "1592.1",
                "2024-08-22T00:00:00Z",
                "https://github.com/gardenlinux/gardenlinux/releases/tag/1592.1",
            ),
            _make_mock_release(
                "1592",
                "2024-08-01T00:00:00Z",
                "https://github.com/gardenlinux/gardenlinux/releases/tag/1592",
            ),
        ]

        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = mock_releases

        mock_client_instance = MagicMock()
        mock_client_instance.get_repo.return_value = mock_repo

        with patch("glrd.git.Client", return_value=mock_client_instance):
            result = git_module.get_github_releases()

        assert len(result) == 2
        for item in result:
            assert "tag_name" in item
            assert "published_at" in item
            assert "html_url" in item

        assert result[0]["tag_name"] == "1592.1"
        assert result[0]["published_at"] == "2024-08-22T00:00:00Z"
        assert result[1]["tag_name"] == "1592"

    def test_missing_token_exits(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("glrd.git.Client", side_effect=ValueError("GITHUB_TOKEN not set")):
            with pytest.raises(SystemExit):
                git_module.get_github_releases()

    def test_api_error_exits(self):
        mock_client_instance = MagicMock()
        mock_client_instance.get_repo.side_effect = Exception("API error")

        with patch("glrd.git.Client", return_value=mock_client_instance):
            with pytest.raises(SystemExit):
                git_module.get_github_releases()


# ---------------------------------------------------------------------------
# get_git_commit_from_tag
# ---------------------------------------------------------------------------


class TestGetGitCommitFromTag:
    def test_lightweight_tag_returns_sha(self):
        sha = "abc123def456" + "0" * 28
        mock_ref = _make_mock_ref(sha, obj_type="commit")

        mock_repo = MagicMock()
        mock_repo.get_git_ref.return_value = mock_ref

        mock_client_instance = MagicMock()
        mock_client_instance.get_repo.return_value = mock_repo

        with patch("glrd.git.Client", return_value=mock_client_instance):
            full, short = git_module.get_git_commit_from_tag("1592.1")

        assert full == sha
        assert short == sha[:8]
        mock_repo.get_git_ref.assert_called_once_with("tags/1592.1")

    def test_annotated_tag_is_dereferenced(self):
        tag_sha = "tagobj" + "0" * 34
        commit_sha = "realcommit" + "0" * 30

        mock_tag_obj = MagicMock()
        mock_tag_obj.object.sha = commit_sha

        mock_ref = _make_mock_ref(tag_sha, obj_type="tag")

        mock_repo = MagicMock()
        mock_repo.get_git_ref.return_value = mock_ref
        mock_repo.get_git_tag.return_value = mock_tag_obj

        mock_client_instance = MagicMock()
        mock_client_instance.get_repo.return_value = mock_repo

        with patch("glrd.git.Client", return_value=mock_client_instance):
            full, short = git_module.get_git_commit_from_tag("1592")

        assert full == commit_sha
        assert short == commit_sha[:8]
        mock_repo.get_git_tag.assert_called_once_with(tag_sha)

    def test_missing_token_exits(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with patch("glrd.git.Client", side_effect=ValueError("GITHUB_TOKEN not set")):
            with pytest.raises(SystemExit):
                git_module.get_git_commit_from_tag("1592.1")

    def test_api_error_exits(self):
        mock_client_instance = MagicMock()
        mock_client_instance.get_repo.side_effect = Exception("API error")

        with patch("glrd.git.Client", return_value=mock_client_instance):
            with pytest.raises(SystemExit):
                git_module.get_git_commit_from_tag("1592.1")


# ---------------------------------------------------------------------------
# get_git_commit_at_time — uses a real in-memory pygit2 repo as fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def local_git_repo(tmp_path):
    """
    Create a minimal bare+non-bare pair of pygit2 repos so that
    get_git_commit_at_time can clone from a local file:// URL.

    Returns a dict with keys:
        repo_url  – file:// URL to the *bare* origin
        sha_old   – SHA of the earlier commit  (committed at epoch 1_000_000)
        sha_new   – SHA of the later  commit  (committed at epoch 2_000_000)
    """
    bare_path = tmp_path / "origin.git"
    bare_path.mkdir()
    bare_repo = pygit2.init_repository(str(bare_path), bare=True)

    sig_old = pygit2.Signature("Test", "test@example.com", time=1_000_000, offset=0)
    sig_new = pygit2.Signature("Test", "test@example.com", time=2_000_000, offset=0)

    # Initial commit
    tb = bare_repo.TreeBuilder()
    tree_oid = tb.write()
    old_commit_oid = bare_repo.create_commit(
        "refs/heads/main",
        sig_old,
        sig_old,
        "first commit",
        tree_oid,
        [],
    )

    # Second commit
    tb2 = bare_repo.TreeBuilder()
    tree_oid2 = tb2.write()
    new_commit_oid = bare_repo.create_commit(
        "refs/heads/main",
        sig_new,
        sig_new,
        "second commit",
        tree_oid2,
        [old_commit_oid],
    )

    return {
        "repo_url": bare_path.as_uri(),
        "sha_old": str(old_commit_oid),
        "sha_new": str(new_commit_oid),
    }


class TestGetGitCommitAtTime:
    def setup_method(self):
        # Reset module-level cache before each test.
        git_module._repo_clone_path = None
        git_module._repo_instance = None

    def teardown_method(self):
        # Clean up any clone created during the test.
        git_module.cleanup_temp_repo()

    def test_returns_commit_before_target_time(self, local_git_repo):
        # epoch 1_500_000 is between old (1_000_000) and new (2_000_000)
        # so the walk should return old_commit (the last one <= target).
        target_dt = datetime.fromtimestamp(1_500_000, tz=pytz.UTC)
        date_str = target_dt.strftime("%Y-%m-%d")
        time_str = target_dt.strftime("%H:%M")

        full, short = git_module.get_git_commit_at_time(
            date=date_str,
            time=time_str,
            branch="main",
            remote_repo=local_git_repo["repo_url"],
        )

        assert full == local_git_repo["sha_old"]
        assert short == local_git_repo["sha_old"][:8]

    def test_clone_is_cached(self, local_git_repo):
        target_dt = datetime.fromtimestamp(1_500_000, tz=pytz.UTC)
        date_str = target_dt.strftime("%Y-%m-%d")
        time_str = target_dt.strftime("%H:%M")

        with patch(
            "glrd.git.Repository.checkout_repo",
            wraps=git_module.Repository.checkout_repo,
        ) as p:
            git_module.get_git_commit_at_time(
                date=date_str,
                time=time_str,
                branch="main",
                remote_repo=local_git_repo["repo_url"],
            )
            first_path = git_module._repo_clone_path

            # Second call must NOT clone again.
            git_module.get_git_commit_at_time(
                date=date_str,
                time=time_str,
                branch="main",
                remote_repo=local_git_repo["repo_url"],
            )
            assert git_module._repo_clone_path == first_path
            assert p.call_count == 1

    def test_no_commit_before_very_early_date_exits(self, local_git_repo):
        # epoch 100 is before all commits; should exit.
        target_dt = datetime.fromtimestamp(100, tz=pytz.UTC)
        date_str = target_dt.strftime("%Y-%m-%d")
        time_str = target_dt.strftime("%H:%M")

        with pytest.raises(SystemExit):
            git_module.get_git_commit_at_time(
                date=date_str,
                time=time_str,
                branch="main",
                remote_repo=local_git_repo["repo_url"],
            )


# ---------------------------------------------------------------------------
# cleanup_temp_repo
# ---------------------------------------------------------------------------


class TestCleanupTempRepo:
    def test_cleanup_removes_directory(self, tmp_path):
        clone_dir = tmp_path / "clone"
        clone_dir.mkdir()

        git_module._repo_clone_path = str(clone_dir)
        git_module._repo_instance = MagicMock()

        git_module.cleanup_temp_repo()

        assert not clone_dir.exists()
        assert git_module._repo_clone_path is None
        assert git_module._repo_instance is None

    def test_cleanup_is_idempotent(self):
        git_module._repo_clone_path = None
        git_module._repo_instance = None
        # Should not raise.
        git_module.cleanup_temp_repo()


# ---------------------------------------------------------------------------
# get_garden_version_for_date (pure logic — no mocking needed)
# ---------------------------------------------------------------------------


class TestGetGardenVersionForDate:
    def test_major_version_is_days_since_base(self):
        base_date = datetime(2020, 3, 31, tzinfo=pytz.UTC)
        test_date = datetime(2024, 8, 1, tzinfo=pytz.UTC)
        expected_major = (test_date - base_date).days

        major, minor, patch = git_module.get_garden_version_for_date(
            "major", test_date, []
        )
        assert major == expected_major
        assert minor == 0
        assert patch == 0

    def test_nightly_minor_increments(self):
        base_date = datetime(2020, 3, 31, tzinfo=pytz.UTC)
        test_date = datetime(2024, 8, 1, tzinfo=pytz.UTC)
        major = (test_date - base_date).days

        existing = [
            {
                "type": "nightly",
                "version": {"major": major, "minor": 0, "patch": 0},
            }
        ]

        major2, minor2, patch2 = git_module.get_garden_version_for_date(
            "nightly", test_date, existing
        )
        assert major2 == major
        # minor increments from 0 to 1; patch restarts at 0+1=1 because the
        # existing release (minor=0, patch=0) is counted before incrementing
        assert minor2 == 1
        assert patch2 == 1
