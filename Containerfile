ARG GL_VERSION=nightly
ARG GL_BASE=ghcr.io/gardenlinux/gardenlinux:${GL_VERSION}

FROM ${GL_BASE}

LABEL org.opencontainers.image.source=https://github.com/gardenlinux/glrd
LABEL org.opencontainers.image.description="Garden Linux Release Database"
LABEL org.opencontainers.image.licenses=MIT

ENV PYTHON=python3.13
ENV POETRY_HOME=/opt/poetry
ENV DEBIAN_FRONTEND noninteractive
ENV PATH=${POETRY_HOME}/bin:/app/.venv/bin:$PATH

# install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ${PYTHON}-venv \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN ${PYTHON} -m venv ${POETRY_HOME} \
    && pip install poetry poetry-dynamic-versioning && poetry config virtualenvs.in-project true

# Set up project
WORKDIR /app
COPY . .
RUN poetry install --no-interaction

ENTRYPOINT ["/usr/bin/sh", "-c"]
