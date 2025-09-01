"""
Integration tests for glrd-manage and glrd commands.

This test suite validates:
1. glrd-manage command execution with various version formats
2. JSON output file generation
3. glrd query verification of generated files
4. Schema validation for both v1 and v2 schemas
"""

import os
import json
import subprocess
import sys
import pytest
from pathlib import Path


@pytest.mark.integration
class TestGLRDIntegration:
    """Integration tests for GLRD manage and query commands."""

    def run_manage_command(self, manage_script, args, expect_success=True):
        """Run glrd-manage command and return result."""
        cmd = [sys.executable, manage_script] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(manage_script)
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

    def run_manage_command_stdin(self, manage_script, args, stdin_data, expect_success=True):
        """Run glrd-manage command with data on stdin and return result."""
        cmd = [sys.executable, manage_script] + args
        result = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(manage_script)
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

    def run_query_command(self, query_script, args):
        """Run glrd query command and return result."""
        cmd = [sys.executable, query_script] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(query_script)
        )

        assert result.returncode == 0, (
            f"Query command failed: {' '.join(cmd)}\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )
        return result

    def load_json_output(self, filepath):
        """Load and parse JSON output file."""
        assert os.path.exists(filepath), f"Output file not found: {filepath}"
        with open(filepath, 'r') as f:
            return json.load(f)

    @pytest.mark.parametrize("version,expected_name", [
        ("1990.0", "nightly-1990.0"),
        ("1999.0", "nightly-1999.0"),
        ("1500.5", "nightly-1500.5"),
    ])
    def test_v1_schema_valid_versions(self, test_dir, manage_script, version, expected_name):
        """Test v1 schema with valid version formats (versions < 2000)."""
        prefix = os.path.join(test_dir, f'releases-nightly-{version.replace(".", "_")}')
        output_file = f'{prefix}-nightly.json'

        # Create release
        result = self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', version,
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        # Verify output file was created
        assert os.path.exists(output_file), f"Output file not created for version {version}"

        # Load and verify JSON structure
        data = self.load_json_output(output_file)
        assert 'releases' in data
        assert len(data['releases']) == 1

        release = data['releases'][0]
        assert release['name'] == expected_name
        assert release['type'] == 'nightly'
        assert release['version']['major'] == int(version.split('.')[0])
        assert release['version']['minor'] == int(version.split('.')[1])
        # v1 schema should not have micro field
        assert 'micro' not in release['version']

    @pytest.mark.parametrize("version", [
        "1990.0.1",
        "1999.0.5",
        "1500.5.2",
    ])
    def test_v1_schema_invalid_versions(self, test_dir, manage_script, version):
        """Test v1 schema with invalid version formats (versions < 2000 with micro)."""
        prefix = os.path.join(test_dir, f'releases-nightly-{version.replace(".", "_")}')
        output_file = f'{prefix}-nightly.json'

        # Should fail because v1 schema doesn't support micro field
        result = self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', version,
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ], expect_success=False)

        # Verify error message mentions v1 schema
        assert "v1 schema" in result.stderr
        assert "micro version" in result.stderr

        # Verify no output file was created
        assert not os.path.exists(output_file), f"Output file should not be created for invalid version {version}"

    @pytest.mark.parametrize("version,expected_name", [
        ("2000.0.0", "nightly-2000.0.0"),
        ("2222.0.0", "nightly-2222.0.0"),
        ("3000.5.2", "nightly-3000.5.2"),
    ])
    def test_v2_schema_valid_versions(self, test_dir, manage_script, version, expected_name):
        """Test v2 schema with valid version formats (versions >= 2000)."""
        prefix = os.path.join(test_dir, f'releases-nightly-{version.replace(".", "_")}')
        output_file = f'{prefix}-nightly.json'

        # Create release
        result = self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', version,
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        # Verify output file was created
        assert os.path.exists(output_file), f"Output file not created for version {version}"

        # Load and verify JSON structure
        data = self.load_json_output(output_file)
        assert 'releases' in data
        assert len(data['releases']) == 1

        release = data['releases'][0]
        assert release['name'] == expected_name
        assert release['type'] == 'nightly'

        version_parts = version.split('.')
        assert release['version']['major'] == int(version_parts[0])
        assert release['version']['minor'] == int(version_parts[1])
        assert release['version']['micro'] == int(version_parts[2])

    @pytest.mark.parametrize("version", [
        "2000.0",
        "2222.0",
        "3000.5",
    ])
    def test_v2_schema_invalid_versions(self, test_dir, manage_script, version):
        """Test v2 schema with invalid version formats (versions >= 2000 without micro)."""
        prefix = os.path.join(test_dir, f'releases-nightly-{version.replace(".", "_")}')
        output_file = f'{prefix}-nightly.json'

        # Should fail because v2 schema requires micro field
        result = self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', version,
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ], expect_success=False)

        # Verify error message mentions v2 schema
        assert "v2 schema" in result.stderr
        assert "missing micro version" in result.stderr

        # Verify no output file was created
        assert not os.path.exists(output_file), f"Output file should not be created for invalid version {version}"

    def test_glrd_query_verification(self, test_dir, manage_script, query_script):
        """Test that generated JSON files can be queried with glrd."""
        prefix = os.path.join(test_dir, 'releases-nightly')
        output_file = f'{prefix}-nightly.json'

        # Create a valid v1 schema release
        self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', '1990.0',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        # Verify the file exists
        assert os.path.exists(output_file)

        # Query the generated file
        result = self.run_query_command(query_script, [
            '--type', 'nightly',
            '--input-type', 'file',
            '--input-file-prefix', prefix,
            '--output-format', 'json'
        ])

        # Parse query result
        query_data = json.loads(result.stdout)
        assert 'releases' in query_data
        assert len(query_data['releases']) == 1

        release = query_data['releases'][0]
        assert release['name'] == 'nightly-1990.0'
        assert release['type'] == 'nightly'

    def test_query_created_dev_release(self, test_dir, manage_script, query_script):
        """Create a dev release and query it using glrd."""
        prefix = os.path.join(test_dir, 'releases-dev-ci')
        output_file = f'{prefix}-dev.json'

        # Create dev release (v1 schema)
        self.run_manage_command(manage_script, [
            '--create', 'dev',
            '--version', '1990.0',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        # Ensure file exists
        assert os.path.exists(output_file)

        # Query using glrd
        result = self.run_query_command(query_script, [
            '--type', 'dev',
            '--input-type', 'file',
            '--input-file-prefix', prefix,
            '--output-format', 'json'
        ])

        data = json.loads(result.stdout)
        assert 'releases' in data
        assert len(data['releases']) == 1
        assert data['releases'][0]['name'] == 'dev-1990.0'
        assert data['releases'][0]['type'] == 'dev'

    def test_query_created_stable_release(self, test_dir, manage_script, query_script):
        """Create a stable release and query it using glrd."""
        prefix = os.path.join(test_dir, 'releases-stable-ci')
        output_file = f'{prefix}-stable.json'

        # Create stable release
        self.run_manage_command(manage_script, [
            '--create', 'stable',
            '--version', '1312',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        # Ensure file exists
        assert os.path.exists(output_file)

        # Query using glrd
        result = self.run_query_command(query_script, [
            '--type', 'stable',
            '--input-type', 'file',
            '--input-file-prefix', prefix,
            '--output-format', 'json'
        ])

        data = json.loads(result.stdout)
        assert 'releases' in data
        assert len(data['releases']) == 1
        assert data['releases'][0]['name'] == 'stable-1312'
        assert data['releases'][0]['type'] == 'stable'

    def test_create_query_patch_via_input_stdin(self, test_dir, manage_script, query_script):
        """Create a patch release via input-stdin and query it using glrd."""
        prefix = os.path.join(test_dir, 'releases-patch-ci')
        output_file = f'{prefix}-patch.json'

        patch_json = {
            "releases": [
                {
                    "name": "patch-1592.6",
                    "type": "patch",
                    "version": {"major": 1592, "minor": 6},
                    "lifecycle": {
                        "released": {"isodate": "2025-02-19", "timestamp": 1739951325},
                        "eol": {"isodate": "2025-08-12", "timestamp": 1754956800}
                    },
                    "git": {
                        "commit": "cb05e11f0481b72d0a30da3662295315b220a436",
                        "commit_short": "cb05e11f"
                    },
                    "github": {"release": "https://github.com/gardenlinux/gardenlinux/releases/tag/1592.6"},
                    "flavors": [
                        "container-amd64",
                        "container-arm64"
                    ],
                    "attributes": {"source_repo": True}
                }
            ]
        }

        stdin_payload = json.dumps(patch_json)

        # Create via stdin
        self.run_manage_command_stdin(manage_script, [
            '--input-stdin',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ], stdin_payload)

        # Ensure file exists
        assert os.path.exists(output_file)

        # Query using glrd
        result = self.run_query_command(query_script, [
            '--type', 'patch',
            '--input-type', 'file',
            '--input-file-prefix', prefix,
            '--output-format', 'json'
        ])

        data = json.loads(result.stdout)
        assert 'releases' in data
        assert len(data['releases']) == 1
        assert data['releases'][0]['name'] == 'patch-1592.6'
        assert data['releases'][0]['type'] == 'patch'

    def test_create_query_next_release(self, test_dir, manage_script, query_script):
        """Create a next release (via stdin for full lifecycle) and query it using glrd."""
        prefix = os.path.join(test_dir, 'releases-next-ci')
        output_file = f'{prefix}-next.json'

        next_json = {
            "releases": [
                {
                    "name": "next",
                    "type": "next",
                    "version": {"major": "next"},
                    "lifecycle": {
                        "released": {"isodate": "2025-12-01", "timestamp": 1764547200},
                        "extended": {"isodate": "2026-06-01", "timestamp": 1780262400},
                        "eol": {"isodate": "2026-09-01", "timestamp": 1788297600}
                    }
                }
            ]
        }

        stdin_payload = json.dumps(next_json)

        # Create via stdin
        self.run_manage_command_stdin(manage_script, [
            '--input-stdin',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ], stdin_payload)

        # Ensure file exists
        assert os.path.exists(output_file)

        # Query using glrd
        result = self.run_query_command(query_script, [
            '--type', 'next',
            '--input-type', 'file',
            '--input-file-prefix', prefix,
            '--output-format', 'json'
        ])

        data = json.loads(result.stdout)
        assert 'releases' in data
        assert len(data['releases']) == 1
        assert data['releases'][0]['name'] == 'next'
        assert data['releases'][0]['type'] == 'next'

    def test_multiple_releases_query(self, test_dir, manage_script, query_script):
        """Test querying multiple releases of different schema versions."""
        # Create multiple releases
        releases = [
            ('1990.0', 'nightly-1990.0'),  # v1 schema
            ('2000.0.0', 'nightly-2000.0.0'),  # v2 schema
        ]

        all_releases = []

        for version, expected_name in releases:
            prefix = os.path.join(test_dir, f'releases-nightly-{version.replace(".", "_")}')
            output_file = f'{prefix}-nightly.json'

            # Create release
            self.run_manage_command(manage_script, [
                '--create', 'nightly',
                '--version', version,
                '--output-format', 'json',
                '--output-file-prefix', prefix,
                '--no-query'
            ])

            # Load and verify
            data = self.load_json_output(output_file)
            all_releases.extend(data['releases'])

        # Create combined file for querying with correct naming
        combined_file = os.path.join(test_dir, 'releases-nightly-combined-nightly.json')
        with open(combined_file, 'w') as f:
            json.dump({'releases': all_releases}, f)

        # Query combined file using direct file path
        result = self.run_query_command(query_script, [
            '--type', 'nightly',
            '--input-type', 'file',
            '--input-file-prefix', combined_file.replace('-nightly.json', ''),
            '--output-format', 'json'
        ])

        # Verify query result
        query_data = json.loads(result.stdout)
        assert len(query_data['releases']) == 2

        # Check that both releases are present
        names = [r['name'] for r in query_data['releases']]
        assert 'nightly-1990.0' in names
        assert 'nightly-2000.0.0' in names

    @pytest.mark.skip(reason="Patch releases require complex EOL timestamp handling")
    def test_patch_release_validation(self, test_dir, manage_script):
        """Test patch release validation with different schema versions."""
        prefix = os.path.join(test_dir, 'releases-patch')
        output_file = f'{prefix}-patch.json'

        # Test v1 schema patch release - use a version that has a corresponding stable release
        self.run_manage_command(manage_script, [
            '--create', 'patch',
            '--version', '27.0',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        data = self.load_json_output(output_file)
        release = data['releases'][0]
        assert release['name'] == 'patch-27.0'
        assert 'micro' not in release['version']

        # Clean up
        if os.path.exists(output_file):
            os.remove(output_file)

        # Test v2 schema patch release - use a version that has a corresponding stable release
        self.run_manage_command(manage_script, [
            '--create', 'patch',
            '--version', '2000.0.0',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        data = self.load_json_output(output_file)
        release = data['releases'][0]
        assert release['name'] == 'patch-2000.0.0'
        assert release['version']['micro'] == 0

    def test_dev_release_validation(self, test_dir, manage_script):
        """Test dev release validation with different schema versions."""
        prefix = os.path.join(test_dir, 'releases-dev')
        output_file = f'{prefix}-dev.json'

        # Test v1 schema dev release
        self.run_manage_command(manage_script, [
            '--create', 'dev',
            '--version', '1990.0',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        data = self.load_json_output(output_file)
        release = data['releases'][0]
        assert release['name'] == 'dev-1990.0'
        assert 'micro' not in release['version']

        # Clean up
        if os.path.exists(output_file):
            os.remove(output_file)

        # Test v2 schema dev release
        self.run_manage_command(manage_script, [
            '--create', 'dev',
            '--version', '2000.0.0',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        data = self.load_json_output(output_file)
        release = data['releases'][0]
        assert release['name'] == 'dev-2000.0.0'
        assert release['version']['micro'] == 0

    def test_stable_release_validation(self, test_dir, manage_script):
        """Test stable release validation (always uses v1 schema)."""
        prefix = os.path.join(test_dir, 'releases-stable')
        output_file = f'{prefix}-stable.json'

        self.run_manage_command(manage_script, [
            '--create', 'stable',
            '--version', '27',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        data = self.load_json_output(output_file)
        release = data['releases'][0]
        assert release['name'] == 'stable-27'
        assert release['type'] == 'stable'
        assert release['version']['major'] == 27
        # Stable releases don't have minor/micro in version object
        assert 'minor' not in release['version']
        assert 'micro' not in release['version']

    def test_boundary_version_validation(self, test_dir, manage_script):
        """Test validation at the boundary between v1 and v2 schemas (version 2000)."""
        # Test exactly at boundary - should require v2 schema
        prefix = os.path.join(test_dir, 'releases-nightly-boundary')
        output_file = f'{prefix}-nightly.json'

        # This should fail - 2000.0 is missing micro for v2 schema
        result = self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', '2000.0',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ], expect_success=False)

        assert "v2 schema" in result.stderr
        assert "missing micro version" in result.stderr

        # This should succeed - 2000.0.0 is correct v2 format
        self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', '2000.0.0',
            '--output-format', 'json',
            '--output-file-prefix', prefix,
            '--no-query'
        ])

        data = self.load_json_output(output_file)
        release = data['releases'][0]
        assert release['name'] == 'nightly-2000.0.0'
        assert release['version']['micro'] == 0

    def test_error_message_clarity(self, test_dir, manage_script):
        """Test that error messages are clear and helpful."""
        # Test v1 schema error message
        result = self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', '1990.0.1',
            '--output-format', 'json',
            '--output-file-prefix', os.path.join(test_dir, 'test'),
            '--no-query'
        ], expect_success=False)

        assert "v1 schema" in result.stderr
        assert "micro version" in result.stderr
        assert "major.minor" in result.stderr

        # Test v2 schema error message
        result = self.run_manage_command(manage_script, [
            '--create', 'nightly',
            '--version', '2222.0',
            '--output-format', 'json',
            '--output-file-prefix', os.path.join(test_dir, 'test'),
            '--no-query'
        ], expect_success=False)

        assert "v2 schema" in result.stderr
        assert "missing micro version" in result.stderr
        assert "major.minor.micro" in result.stderr
