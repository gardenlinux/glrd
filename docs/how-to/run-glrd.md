---
title: "Run GLRD"
description: "How to install and run the GLRD tools locally, in a container, or via GitHub Actions."
order: 1
github_org: gardenlinux
github_repo: glrd
github_source_path: docs/how-to/run-glrd.md
github_target_path: docs/how-to/releases/glrd/run-glrd.md
related_topics:
  - /how-to/releases/glrd/
  - /how-to/releases/glrd/run-glrd.md
  - /how-to/releases/glrd/query-releases.md
  - /how-to/releases/glrd/manage-releases.md
  - /reference/supporting_tools/glrd/
  - /reference/supporting_tools/glrd/cli.md
  - /reference/supporting_tools/glrd/schema.md
  - /explanation/glrd-release-lifecycle.md
---

# Run GLRD

This guide covers how to set up and run the `glrd` and `glrd-manage` tools. Choose the method that fits your environment.

## Prerequisites

All methods require:

- A network connection to the Garden Linux GLRD Amazon S3 bucket for read queries (unless using local file input).
- Amazon Web Services (AWS) credentials with write access to the S3 bucket when using `glrd-manage --s3-update`.

For local Python installation, you also need:

- **Python 3.10 or later**
- A **`GITHUB_TOKEN`** environment variable — required only if you plan to generate release data from GitHub history (the `--create-initial-releases` flag). The token needs no special scopes for the public Garden Linux repository. You can obtain one from [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) or, if you have the GitHub CLI installed, by running `export GITHUB_TOKEN=$(gh auth token)`.

## Install locally with Poetry

1. Clone the repository:

   ```bash
   git clone https://github.com/gardenlinux/glrd.git
   cd glrd
   ```

1. Install dependencies:

   ```bash
   poetry install
   ```

1. Verify the installation:

   ```bash
   poetry run glrd --help
   poetry run glrd-manage --help
   ```

After installation the tools are available as `glrd` and `glrd-manage` within the Poetry virtual environment, or via `.venv/bin/glrd` and `.venv/bin/glrd-manage` if you activate the environment.

## Run in a container

You can run both tools from the pre-built container image without installing Python or Poetry locally.

### Use the pre-built image

```bash
# Query releases (read-only, no credentials needed)
podman run -it --rm ghcr.io/gardenlinux/glrd glrd

# Manage releases (requires AWS credentials)
podman run -it --rm \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN \
  ghcr.io/gardenlinux/glrd glrd-manage
```

### Build and run locally

```bash
podman build -t glrd .

# Query releases
podman run -it --rm glrd glrd

# Manage releases
podman run -it --rm \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN \
  glrd glrd-manage
```

## Run in a GitHub Actions workflow

The GLRD repository publishes a GitHub Action you can use directly in your workflows. The following example retrieves the latest minor and nightly versions:

```yaml
steps:
  - name: Get latest Garden Linux minor version
    id: gl_version_latest
    uses: gardenlinux/glrd@main
    with:
      cmd: glrd --no-header --type minor --latest --fields Version

  - name: Use latest Garden Linux minor version
    run: echo "${{ steps.gl_version_latest.outputs.result }}"

  - name: Get latest Garden Linux nightly version
    id: gl_version_nightly
    uses: gardenlinux/glrd@main
    with:
      cmd: glrd --no-header --type nightly --latest --fields Version

  - name: Use latest Garden Linux nightly version
    run: echo "${{ steps.gl_version_nightly.outputs.result }}"
```

The `result` output contains the raw text output of the `cmd` command.

## Query JSON data manually

You can fetch raw JSON release data directly from the S3 bucket without using the `glrd` CLI. The available files are:

- `releases-major.json`
- `releases-minor.json`
- `releases-nightly.json`
- `releases-dev.json`

Example — fetch all major releases:

```bash
curl -s https://gardenlinux-glrd.s3.eu-central-1.amazonaws.com/releases-major.json
```

## AWS authentication for `glrd-manage`

`glrd-manage` requires write access to the S3 bucket when `--s3-update` is passed. Configure credentials using any method supported by the [AWS Boto3 credentials chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html).

When running in a container, pass credentials via environment variables:

```bash
podman run -it --rm \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_SESSION_TOKEN \
  ghcr.io/gardenlinux/glrd glrd-manage --create minor --version 1592.7
```

The environment variables are forwarded from the host shell into the container without exposing their values in the command line.

## Related topics

<RelatedTopics />
