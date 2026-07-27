FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV MEROX_CONFIG=/config/config.yml
VOLUME ["/config", "/data"]

ENTRYPOINT ["merox"]
CMD ["daemon", "-c", "/config/config.yml"]
