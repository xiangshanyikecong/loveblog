# Love Journal 生产环境部署指南

## 📋 目录

1. [服务器要求](#服务器要求)
2. [快速部署](#快速部署)
3. [详细步骤](#详细步骤)
4. [SSL/HTTPS 配置](#sslhttps-配置)
5. [备份与恢复](#备份与恢复)
6. [监控与维护](#监控与维护)
7. [常见问题](#常见问题)

---

## 服务器要求

### 最低配置
- **CPU**: 2 核
- **内存**: 4GB RAM
- **存储**: 20GB SSD（根据上传文件量调整）
- **系统**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+（含 Rocky Linux 8+ / AlmaLinux 9+）/ Fedora 35+ / openSUSE Leap 15.4+ / Arch Linux，或 **Windows 10/11 + Docker Desktop**
- **软件**: Docker 20.10+ 和 Docker Compose 2.0+（Windows 用 Docker Desktop 自带）

### 推荐配置
- **CPU**: 4 核
- **内存**: 8GB RAM
- **存储**: 50GB SSD
- **带宽**: 5Mbps+

---

## 快速部署

### 1. 安装 Docker

```bash
# 通用方式（推荐，支持 Ubuntu/Debian/CentOS/RHEL/Rocky/AlmaLinux/Fedora/openSUSE）
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# 重新登录（或执行 newgrp docker）使 docker 组生效

# Docker Engine 已自带 docker compose V2 插件，无需单独安装
```

```bash
# Arch Linux（使用官方仓库）
sudo pacman -S --noconfirm docker docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# 重新登录（或执行 newgrp docker）使 docker 组生效
```

### 2. 克隆项目

```bash
git clone https://github.com/xiangshanyikecong/loveblog.git love-journal
cd love-journal
```

### 3. 配置环境变量

```bash
# 复制配置模板
cp .env.production.example .env.production

# 编辑配置文件
nano .env.production
```

**必须修改的配置：**
```env
# 数据库密码（强密码）
POSTGRES_PASSWORD=your_strong_password_here

# Redis 密码
REDIS_PASSWORD=your_redis_password_here

# JWT 密钥（生成方法见下方）
JWT_SECRET_KEY=your_jwt_secret_key_here
COOKIE_VAULT_KEY=another_independent_secret_of_64_chars_or_more

# 首次生产初始化令牌（用于创建第一位 Partner）
BOOTSTRAP_SETUP_TOKEN=your_bootstrap_setup_token_here

# 域名和 CORS
DOMAIN=yourdomain.com
CORS_ORIGINS=https://yourdomain.com
VITE_API_BASE_URL=/api
COOKIE_SECURE=true
```

**生成密钥（需生成两个不同的密钥，分别用于 JWT_SECRET_KEY 和 COOKIE_VAULT_KEY）：**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 4. 执行部署

**一键安装（推荐）**：全新 Linux 服务器上一条命令完成「安装 Docker（如缺失）→
拉取代码 → 生成配置（随机密码/密钥）→ 自动申请 SSL → 部署 → 配置证书自动续期」：

```bash
curl -fsSL https://raw.githubusercontent.com/xiangshanyikecong/loveblog/main/install.sh | sudo bash
```

脚本会交互式询问域名与 Let's Encrypt 邮箱（也可用环境变量免交互：在 `bash` 前加
`DOMAIN=love.example.com ACME_EMAIL=me@example.com`）。执行前请确保：
- 域名已解析到本机公网 IP（A 记录指向服务器 IP，并等待 DNS 生效）
- 防火墙/安全组已放行 80 与 443 端口

**手动部署**：已克隆项目或不想用一键脚本时：

```bash
# 给部署脚本执行权限
chmod +x deploy.sh

# 执行部署（缺证书时自动向 Let's Encrypt 申请，无需手动准备证书）
./deploy.sh

# 也可以一键从 GitHub 拉取最新代码并部署
./deploy.sh --update
```

> 提示：部署脚本默认直接拉取 ghcr.io 上的预构建镜像（由 GitHub Actions 构建的公开
> 镜像，无需登录），不在服务器上编译，速度快且不受服务器环境影响；同时支持
> x86_64 与 ARM64（树莓派/ARM NAS）服务器。如需在服务器上本地构建（例如网络
> 无法访问 ghcr.io，或自定义了 `VITE_API_BASE_URL`），使用 `./deploy.sh --build`。

> 提示：首次申请 SSL 需要域名能通过 80 端口完成验证；证书 90 天有效，部署脚本
> 会在到期前 30 天自动续期，并自动安装每周一 03:00 的续期定时任务
> （`./deploy.sh --renew-ssl`），无需人工干预。

### 5. 访问应用

- 前端: `https://yourdomain.com`
- API 文档：生产 Nginx 默认不公开 `/docs`；本地开发可访问 `http://localhost:8000/docs`，生产调试请临时配置 IP 白名单
- 首次进入时，使用 `X-Bootstrap-Token` 完成第一位 Partner 初始化
- 初始化完成后，再使用刚创建的账号登录

---

## Windows 生产部署（Docker Desktop）

生产环境同样支持 Windows，底层仍是 `docker-compose.prod.yml`，只是用 PowerShell 部署脚本
`deploy.ps1` 替代 bash 的 `deploy.sh`。

### 前置条件
- 安装 **Docker Desktop for Windows**（含 WSL2 后端）并确保其正在运行
- 在 Docker Desktop 设置中开启对项目所在盘符的 **File Sharing**（bind mount `./server/uploads`、`./server/backups` 需要）

### 步骤
```powershell
# 1. 复制并填写生产环境配置
copy .env.production.example .env.production
# 用编辑器填写 POSTGRES_PASSWORD / REDIS_PASSWORD / JWT_SECRET_KEY / CORS_ORIGINS 等

# 2. 生成 JWT 密钥（任选其一）
python -c "import secrets; print(secrets.token_urlsafe(64))"

# 3. 执行部署（二选一）
powershell -ExecutionPolicy Bypass -File deploy.ps1
#   或直接双击 deploy.bat
# 需要在本机构建镜像时，追加 -Build 参数（默认拉取 ghcr.io 预构建镜像）
```

`deploy.ps1` 与 `deploy.sh` 行为一致：校验配置 -> 加载环境变量 -> 创建目录 -> 备份旧上传文件
-> 拉取/构建镜像 -> 启动 -> 健康检查。脚本会自动探测 `docker compose`（插件）或 `docker-compose`。

> 说明：Windows 上没有 nginx 的额外系统配置差异，所有服务都在容器内运行，行为与 Linux 一致。
> 注意：SSL 自动申请/续期是 Linux（`deploy.sh`/`install.sh`）的功能；Windows 的
> `deploy.ps1` 仍需按下方 SSL 章节手动放置证书到 `nginx/ssl/`（或安装 WSL2 后在
> WSL 里使用 `install.sh` 一键安装）。

---

## 详细步骤

### 步骤 1: 准备服务器

```bash
# ===== Ubuntu/Debian =====
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget vim

# ===== CentOS/RHEL/Rocky Linux/AlmaLinux/Fedora =====
sudo dnf update -y
sudo dnf install -y git curl wget vim

# ===== openSUSE =====
sudo zypper refresh && sudo zypper update -y
sudo zypper install -y git curl wget vim

# ===== Arch Linux =====
sudo pacman -Syu --noconfirm
sudo pacman -S --noconfirm git curl wget vim
```

配置防火墙：

```bash
# ===== Ubuntu/Debian（ufw）=====
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# ===== CentOS/RHEL/Rocky Linux/AlmaLinux/Fedora/openSUSE（firewalld）=====
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# ===== Arch Linux（firewalld，需先安装）=====
sudo pacman -S --noconfirm firewalld
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 步骤 2: 配置域名

1. 在域名提供商处添加 A 记录：
   ```
   类型: A
   主机: @
   值: 你的服务器IP
   TTL: 600
   ```

2. 等待 DNS 生效（通常 5-30 分钟）：
   ```bash
   nslookup yourdomain.com
   ```

### 步骤 3: 目录结构

部署后的目录结构：
```
love-journal/
├── docker-compose.prod.yml    # 生产环境编排
├── .env.production            # 生产环境配置（不要提交到 Git）
├── deploy.sh                  # 部署脚本
├── nginx/                     # Nginx 配置
│   ├── nginx.conf
│   ├── conf.d/
│   │   └── love-journal.conf
│   ├── ssl/                   # SSL 证书（fullchain.pem / privkey.pem，部署时自动签发/续期）
│   ├── ssl-challenge/         # ACME HTTP-01 验证目录（自动生成，供续期使用）
│   └── certbot/               # certbot/Let's Encrypt 账户与证书数据（自动生成）
├── server/
│   ├── uploads/               # 上传文件（需要备份）
│   ├── backups/               # 自动备份与运行状态（统一持久化目录）
│   │   ├── backup_history.json
│   │   └── backup_schedule.json
│   └── ...
└── web/
```

### 步骤 4: 数据持久化

Docker 卷会自动创建，数据存储在：
```bash
# 查看卷
docker volume ls

# 数据库数据
docker volume inspect love-journal_postgres_data

# Redis 数据
docker volume inspect love-journal_redis_data
```

---

## SSL/HTTPS 配置

### 自动申请与续期（推荐，默认行为）

`deploy.sh` 已内置 SSL 自动管理，无需手工安装 Certbot 或放置证书：

- **自动申请**：首次部署时若 `nginx/ssl/` 缺少证书，脚本会用 certbot 容器自动向
  Let's Encrypt 申请证书并安装到 `nginx/ssl/`。只需在 `.env.production` 中配置
  `ACME_EMAIL`，并保证域名已解析到本机、80 端口可达。
- **自动续期**：证书 90 天有效。部署脚本在证书剩余不足 30 天时自动续期，并在
  首次部署时自动安装 cron 定时任务（每周一 03:00 调用 `./deploy.sh --renew-ssl`），
  续期后自动重载 nginx，全程零维护。
- **手动续期**：随时执行 `./deploy.sh --renew-ssl`。

### 手动放置证书（可选）

已有证书（如商业证书）时，直接把 `fullchain.pem` 和 `privkey.pem` 放到
`nginx/ssl/` 即可；部署脚本检测到有效证书会自动跳过申请。

### 自签名证书（仅测试）

```bash
# 生成自签名证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=yourdomain.com"
```

---

## 备份与恢复

### 自动备份

登录管理员界面的备份页配置启用状态、间隔与保留份数。旧的
`BACKUP_ENABLED/BACKUP_INTERVAL_HOURS/BACKUP_KEEP_LAST` 环境变量从未被后端读取，
已经移除，避免出现"配置已写但实际未启用"的假象。

备份文件、计划和历史统一持久化到 `server/backups/`；状态文件分别是
`server/backups/backup_schedule.json` 和
`server/backups/backup_history.json`，容器重建不会重置。旧版根目录状态文件会由
`deploy.sh` 自动迁入该目录，避免 Docker 对不存在的单文件挂载误创建目录。

### 手动备份

```bash
# 备份数据库
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U love love_node > backup_$(date +%Y%m%d).sql

# 备份上传文件
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz server/uploads/

# 备份到远程服务器（推荐）
rsync -avz server/uploads/ user@backup-server:/backups/love-journal/
```

### 恢复数据

```bash
# 恢复数据库
cat backup_20240101.sql | docker-compose -f docker-compose.prod.yml exec -T postgres psql -U love love_node

# 恢复上传文件
tar -xzf uploads_backup_20240101.tar.gz -C server/
```

---

## 监控与维护

### 查看日志

```bash
# 查看所有服务日志
docker-compose -f docker-compose.prod.yml logs -f

# 查看特定服务
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f postgres

# 查看最近 100 行
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### 服务管理

```bash
# 重启所有服务
docker-compose -f docker-compose.prod.yml restart

# 重启单个服务
docker-compose -f docker-compose.prod.yml restart backend

# 停止服务
docker-compose -f docker-compose.prod.yml stop

# 启动服务
docker-compose -f docker-compose.prod.yml start

# 完全停止并删除容器
docker-compose -f docker-compose.prod.yml down
```

### 更新应用

```bash
# 方式一：手动拉取最新代码后部署
git pull origin main
./deploy.sh

# 方式二：使用部署脚本一键从 GitHub 拉取更新并部署（推荐）
./deploy.sh --update

# 服务器网络无法访问 ghcr.io 时，可改为在服务器上本地构建
./deploy.sh --update --build
```

更新默认只拉取新镜像并重启，无需在服务器上重新构建，通常一分钟内完成。

### 数据库维护

```bash
# 进入数据库
docker-compose -f docker-compose.prod.yml exec postgres psql -U love love_node

# 查看数据库大小
SELECT pg_size_pretty(pg_database_size('love_node'));

# 清理旧数据（在应用内通过回收站功能）
```

### 性能监控

```bash
# 查看容器资源使用
docker stats

# 查看磁盘使用
df -h
du -sh server/uploads/*

# 查看数据库连接数
docker-compose -f docker-compose.prod.yml exec postgres psql -U love love_node -c "SELECT count(*) FROM pg_stat_activity;"
```

---

## 常见问题

### 1. 容器启动失败

**问题**: 后端容器一直重启
```bash
# 查看详细日志
docker-compose -f docker-compose.prod.yml logs backend

# 常见原因：
# - 数据库连接失败：检查 POSTGRES_PASSWORD
# - 端口被占用：检查 80/443 端口（生产环境仅 nginx 映射到宿主机）
# - 权限问题：检查 uploads 目录权限
```

### 2. 无法访问网站

**问题**: 浏览器无法打开网站
```bash
# 检查服务状态
docker-compose -f docker-compose.prod.yml ps

# 检查端口监听
sudo netstat -tlnp | grep -E '80|443'

# 检查防火墙
sudo ufw status

# 检查 Nginx 配置
docker-compose -f docker-compose.prod.yml exec nginx nginx -t
```

### 3. 图片无法显示

**问题**: 上传的图片显示 404
```bash
# 检查 uploads 目录权限
ls -la server/uploads/

# 检查后端日志
docker-compose -f docker-compose.prod.yml logs backend | grep uploads

# 确保 CORS 配置正确
# 检查 .env.production 中的 CORS_ORIGINS
```

### 4. 数据库连接错误

**问题**: `could not connect to server`
```bash
# 检查 PostgreSQL 容器
docker-compose -f docker-compose.prod.yml ps postgres

# 检查数据库日志
docker-compose -f docker-compose.prod.yml logs postgres

# 重启数据库
docker-compose -f docker-compose.prod.yml restart postgres
```

### 5. 内存不足

**问题**: 服务器内存占用过高
```bash
# 查看内存使用
free -h

# 限制容器内存（编辑 docker-compose.prod.yml）
services:
  backend:
    mem_limit: 1g
  postgres:
    mem_limit: 512m
```

### 6. 磁盘空间不足

```bash
# 清理 Docker 缓存
docker system prune -a

# 清理旧日志
docker-compose -f docker-compose.prod.yml logs --tail=0 -f > /dev/null

# 清理旧备份
find server/backups/ -name "*.zip" -mtime +30 -delete
```

### 7. 「一起听」扫码登录异常 / profile 为 null

「小屋一起听」依赖容器 `netease`（`NeteaseCloudMusicApiEnhanced` 自构建镜像，由 `./netease-api` 目录构建为 `love-netease-enhanced:local`）。

- **生产环境必须包含 `netease` 服务**：`docker-compose.prod.yml` 已内置该服务，仅在内网
  （`love-network`）暴露，不映射到宿主机端口。确认其健康：
  ```bash
  docker compose -f docker-compose.prod.yml ps netease
  ```
- **后端连不上 netease**：检查 backend 环境变量 `NETEASE_API_BASE_URL=http://netease:3000`，
  并确认两者在同一网络。
- **扫码后 `profile: null` / 登录态异常**：这是上游社区库的已知问题（与最新网易云服务端
  偶有不兼容），并非本项目代码问题。缓解办法是重新构建镜像后重启：
  ```bash
  docker compose -f docker-compose.prod.yml build --no-cache netease
  docker compose -f docker-compose.prod.yml up -d netease
  ```

---

## 安全建议

### 1. 修改默认密码
登录后立即修改 `admin` 和 `partner` 账户密码

### 2. 定期更新
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL/Rocky Linux/AlmaLinux/Fedora
sudo dnf upgrade --refresh -y

# openSUSE
sudo zypper refresh && sudo zypper update -y

# Arch Linux
sudo pacman -Syu --noconfirm

# 更新 Docker 镜像
docker-compose --env-file .env.production -f docker-compose.prod.yml pull
docker-compose --env-file .env.production -f docker-compose.prod.yml up -d
```

### 3. 限制 API 文档访问
编辑 `nginx/conf.d/love-journal.conf`，添加 IP 白名单：
```nginx
location /docs {
    allow 192.168.1.0/24;  # 你的 IP 段
    deny all;
    # ...
}
```

### 4. 启用防火墙
```bash
# Ubuntu/Debian（ufw）
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# CentOS/RHEL/Rocky Linux/AlmaLinux/Fedora/openSUSE/Arch Linux（firewalld）
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 5. 配置 Fail2ban（防暴力破解）
```bash
# Ubuntu/Debian
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# CentOS/RHEL/Rocky Linux/AlmaLinux/Fedora
sudo dnf install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# openSUSE
sudo zypper install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Arch Linux
sudo pacman -S --noconfirm fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 技术支持

如有问题，请查看：
1. 项目 GitHub Issues
2. 日志文件：`docker-compose -f docker-compose.prod.yml logs`
3. 健康检查：`https://yourdomain.com/health`

---

**祝部署顺利！💕**
