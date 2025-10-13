# syntax=docker/dockerfile:1

ARG APP_VERSION

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS compile-image

ARG APP_VERSION

RUN if [ -n "$APP_VERSION" ]; then echo "Building for version $APP_VERSION"; else echo "ERROR: APP_VERSION not set" && false; fi

WORKDIR /app

COPY . .

RUN chmod u+x ./init.sh && \ 
    ./init.sh

FROM python:3.11-slim AS build-image

ARG APP_VERSION

COPY --from=compile-image /bin/ffmpeg /bin/ffmpeg
COPY --from=compile-image /app /app

WORKDIR /app

# Set XDG_CACHE_HOME for gallery-dl usage
ENV XDG_CACHE_HOME=/app/volume
ENV APP_VERSION=$APP_VERSION

RUN useradd nonroot && \
    mkdir -m 777 gallery-dl

USER nonroot

CMD ["/app/.venv/bin/my-discord-bot"]
