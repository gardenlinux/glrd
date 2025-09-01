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
        # Valid v1 formats (versions < 2000)
        valid_cases = [
            ("1990.0", "nightly"),
            ("1999.0", "patch"),
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
        # Invalid v1 formats (versions < 2000 with micro)
        invalid_cases = [
            ("1990.0.1", "nightly"),
            ("1999.0.5", "patch"),
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
            assert "micro version" in error_message

    def test_v2_schema_valid_formats(self):
        """Test v2 schema validation with valid formats."""
        # Valid v2 formats (versions >= 2000)
        valid_cases = [
            ("2000.0.0", "nightly"),
            ("2222.0.0", "patch"),
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
        # Invalid v2 formats (versions >= 2000 without micro)
        invalid_cases = [
            ("2000.0", "nightly"),
            ("2222.0", "patch"),
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
            assert "missing micro version" in error_message

    def test_stable_next_releases(self):
        """Test that stable and next releases don't use version validation."""
        # Stable and next releases should always pass validation
        test_cases = [
            ("1990.0", "stable"),
            ("2000.0.0", "stable"),
            ("1990.0.1", "stable"),
            ("2000.0", "stable"),
            ("1990.0", "next"),
            ("2000.0.0", "next"),
            ("1990.0.1", "next"),
            ("2000.0", "next"),
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
        is_valid, error_message = validate_input_version_format("2000.0", "nightly")
        assert not is_valid
        assert "v2 schema" in error_message
        assert "missing micro version" in error_message

        # Just below boundary - should use v1 schema
        is_valid, error_message = validate_input_version_format("1999.0.1", "nightly")
        assert not is_valid
        assert "v1 schema" in error_message
        assert "micro version" in error_message

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
