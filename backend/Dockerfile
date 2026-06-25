FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8000

# A single worker is intentional: the ETL scheduler (app/__init__.py) runs
# in-process, so >1 worker would double-ingest and race on the same writes.
# For real traffic, split ingestion into its own Render "Background Worker"
# service with ENABLE_SCHEDULER=false on the web service, and scale workers
# here independently.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "60", "wsgi:app"]
