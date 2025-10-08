"""
Schema v2 for Garden Linux releases with versions >= 2017.0.0.
This schema version requires the patch field in version objects.
"""

# Schema v2 for releases that have patch field
SCHEMA_V2 = {
    "next": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["next"]},
            "version": {
                "type": "object",
                "properties": {"major": {"enum": ["next"]}},
                "required": ["major"],
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": "string",
                                "format": "date",
                            },
                            "timestamp": {"type": "integer"},
                        },
                        "required": ["isodate", "timestamp"],
                    },
                    "extended": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": ["string"],
                                "format": "date",
                            },
                            "timestamp": {"type": ["integer"]},
                        },
                    },
                    "eol": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": ["string"],
                                "format": "date",
                            },
                            "timestamp": {"type": ["integer"]},
                        },
                    },
                },
                "required": ["released", "extended", "eol"],
            },
        },
        "required": ["name", "type", "version", "lifecycle"],
    },
    "major": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["major"]},
            "version": {
                "type": "object",
                "properties": {"major": {"type": "integer"}},
                "required": ["major"],
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": "string",
                                "format": "date",
                            },
                            "timestamp": {"type": "integer"},
                        },
                        "required": ["isodate", "timestamp"],
                    },
                    "extended": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": ["string"],
                                "format": "date",
                            },
                            "timestamp": {"type": ["integer"]},
                        },
                    },
                    "eol": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": ["string"],
                                "format": "date",
                            },
                            "timestamp": {"type": ["integer"]},
                        },
                    },
                },
                "required": ["released", "extended", "eol"],
            },
        },
        "required": ["name", "type", "version", "lifecycle"],
    },
    "minor": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["minor"]},
            "version": {
                "type": "object",
                "properties": {
                    "major": {"type": "integer"},
                    "minor": {"type": "integer"},
                    "patch": {"type": "integer"},
                },
                "required": ["major", "minor", "patch"],
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": "string",
                                "format": "date",
                            },
                            "timestamp": {"type": "integer"},
                        },
                        "required": ["isodate", "timestamp"],
                    },
                    "eol": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": ["string"],
                                "format": "date",
                            },
                            "timestamp": {"type": ["integer"]},
                        },
                    },
                },
                "required": ["released", "eol"],
            },
            "git": {
                "type": "object",
                "properties": {
                    "commit": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{40}$",
                    },
                    "commit_short": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{7,8}$",
                    },
                },
                "required": ["commit", "commit_short"],
            },
            "github": {
                "type": "object",
                "properties": {"release": {"type": "string", "format": "uri"}},
                "required": ["release"],
            },
            "flavors": {"type": "array", "items": {"type": "string"}},
            "attributes": {
                "type": "object",
                "properties": {"source_repo": {"type": "boolean", "default": True}},
                "required": ["source_repo"],
            },
        },
        "required": [
            "name",
            "type",
            "version",
            "lifecycle",
            "git",
            "github",
        ],
    },
    "nightly": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["nightly"]},
            "version": {
                "type": "object",
                "properties": {
                    "major": {"type": "integer"},
                    "minor": {"type": "integer"},
                    "patch": {"type": "integer"},
                },
                "required": ["major", "minor", "patch"],
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": "string",
                                "format": "date",
                            },
                            "timestamp": {"type": "integer"},
                        },
                        "required": ["isodate", "timestamp"],
                    }
                },
                "required": ["released"],
            },
            "git": {
                "type": "object",
                "properties": {
                    "commit": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{40}$",
                    },
                    "commit_short": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{7,8}$",
                    },
                },
                "required": ["commit", "commit_short"],
            },
            "flavors": {"type": "array", "items": {"type": "string"}},
            "attributes": {
                "type": "object",
                "properties": {"source_repo": {"type": "boolean", "default": True}},
                "required": ["source_repo"],
            },
        },
        "required": ["name", "type", "version", "lifecycle", "git"],
    },
    "dev": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "type": {"enum": ["dev"]},
            "version": {
                "type": "object",
                "properties": {
                    "major": {"type": "integer"},
                    "minor": {"type": "integer"},
                    "patch": {"type": "integer"},
                },
                "required": ["major", "minor", "patch"],
            },
            "lifecycle": {
                "type": "object",
                "properties": {
                    "released": {
                        "type": "object",
                        "properties": {
                            "isodate": {
                                "type": "string",
                                "format": "date",
                            },
                            "timestamp": {"type": "integer"},
                        },
                        "required": ["isodate", "timestamp"],
                    }
                },
                "required": ["released"],
            },
            "git": {
                "type": "object",
                "properties": {
                    "commit": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{40}$",
                    },
                    "commit_short": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{7,8}$",
                    },
                },
                "required": ["commit", "commit_short"],
            },
            "flavors": {"type": "array", "items": {"type": "string"}},
            "attributes": {
                "type": "object",
                "properties": {"source_repo": {"type": "boolean", "default": True}},
                "required": ["source_repo"],
            },
        },
        "required": ["name", "type", "version", "lifecycle", "git"],
    },
}
