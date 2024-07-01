# syntax=docker/dockerfile:1

FROM python:3.11 AS compile-image

WORKDIR /app

COPY init.sh requirements.txt ./

RUN chmod u+x ./init.sh && \ 
./init.sh

FROM python:3.11-slim AS build-image
COPY --from=compile-image /opt/venv /opt/venv
COPY --from=compile-image /bin/ffmpeg /bin/ffmpeg

# Override system Python with the one in venv
ENV PATH=/opt/venv/bin:$PATH \
    XDG_CONFIG_HOME=/app/volume

WORKDIR /app

COPY . .

RUN useradd nonroot && \ 
printf "[safe]\ndirectory = /app" >/etc/gitconfig && \ 
mkdir gallery-dl && \ 
chmod -R 777 ./

USER nonroot

CMD ["python", "-u", "main.py"]
