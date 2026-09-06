# 恋爱记 Android（Kotlin + Jetpack Compose）

原生 Android 客户端，对接现有 FastAPI 后端（`/v1`）。离线优先，登录态用持久化 Cookie，
后台 WorkManager 自动同步，含相机/相册上传、FCM 推送骨架与桌面小组件。

## 技术栈

- Kotlin 1.9 · Jetpack Compose（Material3）
- Hilt（依赖注入）
- Retrofit + OkHttp + Kotlinx Serialization
- Room（离线缓存）+ DataStore（会话）
- WorkManager（离线编辑自动同步）
- 系统相机/相册（拍照/选图上传）
- Glance（桌面小组件：在一起天数）
- Firebase Cloud Messaging（推送，需正式构建提供 Firebase 配置）

## 架构概览

```
ui/           Compose 屏幕 + ViewModel（auth / dashboard / messages / mood）
data/
  remote/     Retrofit API、DTO、AuthCookieJar（持久化 HttpOnly Cookie）
  local/      Room 实体、DAO、数据库
  prefs/      SessionManager（DataStore）
  repository/ 仓库层（离线优先 + 同步队列入队）
sync/         SyncEngine（重放队列）、SyncWorker、SyncScheduler
push/         NotificationChannels、LoveMessagingService（FCM）
widget/       LoveDaysWidget（Glance 桌面小组件）
media/        MediaCapture（FileProvider 拍照 URI）
di/           Hilt 模块（网络 / 数据库）
```

### 离线编辑 + 自动同步

发消息 / 心情打卡会先乐观写入 Room（标记 `pendingSync`），同时把变更入队到
`sync_queue` 表。`SyncWorker`（周期 15 分钟 + 写入后立即触发一次）在联网时重放队列、
用服务端返回的记录覆盖本地乐观行，失败自动重试。

### 鉴权

后端用 HttpOnly Cookie（`access_token`）而非 Bearer Token。`AuthCookieJar` 把 Cookie
持久化到 SharedPreferences，跨进程存活；登录成功后再拉 `/v1/auth/me` 取用户资料存入 DataStore。

## 构建

```bash
cd Android
# 在 local.properties 写入 sdk.dir=<Android SDK 路径>
./gradlew assembleDebug
```

产物：`app/build/outputs/apk/debug/app-debug.apk`

### 后端地址

`API_BASE_URL` release 默认 `https://love.invalid/api/v1/`（占位域名，正式构建前必须修改）。
debug 构建默认 `http://10.0.2.2:8000/v1/`（模拟器访问宿主机 localhost）。
真机调试请改 `app/build.gradle.kts` 里的 `buildConfigField`。

## 推送（可选）

FCM 默认未启用。启用步骤：

1. 在 Firebase 控制台创建应用（包名 `com.lovejournal.app`），下载 `google-services.json` 放到 `app/`。
2. 在正式构建环境启用 `com.google.gms.google-services` 插件，让 `google-services.json` 生成 Firebase 资源。
3. 后端设置 `FCM_PUSH_ENABLED=true`，并配置 `FCM_SERVICE_ACCOUNT_FILE` 或 `FCM_SERVICE_ACCOUNT_JSON`。

`google-services.json` 已在 `.gitignore`，请勿提交。

## 已覆盖范围

Android 客户端现已与 FastAPI 服务端的 REST 能力完整对齐，并接入主要实时 WebSocket：

- 主内容：文章、相册、留言、纪念日、时间线、回忆、评论、版本历史与回滚、胶囊、搜索、通知、回收站。
- 小屋互动：聊天、收藏、撤回、置顶语录、媒体面板、聊天关键词与回忆卡、心情、签到、心愿、每日一问。
- 同步娱乐：一起听、一起看、五子棋、井字棋、黑白棋、记忆翻牌、连连看、你画我猜。
- 生活工具：兑换券、提醒、约会计划、情侣账本、恋爱月报、足迹地图、生理期关怀。
- 私密空间：PBKDF2-SHA256 + AES-GCM 客户端加密，与 Web 端保险箱协议互通，支持换口令、重置和自动锁定。
- 管理维护：系统健康、存储统计、审计日志、安全用户、备份计划/历史与自动备份触发。
- 平台能力：离线队列、Cookie 会话、FCM、桌面小组件、相机/系统相册上传。

服务端 220 个 HTTP/WebSocket 路由中，214 个 REST 路由均已在 Retrofit 声明；聊天、一起听、一起看、通用游戏、你画我猜等 WebSocket 由专用 OkHttp 客户端实现。
