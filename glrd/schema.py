"""
Unified schema definitions for Garden Linux releases.

Schema v1: versions < 2017.0.0 (no patch field required)
Schema v2: versions >= 2017.0.0 (patch field required for minor, nightly, dev)

Schema v2.1 is a backward-compatible evolution of v2 and the current default.
It adds an optional ``attributes`` object (including the optional ``lts`` flag)
to ``major`` and ``next`` releases. Because the new field is optional, all
existing v2 release data remains valid. The LTS semantics ("LTS applies from
major 1877 onwards") are enforced in the lifecycle/management logic, not by the
schema itself, so the schema only describes the optional field.

This module generates the schemas from shared building blocks to eliminate
code duplication between the previous schema_v1.py and schema_v2.py files.
"""


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
        schema["properties"]["git"] = {
            "type": "object",
            "properties": git_props,
            "required": ["commit", "commit_short"],
        }
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
                "properties": (
                    {"major": {"enum": ["next"]}}
                    if release_type == "next"
                    else {"major": {"type": "integer"}}
                ),
                "required": ["major"],
            },
            "lifecycle": {
                "type": "object",
                "properties": lifecycle_props,
                "required": ["released", "extended", "eol"],
            },
            "attributes": {
                "type": "object",
                "properties": {"lts": {"type": "boolean", "default": False}},
                "additionalProperties": True,
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

# Schema v2.1 is a backward-compatible superset of v2: the optional
# ``attributes.lts`` field on major/next releases is already part of the
# generated schema, so v2.1 is identical in structure to v2. It is exposed as a
# named alias and set as the default schema for new releases.
SCHEMA_V2_1 = SCHEMA_V2
SCHEMA_DEFAULT = SCHEMA_V2_1
