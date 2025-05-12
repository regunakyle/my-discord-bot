# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS compile-image

WORKDIR /app

COPY . .

RUN chmod u+x ./init.sh && \ 
./init.sh

FROM python:3.11-slim AS build-image
COPY --from=compile-image /bin/ffmpeg /bin/ffmpeg
COPY --from=compile-image /app /app

WORKDIR /app

# Set XDG_CACHE_HOME for gallery-dl usage
ENV XDG_CACHE_HOME=/app/volume

RUN useradd nonroot && \ 
printf "[safe]\ndirectory = /app" >/etc/gitconfig && \ 
mkdir gallery-dl && \ 
# Use `chmod 777` here instead of `chown nonroot` in case user wants to use their own docker user
chmod -R 777 ./

USER nonroot

CMD ["/app/.venv/bin/my-discord-bot"]
