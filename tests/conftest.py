"""
Pytest configuration and fixtures for GLRD tests.
"""

import os
import tempfile
import shutil
import pytest
from pathlib import Path


@pytest.fixture
def test_dir():
    """Create a temporary directory for test files."""
    test_dir = tempfile.mkdtemp(prefix='glrd_test_')
    yield test_dir
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)


@pytest.fixture
def manage_script():
    """Path to the manage.py script."""
    script_path = Path(__file__).parent.parent / "glrd" / "manage.py"
    assert script_path.exists(), f"manage.py not found at {script_path}"
    return str(script_path)


@pytest.fixture
def query_script():
    """Path to the query.py script."""
    script_path = Path(__file__).parent.parent / "glrd" / "query.py"
    assert script_path.exists(), f"query.py not found at {script_path}"
    return str(script_path)


@pytest.fixture
def glrd_script():
    """Path to the glrd script (query.py)."""
    script_path = Path(__file__).parent.parent / "glrd" / "query.py"
    assert script_path.exists(), f"query.py not found at {script_path}"
    return str(script_path)
