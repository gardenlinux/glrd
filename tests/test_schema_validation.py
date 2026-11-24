"""
Unit tests for schema validation logic.
"""

import pytest
from glrd.validation import (
    validate_input_version_format,
    validate_release_data,
    get_schema_for_release,
)
from glrd.schema import SCHEMA_V2, SCHEMA_V2_1, SCHEMA_DEFAULT
from glrd.util import SCHEMA_VERSION


@pytest.mark.unit
class TestSchemaValidation:
    """Unit tests for schema validation functions."""

    def test_v1_schema_valid_formats(self):
        """Test v1 schema validation with valid formats."""
        # Valid v1 formats (versions < 2017)
        valid_cases = [
            ("1990.0", "nightly"),
            ("1999.0", "minor"),
            ("1500.5", "dev"),
        ]

        for version, release_type in valid_cases:
            is_valid, error_message = validate_input_version_format(
                version, release_type
            )
            assert is_valid, f"Version {version} should be valid for {release_type}"
            assert error_message is None

    def test_v1_schema_invalid_formats(self):
        """Test v1 schema validation with invalid formats."""
        # Invalid v1 formats (versions < 2017 with patch)
        invalid_cases = [
            ("1990.0.1", "nightly"),
            ("1999.0.5", "minor"),
            ("1500.5.2", "dev"),
        ]

        for version, release_type in invalid_cases:
            is_valid, error_message = validate_input_version_format(
                version, release_type
            )
            assert (
                not is_valid
            ), f"Version {version} should be invalid for {release_type}"
            assert "v1 schema" in error_message
            assert "patch version" in error_message

    def test_v2_schema_valid_formats(self):
        """Test v2 schema validation with valid formats."""
        # Valid v2 formats (versions >= 2017)
        valid_cases = [
            ("2017.0.0", "nightly"),
            ("2222.0.0", "minor"),
            ("3000.5.2", "dev"),
        ]

        for version, release_type in valid_cases:
            is_valid, error_message = validate_input_version_format(
                version, release_type
            )
            assert is_valid, f"Version {version} should be valid for {release_type}"
            assert error_message is None

    def test_v2_schema_invalid_formats(self):
        """Test v2 schema validation with invalid formats."""
        # Invalid v2 formats (versions >= 2017 without patch)
        invalid_cases = [
            ("2017.0", "nightly"),
            ("2222.0", "minor"),
            ("3000.5", "dev"),
        ]

        for version, release_type in invalid_cases:
            is_valid, error_message = validate_input_version_format(
                version, release_type
            )
            assert (
                not is_valid
            ), f"Version {version} should be invalid for {release_type}"
            assert "v2 schema" in error_message
            assert "missing patch version" in error_message

    def test_major_next_releases(self):
        """Test that major and next releases don't use version validation."""
        # Major and next releases should always pass validation
        test_cases = [
            ("1990.0", "major"),
            ("2017.0.0", "major"),
            ("1990.0.1", "major"),
            ("2017.0", "major"),
            ("1990.0", "next"),
            ("2017.0.0", "next"),
            ("1990.0.1", "next"),
            ("2017.0", "next"),
        ]

        for version, release_type in test_cases:
            is_valid, error_message = validate_input_version_format(
                version, release_type
            )
            assert is_valid, f"Version {version} should be valid for {release_type}"
            assert error_message is None

    def test_boundary_validation(self):
        """Test validation at the boundary between v1 and v2 schemas."""
        # Exactly at boundary - should require v2 schema
        is_valid, error_message = validate_input_version_format("2017.0", "nightly")
        assert not is_valid
        assert "v2 schema" in error_message
        assert "missing patch version" in error_message

        # Just below boundary - should use v1 schema
        is_valid, error_message = validate_input_version_format("1999.0.1", "nightly")
        assert not is_valid
        assert "v1 schema" in error_message
        assert "patch version" in error_message

    def test_invalid_version_formats(self):
        """Test validation with completely invalid version formats."""
        invalid_formats = [
            "1990",  # Missing minor
            "1990.0.0.0",  # Too many parts
            "abc.def",  # Non-numeric
            "",  # Empty
        ]

        for version in invalid_formats:
            # This should raise an exception or return invalid
            try:
                is_valid, error_message = validate_input_version_format(
                    version, "nightly"
                )
                # If no exception, should be invalid
                assert not is_valid, f"Version {version} should be invalid"
            except (ValueError, IndexError):
                # Expected for invalid formats
                pass


def _make_major(major, attributes=None):
    """Build a minimal valid major release dict for schema validation."""
    release = {
        "name": f"major-{major}",
        "type": "major",
        "version": {"major": major},
        "lifecycle": {
            "released": {"isodate": "2025-05-26", "timestamp": 1748217600},
            "extended": {"isodate": "2026-02-26", "timestamp": 1772064000},
            "eol": {"isodate": "2030-05-31", "timestamp": 1906675200},
        },
    }
    if attributes is not None:
        release["attributes"] = attributes
    return release


@pytest.mark.unit
class TestSchemaV21:
    """Unit tests for the backward-compatible v2.1 schema."""

    def test_schema_default_is_v2_1_alias(self):
        """v2.1 is the default and is a structural alias of v2."""
        assert SCHEMA_DEFAULT is SCHEMA_V2_1
        assert SCHEMA_V2_1 is SCHEMA_V2

    def test_schema_version_constant(self):
        """The internal schema version identifier is 2.1."""
        assert SCHEMA_VERSION == "2.1"

    def test_major_uses_default_schema(self):
        """Major releases are validated against the default (v2.1) schema."""
        assert get_schema_for_release(_make_major(1877)) is SCHEMA_DEFAULT["major"]

    def test_major_without_attributes_is_valid(self):
        """Existing v2 data without attributes stays valid (backward compat)."""
        errors = []
        assert validate_release_data(_make_major(1592), errors) is True
        assert errors == []

    def test_major_with_lts_true_is_valid(self):
        """A major release flagged as LTS validates."""
        errors = []
        release = _make_major(1877, attributes={"lts": True})
        assert validate_release_data(release, errors) is True
        assert errors == []

    def test_major_with_lts_false_is_valid(self):
        """A non-LTS major release with an explicit lts=false validates."""
        errors = []
        release = _make_major(2150, attributes={"lts": False})
        assert validate_release_data(release, errors) is True
        assert errors == []
