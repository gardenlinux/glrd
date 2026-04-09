"""
Tests for the --update action and update_release() function in glrd-manage.

This test suite validates:
1. Integration tests: full CLI flow via subprocess with --input-stdin seeding
2. Unit tests: direct update_release() function calls with mocked args
"""

import copy
import json
import os
import subprocess
import sys
import pytest
from unittest.mock import MagicMock


SAMPLE_MAJOR_RELEASE = {
    "name": "major-1520",
    "type": "major",
    "version": {"major": 1520},
    "lifecycle": {
        "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
        "extended": {"isodate": "2025-07-01", "timestamp": 1751328000},
        "eol": {"isodate": "2025-10-01", "timestamp": 1759276800},
    },
}

SAMPLE_MINOR_RELEASE = {
    "name": "minor-1500.5",
    "type": "minor",
    "version": {"major": 1500, "minor": 5},
    "lifecycle": {
        "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
        "eol": {"isodate": "2025-10-01", "timestamp": 1759276800},
    },
    "git": {
        "commit": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
        "commit_short": "a94a8fe5",
    },
    "github": {
        "release": "https://github.com/gardenlinux/gardenlinux/releases/tag/1500.5"
    },
    "flavors": ["container-amd64"],
    "attributes": {"source_repo": True},
}

SAMPLE_NIGHTLY_RELEASE = {
    "name": "nightly-1500.6",
    "type": "nightly",
    "version": {"major": 1500, "minor": 6},
    "lifecycle": {
        "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
    },
    "git": {
        "commit": "b94a8fe5ccb19ba61c4c0873d391e987982fbbd4",
        "commit_short": "b94a8fe5",
    },
    "github": {
        "release": "https://github.com/gardenlinux/gardenlinux/releases/tag/1500.6"
    },
    "flavors": ["container-amd64"],
    "attributes": {"source_repo": True},
}

SAMPLE_DEV_RELEASE = {
    "name": "dev-1500.7",
    "type": "dev",
    "version": {"major": 1500, "minor": 7},
    "lifecycle": {
        "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
    },
    "git": {
        "commit": "c94a8fe5ccb19ba61c4c0873d391e987982fbbd5",
        "commit_short": "c94a8fe5",
    },
    "github": {
        "release": "https://github.com/gardenlinux/gardenlinux/releases/tag/1500.7"
    },
    "flavors": ["container-amd64"],
    "attributes": {"source_repo": True},
}


@pytest.mark.integration
class TestUpdateIntegration:
    """Integration tests for the --update CLI action."""

    def run_manage_command_stdin(
        self, manage_script, args, stdin_data, expect_success=True
    ):
        """Run glrd-manage command with data on stdin and return result."""
        cmd = [sys.executable, manage_script] + args
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(manage_script),
        )

        if expect_success:
            assert result.returncode == 0, (
                f"Command failed: {' '.join(cmd)}\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )
        else:
            assert result.returncode != 0, (
                f"Command should have failed but succeeded: {' '.join(cmd)}\n"
                f"STDOUT: {result.stdout}"
            )

        return result

    def load_json_output(self, filepath):
        """Load and parse JSON output file."""
        assert os.path.exists(filepath), f"Output file not found: {filepath}"
        with open(filepath, "r") as f:
            return json.load(f)

    # ===========================================================================
    # Happy Path Tests - Lifecycle Updates
    # ===========================================================================

    def test_update_major_lifecycle_eol(self, test_dir, manage_script):
        """Update EOL date on a major release."""
        prefix = os.path.join(test_dir, "releases-major-eol")
        output_file = f"{prefix}-major.json"

        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--lifecycle-eol-isodatetime",
                "2026-06-15T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release = next(r for r in data["releases"] if r["name"] == "major-1520")
        assert release["lifecycle"]["eol"]["isodate"] == "2026-06-15"
        assert isinstance(release["lifecycle"]["eol"]["timestamp"], int)

    def test_update_major_lifecycle_extended(self, test_dir, manage_script):
        """Update extended maintenance date on a major release."""
        prefix = os.path.join(test_dir, "releases-major-extended")
        output_file = f"{prefix}-major.json"

        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--lifecycle-extended-isodatetime",
                "2026-03-15T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release = next(r for r in data["releases"] if r["name"] == "major-1520")
        assert release["lifecycle"]["extended"]["isodate"] == "2026-03-15"
        assert isinstance(release["lifecycle"]["extended"]["timestamp"], int)

    def test_update_major_lifecycle_released(self, test_dir, manage_script):
        """Update released date on a major release."""
        prefix = os.path.join(test_dir, "releases-major-released")
        output_file = f"{prefix}-major.json"

        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--lifecycle-released-isodatetime",
                "2026-01-01T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release = next(r for r in data["releases"] if r["name"] == "major-1520")
        assert release["lifecycle"]["released"]["isodate"] == "2026-01-01"
        assert isinstance(release["lifecycle"]["released"]["timestamp"], int)

    def test_update_minor_lifecycle_eol(self, test_dir, manage_script):
        """Update EOL date on a minor release."""
        prefix = os.path.join(test_dir, "releases-minor-eol")
        output_file = f"{prefix}-minor.json"

        releases_json = {"releases": [copy.deepcopy(SAMPLE_MINOR_RELEASE)]}

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "minor-1500.5",
                "--lifecycle-eol-isodatetime",
                "2026-06-15T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release = next(r for r in data["releases"] if r["name"] == "minor-1500.5")
        assert release["lifecycle"]["eol"]["isodate"] == "2026-06-15"

    # ===========================================================================
    # Happy Path Tests - Commit Updates
    # ===========================================================================

    def test_update_minor_commit(self, test_dir, manage_script):
        """Update commit hash on a minor release."""
        prefix = os.path.join(test_dir, "releases-minor-commit")
        output_file = f"{prefix}-minor.json"

        releases_json = {"releases": [copy.deepcopy(SAMPLE_MINOR_RELEASE)]}
        new_commit = "deadbeef1234567890abcdef1234567890abcdef"

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "minor-1500.5",
                "--commit",
                new_commit,
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release = next(r for r in data["releases"] if r["name"] == "minor-1500.5")
        assert release["git"]["commit"] == new_commit
        assert release["git"]["commit_short"] == new_commit[:8]

    def test_update_nightly_commit(self, test_dir, manage_script):
        """Update commit hash on a nightly release."""
        prefix = os.path.join(test_dir, "releases-nightly-commit")
        output_file = f"{prefix}-nightly.json"

        releases_json = {"releases": [copy.deepcopy(SAMPLE_NIGHTLY_RELEASE)]}
        new_commit = "deadbeef1234567890abcdef1234567890abcdef"

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "nightly-1500.6",
                "--commit",
                new_commit,
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release = next(r for r in data["releases"] if r["name"] == "nightly-1500.6")
        assert release["git"]["commit"] == new_commit
        assert release["git"]["commit_short"] == new_commit[:8]

    def test_update_dev_commit(self, test_dir, manage_script):
        """Update commit hash on a dev release."""
        prefix = os.path.join(test_dir, "releases-dev-commit")
        output_file = f"{prefix}-dev.json"

        releases_json = {"releases": [copy.deepcopy(SAMPLE_DEV_RELEASE)]}
        new_commit = "deadbeef1234567890abcdef1234567890abcdef"

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "dev-1500.7",
                "--commit",
                new_commit,
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release = next(r for r in data["releases"] if r["name"] == "dev-1500.7")
        assert release["git"]["commit"] == new_commit
        assert release["git"]["commit_short"] == new_commit[:8]

    # ===========================================================================
    # Happy Path Tests - Multiple Fields and Missing Sections
    # ===========================================================================

    def test_update_multiple_fields(self, test_dir, manage_script):
        """Update multiple lifecycle fields in a single --update call."""
        prefix = os.path.join(test_dir, "releases-multiple")
        output_file = f"{prefix}-major.json"

        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--lifecycle-released-isodatetime",
                "2026-02-01T00:00:00",
                "--lifecycle-eol-isodatetime",
                "2026-12-01T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release = next(r for r in data["releases"] if r["name"] == "major-1520")
        assert release["lifecycle"]["released"]["isodate"] == "2026-02-01"
        assert release["lifecycle"]["eol"]["isodate"] == "2026-12-01"
        assert release["lifecycle"]["extended"]["isodate"] == "2025-07-01"

    def test_update_creates_missing_lifecycle_section(self, test_dir, manage_script):
        """Update a release that has no lifecycle.eol section - verify it gets created."""
        prefix = os.path.join(test_dir, "releases-missing-section")
        output_file = f"{prefix}-major.json"

        release = copy.deepcopy(SAMPLE_MAJOR_RELEASE)
        del release["lifecycle"]["eol"]
        releases_json = {"releases": [release]}

        self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--lifecycle-eol-isodatetime",
                "2026-06-15T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
        )

        data = self.load_json_output(output_file)
        release_out = next(r for r in data["releases"] if r["name"] == "major-1520")
        assert "eol" in release_out["lifecycle"]
        assert release_out["lifecycle"]["eol"]["isodate"] == "2026-06-15"
        assert isinstance(release_out["lifecycle"]["eol"]["timestamp"], int)

    # ===========================================================================
    # Validation Error Tests
    # ===========================================================================

    def test_update_with_no_query_fails(self, test_dir, manage_script):
        """--update with --no-query should exit with error."""
        prefix = os.path.join(test_dir, "releases-no-query")
        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}

        result = self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--lifecycle-eol-isodatetime",
                "2026-06-15T00:00:00",
                "--no-query",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
            expect_success=False,
        )

        assert "'--update' cannot run with '--no-query'" in result.stderr

    def test_update_without_modifiers_fails(self, test_dir, manage_script):
        """--update without any modifier flags should exit with error."""
        prefix = os.path.join(test_dir, "releases-no-modifiers")
        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}

        result = self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
            expect_success=False,
        )

        assert "'--update' requires at least one of" in result.stderr

    def test_update_nonexistent_release_fails(self, test_dir, manage_script):
        """--update with a release name not in the input data should exit with error."""
        prefix = os.path.join(test_dir, "releases-nonexistent")
        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}

        result = self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-0000",
                "--lifecycle-eol-isodatetime",
                "2026-06-15T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
            expect_success=False,
        )

        assert "not found in the existing data" in result.stderr

    def test_update_invalid_datetime_format_fails(self, test_dir, manage_script):
        """--update with malformed datetime should exit with error."""
        prefix = os.path.join(test_dir, "releases-invalid-datetime")
        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}

        result = self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--lifecycle-eol-isodatetime",
                "not-a-date",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
            expect_success=False,
        )

        assert "Invalid" in result.stderr or "invalid" in result.stderr

    def test_update_invalid_commit_length_fails(self, test_dir, manage_script):
        """--update with a commit hash that is not 40 characters should exit with error."""
        prefix = os.path.join(test_dir, "releases-invalid-commit")
        releases_json = {"releases": [copy.deepcopy(SAMPLE_MINOR_RELEASE)]}

        result = self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "minor-1500.5",
                "--commit",
                "tooshort",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
            expect_success=False,
        )

        assert "40 characters" in result.stderr

    def test_update_extended_on_minor_fails(self, test_dir, manage_script):
        """--lifecycle-extended-isodatetime on a minor release should fail."""
        prefix = os.path.join(test_dir, "releases-extended-minor")
        releases_json = {"releases": [copy.deepcopy(SAMPLE_MINOR_RELEASE)]}

        result = self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "minor-1500.5",
                "--lifecycle-extended-isodatetime",
                "2026-06-15T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
            expect_success=False,
        )

        assert "only valid for 'major' and 'next'" in result.stderr

    def test_update_eol_on_nightly_fails(self, test_dir, manage_script):
        """--lifecycle-eol-isodatetime on a nightly release should fail."""
        prefix = os.path.join(test_dir, "releases-eol-nightly")
        releases_json = {"releases": [copy.deepcopy(SAMPLE_NIGHTLY_RELEASE)]}

        result = self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "nightly-1500.6",
                "--lifecycle-eol-isodatetime",
                "2026-06-15T00:00:00",
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
            expect_success=False,
        )

        assert "only valid for 'next', 'major', and 'minor'" in result.stderr

    def test_update_commit_on_major_fails(self, test_dir, manage_script):
        """--commit on a major release should fail."""
        prefix = os.path.join(test_dir, "releases-commit-major")
        releases_json = {"releases": [copy.deepcopy(SAMPLE_MAJOR_RELEASE)]}
        new_commit = "deadbeef1234567890abcdef1234567890abcdef"

        result = self.run_manage_command_stdin(
            manage_script,
            [
                "--update",
                "major-1520",
                "--commit",
                new_commit,
                "--input-stdin",
                "--output-format",
                "json",
                "--output-file-prefix",
                prefix,
            ],
            json.dumps(releases_json),
            expect_success=False,
        )

        assert "only valid for 'minor', 'nightly', and 'dev'" in result.stderr


@pytest.mark.unit
class TestUpdateUnit:
    """Unit tests for the update_release() function."""

    def test_update_release_modifies_in_place(self):
        """Verify the function modifies the release dict in-place."""
        from glrd.manage import update_release

        args = MagicMock()
        args.update = "major-1520"
        args.lifecycle_eol_isodatetime = "2026-06-15T00:00:00"
        args.lifecycle_released_isodatetime = None
        args.lifecycle_extended_isodatetime = None
        args.commit = None

        release = {
            "name": "major-1520",
            "lifecycle": {"eol": {"isodate": "2025-10-01", "timestamp": 1759276800}},
        }
        major_releases = [release]

        update_release(args, [], major_releases, [], [], [])

        assert release["lifecycle"]["eol"]["isodate"] == "2026-06-15"

    def test_update_release_preserves_other_fields(self):
        """Verify fields not targeted by the update remain unchanged."""
        from glrd.manage import update_release

        args = MagicMock()
        args.update = "major-1520"
        args.lifecycle_eol_isodatetime = "2026-06-15T00:00:00"
        args.lifecycle_released_isodatetime = None
        args.lifecycle_extended_isodatetime = None
        args.commit = None

        release = {
            "name": "major-1520",
            "type": "major",
            "version": {"major": 1520},
            "lifecycle": {
                "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
                "extended": {"isodate": "2025-07-01", "timestamp": 1751328000},
                "eol": {"isodate": "2025-10-01", "timestamp": 1759276800},
            },
        }
        major_releases = [release]

        update_release(args, [], major_releases, [], [], [])

        assert release["name"] == "major-1520"
        assert release["type"] == "major"
        assert release["version"] == {"major": 1520}
        assert release["lifecycle"]["released"]["isodate"] == "2025-01-01"
        assert release["lifecycle"]["extended"]["isodate"] == "2025-07-01"

    def test_update_release_timestamp_consistency(self):
        """Verify isodate and timestamp are consistent after update."""
        import pytz
        from datetime import datetime
        from glrd.manage import update_release

        args = MagicMock()
        args.update = "major-1520"
        args.lifecycle_released_isodatetime = "2026-01-15T00:00:00"
        args.lifecycle_extended_isodatetime = None
        args.lifecycle_eol_isodatetime = None
        args.commit = None

        release = {
            "name": "major-1520",
            "lifecycle": {
                "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
            },
        }
        major_releases = [release]

        update_release(args, [], major_releases, [], [], [])

        isodate = release["lifecycle"]["released"]["isodate"]
        timestamp = release["lifecycle"]["released"]["timestamp"]

        parsed = datetime.strptime(isodate, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
        expected_ts = int(parsed.timestamp())

        assert timestamp == expected_ts

    def test_update_release_creates_git_section(self):
        """Update commit on a release missing the git key - verify git dict is created."""
        from glrd.manage import update_release

        args = MagicMock()
        args.update = "minor-1500.5"
        args.lifecycle_released_isodatetime = None
        args.lifecycle_extended_isodatetime = None
        args.lifecycle_eol_isodatetime = None
        args.commit = "deadbeef1234567890abcdef1234567890abcdef"

        release = {
            "name": "minor-1500.5",
            "type": "minor",
            "version": {"major": 1500, "minor": 5},
            "lifecycle": {
                "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
            },
        }
        minor_releases = [release]

        update_release(args, [], [], minor_releases, [], [])

        assert "git" in release
        assert release["git"]["commit"] == "deadbeef1234567890abcdef1234567890abcdef"
        assert release["git"]["commit_short"] == "deadbeef"

    def test_update_release_exit_on_not_found(self):
        """Mock args targeting a non-existent release name - verify SystemExit is raised."""
        from glrd.manage import update_release

        args = MagicMock()
        args.update = "major-0000"
        args.lifecycle_released_isodatetime = None
        args.lifecycle_extended_isodatetime = None
        args.lifecycle_eol_isodatetime = None
        args.commit = None

        release = {
            "name": "major-1520",
            "lifecycle": {
                "released": {"isodate": "2025-01-01", "timestamp": 1735689600},
            },
        }
        major_releases = [release]

        with pytest.raises(SystemExit) as exc_info:
            update_release(args, [], major_releases, [], [], [])

        assert exc_info.value.code == 1
