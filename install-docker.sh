#!/bin/bash
# ============================================
# Love Journal Docker 版一键安装脚本
#（预构建镜像：免 Git、免源码、不在服务器上编译）
#
# 用法（在全新的 Linux 服务器上执行，一条命令）：
#   curl -fsSL https://raw.githubusercontent.com/xiangshanyikecong/loveblog/main/install-docker.sh | sudo bash
#
# 已下载到本地后执行：
#   sudo bash install-docker.sh
#
# 非交互安装（提前用环境变量传入，避免交互提问）：
#   curl -fsSL https://raw.githubusercontent.com/xiangshanyikecong/loveblog/main/install-docker.sh | sudo DOMAIN=love.example.com ACME_EMAIL=me@example.com bash
#
# 与 install.sh（源码克隆版）的区别：
#   本脚本只下载运行所需文件（docker-compose.prod.yml、deploy.sh、nginx
#   配置、配置模板），应用镜像直接从 ghcr.io 拉取（GitHub Actions 预构建，
#   支持 x86_64/ARM64），全程无需 Git，也不在服务器上编译。
#   需要在服务器上本地构建（./deploy.sh --build）时，请改用源码版：
#   git clone https://github.com/xiangshanyikecong/loveblog.git
#
# 已安装过的情况下重复执行 = 更新运行文件并重新部署
#（.env.production 与全部数据均保留）。
#
# 数据保存位置（升级/重装均保留）：
#   server/uploads/    上传的媒体文件
#   server/backups/    应用自动备份 zip
#   postgres_data 卷   PostgreSQL 数据
#   redis_data 卷      Redis 数据（AOF 持久化）
# ============================================

set -euo pipefail

GIT_REPO_URL="https://github.com/xiangshanyikecong/loveblog.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/love-journal}"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🚀 Love Journal Docker 版一键安装开始${NC}"

# ---- 1. 前置依赖检查（不需要 Git）----
DL_CMD=""
if command -v curl &>/dev/null; then
    DL_CMD="curl"
elif command -v wget &>/dev/null; then
    DL_CMD="wget"
fi

MISSING=()
if [ -z "$DL_CMD" ]; then
    MISSING+=("curl(或wget)")
fi
command -v tar &>/dev/null || MISSING+=(tar)
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

download() {
    local url="$1" dest="$2"
    if [ "$DL_CMD" = "curl" ]; then
        curl -fsSL "$url" -o "$dest"
    else
        wget -q "$url" -O "$dest"
    fi
}

# ---- 2. Docker（缺失时自动安装，需 root/sudo）----
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
        download https://get.docker.com /tmp/get-docker.sh
        sh /tmp/get-docker.sh
    fi
}

if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}🐳 未检测到 Docker，尝试自动安装...${NC}"
    if [ "$(id -u)" = "0" ]; then
        install_docker
    elif command -v sudo &> /dev/null; then
        sudo bash -c "$(declare -f install_docker install_docker_hce download); install_docker"
    else
        echo -e "${RED}❌ 未检测到 Docker 且无 root/sudo 权限，请先手动安装 Docker${NC}"
        echo "   参考：https://docs.docker.com/engine/install/"
        exit 1
    fi
    echo -e "${GREEN}✅ Docker 安装完成（若当前用户不在 docker 组，请重新登录后重试）${NC}"
fi

# 确保 Docker 守护进程已启动并开机自启（get.docker.com 会自动处理，
# 但 HCE/openEuler 的 dnf 安装路径不会，daemon 未启动会导致后续
# docker info 全部失败并被误报为"权限不足"）
if [ "$(id -u)" = "0" ]; then
    systemctl enable --now docker &> /dev/null || true
else
    sudo systemctl enable --now docker &> /dev/null || true
fi

# ---- 3. 确定安装目录（在本项目目录内运行则直接用当前目录）----
if [ -f "$(pwd)/docker-compose.prod.yml" ] && [ -f "$(pwd)/deploy.sh" ]; then
    INSTALL_DIR="$(pwd)"
    echo "📂 检测到已在本项目目录内，直接使用当前目录：$INSTALL_DIR"
fi

# ---- 4. 下载运行文件（从源码包中仅提取运行所需部分）----
# 仓库 tarball 仅含源码，不含任何用户数据，可安全覆盖以下运行文件；
# .env.production、nginx/ssl、nginx/certbot、server/uploads、server/backups
# 均不在复制范围内，绝不会被触碰。
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

SRC_DIR=""
for branch in main master; do
    TARBALL_URL="${GIT_REPO_URL%.git}/archive/refs/heads/${branch}.tar.gz"
    echo "📥 下载运行文件（${branch} 分支）..."
    rm -f "$TMP_DIR/loveblog.tar.gz"
    if download "$TARBALL_URL" "$TMP_DIR/loveblog.tar.gz" 2>/dev/null && [ -s "$TMP_DIR/loveblog.tar.gz" ]; then
        tar -xzf "$TMP_DIR/loveblog.tar.gz" -C "$TMP_DIR"
        if [ -d "$TMP_DIR/loveblog-$branch" ]; then
            SRC_DIR="$TMP_DIR/loveblog-$branch"
            break
        fi
    fi
done

# 运行所需文件清单（用于源码包校验与本地降级检查）
RUNTIME_FILES=(
    "docker-compose.prod.yml"
    "deploy.sh"
    ".env.production.example"
    "nginx/nginx.conf"
    "nginx/conf.d/love-journal.conf"
)

have_local_runtime_files() {
    local f
    for f in "${RUNTIME_FILES[@]}"; do
        [ -f "$INSTALL_DIR/$f" ] || return 1
    done
    return 0
}

if [ -z "$SRC_DIR" ]; then
    # 下载失败：本地已有全套运行文件时降级继续（例如手动放置了文件、或
    # 仓库暂不可匿名访问的服务器环境），否则确实无法继续
    if have_local_runtime_files; then
        echo -e "${YELLOW}⚠️  下载运行文件失败（网络问题或仓库访问受限），继续使用本地已有文件${NC}"
    else
        echo -e "${RED}❌ 下载运行文件失败，且本地缺少运行文件，无法继续${NC}"
        echo "   可手动下载运行文件后重试，或检查网络后重新执行本脚本"
        exit 1
    fi
else
    # 校验源码包内运行文件齐全
    for f in "${RUNTIME_FILES[@]}"; do
        if [ ! -f "$SRC_DIR/$f" ]; then
            echo -e "${RED}❌ 源码包缺少运行文件：$f${NC}"
            exit 1
        fi
    done

    mkdir -p "$INSTALL_DIR/nginx/conf.d"
    cp -f "$SRC_DIR/docker-compose.prod.yml" "$INSTALL_DIR/"
    cp -f "$SRC_DIR/deploy.sh" "$INSTALL_DIR/"
    cp -f "$SRC_DIR/.env.production.example" "$INSTALL_DIR/"
    cp -f "$SRC_DIR/nginx/nginx.conf" "$INSTALL_DIR/nginx/"
    cp -f "$SRC_DIR/nginx/conf.d/love-journal.conf" "$INSTALL_DIR/nginx/conf.d/"
    chmod +x "$INSTALL_DIR/deploy.sh"
fi
cd "$INSTALL_DIR"
echo -e "${GREEN}✅ 运行文件已就绪：$INSTALL_DIR${NC}"

# ---- 5. 生成生产配置（已存在则保留，不覆盖用户数据）----
if [ -f .env.production ]; then
    echo -e "${GREEN}✅ 检测到已有 .env.production，保留现有配置（本次为更新部署）${NC}"
else
    echo "🔧 首次安装，正在生成 .env.production（随机密码/密钥自动生成）..."

    # 从 /dev/tty 读取输入，兼容 curl | sudo bash 的一键安装方式
    ask() {
        local prompt="$1" var="$2" answer=""
        while [ -z "$answer" ]; do
            printf '%s: ' "$prompt" > /dev/tty
            if ! read -r answer < /dev/tty; then
                echo -e "${RED}❌ 无法读取输入（非交互环境），请改用环境变量安装：${NC}"
                echo "   curl -fsSL <install-docker.sh 地址> | sudo DOMAIN=love.example.com ACME_EMAIL=me@example.com bash"
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

# ---- 6. 部署（拉取 ghcr.io 预构建镜像；首次自动申请 SSL 证书）----
echo -e "${GREEN}🚀 开始部署（拉取预构建镜像，请确保域名已解析到本机且 80/443 可达）...${NC}"
bash ./deploy.sh

# ---- 7. 完成 ----
DOMAIN_VALUE="$(grep -E '^DOMAIN=' .env.production | head -n1 | cut -d= -f2- || true)"
BOOTSTRAP_TOKEN="$(grep -E '^BOOTSTRAP_SETUP_TOKEN=' .env.production 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\r' || true)"
echo ""
echo -e "${GREEN}🎉 部署完成！${NC}"
echo "   访问地址：https://${DOMAIN_VALUE}"
echo "   更新版本：./deploy.sh --update"
echo "   证书管理：已自动申请并配置每周自动续期（日志：nginx/ssl/ssl-renew.log）"
if [ -n "$BOOTSTRAP_TOKEN" ]; then
    echo ""
    echo -e "${YELLOW}🔑 初始化令牌（BOOTSTRAP_SETUP_TOKEN，仅本次显示，请立即记录并妥善保存）：${NC}"
    echo -e "${YELLOW}   ${BOOTSTRAP_TOKEN}${NC}"
    echo "   首次访问 https://${DOMAIN_VALUE} 时输入此令牌完成初始化（忘记密码时也可用于重置）"
    echo "   如需再次查看，可在服务器上执行：grep '^BOOTSTRAP_SETUP_TOKEN=' .env.production"
fi
echo ""
echo "📁 数据保存位置（升级/重装均保留，请定期异地备份 server/backups/）："
echo "   server/uploads/    上传的媒体文件"
echo "   server/backups/    应用自动备份 zip"
echo "   postgres_data 卷   PostgreSQL 数据"
echo "   redis_data 卷      Redis 数据（AOF 持久化）"
