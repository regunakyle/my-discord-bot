# syntax=docker/dockerfile:1

FROM python:3.9-slim-buster

WORKDIR /app

COPY . .

RUN apt -y update && apt install -y ffmpeg && pip3 install -r requirements.txt --no-cache-dir && mv .gallery-dl.conf $HOME/.gallery-dl.conf

CMD ["python3", "-u", "main.py"]
