# syntax=docker/dockerfile:1

FROM python:3.11-slim AS compile-image

WORKDIR /app

COPY init.sh requirements.txt ./

USER root
RUN chmod u+x ./init.sh && ./init.sh

FROM python:3.11-slim AS build-image
COPY --from=compile-image /opt/venv /opt/venv
COPY --from=compile-image /bin/ffmpeg /bin/ffmpeg

RUN useradd --create-home nonroot

USER nonroot

WORKDIR /app

COPY --chown=nonroot . .

COPY .gallery-dl.conf /etc/gallery-dl.conf

# Override system Python with one in venv
ENV PATH=/opt/venv/bin:$PATH

CMD ["python", "-u", "main.py"]
