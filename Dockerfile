# syntax=docker/dockerfile:1

FROM python:3.11-slim AS compile-image

WORKDIR /app

COPY init.sh requirements.txt ./

RUN ./init.sh

FROM python:3.11-slim AS build-image
COPY --from=compile-image /opt/venv /opt/venv
COPY --from=compile-image /bin/ffmpeg /bin/ffmpeg

WORKDIR /app

COPY . .

RUN mv .gallery-dl.conf /etc/gallery-dl.conf
ENV PATH=/opt/venv/bin:$PATH

CMD ["python", "-u", "main.py"]
