# 恋爱记（Love Journal）— Node 私有化实例

面向情侣的「恋爱记录 + 博客分享 + 实时互动」私有化平台：每对情侣可独立部署属于自己的
Node，记录日记、相册、纪念日，并通过「报备」「一起听」等模块实时互动。仓库已从早期
MVP 成长为前后端一体化、含多端客户端的完整应用。

当前源码发布版本：`1.0.1`。

> **English**: Love Journal is a self-hosted private platform for couples — a journal +
> blog + real-time interaction suite. Each couple deploys their own Node to record diaries,
> photo albums, anniversaries, and interact in real time (check-ins, listen-together, and
> more). Tech stack: FastAPI + Vue 3 + PostgreSQL + Redis, with Android (Kotlin) and web
> clients. See [CONTRIBUTING.md](./CONTRIBUTING.md) to get involved.

## 技术栈

- **后端**：FastAPI + SQLAlchemy 2.0 + Alembic 迁移
- **数据库**：PostgreSQL（默认/生产）+ Redis（缓存/状态）；测试与轻量本地可用 SQLite
- **前端**：Vue 3 + Vite + Tailwind CSS + Vue Router + Pinia
- **实时**：WebSocket（「一起听」同步播放）
- **富文本**：Vditor 编辑器
- **第三方**：内置 `netease` 服务（NeteaseCloudMusicApi 维护分支，供「一起听」检索/取流）
- **客户端**：Web（主端）、iOS（SwiftUI，封面 + 一起听）、Android（Kotlin + Jetpack Compose，详见 `Android/README.md`）
- **编排**：开发 `docker-compose.yml`；生产 `docker-compose.prod.yml`（含 nginx、PostgreSQL、Redis、netease）

## 功能总览

### 首页 Dashboard

- 恋爱计时器：在一起的天 / 时 / 分 / 秒（由站点配置的恋爱起始日计算）
- 文章 / 相册 / 事件 / 留言数量统计
- 近期纪念日、最新文章 / 相册 / 公开留言摘要（加密内容按可见性策略脱敏）

### 文章 / 日记

- CRUD：`/v1/articles`，状态 `Draft / Published`
- **Vditor 富文本编辑器**：所见即所得 / 即时渲染 / 分屏预览，Markdown 全支持，图片拖拽·粘贴·点击上传，每 30s 自动保存草稿，`Ctrl+S` 等快捷键
- 加密内容（`is_encrypted`）、积木式内容块（`article_blocks`）
- **共同创作**：服务端支持 `partner_can_edit`（授权对方可编辑）+ `is_co_created`（标记为两人共同创作）。伴侣实际写入时服务端会自动把 `is_co_created` 置为 `True`，并在快照中保留各 block 的 `author_id` 用于回滚与协作者头像行。响应字段 `collaborator_uids` 提供权威去重的共同创作者列表。
- **乐观并发 / 编辑冲突解决**：所有写接口（PUT/PATCH）都接受 `If-Match: "<version>"` 头（GET 响应同时回传 `ETag`），保存时若版本不匹配返回 `409 article_version_conflict`（包含 `current_version` / `expected_version`），前端编辑器提供「覆盖对方修改 / 重新载入 / 取消」三选项对话框
- **内容版本历史**（`content_version`）：编辑留痕、可回溯；快照完整保存 `is_co_created` 与每段的 `author_id`，回滚后协作者标记不会丢失

### 相册

- CRUD：`/v1/albums`，媒体项（图片 / 视频，`album_media`）
- 加密相册与媒体项（`is_encrypted`）、私密相册（`is_public=false`）
- 封面与媒体上传持久化到 `server/uploads/`

### 纪念日 / 事件时间线

- CRUD：`/v1/events`，类型 `Countdown`（倒计时）/ `Anniversary`（周年）
- 重要事件 `is_important`、每年重复 `is_yearly_repeat`、可见性 `Public / PartnersOnly / Encrypted`、标签
- 返回距离下次发生天数 `next_occurrence_days`

### 留言板

- CRUD：`/v1/messages`，访客与登录用户均可留言
- 公开开关 `is_public`，后台软删除

### 时间胶囊

- `/v1/capsules`：写下一段话，设定开启时间 `open_at`，到期前内容不可读、到期后自动解锁

### 碎碎念 / 时间线

- `Moment` 图文记录，统一汇入 `/v1/timeline` 时间线，并纳入搜索 / 导出 / 回收站

### 互动小屋（Cottage）

- **报备**：`/v1/checkins` —— 向另一半报备此刻所在位置。隐私设计：原始 IP 与经纬度仅用于一次性反向地理编码，**只持久化解析后的城市文本**，原始定位不落库、不入日志
- **一起听**：`/v1/cottage/listen`（含 WebSocket）—— 和 Ta 同步播放同一首歌：网易云登录、搜索、每日推荐 / 推荐歌单 / 排行榜、听歌历史（持久化到数据库）、歌词、队列、播放进度实时同步、播放结束自动暂停
- **一起看**：`/v1/cottage/watch`（含 WebSocket）—— 共享片库（支持 `poster_url` 海报字段，富 UI 海报墙）+ 同步播放本地上传或直链视频（`.mp4` / `.m3u8`）
- **悄悄话**：`/v1/cottage/chat`（含 WebSocket）—— 双人私密聊天，支持文字 / 图片 / 贴纸；启用共享客户端密钥后使用 AES-GCM 端到端加密，密钥不可用时拒绝降级发送明文
- **心情打卡**：`/v1/cottage/mood` —— 每日心情记录与情绪日历
- **心愿单**：`/v1/wishes` —— 两人想一起做的事，可勾选完成
- **每日一问**：`/v1/cottage/questions` —— 双方盲答，答完后互相揭晓
- **共同计划 / 提醒**：`/v1/cottage/plans`、`/v1/cottage/reminders`
- **一起玩**：`/v1/cottage/games/*`（含 WebSocket）—— 五子棋、井字棋、黑白棋、记忆翻牌、连连看、你画我猜；实时对局 + 战绩统计（持久化到数据库）+ 跨游戏战绩聚合页 `CottageGamesStatsView`（每位 partner 的胜 / 负 / 平局一目了然）

> **依赖 Redis**：一起听、一起看、悄悄话、一起玩等实时模块的状态保存在 Redis。本地开发需启动 Redis（见下方「本地开发启动」）；无 Redis 时这些功能会降级为不可用（HTTP 503 / WebSocket 断开），不会拖垮其余模块。

### 社交与发现

- **评论**：楼中楼，覆盖文章 / 相册等内容
- **通知中心**：`/v1/notifications`，含纪念日提醒、互动通知等类型与已读状态
- **全文搜索**：`/v1/search`，跨文章 / 相册 / 事件 / 碎碎念
- **内容可见性策略**：统一的 `Public / PartnersOnly / Encrypted` 脱敏

## 后台 / 管理

- **账号管理**：双人角色 `PartnerA / PartnerB` 与 `Visitor`；封禁、管理员备注、权限状态
- **安全**：`/v1/security` —— JWT + 会话版本号、登录失败冻结、最后登录 IP / 时间、改密时间
- **审计日志**：`/v1/audit-logs` 记录关键操作
- **隐私中心**：`/v1/privacy` —— 统一展示公开、登录可见、双方可见、仅作者和密码保护范围，并将访问控制与服务端可读 / 端到端加密状态分开说明；支持聊天和保险箱的本地恢复包、敏感导出说明及近期隐私操作记录
- **回收站**：`/v1/recycle-bin`，软删除内容的查看与恢复
- **导出与备份 / 恢复**：`/v1/export` —— `v6` 全量导出 ZIP（`data.json` + Markdown + `uploads/`）、自动备份调度（持久化到 `server/backups/`）；聊天和保险箱保留密文及 KDF 元数据，但不导出口令、派生密钥或账号密码哈希。支持上传 `v1`–`v6` 备份 ZIP **恢复**：先做预检，再幂等地按业务键补齐媒体文件与数据库内容（文章 / 相册 / 事件 / 时间线 / 留言 / 胶囊 / 用户 / 站点设置 / 小屋数据：报备、心愿、聊天、心情、一起看片库、每日一问、计划与提醒、对局战绩、听歌历史等），已存在的条目自动跳过、绝不覆盖现有数据。ZIP 归档本身不加密，应作为敏感文件保管
- **站点设置**：`/v1/settings`，恋爱起始日、基础路径等
- **系统健康检查**：`GET /health/system`，健康评分（0–100）、组件状态、优化建议、运行时长
  - 参数：`components`（database / redis / disk_space / memory / cpu / uploads_directory）、`include_recommendations`、`detailed`
  - **历史趋势**：`GET /health/system/history?hours=24&limit=288` —— 周期采样的 `HealthSnapshot`（默认每 5 分钟一条），供后台面板绘制健康评分曲线 / 状态色点
  - **告警 + 自动修复**：`POST /health/system/remediate` 立即清理 `love_auto_backup_*` 与临时 `.tmp` 文件并写入新快照；后台 `health_monitor_loop` 定时巡检，触发阈值告警（健康评分 < 60、磁盘占用过高、临时文件堆积等）。前端 `AdminView` 提供「立即清理」按钮与最近 24 小时趋势图

## API 一览

所有业务接口以 `/v1` 为前缀，文档见 `http://localhost:8000/docs`。

| 模块 | 前缀 |
| --- | --- |
| 健康检查 | `GET /health`、`GET /health/system`、`GET /health/system/history`、`POST /health/system/remediate` |
| 认证 | `/v1/auth`（register / login …） |
| 首页 | `/v1/dashboard` |
| 文章 | `/v1/articles` |
| 相册 | `/v1/albums` |
| 事件 | `/v1/events` |
| 留言板 | `/v1/messages` |
| 时间胶囊 | `/v1/capsules` |
| 时间线 | `/v1/timeline` |
| 报备 | `/v1/checkins` |
| 一起听 | `/v1/cottage/listen`（REST + WebSocket） |
| 一起看 | `/v1/cottage/watch`（REST + WebSocket） |
| 悄悄话 | `/v1/cottage/chat`（REST + WebSocket） |
| 心情打卡 | `/v1/cottage/mood` |
| 心愿单 | `/v1/wishes` |
| 每日一问 | `/v1/cottage/questions` |
| 共同计划 | `/v1/cottage/plans` |
| 小屋提醒 | `/v1/cottage/reminders` |
| 一起玩 | `/v1/cottage/games/{game}`（REST + WebSocket；`gomoku` / `tictactoe` / `reversi` / `memory` / `linklink` / `draw`） |
| 通知 | `/v1/notifications` |
| 搜索 | `/v1/search` |
| 上传 | `/v1/uploads` |
| 导出 / 备份 | `/v1/export` |
| 设置 | `/v1/settings` |
| 安全 | `/v1/security` |
| 隐私中心 | `/v1/privacy` |
| 审计日志 | `/v1/audit-logs` |
| 回收站 | `/v1/recycle-bin` |

## 快速启动（Docker）

```bash
docker compose up --build
```

启动后：

- Web：`http://localhost:5173`
- API：`http://localhost:8000`
- API Docs：`http://localhost:8000/docs`

> 上传文件持久化到 `server/uploads/`，备份持久化到 `server/backups/`，容器重启不丢失。

## 本地开发启动

> 后端在 `server/`，前端在 `web/`。一起听 / 一起看 / 悄悄话 / 一起玩等实时功能**依赖 Redis**；请确保 Redis 已运行（Docker Compose 会自动启动，纯本地开发见下方）。

### Redis（实时功能必需）

**Docker Compose（推荐，含 PostgreSQL + Redis）**

```bash
docker compose up --build
```

**仅本地 Redis（已有 PostgreSQL / SQLite 后端时）**

```bash
docker run -d --name love-redis -p 6379:6379 redis:7-alpine redis-server --requirepass love
```

在 `server/.env` 中设置 `REDIS_URL=redis://:love@localhost:6379/0`（密码与上面命令一致）。

### 后端

**Linux / macOS**

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Windows (PowerShell)**

```powershell
cd server
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.lock
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

**Linux / macOS**

```bash
cd web
npm install
cp .env.example .env
npm run dev
```

**Windows (PowerShell)**

```powershell
cd web
npm install
copy .env.example .env
npm run dev
```

## 生产部署

生产基于 `docker-compose.prod.yml`（服务：`postgres`、`redis`、`netease`、`backend`、`web`、`nginx`）：

- **Linux**：`cp .env.production.example .env.production` 填写后执行 `./deploy.sh`
- **Windows（Docker Desktop）**：`copy .env.production.example .env.production` 填写后，
  运行 `powershell -ExecutionPolicy Bypass -File deploy.ps1` 或双击 `deploy.bat`

详见 [部署指南](./DEPLOYMENT_GUIDE.md)。「一起听」依赖内置 `netease` 服务，已在生产 compose 中声明（仅内网可达）。

## 第三方软件与版权

本项目使用的第三方软件、锁定版本、来源及可获得的许可证正文见 [NOTICE](./NOTICE) 与
[THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md)。这些声明由已提交的依赖锁文件和软件包元数据生成；
各上游发布的正式条款仍具有最终效力。依赖升级后必须刷新 Python 锁定依赖和 Android release 运行时库存、
重新生成声明，并通过 CI 的发行合规检查。完整命令见 [CONTRIBUTING.md](./CONTRIBUTING.md#dependency-and-license-maintenance)。

Android release 运行时包含部分 Maven 元数据声明适用 Android Software Development Kit License 的
Google Play 服务/Firebase 外部组件。这些组件不属于 Love Journal 的 AGPL 授权范围，因此发行的 Android
二进制并非完全由开源软件组成；具体构件和条款来源见 Android 应用内的许可证页面及
[THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md)。

## 多端客户端

- **Web**：主端，本仓库 `web/`
- **iOS**：SwiftUI 客户端（未随本仓库开源，`ios/` 不在仓库范围内）
- **Android**：Kotlin + Jetpack Compose 客户端，`Android/`（覆盖文章 / 相册 / 留言 / 纪念日 / 时间线 / 回忆 / 评论 / 版本历史 / 胶囊 / 搜索 / 通知 / 回收站 + 小屋：聊天、收藏、撤回、置顶语录、媒体面板、心情、签到、心愿、每日一问 + 一起听、一起看、五子棋、井字棋、黑白棋、记忆翻牌、连连看、你画我猜 + 兑换券、提醒、计划、情侣账本、恋爱月报、足迹地图、生理期关怀 + 客户端加密保险箱 + 系统健康 / 存储统计 / 审计日志 / 安全用户 / 备份与自动同步 + 离线队列、Cookie 会话、FCM、桌面小组件、相机/相册上传）

## 路线图（候选）

> 以下为已勾勒、尚未落地的方向，按性价比排序，欢迎参与。
> **已落地**（不再列为候选）：每日心情打卡 / 情绪日历、想一起做的事心愿单、每日一问盲答揭晓、一起玩战绩聚合页、文章共同创作 + 冲突解决、系统健康历史趋势 + 自动修复。

1. **主动提醒调度 + 站外推送**：把纪念日 / 胶囊提醒从「打开 App 才生成」改为后台定时主动生成，并可选邮件 / 微信推送，让通知系统真正「活」起来。
2. **恋爱年报 / 月报**：聚合文章、碎碎念、报备、相册、事件生成回忆报告。
3. **总站 Hub OAuth 与跨站访客评论**：`sso_source` 字段已预留，接入后支持跨站登录与来源追踪。

## 工程约定

- API 统一版本化（`/v1/...`），鉴权可平滑扩展到 Hub OAuth 双模式
- 数据库迁移使用 Alembic（`server/migrations/`）
- 数据模型预留扩展字段，便于多端复用同一套 API

## License

本项目采用 **GNU Affero General Public License v3.0** (`AGPL-3.0-only`) 授权。详见 [LICENSE](./LICENSE)。
复制、修改、分发本项目或通过网络向用户提供修改版本时，须遵守 AGPL-3.0 的相应条款，包括向网络用户提供
修改版本的对应源代码。
第三方依赖的许可证见 [NOTICE](./NOTICE) 与 [THIRD_PARTY_LICENSES.md](./THIRD_PARTY_LICENSES.md)。

官方未修改版本的 Web 源码入口默认指向
<https://github.com/xiangshanyikecong/loveblog>。下游修改版或镜像部署者必须在构建时把
`VITE_SOURCE_CODE_URL`（Android 使用 Gradle 属性 `SOURCE_CODE_URL`）改为该发行版本的精确对应源地址；
正式发行应固定到匿名可访问的 tag 或 commit。仅指向会继续变化的分支，或指向未包含部署修改的原始上游，
都不足以长期提供该运行版本的精确对应源。

> **NetEase 外部风险披露（不是软件许可证用途限制）**：`netease-api` 辅助模块的原创代码仍完整按
> `AGPL-3.0-only` 授权，不附加“仅供学习研究”等字段限制。但该授权仅覆盖项目代码，不授予网易云音乐
> API 或服务、账号、音乐及其他内容、数据或商标的任何权利。本模块使用非官方接口，其访问和使用可能受到
> 届时有效的服务条款、账号规则、内容许可、适用法律及地区限制。部署者须自行确认授权与合规性，并应准备在
> 上游规则变化、接口停用或收到权利方要求时禁用该可选模块。详见 [netease-api/NOTICE](./netease-api/NOTICE)。
