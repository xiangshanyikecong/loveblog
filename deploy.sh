#!/bin/bash

# ============================================
# Love Journal 生产环境部署脚本
# ============================================

set -e  # 遇到错误立即退出

echo "🚀 开始部署 Love Journal..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查必需文件
echo "📋 检查配置文件..."
if [ ! -f ".env.production" ]; then
    echo -e "${RED}❌ 错误：.env.production 文件不存在${NC}"
    echo "请复制 .env.production.example 并填写配置"
    exit 1
fi

# 检查 Docker 和 Docker Compose
echo "🔍 检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ 错误：未安装 Docker${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ 错误：未安装 Docker Compose${NC}"
    exit 1
fi

# 选择可用的 compose 命令：优先新版插件 `docker compose`，回退独立的 `docker-compose`
if docker compose version &> /dev/null; then
    COMPOSE="docker compose --env-file .env.production"
else
    COMPOSE="docker-compose --env-file .env.production"
fi

# 加载环境变量。逐行读取可保留密码中的空格/特殊字符，也不会把值当 shell
# 命令执行（旧的 export $(... | xargs) 两者都做不到）。
echo "📦 加载环境变量..."
while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    [[ -z "${line//[[:space:]]/}" || "$line" =~ ^[[:space:]]*# ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo -e "${RED}❌ 错误：.env.production 中包含无效变量名：$key${NC}"
        exit 1
    fi
    if [[ "$value" == \"*\" && "$value" == *\" ]] || [[ "$value" == \'*\' && "$value" == *\' ]]; then
        value="${value:1:${#value}-2}"
    fi
    export "$key=$value"
done < .env.production

# 检查必需的环境变量
REQUIRED_VARS=("POSTGRES_PASSWORD" "REDIS_PASSWORD" "JWT_SECRET_KEY" "COOKIE_VAULT_KEY" "CORS_ORIGINS" "BOOTSTRAP_SETUP_TOKEN" "DOMAIN" "COOKIE_SECURE")
for var in "${REQUIRED_VARS[@]}"; do
    value="${!var:-}"
    if [ -z "$value" ]; then
        echo -e "${RED}❌ 错误：环境变量 $var 未设置${NC}"
        exit 1
    fi
    if [[ "$value" == *"请设置"* || "$value" == *"请生成"* || "$value" == *"yourdomain.com"* ]]; then
        echo -e "${RED}❌ 错误：环境变量 $var 仍是模板占位值${NC}"
        exit 1
    fi
done

if [ "${#POSTGRES_PASSWORD}" -lt 16 ] || [ "${#REDIS_PASSWORD}" -lt 16 ] || [ "${#JWT_SECRET_KEY}" -lt 64 ] || [ "${#COOKIE_VAULT_KEY}" -lt 64 ]; then
    echo -e "${RED}❌ 错误：数据库/Redis 密码至少 16 位，JWT 与 Cookie Vault 密钥至少 64 位${NC}"
    exit 1
fi
if [ "${COOKIE_SECURE,,}" != "true" ]; then
    echo -e "${RED}❌ 错误：生产 nginx 强制 HTTPS，COOKIE_SECURE 必须为 true${NC}"
    exit 1
fi
for cert in nginx/ssl/fullchain.pem nginx/ssl/privkey.pem; do
    if [ ! -s "$cert" ]; then
        echo -e "${RED}❌ 错误：缺少 TLS 文件 $cert（部署前先申请并放入证书）${NC}"
        exit 1
    fi
done

# 创建必需的目录
echo "📁 创建必需的目录..."
mkdir -p server/uploads/{albums,articles,avatars,timeline,videos}
mkdir -p server/backups
mkdir -p nginx/ssl
mkdir -p nginx/conf.d
# Older releases bind-mounted these as individual files at /app. Preserve
# their state before switching to files inside the already-persistent backups
# directory. Docker may have created an empty directory at the old path when
# the source file was missing; remove only that known-empty artifact.
for state_file in backup_history.json backup_schedule.json; do
    old_path="server/${state_file}"
    new_path="server/backups/${state_file}"
    if [ -f "$old_path" ] && [ ! -e "$new_path" ]; then
        mv "$old_path" "$new_path"
    elif [ -d "$old_path" ]; then
        if [ -z "$(ls -A "$old_path")" ]; then
            rmdir "$old_path"
        else
            echo -e "${RED}❌ 错误：$old_path 本应是文件但现在是非空目录，请先人工检查${NC}"
            exit 1
        fi
    fi
done
[ -f server/backups/backup_history.json ] || printf '[]\n' > server/backups/backup_history.json
[ -f server/backups/backup_schedule.json ] || printf '{}\n' > server/backups/backup_schedule.json

# 备份旧数据（如果存在）
if [ -d "server/uploads" ] && [ "$(ls -A server/uploads)" ]; then
    BACKUP_DIR="backups/uploads_$(date +%Y%m%d_%H%M%S)"
    echo -e "${YELLOW}💾 备份现有上传文件到 $BACKUP_DIR${NC}"
    mkdir -p "$BACKUP_DIR"
    cp -r server/uploads/* "$BACKUP_DIR/"
fi

# 停止旧容器
echo "🛑 停止旧容器..."
$COMPOSE -f docker-compose.prod.yml down || true

# 拉取最新镜像
echo "📥 拉取基础镜像..."
$COMPOSE -f docker-compose.prod.yml pull postgres redis nginx

# 构建应用镜像
echo "🔨 构建应用镜像..."
$COMPOSE -f docker-compose.prod.yml build --no-cache

# 启动服务
echo "🚀 启动服务..."
$COMPOSE -f docker-compose.prod.yml up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 健康检查
echo "🏥 执行健康检查..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Traverse TLS termination and the nginx /health route. A direct backend
    # probe can pass while the certificate mount or reverse proxy is broken.
    if $COMPOSE -f docker-compose.prod.yml exec -T nginx \
        wget --no-check-certificate --quiet --tries=1 --spider https://127.0.0.1/health 2>/dev/null; then
        echo -e "${GREEN}✅ Nginx HTTPS 路由与后端服务健康${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "等待后端启动... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ Nginx HTTPS 路由或后端服务启动失败${NC}"
    echo "查看日志："
    $COMPOSE -f docker-compose.prod.yml logs nginx backend
    exit 1
fi

# Verify public DNS, certificate hostname/trust and the same HTTPS route when
# the deployment host has a standard HTTP client. This intentionally does not
# use --insecure: a mismatched, expired or untrusted certificate must fail.
PUBLIC_ORIGIN="https://${DOMAIN}"
if [ "${HTTPS_PORT:-443}" != "443" ]; then
    PUBLIC_ORIGIN="${PUBLIC_ORIGIN}:${HTTPS_PORT}"
fi
if command -v curl &> /dev/null; then
    curl --fail --silent --show-error --max-time 15 "${PUBLIC_ORIGIN}/health" >/dev/null
elif command -v wget &> /dev/null; then
    wget --quiet --tries=1 --timeout=15 --spider "${PUBLIC_ORIGIN}/health"
else
    echo -e "${RED}❌ 错误：需要 curl 或 wget 验证公网 TLS 证书${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 公网 HTTPS、DNS 与证书校验通过${NC}"

# 显示服务状态
echo ""
echo "📊 服务状态："
$COMPOSE -f docker-compose.prod.yml ps

# 显示日志
echo ""
echo "📝 最近日志："
$COMPOSE -f docker-compose.prod.yml logs --tail=20

echo ""
echo -e "${GREEN}✅ 部署完成！${NC}"
echo ""
echo "🌐 访问地址："
echo "   前端: ${PUBLIC_ORIGIN}"
echo "   API:  ${PUBLIC_ORIGIN}/api"
echo "   文档: ${PUBLIC_ORIGIN}/docs"
echo ""
echo "📋 常用命令："
echo "   查看日志: $COMPOSE -f docker-compose.prod.yml logs -f"
echo "   重启服务: $COMPOSE -f docker-compose.prod.yml restart"
echo "   停止服务: $COMPOSE -f docker-compose.prod.yml down"
echo "   进入后端: $COMPOSE -f docker-compose.prod.yml exec backend bash"
echo ""
echo -e "${YELLOW}⚠️  提醒：${NC}"
echo "   1. 请定期验证自动备份可以实际恢复"
echo "   2. 请设置证书自动续期并在续期后 reload nginx"
echo "   3. 请修改默认管理员密码"
echo ""
