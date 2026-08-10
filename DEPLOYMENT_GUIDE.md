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
- **系统**: Ubuntu 20.04+ / Debian 11+ / CentOS 8+，或 **Windows 10/11 + Docker Desktop**
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
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. 克隆项目

```bash
git clone https://github.com/xiangshanyikecong/loveblog.git love-journal
cd love-journal
```

部署修改版 fork 时，请改为该 fork 的仓库地址，并确保其中包含实际部署版本的完整对应源代码。

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
VITE_SOURCE_CODE_URL=https://github.com/xiangshanyikecong/loveblog
COOKIE_SECURE=true
```

`VITE_SOURCE_CODE_URL` 会显示在页面底部和许可证页面。部署任何修改版时，必须将它改为该版本匿名可访问、
固定到 tag 或 commit 的精确对应源地址，并重新构建 Web 镜像；不能继续指向会变化的分支或未包含部署修改的
上游仓库。

**生成 JWT 密钥：**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 4. 执行部署

```bash
# 生产配置强制 TLS；先按下方 SSL/HTTPS 章节准备这两个文件
test -s nginx/ssl/fullchain.pem
test -s nginx/ssl/privkey.pem

# 给部署脚本执行权限
chmod +x deploy.sh

# 执行部署
./deploy.sh
```

### 5. 访问应用

- 前端: `https://yourdomain.com`
- API 文档: `https://yourdomain.com/docs`
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
```

`deploy.ps1` 与 `deploy.sh` 行为一致：校验配置 → 加载环境变量 → 创建目录 → 备份旧上传文件
→ 拉取/构建镜像 → 启动 → 健康检查。脚本会自动探测 `docker compose`（插件）或 `docker-compose`。

> 说明：Windows 上没有 nginx 的额外系统配置差异，所有服务都在容器内运行，行为与 Linux 一致。

---

## 详细步骤

### 步骤 1: 准备服务器

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要工具
sudo apt install -y git curl wget vim

# 配置防火墙
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
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
│   └── ssl/                   # SSL 证书目录
│       ├── fullchain.pem
│       └── privkey.pem
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

### 方法 1: 使用 Let's Encrypt（推荐）

```bash
# 安装 Certbot
sudo apt install -y certbot

# 停止 Nginx（临时）
docker-compose -f docker-compose.prod.yml stop nginx

# 获取证书
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# 复制证书到项目目录
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
sudo chown $USER:$USER nginx/ssl/*.pem

# 配置已经默认启用 HTTPS，证书就位后启动/重启服务
docker-compose -f docker-compose.prod.yml up -d
```

### 方法 2: 使用自签名证书（仅测试）

```bash
# 生成自签名证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=yourdomain.com"
```

### 自动续期

```bash
# 添加 cron 任务
sudo crontab -e

# 添加以下行（每月1号凌晨2点续期）
0 2 1 * * certbot renew --quiet && docker-compose -f /path/to/love-journal/docker-compose.prod.yml restart nginx
```

---

## 备份与恢复

### 自动备份

登录管理员界面的备份页配置启用状态、间隔与保留份数。旧的
`BACKUP_ENABLED/BACKUP_INTERVAL_HOURS/BACKUP_KEEP_LAST` 环境变量从未被后端读取，
已经移除，避免出现“配置已写但实际未启用”的假象。

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
# 拉取最新代码
git pull origin main

# 重新部署
./deploy.sh
```

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
# - 端口被占用：检查 8000 端口
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

「小屋一起听」依赖容器 `netease`（社区维护的 `binaryify/netease_cloud_music_api`）。

- **生产环境必须包含 `netease` 服务**：`docker-compose.prod.yml` 已内置该服务，仅在内网
  （`love-network`）暴露，不映射到宿主机端口。确认其健康：
  ```bash
  docker compose -f docker-compose.prod.yml ps netease
  ```
- **后端连不上 netease**：检查 backend 环境变量 `NETEASE_API_BASE_URL=http://netease:3000`，
  并确认两者在同一网络。
- **扫码后 `profile: null` / 登录态异常**：这是上游社区库的已知问题（与最新网易云服务端
  偶有不兼容），并非本项目代码问题。缓解办法是拉取最新镜像后重启：
  ```bash
  docker compose -f docker-compose.prod.yml pull netease
  docker compose -f docker-compose.prod.yml up -d netease
  ```

---

## 安全建议

### 1. 修改默认密码
登录后立即修改 `admin` 和 `partner` 账户密码

### 2. 定期更新
```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 更新 Docker 镜像
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
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
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### 5. 配置 Fail2ban（防暴力破解）
```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 技术支持

如有问题，请查看：
1. 项目 GitHub Issues
2. 日志文件：`docker-compose -f docker-compose.prod.yml logs`
3. 健康检查：`https://your-domain/health`

---

**祝部署顺利！💕**
