# syntax=docker/dockerfile:1

FROM python:3.11 AS compile-image

WORKDIR /app

COPY init.sh requirements.txt ./

USER root
RUN chmod u+x ./init.sh && ./init.sh

FROM python:3.11-slim AS build-image
COPY --from=compile-image /opt/venv /opt/venv
COPY --from=compile-image /bin/ffmpeg /bin/ffmpeg

# Override system Python with one in venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app

COPY . .

RUN useradd nonroot && mkdir gallery-dl && chmod -R 777 gallery-dl

USER nonroot

CMD ["python", "-u", "main.py"]
