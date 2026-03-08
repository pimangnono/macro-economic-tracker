FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY apps/api /app/apps/api
COPY db_schema.sql /app/db_schema.sql
COPY migrations /app/migrations

RUN python -m pip install --upgrade pip \
    && pip install ./apps/api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "/app/apps/api", "--host", "0.0.0.0", "--port", "8000"]
