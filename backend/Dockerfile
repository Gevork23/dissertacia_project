FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps (psycopg, wget for healthcheck tooling if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
 && rm -rf /var/lib/apt/lists/*

# Base python deps (keep minimal for now)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt

# Project code will be mounted as volume (./backend -> /app)
