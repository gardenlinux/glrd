# overwrite with a stable gardenlinux version
ARG GL_VERSION=latest
ARG GL_BASE=ghcr.io/gardenlinux/gardenlinux:${GL_VERSION}

FROM ${GL_BASE}

LABEL org.opencontainers.image.source=https://github.com/gardenlinux/glrd
LABEL org.opencontainers.image.description="Garden Linux Release Database"
LABEL org.opencontainers.image.licenses=MIT

ENV PYTHON=python3.12

ENV DEBIAN_FRONTEND noninteractive
ENV SHELL /bin/bash
ENV PYTHONPATH /gardenlinux/bin:/gardenlinux/ci:/gardenlinux/ci/glci:/gardenlinux/tests:/gardenlinux/features

# install some basic tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       # python from GL repos, all python packages are supposed to come from pip
       ${PYTHON}-venv \
       # lib${PYTHON}-dev \
       wget \
    && mkdir -p -m 755 /etc/apt/keyrings \
    && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Prepare virtual environment
# We need a virtual env to install packages via pip, and not via apt.
# See: https://peps.python.org/pep-0668/
ENV VIRTUAL_ENV_PARENT=/opt/python-test-env
ENV VIRTUAL_ENV="$VIRTUAL_ENV_PARENT/.venv"
RUN ${PYTHON} -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY . /usr/local/glrd
# Do not use --system, we want the pip from the virtual env
# RUN cd "$VIRTUAL_ENV_PARENT" && pip install -r requirements.txt
RUN pip install -e /usr/local/glrd
WORKDIR /usr/local/glrd
ENTRYPOINT ["/usr/bin/sh", "-c"]
