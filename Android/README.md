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

FCM 默认未启用。**推荐路径：应用内向导，无需重新构建**：

1. 服务端：在 `.env` 设 `FCM_PUSH_ENABLED=true` 并把 Firebase 服务账号 JSON 压成单行填入 `FCM_SERVICE_ACCOUNT_JSON`，重启服务端。
2. Firebase 控制台添加 Android 应用（包名 `com.lovejournal.app`），下载 `google-services.json`。
3. 在应用「设置 → 通知与推送 → 配置推送」中导入该文件并向导会自动完成注册；向导也会检测服务端状态并给出缺失步骤。

进阶路径（分发预构建 APK 时）：把 `google-services.json` 放到 `app/` 并在构建环境启用 `com.google.gms.google-services` 插件后自行构建。`google-services.json` 已在 `.gitignore`，请勿提交。

服务端状态可用 `GET /v1/push/status` 查询；详见 `docs/design/FCM_IN_APP_SETUP_DESIGN.md`。

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

### 2026-09 功能补全记录

上述覆盖范围中此前「仅声明未接线」的部分现已全部落地：

- **时间线**：动态支持多图发布与全屏预览、评论树（含回复对方）、新增「回忆」页签（往年今日）
- **悄悄话**：支持发送图片消息（与 Web 端一致走 `uploads/checkin` 压缩上传），图片 / 贴纸 / 语音消息按类型渲染
- **留言板**：自己的留言支持编辑、删除（进回收站）、版本历史查看与一键回滚
- **情侣账本 / 生理期关怀 / 小屋提醒**：条目编辑（PATCH 仅提交变更字段）
- **离线队列**：报备签到、心愿单创建支持离线暂存、联网自动重放（Idempotency-Key 幂等，防断线重放产生重复数据）
- **首次初始化**：App 内 bootstrap 引导（初始化令牌 + 站点名 + 恋爱起始日），登录后可为另一半开通账号；设置页支持头像上传
- **单元测试**：服务器地址归一化（直连 / 反代两种部署形态）、保险箱加密原语（PBKDF2 + AES-GCM）全覆盖

仍依赖部署配置的能力：FCM 推送需要提供 `google-services.json`（见下方「推送」）；iOS 客户端不在本仓库范围。
