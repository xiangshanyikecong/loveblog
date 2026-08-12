#!/bin/bash

# ============================================
# Love Journal 生产环境部署脚本
# ============================================

set -eu  # 遇到错误立即退出；引用未定义变量也视为错误

# 无论从哪里调用，都以脚本所在目录作为 Compose 项目根目录。
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$SCRIPT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 默认 Git 仓库地址
GIT_REPO_URL="https://github.com/xiangshanyikecong/loveblog.git"

# 解析命令行参数
AUTO_UPDATE=false
for arg in "$@"; do
    case "$arg" in
        --update|-u)
            AUTO_UPDATE=true
            ;;
        --help|-h)
            echo "用法: ./deploy.sh [选项]"
            echo ""
            echo "选项："
            echo "  --update, -u  更新到 GitHub 最新版本后再部署（无需 Git，自动下载源码包）"
            echo "  --help, -h    显示帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 未知参数: $arg${NC}"
            echo "用法: ./deploy.sh [--update|-u]"
            exit 1
            ;;
    esac
done

echo "🚀 开始部署 Love Journal..."

# 如果指定了 --update，更新代码到最新版本
if [ "$AUTO_UPDATE" = true ]; then
    echo "📥 更新代码到最新版本..."

    if [ -d ".git" ] && command -v git &> /dev/null; then
        # 方式一：Git（适合从仓库克隆的贡献者/用户）
        git pull
        echo -e "${GREEN}✅ 代码已通过 Git 更新到最新版本${NC}"
    else
        # 方式二：下载源码包（适合未安装 Git 或直接下载发行版的普通用户）
        # GitHub tarball 仅包含源码，不含任何用户数据（.env.production、上传文件、
        # 备份、SSL 证书等均被 gitignore），因此可安全覆盖到当前目录。
        if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
            echo -e "${RED}❌ 错误：未安装 Git，且未找到 curl/wget，无法下载更新${NC}"
            echo "  请任选其一："
            echo "    1. 安装 git 后克隆：git clone ${GIT_REPO_URL}"
            echo "    2. 安装 curl 或 wget 后重新运行 ./deploy.sh --update"
            exit 1
        fi
        if ! command -v tar &> /dev/null; then
            echo -e "${RED}❌ 错误：未安装 tar，无法解压源码包${NC}"
            exit 1
        fi

        TMP_DIR="$(mktemp -d)"
        trap 'rm -rf "$TMP_DIR"' EXIT

        # 下载源码包：优先 main 分支，失败则回退 master
        download_ok=false
        for branch in main master; do
            TARBALL_URL="${GIT_REPO_URL%.git}/archive/refs/heads/${branch}.tar.gz"
            echo "   正在从 GitHub 下载源码包（${branch}）..."
            if command -v curl &> /dev/null; then
                if curl -fsSL "$TARBALL_URL" -o "$TMP_DIR/loveblog.tar.gz" 2>/dev/null; then
                    download_ok=true
                    break
                fi
            else
                if wget -q "$TARBALL_URL" -O "$TMP_DIR/loveblog.tar.gz" 2>/dev/null; then
                    download_ok=true
                    break
                fi
            fi
        done

        if [ "$download_ok" != "true" ] || [ ! -s "$TMP_DIR/loveblog.tar.gz" ]; then
            echo -e "${RED}❌ 错误：下载源码包失败，请检查网络连接${NC}"
            exit 1
        fi

        tar -xzf "$TMP_DIR/loveblog.tar.gz" -C "$TMP_DIR"
        SRC_DIR="$(find "$TMP_DIR" -maxdepth 1 -mindepth 1 -type d -name "loveblog-*" | head -n1)"
        if [ -z "$SRC_DIR" ] || [ ! -f "$SRC_DIR/deploy.sh" ]; then
            echo -e "${RED}❌ 错误：解压源码包失败或内容异常${NC}"
            exit 1
        fi

        # 同步源码到当前目录。rsync --delete 会清理新版本中已删除的旧文件，
        # 同时通过 --exclude 保留所有用户数据；无 rsync 时回退到 cp（仅覆盖，
        # 不清理旧文件，对 Docker 构建无影响）。
        if command -v rsync &> /dev/null; then
            rsync -a --delete \
                --exclude '.git' \
                --exclude '.env.production' \
                --exclude 'nginx/ssl' \
                --exclude 'server/uploads' \
                --exclude 'server/backups' \
                --exclude 'backups' \
                "$SRC_DIR/" "$SCRIPT_DIR/"
        else
            cp -a "$SRC_DIR"/. "$SCRIPT_DIR"/
        fi

        echo -e "${GREEN}✅ 代码已通过源码包更新到最新版本${NC}"
    fi
fi

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

# 验证当前用户是否有 Docker 权限（避免 usermod 后未重新登录导致后续全部失败）
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ 错误：无法访问 Docker 守护进程（权限不足）${NC}"
    echo "  请确认当前用户在 docker 组中：sudo usermod -aG docker \$USER"
    echo "  添加后需重新登录或执行 newgrp docker 生效"
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
if [ "$JWT_SECRET_KEY" = "$COOKIE_VAULT_KEY" ]; then
    echo -e "${RED}❌ 错误：COOKIE_VAULT_KEY 必须与 JWT_SECRET_KEY 不同${NC}"
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

# 在停止任何现有服务前完成 Compose 配置校验，避免配置错误造成停机。
echo "🔎 校验生产 Compose 配置..."
$COMPOSE -f docker-compose.prod.yml config --quiet

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

    # 备份轮换：仅保留最近 5 份部署快照，避免长期累积占满磁盘。
    # 目录名含固定格式时间戳，字典序降序即时间从新到旧。
    KEEP_COUNT=5
    ls -1d backups/uploads_* 2>/dev/null | sort -r | tail -n +$((KEEP_COUNT + 1)) | while IFS= read -r old; do
        echo -e "${YELLOW}🗑️  清理旧部署快照：$old${NC}"
        rm -rf "$old"
    done
fi

# 先拉取和构建新版本。旧容器保持运行，构建失败时不会主动制造停机。
echo "📥 拉取基础镜像..."
$COMPOSE -f docker-compose.prod.yml pull postgres redis nginx

# 构建应用镜像
echo "🔨 构建应用镜像..."
$COMPOSE -f docker-compose.prod.yml build --no-cache

# 启动服务
echo "🚀 启动服务..."
$COMPOSE -f docker-compose.prod.yml up -d --remove-orphans

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 健康检查
echo "🏥 执行健康检查..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Traverse TLS termination and the nginx /health/ready route. A direct backend
    # probe can pass while the certificate mount or reverse proxy is broken.
    if $COMPOSE -f docker-compose.prod.yml exec -T nginx \
        wget --no-check-certificate --quiet --tries=1 --spider https://127.0.0.1/health/ready 2>/dev/null; then
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
# 公网验证：检查 DNS、证书和 HTTPS 路由。允许一次重试以应对网络波动。
PUB_VERIFY_OK=false
if command -v curl &> /dev/null; then
    PUB_CMD="curl"
elif command -v wget &> /dev/null; then
    PUB_CMD="wget"
else
    echo -e "${YELLOW}⚠️  未找到 curl 或 wget，跳过公网 TLS 证书校验${NC}"
    PUB_VERIFY_OK=true
fi

if [ "$PUB_VERIFY_OK" != "true" ]; then
    for attempt in 1 2; do
        if [ "$PUB_CMD" = "curl" ]; then
            if curl --fail --silent --show-error --max-time 15 "${PUBLIC_ORIGIN}/health/ready" >/dev/null 2>&1; then
                PUB_VERIFY_OK=true
                break
            fi
        else
            if wget --quiet --tries=1 --timeout=15 --spider "${PUBLIC_ORIGIN}/health/ready" 2>/dev/null; then
                PUB_VERIFY_OK=true
                break
            fi
        fi
        if [ $attempt -eq 1 ]; then
            echo -e "${YELLOW}⏳ 公网验证未通过，5 秒后重试...${NC}"
            sleep 5
        fi
    done
fi

if [ "$PUB_VERIFY_OK" != "true" ]; then
    echo -e "${RED}❌ 公网 HTTPS 验证失败${NC}"
    echo "  可能原因："
    echo "    1. DNS 未生效（检查域名是否已解析到本机 IP）"
    echo "    2. TLS 证书不匹配或未受信任"
    echo "    3. 防火墙/安全组未开放 443 端口"
    echo "    4. 网络波动"
    echo ""
    echo "  内部服务日志（供排查）："
    $COMPOSE -f docker-compose.prod.yml logs --tail=30 nginx backend
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
echo "   API 文档: 生产环境默认不公开（本地开发访问 /docs）"
echo ""
echo "📋 常用命令："
echo "   查看日志: $COMPOSE -f docker-compose.prod.yml logs -f"
echo "   重启服务: $COMPOSE -f docker-compose.prod.yml restart"
echo "   停止服务: $COMPOSE -f docker-compose.prod.yml down"
echo "   进入后端: $COMPOSE -f docker-compose.prod.yml exec backend bash"
echo "   更新并部署: ./deploy.sh --update"
echo ""
echo -e "${YELLOW}⚠️  提醒：${NC}"
echo "   1. 请定期验证自动备份可以实际恢复"
echo "   2. 请设置证书自动续期并在续期后 reload nginx"
echo "   3. 请修改默认管理员密码"
echo ""
