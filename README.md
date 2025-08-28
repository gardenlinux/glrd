# Garden Linux Release Database (GLRD)

This repository contains tooling and configuration to create the Garden Linux Release Database (GLRD), a system designed to manage and query release information for the Garden Linux distribution.

This repository contains these tools:

- **`glrd-manage`**: A tool for generating and populating the GLRD with initial release data and for creating individual release entries.
- **`glrd`**: A command-line client for querying the GLRD to retrieve release information based on various criteria.

## Table of Contents

- [Garden Linux Releases](#garden-linux-releases)
- [Overview of GLRD](#overview)
- [Prerequisites](#prerequisites)
- [Run GLRD](#run-glrd)
- [glrd](#glrd)
- [glrd-manage](#glrd-manage)
- [Release Schema](#release-schema)
- [Contributing](#contributing)
- [License](#license)

## Garden Linux Releases

For a general overview about Garden Linux releases and their lifecycle, have a look at the [Garden Linux Release Plan Overview](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md).

## Overview

The GLRD provides a structured way to store and access release data for Garden Linux, including different release types such as stable, patch, nightly, and development releases. It uses JSON and YAML formats to store release information and supports integration with AWS S3 for storage to host release data..

![Overview](assets/overview.png)

## Run GLRD

### Manually run Python scripts

<details>
  <summary>Details</summary>

### Prerequisites

- **Python 3.10+**

You can install the required Python packages using:

```bash
poetry install
```

- **AWS CLI** configured with appropriate permissions if you plan to use S3 integration.
- **Git** and **GitHub CLI (gh)** installed and configured if you plan to generate release data from GitHub.

### Installation

Clone the repository and ensure that the scripts are executable:

```bash
git clone https://github.com/gardenlinux/glrd.git
cd glrd
poetry install
```

</details>

### Run in container

<details>
  <summary>Details</summary>

You can also use the GLRD tools by building or running a container image.

#### Run pre-build image

```
podman run -it --rm ghcr.io/gardenlinux/glrd glrd
podman run -it --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN ghcr.io/gardenlinux/glrd glrd-manage

```

#### Build and run image locally

```
podman build -t glrd .
podman run -it --rm glrd glrd
podman run -it --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN glrd glrd-manage
```

</details>

### Run in GitHub action

<details>
  <summary>Details</summary>

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

</details>

### Manually query JSON data

<details>
  <summary>Details</summary>

You can manually query the release JSON data by getting them from our production S3 bucket.

Query the release type that you want:

- `releases-stable.json`
- `releases-patch.json`
- `releases-nightly.json`
- `releases-dev.json`

To e.g. query the stable releases:

```bash
❯ curl -s https://gardenlinux-glrd.s3.eu-central-1.amazonaws.com/releases-stable.json
{"releases":[{"name":"stable-27","type":"stable","version":{"major":27},"lifecycle":{"released":{"isodate":"2020-06-09","timestamp":1591694693},"extended":{"isodate":"2020-12-09","timestamp":1607472000},"eol":{"isodate":"2021-03-09","timestamp":1615248000}}},{"name":"stable-184","type":"stable","version":{"major":184},"lifecycle":{"released":{"isodate":"2020-10-29","timestamp":1603984625},"extended":{"isodate":"2020-04-29","timestamp":1588118400},"eol":{"isodate":"2021-07-29","timestamp":1627516800}}},{"name":"stable-318","type":"stable","version":{"major":318},"lifecycle":{"released":{"isodate":"2021-04-28","timestamp":1619614135},"extended":{"isodate":"2021-10-28","timestamp":1635379200},"eol":{"isodate":"2023-01-28","timestamp":1674864000}}},{"name":"stable-576","type":"stable","version":{"major":576},"lifecycle":{"released":{"isodate":"2021-11-17","timestamp":1637142852},"extended":{"isodate":"2023-05-17","timestamp":1684281600},"eol":{"isodate":"2023-08-17","timestamp":1692230400}}},{"name":"stable-934","type":"stable","version":{"major":934},"lifecycle":{"released":{"isodate":"2023-06-05","timestamp":1685968163},"extended":{"isodate":"2023-12-05","timestamp":1701734400},"eol":{"isodate":"2024-03-05","timestamp":1709596800}}},{"name":"stable-1312","type":"stable","version":{"major":1312},"lifecycle":{"released":{"isodate":"2023-11-16","timestamp":1700136050},"extended":{"isodate":"2024-05-03","timestamp":1714694400},"eol":{"isodate":"2024-08-03","timestamp":1722643200}}},{"name":"stable-1443","type":"stable","version":{"major":1443},"lifecycle":{"released":{"isodate":"2024-03-13","timestamp":1710341636},"extended":{"isodate":"2024-09-13","timestamp":1726185600},"eol":{"isodate":"2025-01-13","timestamp":1736726400}}},{"name":"stable-1592","type":"stable","version":{"major":1592},"lifecycle":{"released":{"isodate":"2024-08-12","timestamp":1723457202},"extended":{"isodate":"2025-05-12","timestamp":1747008000},"eol":{"isodate":"2025-08-12","timestamp":1754956800}}}]}
```

</details>

### AWS Authentication

`glrd-manage` needs write access to an AWS S3 bucket to create and manage releases. See [Boto3 Credentials documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html) and ways to configure this.
If you are running `glrd-manage` in a container, you might want to use [Environment variables](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html#environment-variables) and pass those via e.g. `podman run ... -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN`.

## glrd

The `glrd` script is a command-line utility for querying the GLRD. It allows you to filter and display release information based on various criteria.

### Usage

#### Show help

```
❯ glrd --help
usage: glrd [-h] [--input-format {yaml,json}] [--input-file-prefix INPUT_FILE_PREFIX] [--input-type {file,url}] [--input-url INPUT_URL] [--no-input-split] [--output-format {json,yaml,markdown,mermaid_gantt,shell}] [--output-description OUTPUT_DESCRIPTION] [--active] [--archived] [--latest] [--type TYPE] [--version VERSION] [--fields FIELDS] [--no-header] [-V]

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
                        Input URL to the releases data. Defaults to gardenlinux-glrd S3 URL.
  --no-input-split      Do not split Input into stable+patch and nightly. No additional input-files *-nightly and *-dev will be parsed.
  --output-format {json,yaml,markdown,mermaid_gantt,shell}
                        Output format: json, yaml, markdown, mermaid_gantt, shell (default).
  --output-description OUTPUT_DESCRIPTION
                        Description, added to certain outputs, e.g. mermaid (default: 'Garden Linux Releases').
  --active              Show only active releases.
  --archived            Show only archived releases.
  --latest              Show the latest active major.minor release.
  --type TYPE           Filter by release types (comma-separated list, default: stable,patch). E.g., --type stable,patch,nightly,dev,next
  --version VERSION     Filter by a specific version (major, major.minor, or major.minor.micro). E.g., --version 1312, --version 1312.0, or --version 2000.0.0
  --fields FIELDS       Comma-separated list of fields to output. Possible fields: Name,Version,Type,GitCommit,GitCommitShort,ReleaseDate,ReleaseTime,ExtendedMaintenance,EndOfMaintenance,Flavors,OCI,AttributesSourceRepo (default: Name,Version,Type,GitCommitShort,ReleaseDate,ExtendedMaintenance,EndOfMaintenance)
  --no-header           Omit the header in shell output.
  -V                    show program's version number and exit
```

### Get latest Garden Linux Version

#### Default shell output

```
# default shell output
❯ glrd --latest
Name            Version  Type    GitCommitShort    ReleaseDate    ExtendedMaintenance    EndOfMaintenance
patch-1592.6     1592.6  patch   cb05e11f          2025-02-19     N/A                    2025-08-12
```

#### Get only version field

```
❯ glrd --latest --fields Version --no-header
1592.6
```

#### Get JSON output

<details>
  <summary>Details</summary>

```
❯ glrd --latest --output-format json
{
  "releases": [
    {
      "name": "patch-1592.6",
      "type": "patch",
      "version": {
        "major": 1592,
        "minor": 6
        // Note: micro field is only present for versions ≥ 2000.0.0
      },
      "lifecycle": {
        "released": {
          "isodate": "2025-02-19",
          "timestamp": 1739951325
        },
        "eol": {
          "isodate": "2025-08-12",
          "timestamp": 1754956800
        }
      },
      "git": {
        "commit": "cb05e11f0481b72d0a30da3662295315b220a436",
        "commit_short": "cb05e11f"
      },
      "github": {
        "release": "https://github.com/gardenlinux/gardenlinux/releases/tag/1592.6"
      },
      "flavors": {
        "ali-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/ali-gardener_prod-amd64-1592.6-cb05e11f/ali-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/ali-gardener_prod-amd64-1592.6-cb05e11f/ali-gardener_prod-amd64-1592.6-cb05e11f.qcow2"
        },
        "ali-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/ali-gardener_prod-arm64-1592.6-cb05e11f/ali-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/ali-gardener_prod-arm64-1592.6-cb05e11f/ali-gardener_prod-arm64-1592.6-cb05e11f.qcow2"
        },
        "aws-gardener_persistence_prod_readonly_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f/aws-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f/aws-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "aws-gardener_persistence_prod_readonly_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f/aws-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f/aws-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "aws-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod-amd64-1592.6-cb05e11f/aws-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod-amd64-1592.6-cb05e11f/aws-gardener_prod-amd64-1592.6-cb05e11f.raw"
        },
        "aws-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod-arm64-1592.6-cb05e11f/aws-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod-arm64-1592.6-cb05e11f/aws-gardener_prod-arm64-1592.6-cb05e11f.raw"
        },
        "aws-gardener_prod_readonly_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f/aws-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f/aws-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "aws-gardener_prod_readonly_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f/aws-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f/aws-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "aws-gardener_prod_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod_secureboot-amd64-1592.6-cb05e11f/aws-gardener_prod_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod_secureboot-amd64-1592.6-cb05e11f/aws-gardener_prod_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "aws-gardener_prod_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod_secureboot-arm64-1592.6-cb05e11f/aws-gardener_prod_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/aws-gardener_prod_secureboot-arm64-1592.6-cb05e11f/aws-gardener_prod_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "azure-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/azure-gardener_prod-amd64-1592.6-cb05e11f/azure-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/azure-gardener_prod-amd64-1592.6-cb05e11f/azure-gardener_prod-amd64-1592.6-cb05e11f.vhd"
        },
        "azure-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/azure-gardener_prod-arm64-1592.6-cb05e11f/azure-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/azure-gardener_prod-arm64-1592.6-cb05e11f/azure-gardener_prod-arm64-1592.6-cb05e11f.vhd"
        },
        "gcp-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/gcp-gardener_prod-amd64-1592.6-cb05e11f/gcp-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/gcp-gardener_prod-amd64-1592.6-cb05e11f/gcp-gardener_prod-amd64-1592.6-cb05e11f.gcpimage.tar.gz"
        },
        "gcp-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/gcp-gardener_prod-arm64-1592.6-cb05e11f/gcp-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/gcp-gardener_prod-arm64-1592.6-cb05e11f/gcp-gardener_prod-arm64-1592.6-cb05e11f.gcpimage.tar.gz"
        },
        "gdch-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/gdch-gardener_prod-amd64-1592.6-cb05e11f/gdch-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/gdch-gardener_prod-amd64-1592.6-cb05e11f/gdch-gardener_prod-amd64-1592.6-cb05e11f.gcpimage.tar.gz"
        },
        "gdch-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/gdch-gardener_prod-arm64-1592.6-cb05e11f/gdch-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/gdch-gardener_prod-arm64-1592.6-cb05e11f/gdch-gardener_prod-arm64-1592.6-cb05e11f.gcpimage.tar.gz"
        },
        "kvm-gardener_persistence_prod_readonly_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f/kvm-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f/kvm-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "kvm-gardener_persistence_prod_readonly_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f/kvm-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f/kvm-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "kvm-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod-amd64-1592.6-cb05e11f/kvm-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod-amd64-1592.6-cb05e11f/kvm-gardener_prod-amd64-1592.6-cb05e11f.raw"
        },
        "kvm-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod-arm64-1592.6-cb05e11f/kvm-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod-arm64-1592.6-cb05e11f/kvm-gardener_prod-arm64-1592.6-cb05e11f.raw"
        },
        "kvm-gardener_prod_readonly_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f/kvm-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f/kvm-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "kvm-gardener_prod_readonly_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f/kvm-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f/kvm-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "kvm-gardener_prod_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod_secureboot-amd64-1592.6-cb05e11f/kvm-gardener_prod_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod_secureboot-amd64-1592.6-cb05e11f/kvm-gardener_prod_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "kvm-gardener_prod_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod_secureboot-arm64-1592.6-cb05e11f/kvm-gardener_prod_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/kvm-gardener_prod_secureboot-arm64-1592.6-cb05e11f/kvm-gardener_prod_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_persistence_prod_readonly_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f/metal-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f/metal-gardener_persistence_prod_readonly_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_persistence_prod_readonly_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f/metal-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f/metal-gardener_persistence_prod_readonly_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod-amd64-1592.6-cb05e11f/metal-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod-amd64-1592.6-cb05e11f/metal-gardener_prod-amd64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod-arm64-1592.6-cb05e11f/metal-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod-arm64-1592.6-cb05e11f/metal-gardener_prod-arm64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_prod_pxe-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_pxe-amd64-1592.6-cb05e11f/metal-gardener_prod_pxe-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_pxe-amd64-1592.6-cb05e11f/metal-gardener_prod_pxe-amd64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_prod_pxe-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_pxe-arm64-1592.6-cb05e11f/metal-gardener_prod_pxe-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_pxe-arm64-1592.6-cb05e11f/metal-gardener_prod_pxe-arm64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_prod_readonly_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f/metal-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f/metal-gardener_prod_readonly_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_prod_readonly_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f/metal-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f/metal-gardener_prod_readonly_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_prod_secureboot-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_secureboot-amd64-1592.6-cb05e11f/metal-gardener_prod_secureboot-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_secureboot-amd64-1592.6-cb05e11f/metal-gardener_prod_secureboot-amd64-1592.6-cb05e11f.raw"
        },
        "metal-gardener_prod_secureboot-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_secureboot-arm64-1592.6-cb05e11f/metal-gardener_prod_secureboot-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/metal-gardener_prod_secureboot-arm64-1592.6-cb05e11f/metal-gardener_prod_secureboot-arm64-1592.6-cb05e11f.raw"
        },
        "openstack-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/openstack-gardener_prod-amd64-1592.6-cb05e11f/openstack-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/openstack-gardener_prod-amd64-1592.6-cb05e11f/openstack-gardener_prod-amd64-1592.6-cb05e11f.qcow2"
        },
        "openstack-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/openstack-gardener_prod-arm64-1592.6-cb05e11f/openstack-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/openstack-gardener_prod-arm64-1592.6-cb05e11f/openstack-gardener_prod-arm64-1592.6-cb05e11f.qcow2"
        },
        "openstackbaremetal-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/openstackbaremetal-gardener_prod-amd64-1592.6-cb05e11f/openstackbaremetal-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/openstackbaremetal-gardener_prod-amd64-1592.6-cb05e11f/openstackbaremetal-gardener_prod-amd64-1592.6-cb05e11f.qcow2"
        },
        "openstackbaremetal-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/openstackbaremetal-gardener_prod-arm64-1592.6-cb05e11f/openstackbaremetal-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/openstackbaremetal-gardener_prod-arm64-1592.6-cb05e11f/openstackbaremetal-gardener_prod-arm64-1592.6-cb05e11f.qcow2"
        },
        "vmware-gardener_prod-amd64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/vmware-gardener_prod-amd64-1592.6-cb05e11f/vmware-gardener_prod-amd64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/vmware-gardener_prod-amd64-1592.6-cb05e11f/vmware-gardener_prod-amd64-1592.6-cb05e11f.ova"
        },
        "vmware-gardener_prod-arm64": {
          "metadata": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/vmware-gardener_prod-arm64-1592.6-cb05e11f/vmware-gardener_prod-arm64-1592.6-cb05e11f.manifest",
          "image": "https://gardenlinux-github-releases.s3.amazonaws.com/objects/vmware-gardener_prod-arm64-1592.6-cb05e11f/vmware-gardener_prod-arm64-1592.6-cb05e11f.ova"
        }
      },
      "oci": "ghcr.io/gardenlinux/gardenlinux:1592.6",
      "attributes": {
        "source_repo": true
      }
    }
  ]
}
```

</details>

#### Get json output and filter for version

```
❯ glrd --latest --output-format json | jq -r '.releases[] | "\(.version.major).\(.version.minor)"'
1592.6
```

**Note**: For versions ≥ 2000.0.0, you can also filter by micro version: `jq -r '.releases[] | "\(.version.major).\(.version.minor).\(.version.micro)"'`

### Get all active and supported Garden Linux Versions

```
❯ glrd --active
Name                	Version             	Type                	Git Commit          	Release date        	Extended maintenance	End of maintenance
stable-1443         	1443                	stable              	N/A                 	2024-03-13          	2024-09-13          	2025-01-13
patch-1443.15       	1443.15             	patch               	5d33a69             	2024-10-10          	N/A                 	2025-01-13
stable-1592         	1592                	stable              	N/A                 	2024-08-12          	2025-05-12          	2025-08-12
patch-1592.1        	1592.1              	patch               	ec945aa             	2024-08-22          	N/A                 	2025-08-12
```

### Create [Mermaid Gantt Chart](https://mermaid.js.org/syntax/gantt.html) for active releases

```
❯ glrd --active --type next,stable --output-format mermaid_gantt --output-description "Garden Linux active Releases"
gantt
    title Garden Linux active Releases
    axisFormat %m.%y
    section 1443
        Release:                milestone, 2024-03-13, 0m
        Standard maintenance:       task, 2024-03-13, 6M
        Extended maintenance:       milestone, 2024-09-13, 0m
        Extended maintenance:       task, 2024-09-13, 4M
        End of maintenance:         milestone, 2025-01-13, 0m
    section 1592
        Release:                milestone, 2024-08-12, 0m
        Standard maintenance:       task, 2024-08-12, 9M
        Extended maintenance:       milestone, 2025-05-12, 0m
        Extended maintenance:       task, 2025-05-12, 3M
        End of maintenance:         milestone, 2025-08-12, 0m
    section next
        Release:                milestone, 2024-12-01, 0m
        Standard maintenance:       task, 2024-12-01, 6M
        Extended maintenance:       milestone, 2025-06-01, 0m
        Extended maintenance:       task, 2025-06-01, 3M
        End of maintenance:         milestone, 2025-09-01, 0m
```

## glrd-manage

The `glrd-manage` script is used to generate release data for Garden Linux. It can create initial releases by fetching data from GitHub, generate individual release entries, and manage release data files.

### Show help

```
❯ glrd-manage --help
usage: glrd-manage [-h] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--input-file INPUT_FILE] [--output-format {yaml,json}] [--output-file-prefix OUTPUT_FILE_PREFIX] [--s3-bucket-name S3_BUCKET_NAME] [--s3-bucket-region S3_BUCKET_REGION] [--s3-bucket-prefix S3_BUCKET_PREFIX] [--delete DELETE] [--create-initial-releases CREATE_INITIAL_RELEASES] [--create CREATE]
                   [--version VERSION] [--commit COMMIT] [--lifecycle-released-isodatetime LIFECYCLE_RELEASED_ISODATETIME] [--lifecycle-extended-isodatetime LIFECYCLE_EXTENDED_ISODATETIME] [--lifecycle-eol-isodatetime LIFECYCLE_EOL_ISODATETIME] [--no-query] [--input-stdin] [--input] [--no-output-split] [--s3-create-bucket] [--s3-update] [--output-all] [--input-all] [-V]

Manage Garden Linux releases data.

options:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the logging level
  --input-file INPUT_FILE
                        The name of the input file (default: releases-input.yaml).
  --output-format {yaml,json}
                        Output format: yaml or json (default: yaml).
  --output-file-prefix OUTPUT_FILE_PREFIX
                        The prefix for output files (default: releases).
  --s3-bucket-name S3_BUCKET_NAME
                        Name of S3 bucket. Defaults to 'gardenlinux-glrd'.
  --s3-bucket-region S3_BUCKET_REGION
                        Region for S3 bucket. Defaults to 'eu-central-1'.
  --s3-bucket-prefix S3_BUCKET_PREFIX
                        Prefix for S3 bucket objects. Defaults to empty string.
  --delete DELETE       Delete a release by name (format: type-major.minor). Requires --s3-update.
  --create-initial-releases CREATE_INITIAL_RELEASES
                        Comma-separated list of initial releases to retrieve and generate: 'stable,patch,nightly'.
  --create CREATE       Create a release for this type using the current timestamp and git information (choose one of: stable,patch,nightly,dev,next)'.
  --version VERSION     Manually specify the version (format: major.minor for versions < 2000.0.0, major.minor.micro for versions ≥ 2000.0.0).
  --commit COMMIT       Manually specify the git commit hash (40 characters).
  --lifecycle-released-isodatetime LIFECYCLE_RELEASED_ISODATETIME
                        Manually specify the release date and time in ISO format (YYYY-MM-DDTHH:MM:SS).
  --lifecycle-extended-isodatetime LIFECYCLE_EXTENDED_ISODATETIME
                        Manually specify the extended maintenance date and time in ISO format (YYYY-MM-DDTHH:MM:SS).
  --lifecycle-eol-isodatetime LIFECYCLE_EOL_ISODATETIME
                        Manually specify the EOL date and time in ISO format (YYYY-MM-DDTHH:MM:SS).
  --no-query            Do not query and use existing releases using glrd command. Be careful, this can delete your releases.
  --input-stdin         Process a single input from stdin (JSON data).
  --input               Process input from --input-file.
  --no-output-split     Do not split Output into stable+patch and nightly. Additional output-files *-nightly and *-dev will not be created.
  --s3-create-bucket    Create an S3 bucket.
  --s3-update           Update (merge) the generated files with S3.
  --output-all          Download and write all release files found in S3 to local disk
  --input-all           Upload all local release files to S3
  -V                    show program's version number and exit
```

### Testing release creation

Files named `releases-${type}.json` will be created in the current working directory.

Without passing `--s3-update`, no actual update will be made and changes can safely be tested and verified locally.

### Generate and populate initial release data

This will generate the following initial release data ...

- stable releases
- patch releases
- nightly releases
- releases from `releases-input.yaml` (contain manual lifecycle fields)

... and upload it to the default S3 bucket (if `--s3-update` is passed).

```
❯ glrd-manage --create-initial-releases stable,patch,nightly --input
```

### Generate/Update an arbitrary release from JSON/YAML data

This will generate/update a release from JSON data and upload it to the default S3 bucket.

```
❯ echo '{
  "releases": [
    {
      "name": "patch-1592.1",
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
      },
      "flavors": [
        "ali-gardener_prod",
        "azure-gardener_prod",
        "aws-gardener_prod",
        "gcp-gardener_prod"
      ],
      "attributes": {
        "source_repo": false
      }
    }
  ]
}' | glrd-manage --input-stdin
```

Another approach is writing release YAML data to an input file and use this file as input parameter.

```
❯ cat releases-input.yaml
releases:
  - name: patch-1592.1
    type: patch
    version:
      major: 1592
      minor: 1
    lifecycle:
      released:
        isodate: "2024-08-22"
        timestamp: 1724277600
      eol:
        isodate: "2025-08-27"
        timestamp: 1754949600
    git:
      commit: ec945aa995d0f08d64303ff6045b313b40b66fff
      commit_short: ec945aa
    github:
      release: https://github.com/gardenlinux/gardenlinux/releases/tag/1592.1
    flavors:
      - ali-gardener_prod
      - azure-gardener_prod
      - aws-gardener_prod
      - gcp-gardener_prod
    attributes:
      source_repo: false

❯ glrd-manage --input --input-file releases-input.yaml
```

### Create or update a stable release

https://github.com/gardenlinux/glrd?tab=readme-ov-file#default-stable-dates
When creating a new stable release, [Default Stable dates](#default-stable-dates) can be automatically set for you. In addition to that, you can also overwrite the dates by hand.

```
# use default dates
❯ glrd-manage --create stable --version 1312

# overwrite default dates
❯ glrd-manage --create stable --version 1312 --date-time-released 2023-11-16T00:00:00 --date-time-extended 2024-05-03T00:00:00 --date-time-eol 2024-08-03T00:00:00
```

### Create or update a patch release

When creating a new patch release, the previous patch release of the same major release gets automatically updated. See [Lifecycle Dependencies](#stable-and-patch-releases) for details.

```
# create new patch
❯ glrd-manage --create patch --version 1312.7
```

### Create a new nightly release

Without any additional parameters, the current timestamp and git information will be used to create releases. For patch, nightly and dev releases, the next free minor version is automatically chosen.

```
❯ glrd-manage --create nightly
```

## Release Schema

The Garden Linux Release Database (GLRD) uses structured JSON schemas to represent different types of releases: **stable**, **patch**, **nightly**, and **development** releases. Each release type has specific fields that capture essential information about the release.

### Versioning Scheme

Gardenlinux [introduced semantic Versioning](https://github.com/gardenlinux/gardenlinux/issues/3069) in [TODO!!! name commit !!!]. GLRD supports both versioning schemes based on the major version number:

- **v1: Versions < 2000.0.0**: Use the `major.minor` format (e.g., `27.0`, `1592.6`)
- **v2: Versions ≥ 2000.0.0**: Use the `major.minor.micro` format (e.g., `2000.0.0`, `2222.1.5`)

### Stable Releases

[Stable releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#stable-releases) are major releases that are supported over an extended period of time.

#### Schema Fields

- **`name`**: A string representing the release name (e.g., `stable-1312`).
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

[Patch Releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#patches) are updates delivered during the standard and extended mainteance periods of [Stable releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#stable-releases).

#### Schema Fields

- **`name`**: A string representing the release name (e.g., `patch-1312.1` for v1 versions, `patch-2000.0.0` for v2 versions).
- **`type`**: `patch`.
- **`version`**:
  - **`major`**: An integer indicating the major version number (e.g. `1312`).
  - **`minor`**: An integer indicating the minor version number (e.g. `1`).
  - **`micro`**: An integer indicating the micro version number (only present for versions ≥ 2000.0.0, e.g. `0`).
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
- **`flavors`**: A list of flavors that are included in this release. `glrd` creates `metadata`, `image` and/or `oci` links for each flavor.
- **`attributes`**: An object that does contain additional metadata about the release.
  - **`source_repo`**: A boolean indicating whether the release has debian source repoitories (default: true).

### Nightly Releases

[Nightly releases](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#nightly-releases) are automated builds that are generated every night, reflecting the latest state of the codebase.

#### Schema Fields

- **`name`**: A string representing the release name (e.g., `nightly-1312.0` for v1 versions, `nightly-2000.0.0` for v2 versions).
- **`type`**: `nightly`.
- **`version`**:
  - **`major`**: An integer indicating the major version number.
  - **`minor`**: An integer indicating the minor version number.
  - **`micro`**: An integer indicating the micro version number (only present for versions ≥ 2000.0.0, e.g. `0`).
- **`lifecycle`**:
  - **`released`**:
    - **`isodate`**: The release date in ISO format.
    - **`timestamp`**: The UNIX timestamp of the release date.
- **`git`**:
  - **`commit`**: The full git commit hash associated with the release.
  - **`commit_short`**: The short git commit hash.
- **`flavors`**: A list of flavors that are included in this release. `glrd` creates `metadata`, `image` and/or `oci` links for each flavor.
- **`attributes`**: An object that does contain additional metadata about the release.
  - **`source_repo`**: A boolean indicating whether the release has debian source repoitories (default: true).

### Development Releases

[Development releases](TODO: define and link) are used for testing and development purposes, representing the latest changes that may not yet be included in a stable or patch release. These can be manually created by developers.

#### Schema Fields

- **`name`**: A string representing the release name (e.g., `dev-1312.0` for v1 versions, `dev-2000.0.0` for v2 versions).
- **`type`**: `dev`.
- **`version`**:
  - **`major`**: An integer indicating the major version number.
  - **`minor`**: An integer indicating the minor version number.
  - **`micro`**: An integer indicating the micro version number (only present for versions ≥ 2000.0.0, e.g. `0`).
- **`lifecycle`**:
  - **`released`**:
    - **`isodate`**: The release date in ISO format.
    - **`timestamp`**: The UNIX timestamp of the release date.
- **`git`**:
  - **`commit`**: The full git commit hash associated with the release.
  - **`commit_short`**: The short git commit hash.
- **`flavors`**: A list of flavors that are included in this release. `glrd` creates `metadata`, `image` and/or `oci` links for each flavor.
- **`attributes`**: An object that does contain additional metadata about the release.
  - **`source_repo`**: A boolean indicating whether the release has debian source repoitories (default: true).

### Next Release

[Next release](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md#next-release) is the projected next major releases. There can only be a single `next` release.

#### Schema Fields

- **`name`**: A string representing the release name (`next`).
- **`type`**: `next`.
- **`version`**:
  - **`major`**: `next`.
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

### Lifecycle Dependencies

The lifecycle fields in the release schemas help track the release dates, extended maintenance dates and end-of-life (EOL) dates for each release.

#### Default Stable dates

The defaults for `extended` and `eol` dates are based on the [Garden Linux Release Plan Overview](https://github.com/gardenlinux/gardenlinux/blob/main/docs/00_introduction/release.md) and defined to be:

- `extended`
  - `released` + 6 month
- `eol`
  - `released` + 9 month

For example:

- **Stable Release `stable-1443`**:
  - `released`: 2024-03-13
  - `extended`: 2024-09-13
  - `eol`: 2025-01-13

#### Stable and Patch releases

There is a dependency between the `lifecycle` fields of **stable** and **patch** releases:

- **EOL of Patch Releases**: The `eol` date of a patch release is set to the `released` date of the next patch release. If there is no subsequent patch release, the `eol` date is aligned with the `eol` date of the corresponding stable release.
- **EOL of Latest Patch Release**: The latest patch release's `eol` date matches the `eol` date of the stable release.
- **EOL of Stable Releases**: The `eol` date for a stable release marks the end of support for that major version.

This ensures that all minor updates within a major release adhere to the same overall support timeline.

For example:

- **Stable Release `stable-1312`**:
  - `released`: 2023-11-16
  - `extended`: 2024-05-03
  - `eol`: 2024-08-03
- **Patch Release `patch-1312.1`**:
  - `released`: 2023-11-23
  - `eol`: 2024-01-15 (next patch release date)
- **Patch Release `patch-1312.2`**:
  - `released`: 2024-01-15
  - `eol`: 2024-02-14 (next patch release date)
- ...
- **Patch Release `patch-1312.7`**:
  - `released`: 2024-07-03
  - `eol`: 2024-08-03 (inherits from stable release eol)

In this example, the `eol` of `patch-1312.1` is set to the `released` date of `patch-1312.2`, and the `eol` of the latest patch release (`patch-1312.7`) is set to the `eol` of the stable release (`patch-1312`).

Please note that the `extended` lifecycle field is not taken into account for patch releases. This is simply an administrative date that has no technical implications.

#### Nightly an Dev dates

Due to the nature of the `nightly` and `dev` releases, those do not have `extended` and `eol` dates.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
