FROM python:3.12.14-slim-bookworm

# 构建时刷新 Debian 安全补丁：官方镜像的固定 tag 只在 Python 补丁版发布时
# 重建，基础系统包可能落后于 bookworm-security 数月，trivy HIGH/CRITICAL
# 门禁会因此失败。apt upgrade 确保进入镜像的系统包始终是当前已修复版本。
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

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

# 非 root 运行：应用仅需要写 /app/uploads、/app/backups（均为挂载卷）与 /tmp。
# 固定 uid/gid 10001，宿主机按该 uid 调整挂载目录属主（deploy.sh 自动执行；
# 也可用 compose 的 BACKEND_UID/BACKEND_GID 覆盖）。
RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appgroup /app
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
