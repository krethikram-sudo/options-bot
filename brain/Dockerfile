# Hosted routing brain (split architecture). Build from the REPO ROOT so it can
# include the modelpilot package the brain imports (pricing/taxonomy/license):
#   docker build -f brain/Dockerfile -t modelpilot-brain .
FROM python:3.12-slim
WORKDIR /app
COPY brain/requirements.txt brain/requirements.txt
RUN pip install --no-cache-dir -r brain/requirements.txt
# modelpilot is imported for the routing policy + Ed25519 license verification
# (the bundled public key is enough; the PRIVATE key never ships here).
COPY modelpilot/ modelpilot/
COPY brain/ brain/
ENV PORT=8600 BRAIN_DB=/data/brain.db
EXPOSE 8600
# /data should be a mounted volume so the server-side trial clock persists.
CMD ["sh", "-c", "uvicorn brain.server:app --host 0.0.0.0 --port ${PORT:-8600}"]
