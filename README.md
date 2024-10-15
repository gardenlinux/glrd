# Garden Linux Release Database (GLRD)

This repository contains tooling and configuration to create the Garden Linux Release Database (GLRD), a system designed to manage and query release information for the Garden Linux distribution.

This repository contains these tools:

- **`glrd-create`**: A tool for generating and populating the GLRD with initial release data and for creating individual release entries.
- **`glrd`**: A command-line client for querying the GLRD to retrieve release information based on various criteria.
- **TODO: github action**: A github action for creating and querying GLRD entries.

## Table of Contents

- [Garden Linux Releases](#garden-linux-releases)
- [Overview of GLRD](#overview)
- [Release Schema](#release-schema)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [glrd-create](#glrd-create)
- [glrd](#glrd-1)
- [Container images](#container-images)
- [GitHub Action](#github-action)
- [Contributing](#contributing)
- [License](#license)

## Garden Linux Releases

For a general overview about Garden Linux releases and their lifecyle, have a look at the [Garden Linux Release Plan Overview](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md).

## Overview

The GLRD provides a structured way to store and access release data for Garden Linux, including different release types such as stable, patch, nightly, and development releases. It uses JSON and YAML formats to store release information and supports integration with AWS S3 for storage to host release data..

## Release Schema

The Garden Linux Release Database (GLRD) uses structured JSON schemas to represent different types of releases: **stable**, **patch**, **nightly**, and **development** releases. Each release type has specific fields that capture essential information about the release.

### Stable Releases

[Stable releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#stable-releases) are major releases that are supported over an extended period of time.

#### Schema Fields

- **`name`**: A string representing the release name (e.g., `release-1312`).
- **`type`**: `stable`.
- **`version`**:
  - **`major`**: An integer indicating the major version number (e.g. `1312`).
- **`lifecycle`**:
  - **`released`**:
    - **`isodate`**: The release date in ISO format (`YYYY-MM-DD`).
    - **`timestamp`**: The UNIX timestamp of the release date.
  - **`extended`**:
    - **`isodate`**: Optional extended maintenance date in ISO format.
    - **`timestamp`**: Optional UNIX timestamp for the extended maintenance date.
  - **`eol`**:
    - **`isodate`**: End-of-life date in ISO format.
    - **`timestamp`**: UNIX timestamp for the end-of-life date.

### Patch Releases

[Patch Releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#patches) are updates delivered during the standard and extended mainteannce periods of [Stable releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#stable-releases).

#### Schema Fields

- **`name`**: A string representing the release name (e.g., `release-1312.1`).
- **`type`**: `patch`.
- **`version`**:
  - **`major`**: An integer indicating the major version number (e.g. `1312`).
  - **`minor`**: An integer indicating the minor version number (e.g. `1`).
- **`lifecycle`**:
  - **`released`**:
    - **`isodate`**: The release date in ISO format.
    - **`timestamp`**: The UNIX timestamp of the release date.
  - **`eol`**:
    - **`isodate`**: End-of-life date in ISO format.
    - **`timestamp`**: UNIX timestamp for the end-of-life date.
- **`git`**:
  - **`commit`**: The full git commit hash associated with the release.
  - **`commit_short`**: The short git commit hash (first 7 characters).
- **`github`**:
  - **`release`**: The URL to the GitHub release page.

### Nightly Releases

[Nightly releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#nightly-releases) are automated builds that are generated every night, reflecting the latest state of the codebase.

#### Schema Fields

- **`name`**: A string representing the release name (e.g., `nightly-1312.0`).
- **`type`**: `nightly`.
- **`version`**:
  - **`major`**: An integer indicating the major version number.
  - **`minor`**: An integer indicating the minor version number.
- **`lifecycle`**:
  - **`released`**:
    - **`isodate`**: The release date in ISO format.
    - **`timestamp`**: The UNIX timestamp of the release date.
- **`git`**:
  - **`commit`**: The full git commit hash associated with the release.
  - **`commit_short`**: The short git commit hash.

### Development Releases

[Development releases](TODO: define and link) are used for testing and development purposes, representing the latest changes that may not yet be included in a stable or patch release. These can be manually created by developers.

#### Schema Fields

- **`name`**: A string representing the release name (e.g., `dev-1312.0`).
- **`type`**: `dev`.
- **`version`**:
  - **`major`**: An integer indicating the major version number.
  - **`minor`**: An integer indicating the minor version number.
- **`lifecycle`**:
  - **`released`**:
    - **`isodate`**: The release date in ISO format.
    - **`timestamp`**: The UNIX timestamp of the release date.
- **`git`**:
  - **`commit`**: The full git commit hash associated with the release.
  - **`commit_short`**: The short git commit hash.

### Lifecycle Dependencies

The lifecycle fields in the release schemas help track the release dates and end-of-life (EOL) dates for each release. There is a dependency between the `lifecycle` fields of **stable** and **patch** releases:

- **EOL of Patch Releases**: The `eol` date of a patch release is set to the `released` date of the next patch release. If there is no subsequent patch release, the `eol` date is aligned with the `eol` date of the corresponding stable release.
- **EOL of Latest Patch Release**: The latest patch release's `eol` date matches the `eol` date of the stable release.
- **EOL of Stable Releases**: The `eol` date for a stable release marks the end of support for that major version.

This ensures that all minor updates within a major release adhere to the same overall support timeline.

For example:

- **Stable Release `release-1312`**:
  - `released`: 2023-11-16
  - `extended`: 2024-05-03
  - `eol`: 2024-08-03
- **Patch Release `release-1312.1`**:
  - `released`: 2023-11-23
  - `eol`: 2024-01-15 (next patch release date)
- **Patch Release `release-1312.2`**:
  - `released`: 2024-01-15
  - `eol`: 2024-02-14 (next patch release date)
- ...
- **Patch Release `release-1312.7`**:
  - `released`: 2024-07-03
  - `eol`: 2024-08-03 (inherits from stable release eol)

In this example, the `eol` of `release-1312.1` is set to the `released` date of `release-1312.2`, and the `eol` of the latest patch release (`release-1312.7`) is set to the `eol` of the stable release (`release-1312`).

Please note that the `extended` lifecyle field is not taken into account for patch releases. This is simply an administrative date that has no technical implications.


## Prerequisites

- **Python 3.6+**

You can install the required Python packages using:

```bash
pip install -r requirements.txt
```

- **AWS CLI** configured with appropriate permissions if you plan to use S3 integration.
- **Git** and **GitHub CLI (gh)** installed and configured if you plan to generate release data from GitHub.

## Installation

Clone the repository and ensure that the scripts are executable:

```bash
git clone https://github.com/yourusername/gardenlinux-release-database.git
cd gardenlinux-release-database
chmod +x glrd-create glrd
```

## glrd-create

The `glrd-create` script is used to generate release data for Garden Linux. It can create initial releases by fetching data from GitHub, generate individual release entries, and manage release data files.

### Usage

```bash
./glrd-create --help
```

```
usage: glrd-create [-h]
                   [--generate-initial-releases GENERATE_INITIAL_RELEASES]
                   [--dev] [--nightly] [--stable] [--patch] [--input-stdin]
                   [--input] [--input-file INPUT_FILE]
                   [--output-file-prefix OUTPUT_FILE_PREFIX]
                   [--output-format {yaml,json}] [--no-output-split]
                   [--s3-bucket-name S3_BUCKET_NAME]
                   [--s3-bucket-prefix S3_BUCKET_PREFIX]
                   [--s3-bucket-region S3_BUCKET_REGION] [--s3-create-bucket]
                   [--s3-update]

Generate a file of the latest Garden Linux releases in YAML or JSON format.

options:
  -h, --help            show this help message and exit
  --generate-initial-releases GENERATE_INITIAL_RELEASES
                        Comma-separated list of initial releases to retrieve
                        and generate: 'stable,nightly'.
  --dev                 Generate a development release using the current
                        timestamp and git information.
  --nightly             Generate a nightly release using the current timestamp
                        and git information.
  --stable              Generate a stable release using the current timestamp
                        and git information.
  --patch               Generate a patch release using the current timestamp
                        and git information.
  --input-stdin         Process input from stdin (JSON data).
  --input               Process input from --input-file.
  --input-file INPUT_FILE
                        The name of the input file (default: releases-
                        input.yaml).
  --output-file-prefix OUTPUT_FILE_PREFIX
                        The prefix added to the output file (default:
                        releases).
  --output-format {yaml,json}
                        Output format: 'yaml' or 'json' (default: json).
  --no-output-split     Do not split Output into stable+patch and nightly.
                        Additional output-files *-nightly and *-dev will not
                        be created.
  --s3-bucket-name S3_BUCKET_NAME
                        Name of S3 bucket. Defaults to 'gardenlinux-releases'.
  --s3-bucket-prefix S3_BUCKET_PREFIX
                        Prefix inside S3 bucket. Defaults to ''.
  --s3-bucket-region S3_BUCKET_REGION
                        Name of S3 bucket Region. Defaults to 'eu-central-1'.
  --s3-create-bucket    Create an S3 bucket.
  --s3-update           Update (merge) the generated files with S3.
```

### Generate and populate initial release data

This will generate the following initial release data ...

- stable releases
- nightly releases
- releases from `releases-input.yaml` (contain manual lifecycle fields)

... and upload it to the default S3 bucket.

```
./glrd-create --generate-initial-releases stable,nightly --input --s3-update
```

### Generate/Update an arbitrary release from JSON data

This will generate/update a release from JSON data and upload it to the default S3 bucket.

```
echo '{
  "releases": [
    {
      "name": "release-1592.1",
      "type": "patch",
      "version": {
        "major": 1592,
        "minor": 1
      },
      "lifecycle": {
        "released": {
          "isodate": "2024-08-22",
          "timestamp": 1724277600
        },
        "eol": {
          "isodate": "2025-08-12",
          "timestamp": 1754949600
        }
      },
      "git": {
        "commit": "ec945aa995d0f08d64303ff6045b313b40b665fb",
        "commit_short": "ec945aa"
      },
      "github": {
        "release": "https://github.com/gardenlinux/gardenlinux/releases/tag/1592.1"
      }
    }
  ]
}' | ./glrd-create --input-stdin --s3-update
```

## glrd

The `glrd` script is a command-line utility for querying the GLRD. It allows you to filter and display release information based on various criteria.

### Usage

```bash
./glrd --help
```

```
usage: glrd [-h] [--input-format {yaml,json}]
            [--input-file-prefix INPUT_FILE_PREFIX] [--input-type {file,url}]
            [--input-url INPUT_URL] [--no-input-split]
            [--output-type {json,yaml,markdown,shell}] [--active] [--latest]
            [--type TYPE] [--version VERSION] [--fields FIELDS] [--no-header]

Process and filter releases data from a file or URL.

options:
  -h, --help            show this help message and exit
  --input-format {yaml,json}
                        Input format: 'yaml' or 'json' (default: json).
  --input-file-prefix INPUT_FILE_PREFIX
                        The prefix to get input files (default: releases).
  --input-type {file,url}
                        Specify if the input type (default: url).
  --input-url INPUT_URL
                        Input URL to the releases data. Defaults to
                        gardenlinux-releases S3 URL.
  --no-input-split      Do not split Input into stable+patch and nightly. No
                        additional input-files *-nightly and *-dev will be
                        parsed.
  --output-type {json,yaml,markdown,shell}
                        Output format: json, yaml, markdown, shell (default).
  --active              Show only active releases.
  --latest              Show the latest active major.minor release.
  --type TYPE           Filter by release types (comma-separated list,
                        default: stable,patch). E.g., --type
                        stable,patch,nightly,dev
  --version VERSION     Filter by a specific version (major or major.minor).
                        E.g., --version 1312 or --version 1312.0
  --fields FIELDS       Comma-separated list of fields to output. E.g.,
                        --fields "Name, Version, Type, Git Commit, Release
                        date, Extended maintenance, End of maintenance"
  --no-header           Omit the header in shell output.
```

## Container images

You can also use the GLRD tools by building or running a container image.

### build and run image locally

```
podman build -t glrd .
podman run -it --rm localhost/glrd glrd
podman run -it --rm localhost/glrd glrd-create
```

### run pre-build image

```
podman run -it --rm ghcr.io/gardenlinux/glrd glrd
podman run -it --rm ghcr.io/gardenlinux/glrd glrd-create

```

## GitHub action

```
  - name: Get latest GL patch version
    id: gl_version_latest
    uses: gardenlinux/glrd@main
    with:
      cmd: glrd --no-header --type patch --latest --fields Version
  - name: Use latest GL patch version
    run: echo ${{ steps.gl_version_latest.outputs.result }}

  - name: Get latest GL nightly version
    id: gl_version_nightly
    uses: gardenlinux/glrd@main
    with:
      cmd: glrd --no-header --type nightly --latest --fields Version
  - name: Use latest GL nightly version
    run: echo ${{ steps.gl_version_nightly.outputs.result }}
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
