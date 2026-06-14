# Telemetry ingest service. Build from the REPO ROOT:
#   docker build -f ingest/Dockerfile -t modelpilot-ingest .
FROM python:3.12-slim
WORKDIR /app
COPY ingest/requirements.txt ingest/requirements.txt
RUN pip install --no-cache-dir -r ingest/requirements.txt
COPY ingest/ ingest/
ENV PORT=8500 INGEST_DB=/data/ingest.db
EXPOSE 8500
# /data should be a mounted volume so aggregated payloads persist.
CMD ["sh", "-c", "uvicorn ingest.server:app --host 0.0.0.0 --port ${PORT:-8500}"]
