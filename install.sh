#!/bin/bash
# ============================================
# Love Journal 一键安装脚本
#
# 用法（在全新的 Linux 服务器上执行，一条命令）：
#   curl -fsSL https://raw.githubusercontent.com/xiangshanyikecong/loveblog/main/install.sh | sudo bash
#
# 或已下载到本地后执行：
#   sudo bash install.sh
#
# 非交互安装（提前用环境变量传入，避免交互提问）：
#   curl -fsSL https://raw.githubusercontent.com/xiangshanyikecong/loveblog/main/install.sh | sudo DOMAIN=love.example.com ACME_EMAIL=me@example.com bash
#
# 脚本会自动完成：安装 Docker（如缺失）→ 获取代码 → 生成 .env.production
# （随机密码/密钥）→ 自动申请 SSL 证书 → 部署 → 安装证书自动续期定时任务。
# 需要：域名已解析到本机公网 IP，且 80/443 端口可达（防火墙/安全组放行）。
# ============================================

set -euo pipefail

GIT_REPO_URL="https://github.com/xiangshanyikecong/loveblog.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/love-journal}"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Love Journal 一键安装开始${NC}"

# ---- 1. 前置依赖检查 ----
MISSING=()
command -v git     &>/dev/null || MISSING+=(git)
command -v curl    &>/dev/null || MISSING+=(curl)
command -v openssl &>/dev/null || MISSING+=(openssl)
if [ "${#MISSING[@]}" -gt 0 ]; then
    echo -e "${RED}❌ 缺少必要命令：${MISSING[*]}${NC}"
    echo "  请先安装："
    if command -v apt-get &>/dev/null; then
        echo "    sudo apt-get update && sudo apt-get install -y ${MISSING[*]}"
    elif command -v dnf &>/dev/null; then
        echo "    sudo dnf install -y ${MISSING[*]}"
    elif command -v yum &>/dev/null; then
        echo "    sudo yum install -y ${MISSING[*]}"
    elif command -v apk &>/dev/null; then
        echo "    sudo apk add --no-cache ${MISSING[*]}"
    else
        echo "    请安装 ${MISSING[*]} 后重试"
    fi
    exit 1
fi

# ---- 2. 获取代码：已在本仓库内运行则直接用当前目录；否则克隆到 INSTALL_DIR ----
IN_REPO=false
if [ -f "$(pwd)/deploy.sh" ] && [ -f "$(pwd)/.env.production.example" ]; then
    IN_REPO=true
fi

if [ "$IN_REPO" = true ]; then
    INSTALL_DIR="$(pwd)"
    echo "📂 检测到已在本项目目录内，直接使用当前目录：$INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
    echo "📥 更新已有代码（$INSTALL_DIR）..."
    ( cd "$INSTALL_DIR" && git pull --ff-only ) || echo -e "${YELLOW}⚠️  代码更新失败，将继续使用现有代码${NC}"
else
    echo "📥 克隆项目代码到 $INSTALL_DIR ..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth 1 "$GIT_REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# ---- 3. Docker（缺失时自动安装，需 root/sudo）----
# get.docker.com 不支持部分国产发行版（华为 HCE / openEuler，报
# "Unsupported distribution"），此类系统改用 docker-ce 官方 EL 仓库安装。
install_docker_hce() {
    local major
    case "$(grep -E '^VERSION_ID=' /etc/os-release | cut -d= -f2 | tr -d '"')" in
        2.0|22.03*) major=8 ;;
        *)          major=9 ;;
    esac
    cat > /etc/yum.repos.d/docker-ce.repo <<EOF
[docker-ce-stable]
name=Docker CE Stable
baseurl=https://repo.huaweicloud.com/docker-ce/linux/centos/${major}/x86_64/stable
enabled=1
gpgcheck=1
gpgkey=https://repo.huaweicloud.com/docker-ce/linux/centos/gpg
EOF
    dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
}

install_docker() {
    if grep -qE '^ID="(hce|openEuler)"' /etc/os-release 2>/dev/null && command -v dnf &>/dev/null; then
        install_docker_hce
    else
        curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        sh /tmp/get-docker.sh
    fi
}

if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}🐳 未检测到 Docker，尝试自动安装...${NC}"
    if [ "$(id -u)" = "0" ]; then
        install_docker
    elif command -v sudo &> /dev/null; then
        sudo bash -c "$(declare -f install_docker install_docker_hce); install_docker"
    else
        echo -e "${RED}❌ 未检测到 Docker 且无 root/sudo 权限，请先手动安装 Docker${NC}"
        echo "   参考：https://docs.docker.com/engine/install/"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker 安装完成（若当前用户不在 docker 组，请重新登录后重试）${NC}"
fi

# ---- 4. 生成生产配置（已存在则保留，不覆盖用户数据）----
if [ -f .env.production ]; then
    echo -e "${GREEN}✅ 检测到已有 .env.production，保留现有配置${NC}"
else
    echo "🔧 首次安装，正在生成 .env.production（随机密码/密钥自动生成）..."

    # 从 /dev/tty 读取输入，兼容 curl | sudo bash 的一键安装方式
    ask() {
        local prompt="$1" var="$2" answer=""
        while [ -z "$answer" ]; do
            printf '%s: ' "$prompt" > /dev/tty
            if ! read -r answer < /dev/tty; then
                echo -e "${RED}❌ 无法读取输入（非交互环境），请改用环境变量安装：${NC}"
                echo "   curl -fsSL <install.sh 地址> | sudo DOMAIN=love.example.com ACME_EMAIL=me@example.com bash"
                exit 1
            fi
            answer="${answer//[[:space:]]/}"
            if [ -z "$answer" ]; then
                echo "   ⚠️  该值不能为空，请重新输入" > /dev/tty
            fi
        done
        eval "$var='$answer'"
    }

    # 环境变量优先（支持非交互一键安装）
    DOMAIN="${DOMAIN:-}"
    ACME_EMAIL="${ACME_EMAIL:-}"
    [ -n "$DOMAIN" ]     || ask "请输入你的域名（例如 love.example.com）" DOMAIN
    [ -n "$ACME_EMAIL" ] || ask "请输入用于 Let's Encrypt 证书的邮箱" ACME_EMAIL
    while [ -z "$DOMAIN" ] || [ "$DOMAIN" = "yourdomain.com" ]; do
        echo "   ⚠️  域名不能为空或模板值" > /dev/tty
        ask "请输入你的域名（例如 love.example.com）" DOMAIN
    done

    cp .env.production.example .env.production

    rand_hex() { openssl rand -hex "$1"; }
    rand_b64() { openssl rand -base64 "$1" | tr -d '\n'; }

    # 幂等地写入 key=value（替换模板占位行或追加），避免生成值中的特殊字符触发 sed 转义问题
    set_env() {
        local key="$1" value="$2"
        if grep -qE "^${key}=" .env.production; then
            awk -F= -v k="$key" -v v="$value" 'BEGIN{OFS="="} $1==k {$0=k OFS v} {print}' .env.production > .env.production.tmp && mv .env.production.tmp .env.production
        else
            printf '%s=%s\n' "$key" "$value" >> .env.production
        fi
    }

    set_env POSTGRES_PASSWORD      "$(rand_hex 24)"
    set_env REDIS_PASSWORD         "$(rand_hex 24)"
    set_env JWT_SECRET_KEY         "$(rand_b64 64)"
    set_env COOKIE_VAULT_KEY       "$(rand_b64 64)"
    set_env BOOTSTRAP_SETUP_TOKEN  "$(rand_hex 32)"
    set_env DOMAIN                 "$DOMAIN"
    set_env CORS_ORIGINS           "https://$DOMAIN"
    set_env ACME_EMAIL             "$ACME_EMAIL"

    echo -e "${GREEN}✅ .env.production 已生成（随机密码/密钥已写入）${NC}"
fi

# ---- 5. 执行部署（deploy.sh 会自动申请 SSL、自动安装续期定时任务）----
echo -e "${GREEN}🚀 开始部署（首次会自动申请 SSL 证书，请确保域名已解析到本机且 80/443 可达）...${NC}"
chmod +x deploy.sh
bash ./deploy.sh

# ---- 6. 完成 ----
DOMAIN="$(grep -E '^DOMAIN=' .env.production 2>/dev/null | head -n1 | cut -d= -f2- || true)"
echo ""
echo -e "${GREEN}🎉 部署完成！${NC}"
echo "   访问地址：https://${DOMAIN}"
echo "   首次登录：使用 .env.production 中的 BOOTSTRAP_SETUP_TOKEN 完成初始化"
echo "   证书管理：已自动申请并配置每周自动续期（日志：nginx/ssl/ssl-renew.log）"
