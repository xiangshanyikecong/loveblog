# FCM 推送应用内引导式配置设计（自托管友好）

> 状态：设计稿（未实施）。目标：把"FCM 推送配置"从分散在文档里的 5 个手动步骤，变成 Android 应用内可检测、可续做的引导流程，并将客户端配置的门槛从"改 gradle 重打包"降为"应用内导入一个文件"。

## 1. 背景与现状

FCM 推送默认关闭，自托管用户需要跨 Firebase 控制台、Android 工程、服务端环境三处手动配置。现状链路：

| 环节 | 现状 | 位置 |
| --- | --- | --- |
| 客户端依赖 | firebase-messaging 始终打进 APK，但**未应用 google-services gradle 插件**，默认构建无法初始化 Firebase | `Android/app/build.gradle.kts:3-9,122-123` |
| 客户端闸门 | 所有 Firebase 调用前置 `FirebaseApp.getApps(context).isEmpty()` 守卫，未初始化时静默 no-op（无 token 上报、无接收） | `data/repository/PushRepository.kt:47,67,91` |
| 服务端开关 | 三层判断：`fcm_push_enabled`（env）∧ `fcm_configured`（service account file/json 任一非空）∧ firebase-admin 可导入；任一不满足则投递**静默跳过** | `server/app/services/notification_delivery.py:351-382`、`server/app/core/config.py:114-116,193-197` |
| 服务端自检 | 仅当显式 `FCM_PUSH_ENABLED=true` 且缺凭据时启动报 RuntimeError；开关为 false 时一切静默——**自托管用户很难发现"为什么收不到推送"** | `server/app/main.py:584-595` |
| Token 上报 | 登录成功即 `PUT /v1/push/fcm-tokens`；注册端点不检查 FCM 是否启用（禁用时 token 照常入库但不投递） | `LoveJournalApp.kt:117-126`、`server/app/api/v1/push.py:145-180` |
| 设置 UI | **完全没有推送相关 UI**（SettingsScreen 无 push 内容） | `ui/settings/SettingsScreen.kt` 全文 |
| 文档 | 仅 `Android/README.md:60-68` 有三步说明；`DEPLOYMENT_GUIDE.md` / `DEPLOYMENT_CHECKLIST.md` 对 FCM **零覆盖** | — |

当前用户要做的手动步骤（汇总自 `Android/README.md:60-68`）：

1. Firebase 控制台创建应用（包名 `com.lovejournal.app`），下载 `google-services.json` 放入 `Android/app/`；
2. **修改 `build.gradle.kts` 启用 `com.google.gms.google-services` 插件并重新构建安装 APK**；
3. 服务端 `.env` 设 `FCM_PUSH_ENABLED=true` + `FCM_SERVICE_ACCOUNT_JSON`（服务账号 JSON 压成单行）；
4. 重启容器；
5. （无任何反馈机制确认配置成功与否）。

其中第 2 步要求用户具备 Android 构建能力，是最大的门槛；第 5 步的"静默失败"让问题排查无从下手。

## 2. 目标与非目标

**目标：**

1. 设置页提供"通知与推送"状态卡，四态可辨（双端未配 / 仅缺服务端 / 仅缺客户端 / 就绪）。
2. 应用内向导覆盖全部步骤：分端检测 → 服务端步骤给可复制命令 → 客户端步骤**应用内导入 google-services.json 免重打包**（推荐路径）→ 自动注册 token → 验证。
3. 服务端提供状态探测端点，客户端能区分"缺哪一端"。
4. 部署文档补齐 FCM 章节。

**非目标：**

- 不改推送内容与渠道策略（沿用 `NotificationChannels` 三渠道与 data-only 协议）。
- 不做 iOS/APNs。
- 不做"发送测试通知"服务端端点（列为可选增强，见 §7）。

## 3. 核心决策：运行时 Firebase 初始化（免重打包）

### 3.1 原理

gradle 的 `google-services` 插件只是**编译期**把 `google-services.json` 转成资源，再由 `FirebaseInitProvider` 自动初始化；Firebase 本身提供公开的手动初始化 API：

```kotlin
FirebaseApp.initializeApp(context, FirebaseOptions.Builder()
    .setApplicationId(mobilesdkAppId)   // json: client[0].client_info.mobilesdk_app_id
    .setApiKey(currentKey)              // json: client[0].api_key[0].current_key
    .setProjectId(projectId)            // json: project_info.project_id
    .setGcmSenderId(projectNumber)      // json: project_info.project_number
    .build())
```

初始化成功后，现有全部 `FirebaseApp.getApps(context).isEmpty()` 守卫（`PushRepository.kt:47,67,91`）**自动通过**，token 获取、上报、接收链路零改动生效。也就是说：**让用户在应用内选入 google-services.json，即可完全绕过改 gradle + 重打包**。

### 3.2 两种路径对比

| | Option A：运行时导入（推荐，v1 实现） | Option B：构建期插件（现状文档路径，保留为进阶） |
| --- | --- | --- |
| 用户动作 | 应用内选文件 | 改 gradle + 放 json + Android Studio 重打包 |
| 门槛 | 无开发环境要求 | 需完整 Android 构建链 |
| 适用 | 自托管普通用户 | 分发预构建 APK 的维护者 |
| 代码改动 | 新增解析/初始化/导入 UI | 无（文档既有） |

Option B 保留在向导末尾作为"进阶：为分发自构建 APK"的说明，不作为主路径。

### 3.3 风险与缓解

| 风险 | 缓解 |
| --- | --- |
| json 与包名不匹配（用户选错项目） | 解析时校验 `client_info.android_client_info.package_name == "com.lovejournal.app"`，不符即报错并显示实际包名 |
| json 含多个 client | 按 package_name 取匹配项 |
| 设备无 Google Play 服务 | `FirebaseMessaging.getToken` 失败时给出明确错误文案（"设备缺少 Google 服务框架"），不是笼统失败 |
| json 落盘的安全性 | client json 本就是公开的客户端配置（api_key 非机密），存应用私有目录（`MODE_PRIVATE`）足够；真正敏感的是服务端 service account，向导文案明确提醒勿外发 |
| 与 Option B 共存 | 初始化前先查 `FirebaseApp.getApps()`，插件已初始化则跳过导入步骤（向导自动检测并隐藏该步） |
| Play Services 轮询 token 失效 | 沿用既有 `onNewToken` 上报（`push/LoveMessagingService.kt:50-55`），无需改 |

### 3.4 初始化时机与持久化

- `LoveJournalApp.onCreate`：`if (FirebaseApp.getApps(context).isEmpty())` → 读取私有文件 `files/firebase_config.json` → 手动初始化；文件不存在则维持静默 no-op。任何异常捕获并写入诊断信息（§5.1），不崩溃。
- 导入成功时把**原始 json 文本**整体存入该文件（下次启动重放初始化）；设置页提供"移除推送配置"入口（删文件 + 服务端 DELETE token + 本地 `deleteToken`）。
- 时机安全：`FirebaseInitProvider` 是 auto-init ContentProvider，先于 `Application.onCreate` 执行；默认构建下 provider 因缺资源而跳过初始化，与我们手动初始化不冲突。

## 4. 服务端新增：推送状态探测端点

现状 FCM 没有任何状态查询手段（`GET /v1/push/public-key` 的 `enabled` 仅反映 Web Push，`server/app/api/v1/push.py:43-49`），引导流程无法判断"缺哪一端"。新增：

```
GET /v1/push/status        （登录用户可读，仅布尔值，无敏感信息）

{ "fcm":      { "enabled": false, "configured": false, "dependency_available": true },
  "web_push": { "enabled": false, "vapid_configured": false } }
```

- 实现：`push.py` 新路由，直接读 `settings.fcm_push_enabled / fcm_configured`（`config.py:114-116,193-197`）与 firebase_admin 可导入性，逻辑与 `notification_delivery.py:351-353` 的 `_fcm_enabled()` 一致。
- **兼容旧服务端**：客户端收到 404 时降级为"无法检测服务端状态"，向导直接展示两端全部步骤（与现状文档等价，不更差）。
- Web 端 `NotificationsView.vue:56-94` 的推送状态卡可顺手加一行"Android FCM 服务端状态"（同一端点），方便管理员在网页侧核对——可选小改动。

## 5. Android 端设计

### 5.1 探测与诊断层（PushRepository 扩展）

```kotlin
data class PushDiagnostics(
    val firebaseInitialized: Boolean,   // FirebaseApp.getApps().isNotEmpty()
    val importedConfigExists: Boolean,  // files/firebase_config.json 存在
    val initError: String?,             // 手动初始化失败原因
    val token: String?,                 // currentFcmToken() 结果
    val permissionGranted: Boolean,     // POST_NOTIFICATIONS（TIRAMISU+）
)
```

设置卡与向导共用这一个数据源；现有注册成功/失败结果在此汇总展示，终结"配置后无反馈"。

### 5.2 设置页入口

`SettingsScreen.kt` 新增分区"通知与推送"（复用 `LoveSectionTitle` + `LoveSoftCard`，开关行样式参考站内现成的 `Switch` 行，`SettingsScreen.kt:200-219`）。卡片状态机：

| 状态 | 判定（client 探测 + `/push/status`） | 卡片内容 |
| --- | --- | --- |
| 未启用 | FirebaseApp 空 且 服务端 enabled=false | "推送未启用" + 【配置推送】按钮 → 向导 |
| 仅缺客户端 | 服务端 enabled=true 且 FirebaseApp 空 | "服务端已就绪，本应用未配置" → 向导直接落在客户端步 |
| 仅缺服务端 | FirebaseApp 已初始化 且 服务端 enabled=false | "本应用已配置，服务端未启用" → 向导直接落在服务端步 |
| 就绪 | 双端就绪 | 权限状态行 + 已注册设备列表（`GET /v1/push/fcm-tokens`，含删除设备）+ 【重新检测】 |

向导全程**只读展示**，不提供"关闭推送"开关（推送开关即系统通知权限 + 渠道设置，避免重复语义）。

### 5.3 向导（新 PushSetupScreen，顶部 stepper）

仓库内没有多步 stepper 组件；对话框式引导只有 BootstrapDialog 一个先例（`ui/auth/LoginScreen.kt:159-203`，AlertDialog + 说明文案 + 表单 + 行内错误 + 提交态）。因步骤多且含"离开应用操作"，采用**独立全屏 Screen**（返回可续做），视觉沿用 LoveSoftCard 分步卡片。已完成步骤存 `SharedPreferences`（key `push_wizard_progress`），中断后可续。

**S1 自动检测（进入时）**：并行调 `/push/status`（404 则置 unknown）与本地 `PushDiagnostics` → 自动跳过已完成的大步，落到第一个缺失步骤。

**S2 服务端配置（若 `fcm.enabled=false`）**：

1. 图文指引：Firebase 控制台 → 项目设置 → 服务账号 → 生成新私钥；
2. 一键复制命令（把私钥 JSON 压成单行，bash 与 PowerShell 各一条，复制按钮）；
3. 提示填入 `.env`：`FCM_PUSH_ENABLED=true`、`FCM_SERVICE_ACCOUNT_JSON=<单行>`；
4. 提示 `docker compose up -d` 重启（复制按钮）；
5. 【我已完成，重新检测】→ 重调 `/push/status`，`enabled=true` 才放行（unknown 时允许"跳过检测，继续"并提示最终以实际收推为准）。

**S3 客户端配置（若 `firebaseInitialized=false`）**：

1. 图文指引：Firebase 控制台 → 添加 Android 应用（强调包名 `com.lovejournal.app`）→ 下载 `google-services.json`；
2. 【导入配置文件】：`ActivityResultContracts.OpenDocument`（`application/json`）→ 应用内解析 + 校验（§3.3）→ 写私有文件 → 手动初始化；
3. 初始化成功即取 token 并 `PUT /v1/push/fcm-tokens`（复用 `PushRepository.registerCurrentFcmToken`，`PushRepository.kt:41-44`）；
4. 每一步失败都有行内错误（包名不匹配 / 无 Play 服务 / 网络失败分别给出文案与"重试"）。

**S4 验证**：显示 `PushDiagnostics` 全量状态 + 已注册设备列表；提示验证方式："让对方给你发一条留言（或站内通知触发事件），通知应出现在系统通知栏"；附各通知渠道的说明（`NotificationChannels.kt:26-42`）与跳转系统通知设置的入口。

### 5.4 Token 生命周期（零改动确认）

登录上报（`LoveJournalApp.kt:117-126`）、登出注销（`AuthRepository.kt:123-125` → `PushRepository.kt:46-58`）、401 清本地 token（`LoveJournalApp.kt:95-115`）全部复用——运行时初始化完成后这些链路自动生效。

## 6. 文档同步（部署视角补齐）

| 文件 | 改动 |
| --- | --- |
| `DEPLOYMENT_GUIDE.md` | 新增"推送通知（可选）"章节：服务端两变量 + Web Push / FCM 两条路径 + 指向应用内向导 |
| `DEPLOYMENT_CHECKLIST.md` | 追加可选检查项"如需 Android 推送：FCM_PUSH_ENABLED 与 service account 已配置" |
| `Android/README.md:60-68` | 重写为"推荐：应用内向导（免重打包）；进阶：构建期插件"双路径 |
| `.env.production.example:102-106` | 注释补充"可由 Android 应用内向导引导完成" |

## 7. 实施计划

| 项 | 内容 | 预估 |
| --- | --- | --- |
| 服务端 | `GET /v1/push/status`（push.py + 一个响应 schema） | 0.5 天 |
| Android 基础 | json 解析校验 + 手动初始化（LoveJournalApp）+ PushDiagnostics | 1 天 |
| Android UI | 设置卡四态 + PushSetupScreen（S1-S4）+ 进度持久化 | 2-2.5 天 |
| 文档 | §6 四处 | 0.5 天 |

可选增强（不阻塞）：服务端 `POST /v1/push/test`（向当前用户所有活跃 token 发一条 data-only 测试消息，复用 `_deliver_fcm_push`），向导 S4 变成一键真验证。

## 8. 测试计划

状态矩阵（`/push/status` × 本地初始化）：双缺 / 仅缺客户端 / 仅缺服务端 / 双就绪 / 旧服务端 404 降级，逐一走完向导并确认步骤跳转正确。

关键用例：

- 导入匹配/不匹配包名的 json → 成功初始化 / 明确报错；
- 导入后杀进程重启 → 守卫通过、token 自动上报（日志确认一次 `PUT fcm-tokens`）；
- 无 Google Play 服务的设备 → S3 明确错误文案而非静默失败；
- `onNewToken` 轮换（卸载重装）→ 服务端 token 更新且旧 token 不重复投递；
- "移除推送配置"→ 私有文件删除、服务端 token 注销、设置卡回到"未启用"；
- 登录 → 登出 → 再登录的 token 生命周期回归（`AuthRepository.kt:78,123-125`）；
- 服务端配置后故意给错 service account → `/push/status` 仍为 enabled=true，投递失败仅日志（现状行为，文档注明排查方法）。
