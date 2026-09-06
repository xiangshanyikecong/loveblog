# 恋爱记（Love Journal）项目说明与使用手册

> 适用版本：1.0.1  
> 文档更新时间：2026-07-31  
> 本文面向使用者、部署者和项目开发者，内容以当前仓库代码和配置为准。

## 1. 项目简介

恋爱记（Love Journal）是一个面向情侣的私有化恋爱记录平台。它把恋爱日记、相册、纪念日、时间线和双人互动功能放在同一个实例中运行。每对情侣可以部署自己的 Node 私有实例，数据由实例所有者自行保存和管理。

项目的核心目标是：

- 记录：保存文章、碎碎念、图片、视频和重要日期。
- 回顾：通过首页、时间线、搜索、报告和备份整理共同记忆。
- 互动：通过报备、聊天、一起听、一起看和小游戏进行实时互动。
- 私密：按公开、伴侣可见、加密等策略控制内容访问，并提供隐私中心和客户端加密保险箱。
- 可维护：提供健康检查、审计日志、回收站、导出、自动备份和恢复能力。
- 多端：Web 是主端，同时提供 Android 客户端；iOS 客户端不在本仓库的开源范围内。

这里的“Node”指一套独立部署的恋爱记实例，不是 Node.js 运行时。一个实例通常只服务一对情侣及其受控访客。

## 2. 项目组成

| 部分 | 目录 | 作用 |
| --- | --- | --- |
| Web 前端 | web/ | Vue 3 主客户端，提供用户端、情侣小屋和管理后台 |
| API 后端 | server/ | FastAPI 服务、数据模型、鉴权、上传、备份和 WebSocket |
| Android 客户端 | Android/ | Kotlin + Jetpack Compose 原生客户端，支持离线队列和同步 |
| 网易云适配服务 | netease-api/ | 为“一起听”提供歌曲检索、登录和取流能力，仅供内部后端访问 |
| 反向代理 | nginx/ | 生产环境的 HTTPS、前端静态文件、API 和上传文件路由 |
| 编排配置 | docker-compose.yml、docker-compose.prod.yml | 开发和生产服务编排 |
| 文档 | docs/、根目录 Markdown 文件 | 使用指南、部署、安全和开发资料 |

### 2.1 技术栈

- 后端：FastAPI、SQLAlchemy 2、Alembic、Python 3.12。
- 数据库：生产默认 PostgreSQL 16；测试和轻量本地开发可使用 SQLite。
- 状态与实时通信：Redis 7、WebSocket。
- 前端：Vue 3、Vite、Vue Router、Tailwind CSS、Vditor。
- Android：Kotlin、Jetpack Compose、Retrofit、Room、DataStore、WorkManager、Hilt。
- 生产入口：Nginx + HTTPS，应用服务通过 Docker 内部网络连接数据库、Redis 和网易云适配服务。

## 3. 功能说明

### 3.1 账户与权限

项目包含三类角色：

| 角色 | 说明 |
| --- | --- |
| PartnerA | 第一位伴侣账号，也是首次初始化时创建的账号 |
| PartnerB | 第二位伴侣账号，由已登录伴侣在账号管理中创建 |
| Visitor | 访客账号，预留给总站 SSO；本地注册接口不允许直接创建访客 |

伴侣角色可以使用内容编辑、情侣小屋和管理功能。访客权限受可见性策略限制，不能进入要求伴侣身份的功能。登录成功后，后端通过 HttpOnly Cookie 保存会话，前端 JavaScript 不会直接读取 JWT 内容。

内容可见性和客户端加密是两个不同概念：

- Public：按公开策略展示。
- PartnersOnly：仅登录后的伴侣可见。
- Encrypted：内容需要按项目对应的加密/访问策略处理；不能因为字段名含有 encrypted 就将普通服务端加密内容等同于端到端加密。
- 小屋保险箱使用浏览器或客户端侧的口令派生和 AES-GCM 加密，派生密钥不会上传到服务端。忘记保险箱口令时，服务端无法替代用户解密。

### 3.2 记录和回顾

| 模块 | 用途 | 典型操作 |
| --- | --- | --- |
| 首页 Dashboard | 查看恋爱计时器、统计和近期内容 | 设置恋爱开始日期后查看相恋天数和近期动态 |
| 文章 / 日记 | 编写长篇或结构化记录 | 新建、保存草稿、发布、编辑、评论、查看版本、回滚 |
| 相册 | 保存图片和视频 | 新建相册、上传媒体、设置封面、设置可见性 |
| 事件 | 管理倒计时和周年纪念 | 设置日期、标签、是否每年重复、重要程度 |
| 时间线 | 集中浏览 Moment 和其他记录 | 按时间查看、搜索、导出或在回收站恢复 |
| 留言板 | 接收留言和互动 | 发布、设置公开状态、后台软删除或管理 |
| 时间胶囊 | 写下未来某个时间才能打开的内容 | 设置开启时间，开启前不能读取正文 |
| 搜索 | 跨模块查找内容 | 搜索文章、相册、事件和碎碎念 |
| 通知 | 汇总纪念日和互动提醒 | 查看未读通知并标记已读 |

文章编辑器使用 Vditor，支持 Markdown、所见即所得、即时渲染和分屏预览。图片可以拖拽、粘贴或通过上传接口插入。编辑器支持自动保存草稿和内容版本历史；多人编辑时，服务端通过 ETag 与 If-Match 检查版本，发生冲突时应选择重新载入、覆盖或取消。

### 3.3 情侣小屋（Cottage）

小屋页面要求 PartnerA 或 PartnerB 登录。实时模块需要 Redis；如果 Redis 不可用，普通内容功能仍可独立排查，但实时功能可能返回 503 或断开 WebSocket。

| 模块 | 说明 |
| --- | --- |
| 报备 | 记录当前城市或位置文本。原始 IP、经纬度只用于一次性反向地理编码，不作为业务位置长期保存 |
| 悄悄话 | 双人文字、图片和贴纸聊天；配置共享客户端密钥后可使用 AES-GCM 端到端加密，密钥不可用时不会降级发送明文 |
| 心情 | 每日心情记录和情绪日历 |
| 心愿单 | 记录两人想一起完成的事情并标记完成 |
| 每日一问 | 双方先独立回答，双方提交后再互相揭晓 |
| 共同计划 / 提醒 | 维护约会计划、行动计划和提醒 |
| 一起听 | 网易云登录、搜索、歌单、推荐、歌词、队列和播放进度同步 |
| 一起看 | 管理片库，并同步播放本地上传视频或直链视频（如 .mp4、.m3u8） |
| 一起玩 | 五子棋、井字棋、黑白棋、记忆翻牌、连连看、你画我猜和画布作品 |
| 报表 / 日历 | 汇总互动和重要日期，帮助回顾共同活动 |
| 兑换券 / 账本 | 管理可兑换的情侣券和共同收支记录 |
| 生理期关怀 / 足迹 | 记录周期信息和共同去过的地点 |
| 保险箱 | 保存双方的私密条目，使用客户端侧加密协议 |

#### 一起听的使用流程

1. 两位用户登录恋爱记并进入“小屋 > 一起听”。单人也可以使用播放和队列功能。
2. 在页面中完成网易云扫码登录，并在网易云手机端确认授权。
3. 搜索歌曲或打开歌单，点击播放；必要时将歌曲加入队列。
4. 双方同时在线时，播放、暂停、切歌、拖动进度和队列变更通过 WebSocket 同步。
5. 页面关闭后，房间状态仍由 Redis 保留；另一方重新进入时会先同步最新状态。

网易云 Cookie 会由后端加密后保存到 Redis，默认有效期为 30 天。该功能依赖 netease-api，上游服务的登录风控、版权和可用性不由本项目保证。使用者需要自行确认相关服务的合规性。

### 3.4 管理后台

管理后台入口为 /admin，主要包括：

- 系统健康：数据库、Redis、磁盘、内存、CPU、上传目录状态，健康评分和趋势。
- 文章、相册、留言、时间线、胶囊：集中管理和软删除。
- 账号管理：创建缺失的伴侣账号、修改资料、查看访客和处理封禁。
- 导出与备份：运行导出、配置自动备份、查看历史、执行恢复预检和恢复。
- 安全日志：查看登录、账号、内容和隐私相关审计记录。
- 回收站：查看软删除内容并恢复。

删除内容优先使用回收站恢复流程。导出的 ZIP 归档本身不是加密文件，应按最高敏感级别保存，不要上传到公开网盘或提交到 Git。

## 4. 系统架构

~~~mermaid
flowchart LR
    U[浏览器或 Android 客户端] --> E[Nginx / Web 前端]
    E --> A[FastAPI API]
    A --> DB[(PostgreSQL)]
    A --> R[(Redis)]
    A --> F[server/uploads]
    A --> B[server/backups]
    A --> W[WebSocket 实时模块]
    A --> N[内部 Netease API]
    W --> R
    N --> M[网易云服务]
~~~

开发编排包含 PostgreSQL、Redis、netease、backend 和 web。生产编排额外使用 Nginx，并将 PostgreSQL、Redis、backend、web 和 netease 放在 love-network 内部网络；生产不会把数据库、Redis 或网易云适配服务直接暴露到公网。

### 4.1 数据保存位置

| 数据 | 位置或介质 | 说明 |
| --- | --- | --- |
| 业务数据 | PostgreSQL 数据卷 | 文章、账号、事件、互动记录等，必须纳入数据库备份 |
| 实时状态 / 缓存 | Redis | 一起听、一起看、聊天和游戏房间状态等；生产有 Redis 卷，但仍应视为可重建状态 |
| 上传媒体 | server/uploads/ | 相册、文章图片、头像、视频等，必须与数据库一起备份 |
| 自动备份 | server/backups/ | 备份 ZIP、计划和历史文件，部署脚本会创建并持久化该目录 |
| TLS 证书 | nginx/ssl/ | 只在服务器保存，禁止提交到 Git |

### 4.2 API 和实时接口

业务 REST API 统一使用 /v1 前缀，健康检查使用 /health。常用入口如下：

| 功能 | API 前缀 |
| --- | --- |
| 认证 | /v1/auth |
| 文章、相册、事件、时间线 | /v1/articles、/v1/albums、/v1/events、/v1/timeline |
| 留言、胶囊、搜索、通知 | /v1/messages、/v1/capsules、/v1/search、/v1/notifications |
| 小屋 | /v1/cottage/*、/v1/checkins、/v1/cottage/wishes |
| 上传、导出、设置 | /v1/uploads、/v1/export、/v1/settings |
| 安全和维护 | /v1/security、/v1/privacy、/v1/audit-logs、/v1/recycle-bin |
| 健康 | /health、/health/ready、/health/system、/health/system/history、/health/system/remediate |

后端启动后可以访问：

- Swagger UI：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc
- 基础健康检查：http://localhost:8000/health

HTTP 请求使用登录 Cookie；WebSocket 连接也需要有效会话并通过来源校验。Android 客户端使用持久化 Cookie Jar，不应自行改成只保存明文 Bearer Token 的实现。

## 5. 安装与启动

### 5.1 前置条件

推荐使用 Docker Compose 启动完整开发环境：

- Docker 20.10+。
- Docker Compose v2+，Windows 使用 Docker Desktop。
- 推荐至少 4 核 CPU、8 GB 内存和 50 GB 可用磁盘。

纯本地开发还需要 Python 3.12、Node.js 20、npm，以及可访问的 PostgreSQL 或 SQLite、Redis。Android 开发需要 Android Studio、Android SDK 和 JDK，具体以 Android/ 工程配置为准。

### 5.2 Docker 开发环境

在项目根目录执行：

~~~bash
docker compose up --build
~~~

启动后访问：

| 服务 | 地址 |
| --- | --- |
| Web | http://localhost:5173 |
| API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

开发编排会将上传目录挂载到 server/uploads/，将备份目录挂载到 server/backups/。数据库数据保存在 Docker 卷中。

如果是全新的空数据库，需要注意：生产初始化向导依赖 BOOTSTRAP_SETUP_TOKEN；当前开发编排使用本地开发密钥，但没有自动替用户生成初始化令牌。需要在未提交的本地 Compose 覆盖配置或本地后端 .env 中传入该令牌，再访问 /setup。已有伴侣账号的开发数据库可以直接打开登录页登录。

常用命令：

~~~bash
docker compose ps
docker compose logs -f backend
docker compose logs -f web
docker compose restart backend
docker compose down
~~~

不要将开发环境内置的数据库、Redis 或 JWT 密钥用于生产。

### 5.3 本地后端和前端

后端：

~~~powershell
cd server
python -m venv .venv
.venv/Scripts/Activate.ps1
pip install -r requirements.lock
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
~~~

Linux 或 macOS：

~~~bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
~~~

前端：

~~~powershell
cd web
npm install
Copy-Item .env.example .env
npm run dev
~~~

.env 中的 BACKEND_PROXY_TARGET 默认指向 http://127.0.0.1:8000。本地开发时请确保 Redis 已运行；一起听、一起看、悄悄话、一起玩和画布 WebSocket 都会用到它。

### 5.4 生产部署

生产部署使用 docker-compose.prod.yml，必须先准备真实域名、DNS、HTTPS 证书和强随机密钥。

1. 复制配置模板：

   ~~~bash
   cp .env.production.example .env.production
   ~~~

   Windows PowerShell：

   ~~~powershell
   Copy-Item .env.production.example .env.production
   ~~~

2. 至少设置以下值：

   - POSTGRES_PASSWORD：数据库强密码。
   - REDIS_PASSWORD：Redis 强密码。
   - JWT_SECRET_KEY：独立的随机 JWT 密钥。
   - COOKIE_VAULT_KEY：与 JWT 密钥不同的独立随机密钥。
   - BOOTSTRAP_SETUP_TOKEN：仅用于第一次创建 PartnerA 的初始化令牌。
   - CORS_ORIGINS：正式访问域名。
   - DOMAIN：证书和 DNS 对应的域名。
   - COOKIE_SECURE=true：生产 HTTPS 必须保持为 true。

3. 生成随机密钥：

   ~~~bash
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ~~~

4. 将证书放入：

   ~~~text
   nginx/ssl/fullchain.pem
   nginx/ssl/privkey.pem
   ~~~

5. 启动部署脚本：

   Linux：

   ~~~bash
   chmod +x deploy.sh
   ./deploy.sh
   ~~~

   Windows：

   ~~~powershell
   powershell -ExecutionPolicy Bypass -File .\deploy.ps1
   ~~~

部署脚本会校验配置、创建目录、构建镜像、启动服务，并通过公网 HTTPS 做健康检查。详细证书、域名、备份和维护说明见 [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) 与 [DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md)。

### 5.5 首次初始化

全新生产实例的初始化流程如下：

1. 打开部署后的站点，前端检测到没有伴侣账号时会跳转到 /setup。
2. 输入部署时配置的 BOOTSTRAP_SETUP_TOKEN。
3. 填写站点名称和恋爱开始日期。
4. 创建第一位伴侣账号。该账号角色为 PartnerA。
5. 返回登录页，使用刚创建的账号登录。
6. 进入“管理后台 > 账号管理”，创建缺失的 PartnerB 账号，并让另一半使用该账号登录。

初始化接口只允许在不存在伴侣账号时成功一次。初始化完成后，应将令牌从密码管理器或部署记录中按安全流程处理，不要写入截图、日志或公开文档。

## 6. Android 客户端

Android 工程位于 Android/，主要能力包括：

- Compose 界面、Retrofit 网络层和持久化 Cookie 会话。
- Room 离线缓存，WorkManager 自动重放同步队列。
- 相机、系统相册上传和 FCM 推送骨架。
- 一起听、一起看、聊天、游戏等主要 WebSocket 模块。
- 客户端加密保险箱和恋爱天数桌面小组件。

构建 Debug APK：

~~~bash
cd Android
./gradlew assembleDebug
~~~

Windows：

~~~powershell
cd Android
.\gradlew.bat assembleDebug
~~~

产物位于 Android/app/build/outputs/apk/debug/app-debug.apk。默认 API 地址面向 Android 模拟器使用 http://10.0.2.2:8000/v1/；真机调试时，应在 app/build.gradle.kts 或客户端服务器配置中改成开发机在局域网内可访问的地址。需要 Firebase 推送时，将 google-services.json 放入 Android/app/，并配置后端 FCM 相关变量；该文件禁止提交。

## 7. 开发者手册

### 7.1 目录结构

~~~text
server/
  app/
    api/v1/       REST 和 WebSocket 路由
    core/         配置、安全、限流和启动检查
    models/       SQLAlchemy 数据模型
    schemas/      Pydantic 请求与响应模型
    services/     业务服务和后台任务
  migrations/    Alembic 迁移
  tests/         后端测试
web/
  src/views/     页面，包含用户端、后台和 Cottage
  src/components/可复用组件
  src/lib/       API、加密、WebSocket 和 PWA 能力
  src/stores/    前端状态和播放器
Android/
  app/src/main/java/com/lovejournal/app/
    data/         远程、本地、仓库和同步
    ui/           Compose 页面和 ViewModel
    sync/         离线队列和 WorkManager
netease-api/     网易云适配服务
nginx/            生产代理和 TLS 配置
docs/             项目、使用、部署和安全文档
~~~

### 7.2 测试、检查和构建

后端：

~~~bash
cd server
python -m pip install -r requirements.lock -r requirements-dev.txt
pytest -q
flake8 app
~~~

前端：

~~~bash
cd web
npm ci
npm test
npm run lint
npm run build
~~~

CI 会执行后端测试、前端测试、lint、前端构建、依赖审计、生产 Compose 配置校验和三个镜像构建。提交涉及数据模型的改动时，应同时添加 Alembic 迁移和对应测试。

常用迁移命令：

~~~bash
cd server
alembic current
alembic upgrade head
~~~

应用启动时会自动执行待处理迁移；生产环境仍建议在发布前单独确认迁移状态，并为数据库做好可恢复备份。

### 7.3 API 开发约定

- 新业务 API 使用 /v1 前缀，避免破坏已有客户端。
- 请求和响应优先定义在 server/app/schemas/，不要在路由中散落未校验字典。
- 访问控制使用现有依赖和可见性策略，不能只依赖前端隐藏按钮。
- 需要实时同步的模块使用 Redis 保存共享状态，并实现 WebSocket 来源校验和断线处理。
- 涉及上传的接口必须检查媒体类型、访问权限和上传引用。
- 修改文章等可并发编辑资源时，保持 ETag / If-Match 版本校验。
- 敏感数据不进入 URL 查询字符串、普通日志或异常响应。

## 8. 运维手册

### 8.1 健康检查

进程存活检查：

~~~bash
curl -fsS https://your-domain.example/health
~~~

部署和容器编排应使用就绪检查。数据库或 Redis 不可用时，该接口返回 HTTP 503：

~~~bash
curl -fsS https://your-domain.example/health/ready
~~~

管理后台还可以查看系统健康评分、组件状态、最近 24 小时趋势和自动修复入口。后端提供以下系统检查接口：

- GET /health/system
- GET /health/system/history?hours=24&limit=48
- POST /health/system/remediate

自动修复会清理自动备份临时目录和临时文件，并记录新的健康快照。执行前应先查看日志和磁盘状态。

### 8.2 查看日志和服务状态

开发环境：

~~~bash
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 web
~~~

生产环境：

~~~bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=100 backend
docker compose --env-file .env.production -f docker-compose.prod.yml logs --tail=100 nginx
~~~

### 8.3 备份与恢复

建议至少同时保留：

1. 应用内导出的完整 ZIP。
2. PostgreSQL 数据库备份。
3. server/uploads/ 媒体备份。
4. 生产部署配置和 TLS 证书的安全副本。

应用内备份统一保存到 server/backups/，计划和历史文件为：

~~~text
server/backups/backup_schedule.json
server/backups/backup_history.json
~~~

恢复前先在管理后台执行预检，确认目标版本、数据库连接和媒体目录可写；恢复过程按业务键幂等补齐，不会覆盖现有条目。恢复完成后应检查登录、文章、相册媒体、实时模块和健康页面。

不要只备份 Redis。Redis 中的实时房间状态可以重建，而 PostgreSQL 和上传媒体丢失会导致核心内容不可恢复。

### 8.4 更新流程

生产更新建议按以下顺序执行：

1. 验证最近一次备份确实可读取。
2. 查看 CHANGELOG.md，确认迁移和配置变化。
3. 拉取代码并检查 .env.production 未被覆盖。
4. 执行部署脚本重新构建服务。
5. 查看 ps、日志、/health 和关键页面。
6. 使用一位伴侣账号验证登录、上传、实时模块和备份入口。

## 9. 常见问题

### 打开站点后反复跳转到 /setup

检查数据库是否真的包含伴侣账号，并确认 backend 连接的是预期数据库。全新生产实例还需要配置 BOOTSTRAP_SETUP_TOKEN；初始化完成后，刷新前端或重新打开站点。

### /setup 提示 Bootstrap disabled 或令牌无效

BOOTSTRAP_SETUP_TOKEN 未传入 backend、令牌有前后空格、或者实例已经完成初始化都会导致此现象。生产配置修改后需要重建或重启 backend 容器。

### 登录成功但刷新后变成未登录

确认访问地址和 CORS_ORIGINS 一致；生产环境必须使用 HTTPS，并保持 COOKIE_SECURE=true。反向代理还要正确转发 HTTPS 协议。不要在不同域名之间切换测试登录 Cookie。

### 一起听、一起看或游戏返回 503

先检查 Redis：

~~~bash
docker compose ps redis
docker compose logs --tail=100 redis
~~~

然后确认 backend 的 REDIS_URL 或生产环境的 Redis 主机、端口和密码正确。一起听还需要 netease 服务处于运行状态；网易云扫码后必须在手机端确认。

### 图片或视频显示 404

确认 server/uploads/ 存在并且挂载到了 backend 和生产 Nginx。检查文件是否被误删、权限是否允许容器读取，以及反向代理配置中的上传路径是否保持一致。

### 后端启动时提示密钥不安全

开发环境不能使用 change-this-secret-before-production。生产环境还必须满足密钥长度要求，并让 COOKIE_VAULT_KEY 与 JWT_SECRET_KEY 使用两个不同的随机值。

### 文章保存提示版本冲突

这是并发编辑保护。先重新载入当前版本并合并内容，或者确认后覆盖对方修改；不要反复重试旧的 I
f-Match 值。

## 10. 相关文档

- 项目总览：[README.md](../README.md)
- 部署指南：[DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)
- 部署检查清单：[DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md)
- Android 说明：[Android/README.md](../Android/README.md)
- 使用指南目录：[docs/guides/](./guides/)
- 贡献规范：[CONTRIBUTING.md](../CONTRIBUTING.md)
- 安全问题报告：[SECURITY.md](../SECURITY.md)
- 许可证：[LICENSE](../LICENSE)

## 11. 许可证和第三方服务

项目主体采用 GNU Affero General Public License v3.0（AGPL-3.0-only）。第三方依赖和许可证清单见 [NOTICE](../NOTICE) 与 [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md)。netease-api 通过上游网易云相关接口支持“一起听”，使用前应自行评估服务条款、版权和所在司法管辖区的合规要求。
