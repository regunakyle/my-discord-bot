# syntax=docker/dockerfile:1

FROM python:3.9-slim-buster

WORKDIR /app

COPY . .

RUN apt -y update && apt install -y ffmpeg nano sqlite3 && pip3 install -r requirements.txt --no-cache-dir

CMD ["python3", "-u", "main.py"]
