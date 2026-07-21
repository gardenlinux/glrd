---
title: "GLRD Release Lifecycle"
description: "Explains lifecycle dependencies between major and minor releases, default date calculations, nightly and dev date rules, and the GLRD versioning scheme."
github_org: gardenlinux
github_repo: glrd
github_source_path: docs/explanation/release-lifecycle.md
github_target_path: docs/explanation/glrd-release-lifecycle.md
related_topics:
  - /reference/supporting_tools/glrd/
  - /reference/supporting_tools/glrd/cli.md
  - /reference/supporting_tools/glrd/schema.md
  - /how-to/releases/glrd/
  - /how-to/releases/glrd/run-glrd.md
  - /how-to/releases/glrd/query-releases.md
  - /how-to/releases/glrd/manage-releases.md
  - /explanation/glrd-release-lifecycle.md
---

# GLRD Release Lifecycle

This page explains the lifecycle model used by the Garden Linux Release Database (GLRD): why lifecycle phases are structured the way they are, how dates are calculated by default, and how the versioning scheme works.

## Lifecycle phases

Every release in GLRD has a `lifecycle` object. The phases present depend on the release type:

| Phase      | Present for types        | Meaning                                                            |
| ---------- | ------------------------ | ------------------------------------------------------------------ |
| `released` | all                      | The date the release was published.                                |
| `extended` | `major`, `next`          | The date extended maintenance begins (after standard maintenance). |
| `eol`      | `major`, `next`, `minor` | The date support ends entirely.                                    |

`nightly` and `dev` releases do not have `extended` or `eol` phases because they are not supported beyond their immediate build date.

## Default major dates

When you create a major release without explicitly setting `extended` or `eol` dates, GLRD calculates defaults based on the [Garden Linux Release Plan](/reference/releases/release-lifecycle.md):

- **`extended`** = `released` date + 6 months
- **`eol`** = `released` date + 9 months

**Example — `major-1443`:**

| Phase      | Date                    |
| ---------- | ----------------------- |
| `released` | 2024-03-13              |
| `extended` | 2024-09-13 (+ 6 months) |
| `eol`      | 2025-01-13 (+ 9 months) |

You can always override the calculated defaults by passing `--lifecycle-extended-isodatetime` and `--lifecycle-eol-isodatetime` to `glrd-manage --create`.

## Major and minor release dependencies

There is a dependency between the `lifecycle.eol` fields of major and minor releases within the same major version:

- **Intermediate minor releases**: The `eol` of each minor release is set to the `released` date of the next minor release in the same major series. This means support for a given minor ends when the next patch is available.
- **Latest minor release**: The `eol` of the most recent minor release always matches the `eol` of the parent major release. This ensures the final patch remains supported until the major version reaches end-of-life.
- **Major release `eol`**: Marks the end of support for the entire major version, including all its minor releases.

When you create a new minor release with `glrd-manage --create minor`, the previous minor release's `eol` is automatically updated to the new minor release's `released` date.

:::info Note on the extended phase
The `extended` lifecycle field applies to major releases only. It has no direct technical effect on minor releases and is an administrative date that tracks when extended maintenance begins for the parent major version.
:::

**Example — `major-1312` series:**

| Release        | `released` | `eol`      | Reason                          |
| -------------- | ---------- | ---------- | ------------------------------- |
| `major-1312`   | 2023-11-16 | 2024-08-03 | Major EOL                       |
| `minor-1312.1` | 2023-11-23 | 2024-01-15 | Next minor release date         |
| `minor-1312.2` | 2024-01-15 | 2024-02-14 | Next minor release date         |
| `minor-1312.7` | 2024-07-03 | 2024-08-03 | Inherits major EOL (last minor) |

## Nightly and development release dates

`nightly` and `dev` releases only carry a `released` date. They have no `extended` or `eol` phase because:

- Nightly builds are ephemeral: each nightly is superseded by the next nightly run.
- Development releases are manual snapshots for testing; they are not formally supported.

## Versioning scheme

Garden Linux [introduced semantic versioning](https://github.com/gardenlinux/gardenlinux/issues/3069) starting at major version `2017`. GLRD stores both pre- and post-threshold releases and selects the correct schema automatically:

| Scheme | Applies to   | Version format      | Example                |
| ------ | ------------ | ------------------- | ---------------------- |
| v1     | major < 2017 | `major.minor`       | `1592.6`, `27.0`       |
| v2     | major ≥ 2017 | `major.minor.patch` | `2017.0.0`, `2222.1.5` |

The threshold is defined as `V2_SCHEMA_THRESHOLD = 2017` in the GLRD codebase (`glrd/util.py`). Any release with a `version.major` value of 2017 or higher uses the v2 schema and requires the `patch` field in `version` objects for `minor`, `nightly`, and `dev` releases.

For `major` and `next` releases, the version only ever stores `major`; the distinction between v1 and v2 does not affect their schema shape.

<RelatedTopics />
