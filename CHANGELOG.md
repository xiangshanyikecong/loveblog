# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.4-beta] - 2026-09-12

### Added

- 一起听 · 歌曲收藏「我喜欢」（`listen_liked_tracks` 表）：播放卡片 / 迷你播放器 /
  搜索结果均可一键红心收藏，音乐库面板按用户隔离展示，支持批量状态查询与整单播放
- 一起听 · 情侣自建歌单「我们的歌单」（`listen_playlists` / `listen_playlist_tracks`
  表）：双方共同创建、编辑、加歌/删歌（重复加歌返回 409），支持「播放整个歌单」
  一键全部入队并实时同步到在线伴侣的播放器
- 「回到那一天」回忆推送（`memory_push_log` 表幂等去重）：后台调度器每日扫描
  往年今日的日记 / 相册 / 听歌记录，生成站内通知并走现有 Web Push / FCM 外发；
  新增小屋回忆页按年分组展示，可直达对应日记与相册
- 年度报告 `GET /v1/reports/annual`：聚合全年 9 项情侣数据（日记 / 相册 / 照片 /
  报备 / 悄悄话 / 听歌数与分钟数 / 胶囊 / 完成心愿）、12 个月活动分布、最常一起听
  Top10 与中文亮点总结；前端报告页含「在一起第 N 天」与每月足迹柱状图
- 两步验证（2FA）：TOTP（RFC 6238，纯标准库实现，零新增依赖）——
  `POST /v1/auth/totp/setup|enable|disable|GET status`；开启后登录需输入验证器
  动态码，登录接口缺失验证码时返回 401 `totp_required` 供前端切换验证步骤；
  每次开启发放 8 个一次性恢复码（仅哈希存储），验证器丢失时每码可用一次
- 登录设备管理（`login_devices` 表）：每次成功登录自动记录设备指纹 / 名称 / IP；
  `GET|DELETE /v1/auth/devices` 列表与撤销，移除设备即提升会话版本号强制
  所有设备重新登录；操作写入审计日志
- 存储空间统计 `GET /v1/storage/usage`：磁盘用量（psutil）、上传文件分目录统计
  （遍历上限 50000 文件）、PostgreSQL 数据库大小；管理后台新增存储面板
- 前端：小屋新增「回到那一天」「年度报告」「安全中心」入口卡片；
  「加入歌单」浮层组件在搜索结果与音乐库间复用
- `server/conftest.py` — 后端测试统一兜底 `DATABASE_URL`（此前测试依赖
  shell 环境残留变量，无法单独运行任意测试文件）

## [1.0.3] - 2026-09-12

### Added

- 未登录密码找回（自部署应急恢复）：登录页新增「忘记密码？」入口，输入
  用户名、新密码和部署时生成的 `BOOTSTRAP_SETUP_TOKEN` 即可重置任意
  伴侣账号密码；重置会吊销该账号全部会话并解除登录冻结。接口限流
  3 次/分钟，访客账号不支持此方式（由伴侣账号在后台管理），操作写入审计日志

### Fixed

- `install.sh` / `install-docker.sh` — 华为 HCE / openEuler 自动安装 Docker
  支持：`get.docker.com` 不支持这两类发行版，改用 docker-ce 官方 EL 仓库
  （华为云镜像源），已在 HCE 2.0 实测通过
- `deploy.sh` — 修正证书续期 cron 幂等检查跨引号匹配失败导致的重复安装
  （每次部署都会重复追加一条续期定时任务）

## [1.0.2] - 2026-09-11

### Added

- GHCR 预构建镜像发布：
  - `.github/workflows/docker-publish.yml` — 推送 `v*` 标签时由 GitHub Actions
    多架构（amd64/arm64）构建 backend/web/netease 并发布到 ghcr.io（公开包）
  - 部署默认直接拉取预构建镜像，不再在用户服务器上构建；`deploy.sh --build`
    / `deploy.ps1 -Build` 保留服务器本地构建选项，拉取失败时自动回退
  - `.env.production.example` 新增 `IMAGE_TAG`（默认 `latest`，可固定版本）
- `install.sh` — 一键安装脚本：一条命令完成「安装 Docker（如缺失）→ 拉取代码 →
  生成 `.env.production`（随机密码/密钥）→ 部署」，并接入 `deploy.sh` 的自动 SSL 能力
- `install-docker.sh` — Docker 版一键安装：免 Git，仅下载运行所需文件
  （compose / deploy.sh / nginx 配置），直接拉取 ghcr.io 预构建镜像部署；
  重复执行等于更新部署（数据与配置均保留）；下载失败时降级使用本地已有文件
- SSL 证书自动申请与续期（`deploy.sh`）：
  - 缺证书时自动用 certbot 容器向 Let's Encrypt 申请并安装到 `nginx/ssl/`
  - 证书剩余不足 30 天时自动续期（webroot 零停机优先，失败回退 standalone）
  - 新增 `--renew-ssl` 参数供定时任务调用；首次部署自动安装每周续期 cron
  - 新增 `ACME_EMAIL` / `ACME_SERVER` 环境变量（见 `.env.production.example`）

### Changed

- `nginx/conf.d/love-journal.conf` — 80 端口开放 `/.well-known/acme-challenge/`
  供 certbot webroot 方式申请/续期
- `docker-compose.prod.yml` — nginx 挂载 `nginx/ssl-challenge` 作为 ACME 挑战目录；
  生产 Redis 启用 AOF 持久化（`--appendonly yes`），硬重启最多丢约 1 秒写入，
  避免默认 RDB 快照间隔导致网易云登录 Cookie 等数据在异常重启后丢失
- `DEPLOYMENT_GUIDE.md` / `DEPLOYMENT_CHECKLIST.md` — SSL 章节改为自动申请/续期说明

### Fixed

- Dockerfile arm64 构建：构建阶段固定原生平台（`--platform=$BUILDPLATFORM`），
  修复 QEMU 模拟下 node 触发 SIGILL 崩溃
- 迁移链多处 PostgreSQL 兼容性缺陷（此前任何全新服务器部署都会在后端启动
  迁移时崩溃，CI 使用 SQLite 未覆盖）：
  - `20260501_1400` 文章/相册可见性迁移的枚举值大小写错误与 text→enum
    缺失显式转型
  - `20260614_0000` / `20260619_1000` / `20260718_1500` / `20260718_1600`
    Boolean 列 `server_default` 使用裸整数（PostgreSQL 要求 `false`）

## [1.0.1] - 2026-07-30

### Added

- `.github/workflows/ci.yml` — automated CI for server tests, web tests, and linting
- `SECURITY.md` — vulnerability reporting policy (GitHub Private Advisories)
- `CONTRIBUTING.md` — development workflow and Conventional Commits conventions
- `web/eslint.config.js` and `web/.prettierrc.json` - JS/Vue lint and format configs
- English summary section in `README.md`
- Project metadata (`license`, `repository`, `author`, `bugs`) in `web/package.json` and `netease-api/package.json`

### Changed

- `docs/README.md` — removed stale reference to `.kiro/specs/` (not included in the public repo)
- `README.md` — marked iOS client as not open-sourced to match the `.gitignore` policy

## [1.0.0] - 2026-07-25

First public open-source release.

### Core Platform

- **Articles / Diary**: Vditor rich-text editor, draft auto-save, encrypted content,
  co-creation (`partner_can_edit`, `is_co_created`), optimistic concurrency with
  `If-Match`/`ETag` conflict resolution, content version history with rollback
- **Albums**: image/video media, encrypted albums and media items, private albums
- **Events / Timeline**: countdown and anniversary types, yearly repeats, visibility
  policy, `next_occurrence_days` computation
- **Messages**: visitor and authenticated user posting, public toggle, soft delete
- **Time Capsules**: scheduled unlock with `open_at`
- **Moments**:图文记录 unified into timeline, search, export, and recycle bin
- **Comments**: threaded (楼中楼) across articles, albums, and other content

### Cottage (Interaction Hub)

- **Check-in (报备)**: location reporting with privacy-first design (only city text persisted,
  raw IP/lat-lng never stored)
- **Listen Together (一起听)**: NetEase Cloud Music sync playback via WebSocket, search,
  daily recommendations, lyrics, queue management, play-progress sync, auto-pause
- **Watch Together (一起看)**: shared video library with poster wall, sync playback for
  local uploads and direct links (`.mp4` / `.m3u8`)
- **Whisper Chat (悄悄话)**: private two-person chat with text/images/stickers, optional
  AES-GCM end-to-end encryption with shared client key, no plaintext fallback
- **Mood Check-in**: daily mood recording with emotion calendar
- **Wishlist**: shared to-do list with completion toggle
- **Daily Question**: blind-answer reveal mechanism
- **Shared Plans / Reminders**: `/v1/cottage/plans`, `/v1/cottage/reminders`
- **Games (一起玩)**: Gomoku, Tic-Tac-Toe, Reversi, Memory, LinkLink, Draw-and-Guess —
  real-time WebSocket gameplay with persistent match records and cross-game stats aggregation

### Social & Discovery

- Notification center with read state and reminder types
- Full-text search across articles, albums, events, moments
- Unified visibility policy: `Public / PartnersOnly / Encrypted`

### Admin & Management

- Dual-role accounts (`PartnerA` / `PartnerB` / `Visitor`) with ban and permission controls
- JWT + session version, login failure lockout, last-login IP/time tracking
- Audit logs for key operations
- Privacy center with local recovery packages and recent privacy operations
- Recycle bin with soft-delete recovery
- Export/Backup v6 (full ZIP: `data.json` + Markdown + `uploads/`), scheduled auto-backup,
  idempotent restore for v1–v6 archives
- Site settings (love start date, base path)
- System health check with 0–100 scoring, component status, optimization recommendations,
  24h trend history, alert + auto-remediation

### Security

- JWT + HttpOnly Secure SameSite=strict cookies; token never exposed to client JS
- Rate limiting (global per-IP + stricter on sensitive routes)
- Key separation: `JWT_SECRET_KEY` vs `COOKIE_VAULT_KEY` (Fernet-encrypted NetEase cookies in Redis)
- E2EE vault: PBKDF2-SHA256 (210k iterations) + AES-GCM-256, keys never leave browser (`extractable=false`)
- Startup self-check: refuses default/weak secrets in production
- Nginx TLS-only with HSTS, `$uri`-based logging (no query-string secrets in logs)

### Clients

- **Web**: Vue 3 + Vite + Tailwind CSS + Vue Router (primary client)
- **Android**: Kotlin + Jetpack Compose — full REST + WebSocket parity, offline-first with
  WorkManager sync, FCM push, Glance widget, camera/gallery upload, client-side encrypted vault
- **iOS**: SwiftUI client (not open-sourced in this repository)

### Infrastructure

- Docker Compose for development (`docker-compose.yml`) and production (`docker-compose.prod.yml`)
- PostgreSQL 16 + Redis 7 + Nginx + NeteaseCloudMusicApiEnhanced
- Alembic migrations (38 schema versions)
- Third-party notices for all four client tiers (Android 160 pkgs, Web 201 pkgs, Python 82 pkgs, Node 246 pkgs)
