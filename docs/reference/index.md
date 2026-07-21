---
title: "Garden Linux Release Database (GLRD)"
description: "Overview of the Garden Linux Release Database (GLRD): a system for managing and querying Garden Linux release information."
github_org: gardenlinux
github_repo: glrd
github_source_path: docs/reference/index.md
github_target_path: docs/reference/supporting_tools/glrd/index.md
related_topics:
  - /reference/supporting_tools/glrd/
  - /reference/supporting_tools/glrd/cli.md
  - /reference/supporting_tools/glrd/schema.md
  - /how-to/glrd/run-glrd.md
  - /how-to/glrd/query-releases.md
  - /how-to/glrd/manage-releases.md
  - /explanation/glrd-release-lifecycle.md
---

# Garden Linux Release Database (GLRD)

The [GLRD repository](https://github.com/gardenlinux/glrd) contains tooling and configuration to manage and query release information for the Garden Linux distribution.

GLRD provides two command-line tools:

- **`glrd-manage`**: Generates and populates the GLRD with initial release data and creates or updates individual release entries.
- **`glrd`**: Queries the GLRD to retrieve release information based on various criteria.

## Garden Linux Releases

For a general overview of Garden Linux releases and their lifecycle, see the [Garden Linux Release Lifecycle](/reference/releases/release-lifecycle).

## Overview

The GLRD provides a structured way to store and access release data for Garden Linux, including release types such as major, minor, nightly, and development releases. It uses JSON and YAML formats to store release information and supports integration with Amazon Web Services (AWS) S3 for hosting release data.

![Diagram showing the GLRD architecture: glrd-manage writes release data to S3, glrd reads from S3 and outputs to shell, JSON, YAML, Mermaid, or Markdown](./assets/glrd-overview.svg#light-mode-only)
![Diagram showing the GLRD architecture: glrd-manage writes release data to S3, glrd reads from S3 and outputs to shell, JSON, YAML, Mermaid, or Markdown](./assets/glrd-overview_dark.svg#dark-mode-only)

## Related topics

<RelatedTopics />
