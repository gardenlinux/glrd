"""
Unified schema definitions for Garden Linux releases.

Schema v1: versions < 2017.0.0 (no patch field required)
Schema v2: versions >= 2017.0.0 (patch field required for minor, nightly, dev)

This module generates both schemas from shared building blocks to eliminate
code duplication between the previous schema_v1.py and schema_v2.py files.
"""

from copy import deepcopy


def _build_lifecycle_required_fields(release_type: str) -> list:
    if release_type in ("next", "major"):
        return ["released", "extended", "eol"]
    elif release_type == "minor":
        return ["released", "eol"]
    else:
        return ["released"]


def _build_version_properties(include_patch: bool) -> dict:
    props = {"major": {"type": "integer"}, "minor": {"type": "integer"}}
    if include_patch:
        props["patch"] = {"type": "integer"}
    return props


def _build_version_required(include_patch: bool) -> list:
    if include_patch:
        return ["major", "minor", "patch"]
    else:
        return ["major", "minor"]


def _build_release_schema(
    release_type: str,
    include_patch: bool,
    include_github: bool = False,
) -> dict:
    lifecycle_props = {
        "released": {
            "type": "object",
            "properties": {
                "isodate": {"type": "string", "format": "date"},
                "timestamp": {"type": "integer"},
            },
            "required": ["isodate", "timestamp"],
        }
    }

    if release_type in ("next", "major"):
        lifecycle_props["extended"] = {
            "type": "object",
            "properties": {
                "isodate": {"type": ["string"], "format": "date"},
                "timestamp": {"type": ["integer"]},
            },
        }
        lifecycle_props["eol"] = {
            "type": "object",
            "properties": {
                "isodate": {"type": ["string"], "format": "date"},
                "timestamp": {"type": ["integer"]},
            },
        }
    elif release_type == "minor":
        lifecycle_props["eol"] = {
            "type": "object",
            "properties": {
                "isodate": {"type": ["string"], "format": "date"},
                "timestamp": {"type": ["integer"]},
            },
        }

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": [release_type]},
            "version": {
                "type": "object",
                "properties": _build_version_properties(include_patch),
                "required": _build_version_required(include_patch),
            },
            "lifecycle": {
                "type": "object",
                "properties": lifecycle_props,
                "required": _build_lifecycle_required_fields(release_type),
            },
        },
        "required": ["name", "type", "version", "lifecycle"],
    }

    if release_type in ("minor", "nightly", "dev"):
        git_props = {
            "commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
            "commit_short": {"type": "string", "pattern": "^[0-9a-f]{7,8}$"},
        }
        schema["properties"]["git"] = {"type": "object", "properties": git_props, "required": ["commit", "commit_short"]}
        schema["required"].append("git")

        schema["properties"]["flavors"] = {"type": "array", "items": {"type": "string"}}
        schema["properties"]["attributes"] = {
            "type": "object",
            "properties": {"source_repo": {"type": "boolean", "default": True}},
            "required": ["source_repo"],
        }

    if include_github:
        schema["properties"]["github"] = {
            "type": "object",
            "properties": {"release": {"type": "string", "format": "uri"}},
            "required": ["release"],
        }
        schema["required"].append("github")

    return schema


def _build_next_major_schema(release_type: str) -> dict:
    lifecycle_props = {
        "released": {
            "type": "object",
            "properties": {
                "isodate": {"type": "string", "format": "date"},
                "timestamp": {"type": "integer"},
            },
            "required": ["isodate", "timestamp"],
        },
        "extended": {
            "type": "object",
            "properties": {
                "isodate": {"type": ["string"], "format": "date"},
                "timestamp": {"type": ["integer"]},
            },
        },
        "eol": {
            "type": "object",
            "properties": {
                "isodate": {"type": ["string"], "format": "date"},
                "timestamp": {"type": ["integer"]},
            },
        },
    }

    return {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": [release_type]},
            "version": {
                "type": "object",
                "properties": {"major": {"enum": ["next"]} if release_type == "next" else {"major": {"type": "integer"}}},
                "required": ["major"],
            },
            "lifecycle": {
                "type": "object",
                "properties": lifecycle_props,
                "required": ["released", "extended", "eol"],
            },
        },
        "required": ["name", "type", "version", "lifecycle"],
    }


def _generate_schema(include_patch: bool) -> dict:
    schema = {}
    schema["next"] = _build_next_major_schema("next")
    schema["major"] = _build_next_major_schema("major")
    schema["minor"] = _build_release_schema("minor", include_patch, include_github=True)
    schema["nightly"] = _build_release_schema("nightly", include_patch)
    schema["dev"] = _build_release_schema("dev", include_patch)
    return schema


SCHEMA_V1 = _generate_schema(include_patch=False)
SCHEMA_V2 = _generate_schema(include_patch=True)
