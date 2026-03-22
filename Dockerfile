FROM python:3.12-slim

# git is required by APM for dependency management
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY templates/ templates/
COPY scripts/ scripts/

RUN pip install --no-cache-dir .

ENTRYPOINT ["apm"]
