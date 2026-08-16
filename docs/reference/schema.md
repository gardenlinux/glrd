---
title: "GLRD Release Schema"
description: "JSON schema reference for Garden Linux Release Database (GLRD) release types: major, minor, nightly, dev, and next."
github_org: gardenlinux
github_repo: glrd
github_source_path: docs/reference/schema.md
github_target_path: docs/reference/supporting_tools/glrd/schema.md
related_topics:
  - /reference/supporting_tools/glrd/
  - /reference/supporting_tools/glrd/cli.md
  - /reference/supporting_tools/glrd/schema.md
  - /how-to/glrd/run-glrd.md
  - /how-to/glrd/query-releases.md
  - /how-to/glrd/manage-releases.md
  - /explanation/glrd-release-lifecycle.md
---

# GLRD Release Schema

The Garden Linux Release Database (GLRD) uses structured JSON schemas to represent different types of releases. The five release types are: `major`, `minor`, `nightly`, `dev`, and `next`. Each type has specific required fields that capture version, lifecycle, and build information.

## Versioning scheme

Garden Linux [introduced semantic versioning](https://github.com/gardenlinux/gardenlinux/issues/3069) starting at major version `2017`. GLRD supports both versioning schemes based on the major version number:

- **v1 — versions < 2017.0.0**: Use the `major.minor` format (for example, `27.0`, `1592.6`).
- **v2 — versions ≥ 2017.0.0**: Use the `major.minor.patch` format (for example, `2017.0.0`, `2222.1.5`).

The schema variant is selected automatically based on the `version.major` field value.

## Major releases

[Major releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#major-releases) are long-term supported releases.

### Schema fields

| Field                          | Type          | Required | Description                                      |
| ------------------------------ | ------------- | -------- | ------------------------------------------------ |
| `name`                         | string        | yes      | Release name, for example `major-1312`.          |
| `type`                         | `"major"`     | yes      | Release type discriminator.                      |
| `version.major`                | integer       | yes      | Major version number, for example `1312`.        |
| `lifecycle.released.isodate`   | string (date) | yes      | Release date in `YYYY-MM-DD` format.             |
| `lifecycle.released.timestamp` | integer       | yes      | Unix timestamp of the release date.              |
| `lifecycle.extended.isodate`   | string (date) | yes      | Extended maintenance start date.                 |
| `lifecycle.extended.timestamp` | integer       | yes      | Unix timestamp of the extended maintenance date. |
| `lifecycle.eol.isodate`        | string (date) | yes      | End-of-life date.                                |
| `lifecycle.eol.timestamp`      | integer       | yes      | Unix timestamp of the end-of-life date.          |

## Minor releases

[Minor releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#minor-releases) are patch updates delivered during the standard and extended maintenance periods of a major release.

### Schema fields

| Field                          | Type             | Required | Description                                                                     |
| ------------------------------ | ---------------- | -------- | ------------------------------------------------------------------------------- |
| `name`                         | string           | yes      | Release name, for example `minor-1312.1` (v1) or `minor-2017.0.0` (v2).         |
| `type`                         | `"minor"`        | yes      | Release type discriminator.                                                     |
| `version.major`                | integer          | yes      | Major version number.                                                           |
| `version.minor`                | integer          | yes      | Minor version number.                                                           |
| `version.patch`                | integer          | v2 only  | Patch version number. Only present for versions ≥ 2017.0.0.                     |
| `lifecycle.released.isodate`   | string (date)    | yes      | Release date.                                                                   |
| `lifecycle.released.timestamp` | integer          | yes      | Unix timestamp of the release date.                                             |
| `lifecycle.eol.isodate`        | string (date)    | yes      | End-of-life date.                                                               |
| `lifecycle.eol.timestamp`      | integer          | yes      | Unix timestamp of the end-of-life date.                                         |
| `git.commit`                   | string           | yes      | Full 40-character SHA-1 git commit hash.                                        |
| `git.commit_short`             | string           | yes      | Short git commit hash (7–8 characters).                                         |
| `github.release`               | URI string       | yes      | URL to the GitHub release page.                                                 |
| `flavors`                      | array of strings | yes      | List of build flavor identifiers included in the release.                       |
| `attributes.source_repo`       | boolean          | yes      | Whether the release has Debian source repositories available (default: `true`). |

## Nightly releases

[Nightly releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#nightly-releases) are automated builds generated every night from the latest state of the codebase.

### Schema fields

| Field                          | Type             | Required | Description                                                                 |
| ------------------------------ | ---------------- | -------- | --------------------------------------------------------------------------- |
| `name`                         | string           | yes      | Release name, for example `nightly-1312.0` (v1) or `nightly-2017.0.0` (v2). |
| `type`                         | `"nightly"`      | yes      | Release type discriminator.                                                 |
| `version.major`                | integer          | yes      | Major version number.                                                       |
| `version.minor`                | integer          | yes      | Minor version number.                                                       |
| `version.patch`                | integer          | v2 only  | Patch version number. Only present for versions ≥ 2017.0.0.                 |
| `lifecycle.released.isodate`   | string (date)    | yes      | Build date.                                                                 |
| `lifecycle.released.timestamp` | integer          | yes      | Unix timestamp of the build date.                                           |
| `git.commit`                   | string           | yes      | Full 40-character SHA-1 git commit hash.                                    |
| `git.commit_short`             | string           | yes      | Short git commit hash.                                                      |
| `flavors`                      | array of strings | yes      | List of build flavor identifiers.                                           |
| `attributes.source_repo`       | boolean          | yes      | Whether Debian source repositories are available (default: `true`).         |

## Development releases

Development releases are used for testing and development purposes. They represent the latest changes that may not yet be included in a major or minor release, and can be created manually by developers.

### Schema fields

| Field                          | Type             | Required | Description                                                         |
| ------------------------------ | ---------------- | -------- | ------------------------------------------------------------------- |
| `name`                         | string           | yes      | Release name, for example `dev-1312.0` (v1) or `dev-2017.0.0` (v2). |
| `type`                         | `"dev"`          | yes      | Release type discriminator.                                         |
| `version.major`                | integer          | yes      | Major version number.                                               |
| `version.minor`                | integer          | yes      | Minor version number.                                               |
| `version.patch`                | integer          | v2 only  | Patch version number. Only present for versions ≥ 2017.0.0.         |
| `lifecycle.released.isodate`   | string (date)    | yes      | Build date.                                                         |
| `lifecycle.released.timestamp` | integer          | yes      | Unix timestamp of the build date.                                   |
| `git.commit`                   | string           | yes      | Full 40-character SHA-1 git commit hash.                            |
| `git.commit_short`             | string           | yes      | Short git commit hash.                                              |
| `flavors`                      | array of strings | yes      | List of build flavor identifiers.                                   |
| `attributes.source_repo`       | boolean          | yes      | Whether Debian source repositories are available (default: `true`). |

## Next release

The [next release](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#next-release) represents the projected upcoming major release. Only one `next` entry exists at any time.

### Schema fields

| Field                          | Type          | Required | Description                                                |
| ------------------------------ | ------------- | -------- | ---------------------------------------------------------- |
| `name`                         | `"next"`      | yes      | Always the literal string `next`.                          |
| `type`                         | `"next"`      | yes      | Release type discriminator.                                |
| `version.major`                | `"next"`      | yes      | Always the literal string `next`.                          |
| `lifecycle.released.isodate`   | string (date) | yes      | Projected release date.                                    |
| `lifecycle.released.timestamp` | integer       | yes      | Unix timestamp of the projected release date.              |
| `lifecycle.extended.isodate`   | string (date) | yes      | Projected extended maintenance start date.                 |
| `lifecycle.extended.timestamp` | integer       | yes      | Unix timestamp of the projected extended maintenance date. |
| `lifecycle.eol.isodate`        | string (date) | yes      | Projected end-of-life date.                                |
| `lifecycle.eol.timestamp`      | integer       | yes      | Unix timestamp of the projected end-of-life date.          |

## Related topics

<RelatedTopics />
