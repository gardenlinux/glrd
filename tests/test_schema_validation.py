"""
Unit tests for schema validation logic.
"""

import pytest
from glrd.manage import validate_input_version_format


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
