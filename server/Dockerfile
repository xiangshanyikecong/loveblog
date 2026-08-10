FROM python:3.12.10-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r /app/requirements.lock

COPY app /app/app
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY .env.example /app/.env
COPY LICENSE NOTICE THIRD_PARTY_LICENSES.md /app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
