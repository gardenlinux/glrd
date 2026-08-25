"""
Unit tests for OCI URL generation in glrd.query.

Covers:
- get_container_registry: registry selection by release type
- get_oci_url: top-level OCI URL for a release
- prepare_oci_flavor_url: per-flavor OCI URL for container and bare platforms
"""

import pytest
from glrd.query import get_container_registry, get_oci_url, prepare_oci_flavor_url


@pytest.mark.unit
class TestGetContainerRegistry:
    def test_nightly_returns_nightly_registry(self):
        assert get_container_registry("nightly") == "ghcr.io/gardenlinux/nightly"

    def test_minor_returns_minor_registry(self):
        assert get_container_registry("minor") == "ghcr.io/gardenlinux/gardenlinux"

    def test_dev_returns_minor_registry(self):
        assert get_container_registry("dev") == "ghcr.io/gardenlinux/gardenlinux"

    def test_major_returns_minor_registry(self):
        assert get_container_registry("major") == "ghcr.io/gardenlinux/gardenlinux"

    def test_none_returns_minor_registry(self):
        assert get_container_registry(None) == "ghcr.io/gardenlinux/gardenlinux"


@pytest.mark.unit
class TestGetOciUrl:
    def test_minor_release_oci_url(self):
        release = {"type": "minor", "version": {"major": 2017, "minor": 0, "patch": 0}}
        assert get_oci_url(release) == "ghcr.io/gardenlinux/gardenlinux:2017.0.0"

    def test_nightly_release_oci_url(self):
        release = {"type": "nightly", "version": {"major": 1990, "minor": 0}}
        assert get_oci_url(release) == "ghcr.io/gardenlinux/nightly:1990.0"


@pytest.mark.unit
class TestPrepareOciFlavorUrl:
    def test_container_flavor_minor(self):
        result = prepare_oci_flavor_url(
            "container-amd64", "2017.0.0", "container", "minor"
        )
        assert result == {"oci": "ghcr.io/gardenlinux/gardenlinux:2017.0.0"}

    def test_container_flavor_nightly(self):
        result = prepare_oci_flavor_url(
            "container-amd64", "1990.0", "container", "nightly"
        )
        assert result == {"oci": "ghcr.io/gardenlinux/nightly:1990.0"}

    def test_bare_flavor_minor(self):
        result = prepare_oci_flavor_url("bare-amd64", "2017.0.0", "bare", "minor")
        assert result == {"oci": "ghcr.io/gardenlinux/gardenlinux/bare:2017.0.0"}

    def test_bare_flavor_nightly(self):
        result = prepare_oci_flavor_url("bare-amd64", "1990.0", "bare", "nightly")
        assert result == {"oci": "ghcr.io/gardenlinux/nightly/bare:1990.0"}
