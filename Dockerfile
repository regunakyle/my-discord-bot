# syntax=docker/dockerfile:1

FROM python:3.9

WORKDIR /app

RUN apt update
RUN apt -y upgrade
RUN apt -y install sqlite3 ffmpeg

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD ["python3", "main.py"]