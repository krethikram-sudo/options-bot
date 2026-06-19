# ModelPilot console (vendor-internal). Build from the repo root:
#   docker build -f console/Dockerfile -t modelpilot-console .
# Needs a small persistent volume at /data (SQLite: accounts/metering/billing).
FROM python:3.12-slim

WORKDIR /app
COPY console/requirements.txt /app/console/requirements.txt
RUN pip install --no-cache-dir -r /app/console/requirements.txt

COPY console/ /app/console/
# The console runs the Outlay engine in-process (Spend dashboard, estimator,
# connectors). It's stdlib-only and imported at boot, so it must be in the image
# — including outlay/fixtures, which back the "See it with sample data" demo.
COPY outlay/ /app/outlay/

ENV CONSOLE_DB=/data/console.db \
    CONSOLE_PORT=8700
VOLUME ["/data"]
EXPOSE 8700

CMD ["python", "-m", "console.server"]
