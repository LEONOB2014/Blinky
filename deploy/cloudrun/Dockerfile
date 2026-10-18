# The radar API (api/app.py) for Google Cloud Run. Built from the staged context that
# deploy/cloudrun_stage.py writes: the code the API imports, contracts/, reports/, the lake tables
# under lake/gold/ and lake/views/temporal.json (the graph-facts metadata). Never .env: the Nebius
# key comes from Secret Manager at run time.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RADAR_PROFILE=full \
    RADAR_LAKE=/app/lake \
    PYTHONPATH=/app:/app/src

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --create-home radar && mkdir -p /app/lake/agent_traces && chown -R radar /app/lake
USER radar

# Cloud Run sets PORT (8080 by default).
CMD exec uvicorn api.app:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1
