FROM python:3.12.10-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r /app/requirements.lock

COPY app /app/app
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
# 注意：不要在这里 COPY .env(.example) 进镜像。内置的 .env 若含
# DATABASE_URL=…@localhost:5432 之类的开发值，会覆盖 compose 传进来的
# POSTGRES_HOST 等生产配置，导致后端去连容器自身的 localhost。生产/开发
# 配置一律通过 compose 的环境变量注入。
COPY NOTICE THIRD_PARTY_LICENSES.md /app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
