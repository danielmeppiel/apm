FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/microsoft/apm"
LABEL org.opencontainers.image.description="Agent Package Manager — install, compile, and manage agent packages"
LABEL org.opencontainers.image.licenses="MIT"

# Install git (required for apm's git operations)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install apm-cli from source
COPY . /tmp/apm-src
RUN pip install --no-cache-dir /tmp/apm-src && \
    rm -rf /tmp/apm-src

# Verify installation
RUN apm --version

ENTRYPOINT ["apm"]
