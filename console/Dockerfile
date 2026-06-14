# ModelPilot console (vendor-internal). Build from the repo root:
#   docker build -f console/Dockerfile -t modelpilot-console .
# Needs a small persistent volume at /data (SQLite: accounts/metering/billing).
FROM python:3.12-slim

WORKDIR /app
COPY console/requirements.txt /app/console/requirements.txt
RUN pip install --no-cache-dir -r /app/console/requirements.txt

COPY console/ /app/console/

ENV CONSOLE_DB=/data/console.db \
    CONSOLE_PORT=8700
VOLUME ["/data"]
EXPOSE 8700

CMD ["python", "-m", "console.server"]
