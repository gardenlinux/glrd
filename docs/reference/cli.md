---
title: "GLRD CLI Reference"
description: "Complete flag and option reference for the glrd and glrd-manage command-line tools."
github_org: gardenlinux
github_repo: glrd
github_source_path: docs/reference/cli.md
github_target_path: docs/reference/supporting_tools/glrd/cli.md
related_topics:
  - /reference/supporting_tools/glrd/
  - /reference/supporting_tools/glrd/cli.md
  - /reference/supporting_tools/glrd/schema.md
  - /how-to/glrd/run-glrd.md
  - /how-to/glrd/query-releases.md
  - /how-to/glrd-manage-releases.md
  - /explanation/glrd-release-lifecycle.md
---

# GLRD CLI Reference

This page documents all flags and options for the `glrd` and `glrd-manage` command-line tools.

## `glrd`

`glrd` queries the Garden Linux Release Database (GLRD) and outputs release information in various formats.

### Usage

```text
usage: glrd [-h] [--input-format {yaml,json}]
            [--input-file-prefix INPUT_FILE_PREFIX] [--input-type {file,url}]
            [--input-url INPUT_URL] [--no-input-split]
            [--output-format {json,yaml,markdown,mermaid_gantt,shell}]
            [--output-description OUTPUT_DESCRIPTION] [--active] [--archived]
            [--latest] [--type TYPE] [--version VERSION] [--fields FIELDS]
            [--no-header] [-V]

Process and filter releases data from a file or URL.
```

### Options

| Flag                                                       | Default                 | Description                                                                                                                                                   |
| ---------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `-h`, `--help`                                             | —                       | Show the help message and exit.                                                                                                                               |
| `--input-format {yaml,json}`                               | `json`                  | Input format for release data.                                                                                                                                |
| `--input-file-prefix PREFIX`                               | `releases`              | Prefix used to locate input files when `--input-type file` is set.                                                                                            |
| `--input-type {file,url}`                                  | `url`                   | Source of release data. Use `file` to read local files; use `url` to query the S3 endpoint.                                                                   |
| `--input-url URL`                                          | gardenlinux-glrd S3 URL | Base URL for release data. Only used when `--input-type url`.                                                                                                 |
| `--no-input-split`                                         | —                       | Read a single input file instead of separate `*-nightly` and `*-dev` files.                                                                                   |
| `--output-format {json,yaml,markdown,mermaid_gantt,shell}` | `shell`                 | Output format for results.                                                                                                                                    |
| `--output-description TEXT`                                | `Garden Linux Releases` | Description string included in outputs that support it (for example, Mermaid Gantt chart titles).                                                             |
| `--active`                                                 | —                       | Show only currently active releases (end-of-life date in the future).                                                                                         |
| `--archived`                                               | —                       | Show only archived releases (end-of-life date in the past).                                                                                                   |
| `--latest`                                                 | —                       | Show the single latest active `major.minor.patch` release.                                                                                                    |
| `--type TYPE`                                              | `major,minor`           | Comma-separated list of release types to include. Valid values: `major`, `minor`, `nightly`, `dev`, `next`.                                                   |
| `--version VERSION`                                        | —                       | Filter by a specific version. Accepts `major` (for example, `1312`), `major.minor` (for example, `1312.0`), or `major.minor.patch` (for example, `1312.0.0`). |
| `--fields FIELDS`                                          | see below               | Comma-separated list of output fields.                                                                                                                        |
| `--no-header`                                              | —                       | Omit the column header row in shell output.                                                                                                                   |
| `-V`                                                       | —                       | Show the program version number and exit.                                                                                                                     |

### Default output fields

When `--fields` is not specified, `glrd` outputs these columns:

```text
Name,Version,Type,GitCommitShort,ReleaseDate,ExtendedMaintenance,EndOfMaintenance
```

### Available output fields

| Field name             | Description                                                |
| ---------------------- | ---------------------------------------------------------- |
| `Name`                 | Release name (for example, `minor-1592.6`).                |
| `Version`              | Version string (for example, `1592.6`).                    |
| `Type`                 | Release type (`major`, `minor`, `nightly`, `dev`, `next`). |
| `GitCommit`            | Full 40-character git commit SHA.                          |
| `GitCommitShort`       | Short git commit hash.                                     |
| `ReleaseDate`          | Release date in `YYYY-MM-DD` format.                       |
| `ReleaseTime`          | Release Unix timestamp.                                    |
| `ExtendedMaintenance`  | Extended maintenance start date, or `N/A`.                 |
| `EndOfMaintenance`     | End-of-life date.                                          |
| `Flavors`              | Comma-separated list of build flavors.                     |
| `OCI`                  | OCI container image reference.                             |
| `AttributesSourceRepo` | Whether Debian source repositories are available.          |

---

## `glrd-manage`

`glrd-manage` creates, updates, and manages Garden Linux release entries in GLRD.

### Usage

```text
usage: glrd-manage [-h] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                   [--input-file INPUT_FILE] [--input-type {file,url}]
                   [--input-url INPUT_URL]
                   [--input-file-prefix INPUT_FILE_PREFIX]
                   [--query-input-format {yaml,json}]
                   [--output-format {yaml,json}]
                   [--output-file-prefix OUTPUT_FILE_PREFIX]
                   [--s3-bucket-name S3_BUCKET_NAME]
                   [--s3-bucket-region S3_BUCKET_REGION]
                   [--s3-bucket-prefix S3_BUCKET_PREFIX] [--delete DELETE]
                   [--update UPDATE]
                   [--create-initial-releases CREATE_INITIAL_RELEASES]
                   [--create CREATE] [--version VERSION] [--commit COMMIT]
                   [--no-flavors]
                   [--lifecycle-released-isodatetime LIFECYCLE_RELEASED_ISODATETIME]
                   [--lifecycle-extended-isodatetime LIFECYCLE_EXTENDED_ISODATETIME]
                   [--lifecycle-eol-isodatetime LIFECYCLE_EOL_ISODATETIME]
                   [--no-query] [--input-stdin] [--input] [--no-output-split]
                   [--s3-create-bucket] [--s3-update] [--output-all]
                   [--input-all] [-V]

Manage Garden Linux releases data.
```

### Options

#### General

| Flag                                              | Default | Description                               |
| ------------------------------------------------- | ------- | ----------------------------------------- |
| `-h`, `--help`                                    | —       | Show the help message and exit.           |
| `--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}` | —       | Set the logging verbosity level.          |
| `-V`                                              | —       | Show the program version number and exit. |

#### Input

| Flag                               | Default                 | Description                                                                                                 |
| ---------------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| `--input-file FILE`                | `releases-input.yaml`   | Input file path for `--input` mode.                                                                         |
| `--input-type {file,url}`          | `url`                   | Source for querying existing releases when `--no-query` is not set. Use `file` for fully offline operation. |
| `--input-url URL`                  | gardenlinux-glrd S3 URL | Base URL for querying existing releases. Only used with `--input-type url`.                                 |
| `--input-file-prefix PREFIX`       | `releases`              | File prefix for querying existing releases from local files. Only used with `--input-type file`.            |
| `--query-input-format {yaml,json}` | `json`                  | Format of existing release data queried when not using `--no-query`.                                        |
| `--input-stdin`                    | —                       | Read a single release entry from standard input (JSON).                                                     |
| `--input`                          | —                       | Read release data from `--input-file`.                                                                      |
| `--input-all`                      | —                       | Upload all local release files to S3.                                                                       |

#### Output

| Flag                          | Default    | Description                                                                   |
| ----------------------------- | ---------- | ----------------------------------------------------------------------------- |
| `--output-format {yaml,json}` | `yaml`     | Output format for generated release files.                                    |
| `--output-file-prefix PREFIX` | `releases` | Prefix for generated output files.                                            |
| `--no-output-split`           | —          | Write a single output file instead of separate `*-nightly` and `*-dev` files. |
| `--output-all`                | —          | Download all release files from S3 to local disk.                             |

#### S3 configuration

| Flag                        | Default            | Description                                                                      |
| --------------------------- | ------------------ | -------------------------------------------------------------------------------- |
| `--s3-bucket-name NAME`     | `gardenlinux-glrd` | Name of the Amazon S3 bucket.                                                    |
| `--s3-bucket-region REGION` | `eu-central-1`     | AWS region of the S3 bucket.                                                     |
| `--s3-bucket-prefix PREFIX` | _(empty)_          | Object key prefix within the S3 bucket.                                          |
| `--s3-create-bucket`        | —                  | Create the S3 bucket if it does not exist.                                       |
| `--s3-update`               | —                  | Push generated files to S3. Without this flag, changes are written locally only. |

#### Release actions

| Flag                             | Format                                                        | Description                                                                                         |
| -------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `--create-initial-releases LIST` | `major,minor,nightly`                                         | Fetch release history from GitHub and generate initial release data for the specified types.        |
| `--create TYPE`                  | `major\|minor\|nightly\|dev\|next`                            | Create a new release of the given type using the current timestamp and git state.                   |
| `--update RELEASE`               | `type-major`, `type-major.minor`, or `type-major.minor.patch` | Update lifecycle fields or commit hash on an existing release. Requires at least one modifier flag. |
| `--delete RELEASE`               | `type-major.minor` or `type-major.minor.patch`                | Delete a release by name. Requires `--s3-update`.                                                   |

#### Release modifiers (used with `--create` or `--update`)

| Flag                                        | Format                               | Description                                                                                                                                                 |
| ------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--version VERSION`                         | `major.minor` or `major.minor.patch` | Override the version. Use `major.minor` for versions < 2017.0.0; use `major.minor.patch` for versions ≥ 2017.0.0.                                           |
| `--commit HASH`                             | 40-character hex string              | Override the git commit hash. Valid for `minor`, `nightly`, and `dev` types only.                                                                           |
| `--no-flavors`                              | —                                    | Skip the Git clone and S3 lookup for flavor resolution. Useful for offline use and tests. Can also be set via the `GLRD_SKIP_FLAVORS` environment variable. |
| `--lifecycle-released-isodatetime DATETIME` | `YYYY-MM-DDTHH:MM:SS`                | Override the release date and time.                                                                                                                         |
| `--lifecycle-extended-isodatetime DATETIME` | `YYYY-MM-DDTHH:MM:SS`                | Override the extended maintenance date. Valid for `major` and `next` types only.                                                                            |
| `--lifecycle-eol-isodatetime DATETIME`      | `YYYY-MM-DDTHH:MM:SS`                | Override the end-of-life date. Valid for `next`, `major`, and `minor` types only.                                                                           |

#### Query control

| Flag         | Description                                                                                                                 |
| ------------ | --------------------------------------------------------------------------------------------------------------------------- |
| `--no-query` | Do not query existing releases before writing. Use with care — omitting the existing data can overwrite or delete releases. |

## Related topics

<RelatedTopics />
