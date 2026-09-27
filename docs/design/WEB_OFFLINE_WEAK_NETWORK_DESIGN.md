# Web 端离线与弱网设计（草稿落盘 + 离线写入队列 + 只读缓存）

> 状态：设计稿（未实施）。目标平台 `web/`（Vue 3 + Vite，无 Pinia、无 workbox）。

## 1. 背景与问题

Android 端已有完整的离线优先架构（Room 本地库 + SyncQueue 离线重放），而 Web 端 PWA 只缓存了应用壳和静态资源，**API 数据完全不缓存、没有任何写入队列**。日记/文章写作是本产品核心场景，"写到一半断网/关页丢稿"是 Web 端用户最能感知的痛点。

### 1.1 现状证据

| 现状 | 位置 |
| --- | --- |
| Service Worker 显式排除 `/api/`、`/v1/`，API 请求永不缓存 | `web/public/sw.js:59` |
| SW 仅预缓存 5 个壳文件，静态资源 stale-while-revalidate | `web/public/sw.js:20,76-89` |
| axios 无全局超时、无重试、无离线队列（唯一超时在 logout） | `web/src/lib/api.js:187-240` |
| 编辑器 30s 定时器把未保存内容**直传服务器**，断网时仅置 `saveError`，无本地暂存 | `web/src/views/ArticleEditorView.vue:631-639,560` |
| vditor 自带 localStorage 草稿被显式关闭 | `web/src/components/RichTextEditor.vue:104-106` |
| `utils/editorSave.js` 只防异步保存竞态，不是草稿持久化 | `web/src/utils/editorSave.js:18-28` |
| 全 `web/` 无任何 IndexedDB / localForage / workbox 使用 | 全仓 grep 零命中 |
| 视图每次挂载全量重拉数据，无缓存层 | `TimelineView.vue:121`、`AlbumsView.vue:121` 等 |
| 认证是 cookie 会话（非 token），401 才清会话，已有 `online` 事件重试范式 | `web/src/lib/api.js:187-190`、`web/src/stores/auth.js:63-70,156-161` |
| 媒体一律即时上传，无本地暂存 | `web/src/components/MediaCapture.vue:278-284` |

### 1.2 服务器端已有的同步基建（利好）

增量同步的地基比预期好，多数模型已具备同步三要素：

| 模型 | `updated_at` | `version` | 软删除 | 幂等键 |
| --- | --- | --- | --- | --- |
| Article | ✅ `server/app/models/article.py:67` | ✅ `:74` | ✅ `:73` | ❌ |
| Moment（时光轴） | ✅ `server/app/models/moment.py:60` | ✅ `:67` | ✅ `:66` | ✅ `client_idempotency_key` `:70` |
| CheckIn | ✅ `server/app/models/checkin.py:79` | ✅ `:86` | ✅ `:85` | ✅ `:88` |
| Album | ✅ `server/app/models/album.py:55` | ❌ | ✅ `:61` | ❌ |

此外，文章编辑已跑通 ETag/If-Match 乐观锁与 409 冲突 UI（`web/src/lib/api.js:827-887`、`ArticleEditorView.vue:536-558`），可直接复用为同步冲突策略；聊天消息 POST 已支持 `Idempotency-Key` 头去重（`server/app/api/v1/cottage_chat.py:287-304`）。

## 2. 目标与非目标

**目标（按优先级）：**

1. **P0 草稿永不丢**：编辑中的日记/文章内容实时落 IndexedDB，断网、关页、崩溃后均可恢复。
2. **P1 离线写入队列**：断网期间的创建/编辑操作有序暂存，恢复联网后自动增量重放，幂等不重发。
3. **P2 只读缓存与弱网优化**：最近日记/时光轴/相册等关键只读数据离线可浏览，二次进入秒开；API 请求有超时与受控重试。
4. 全程不破坏项目隐私红线（见 §8）。

**非目标：**

- 不做"一起听"任何数据缓存（模块自身已声明 R8.4 永不持久化，`web/src/lib/cottageListenAudio.js:24`）。
- 不缓存密码保护内容（带 `X-Content-Password` 的请求/响应）。
- 不做 Admin 管理端离线。
- 不做 Web 端聊天离线队列（Android 已覆盖；Web 聊天 WS 发送在未连接时丢弃是既有行为，`web/src/lib/cottageChatWs.js:159-165`，另行评估）。
- 不引入 workbox / vite-plugin-pwa，保留手写 `sw.js`，避免构建链重构。
- 不做端到端加密的离线草稿（与 Android Room 明文落盘对等即可，见 §8）。

## 3. 总体架构

新增一个 `web/src/lib/offline/` 模块作为唯一的 IndexedDB 访问层，视图与 api.js 不直接碰 IndexedDB：

```
视图层 (views/)
  │
  ├─ ArticleEditorView ──── offline/drafts.js ────┐
  │                                               │
api.js（新增 queueWrite 包装）── offline/outbox.js ─┼──▶ IndexedDB `love-offline-v1`
  │                                               │      ├─ store: drafts    (草稿)
sw.js（运行时缓存白名单）◀────────────────────────┘      ├─ store: outbox    (写队列)
                                                         ├─ store: snapshots (只读快照)
flush 引擎（online/visibilitychange/focus 触发）─────────┘      └─ store: meta
```

分层职责：

| 层 | 解决的问题 | 落盘内容 |
| --- | --- | --- |
| L2 草稿（drafts） | 写作中断网/关页/崩溃不丢稿 | 编辑器明文内容 |
| L3 写队列（outbox） | 断网期间的写操作不丢、重放幂等 | 待重放的请求描述 |
| L1 快照（snapshots + SW 缓存） | 离线可浏览、二次进入秒开 | 最近列表/详情 JSON、图片 |

## 4. 存储选型与数据库设计

### 4.1 选型

- **`idb`**（~1.4KB gzip，IndexedDB 的 Promise 封装）作为唯一新增依赖。不选 localForage（无索引/游标抽象，队列扫描不便）；不选手写原生 API（回调地狱、升级事务繁琐）。
- 不用 Pinia 管理离线状态：项目无 Pinia（`web/package.json:26-51`），离线状态沿用现有"模块级单例 ref + 组合式函数"模式（对齐 `stores/auth.js` 的写法），导出 `useOffline()`。

### 4.2 数据库 Schema

数据库名 `love-offline-v1`（版本号随 schema 变更递增，用 `idb` 的 `upgrade` 回调迁移）：

```js
// store: drafts —— 写作草稿（P0）
{ key: "article:new" | "article:<aid>",   // 主键，与路由对应
  title: string,
  content: string,                        // markdown 原文（与提交 payload 一致）
  cover: string | null,
  baseVersion: number | null,             // 打开时的服务端版本，供恢复冲突判断
  serverUpdatedAt: string | null,         // 打开时服务端 updated_at
  updatedAt: number }                     // 本地最后写入时间戳

// store: outbox —— 离线写队列（P1）
{ id: autoIncrement,
  kind: "moment.create" | "checkin.create" | "article.create"
      | "article.update" | "moment.comment",   // v1 白名单，见 §6.3
  resourceKey: "moment:<cid>" | "article:<aid>" | "article:new",
                                          // 同一资源的操作串行重放
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  url: "/v1/...",                        // api.js 相对路径
  body: object | null,
  ifMatch: string | null,                // article.update 的乐观锁版本
  idempotencyKey: "<uuid>",              // 每次入队生成一次，重放复用
  createdAt: number, attempts: number, lastError: string | null }

// store: snapshots —— 只读快照（P2）
{ key: "timeline:page:1:desc" | "articles:published" | "article:<aid>"
      | "albums" | "dashboard", ...,
  payload: object, fetchedAt: number }

// store: meta —— 游标/计数等杂项（P3 增量同步用）
```

### 4.3 存储配额与存续

- 首次初始化时调用 `navigator.storage.persist()` 申请持久化存储，降低浏览器淘汰风险（ IndexedDB 本身是 best-effort，不承诺强持久——文档与 UI 文案中如实表述"本地草稿保留在本设备"）。
- 预算：快照 + 草稿 + 队列 v1 全 JSON，合计 < 5MB；SW 图片缓存单独限额（§7.1）。

## 5. L2 草稿自动保存（P0，纯前端）

### 5.1 写入时机

- **输入防抖 3s**：监听标题输入与 vditor `input` 事件（vditor 已有关键回调出口，`RichTextEditor.vue:93-232`），内容非空才写。
- **强制 flush**：`beforeunload`、`visibilitychange → hidden`、路由离开守卫（复用 `ArticleEditorView.vue:622-629` 的现有拦截点）三个时机同步写入（IndexedDB 事务在 unload 前发起即可，浏览器会保证已提交事务完成）。
- 本地草稿与现有 30s 直传自动保存**并存**：本地草稿先落（毫秒级、必成功），网络自动保存失败（`ArticleEditorView.vue:560` 的 `saveError` 分支）时不清本地草稿——这是"关页即丢"问题的直接补丁。

### 5.2 恢复策略

编辑器挂载时（`ArticleEditorView.vue` 加载文章成功的回调内）：

```
存在本地草稿 且 草稿.updatedAt > serverUpdatedAt
  → 显示恢复条："检测到本地未同步草稿（保存于 12:03），恢复 / 丢弃"
  → 恢复：回填 title/content/cover，baseVersion 沿用草稿值
  → 丢弃：删除 draft key
草稿.baseVersion 与当前服务端 version 不一致时同样提示（正文按草稿恢复，
后续保存走既有 If-Match 409 冲突 UI）
```

### 5.3 清理时机

- 任何一次保存成功（含 30s 自动保存、Ctrl+S）后删除对应 draft key。
- 文章删除成功后顺带删除 `article:<aid>` 草稿。

### 5.4 范围

v1 只接 **ArticleEditorView**（核心写作场景）。时光轴发布框、打卡等短输入场景风险低，列为 P1 之后的小增强，复用同一 `drafts.js`。

## 6. L3 离线写入队列（P1）

### 6.1 入队判定（在 api.js 响应/错误拦截器附近统一收口）

```
请求失败 且 属网络类错误（axios code ERR_NETWORK / ECONNABORTED，
或 !navigator.onLine）
且 method ∈ {POST, PUT, PATCH, DELETE}
且 kind ∈ 白名单（§6.3）
且 请求未携带二进制 FormData（v1 限制，见 §6.4）
→ 生成 idempotencyKey，写入 outbox，返回特殊 rejection
  （调用方据此 toast"已存入待同步队列，联网后自动发送"，不弹原始报错）
```

4xx 校验错误不入队（重放也会失败）；401 不入队（应先登录）。

### 6.2 重放引擎（`offline/outbox.js`）

- **触发时机**：`window online` 事件、`visibilitychange → visible`、`focus`、在线状态下每 15s 轻量轮询（对齐 `stores/auth.js:156-161` 已有的 online 重试范式）。
- **顺序**：同一 `resourceKey` 严格串行（保证 `article.create` 先于其 `article.update`）；跨资源并发 ≤ 2。
- **退避**：网络失败按 1s/5s/15s/30s/60s/120s 重试，超过 8 次转入死信；恢复在线后立即重试一轮。
- **幂等**：重放携带原 `idempotencyKey`。服务端改造见 §6.3。
- **结果处理**：
  - 2xx：删队列项，通知视图刷新对应数据（走既有各视图 onMounted 重拉或事件总线）。
  - **409 冲突**（article.update 的 If-Match 过期）：保留队列项并置 `lastError`，复用既有 `ArticleVersionConflictError` 弹窗流程（`api.js:873-887`、`ArticleEditorView.vue:536-558`），用户选择"强制覆盖/放弃"后更新 If-Match 重放或删除队列项。
  - 401：暂停整个队列，提示重新登录（cookie 会话过期）；登录成功后自动恢复。**不清空队列**。
  - 其余 4xx：转死信（见 §6.5）。

### 6.3 幂等服务端改造点

| 端点 | 现状 | 改造 |
| --- | --- | --- |
| `POST /v1/timeline`（Moment） | 已有 `client_idempotency_key` 列 + 唯一约束（`moment.py:70`） | 确认路由读取请求体该字段并返回已存在资源（未读取则补齐） |
| `POST /v1/checkins`（CheckIn） | 同上（`checkin.py:88`） | 同上 |
| `POST /v1/articles` | 无幂等键 | 接受 `Idempotency-Key` 请求头，重放返回首次创建的资源（参考 chat 的实现 `cottage_chat.py:287-304` 抽成通用依赖） |
| `PUT/PATCH /v1/articles/:aid` | 已有 If-Match 乐观锁 | 版本锁即幂等保障，无需改 |
| `POST /v1/timeline/:mid/comments` | 无 | 同文章，接受 `Idempotency-Key` |

### 6.4 媒体与队列边界（v1 决策）

- v1 队列只支持 **JSON 载荷**。带图写入（时光轴配图、打卡配图）断网时不入队，维持现状提示联网重试。
- 理由：图片 Blob 入队需要把 `uploadImageWithCompression` 的产物（`api.js:321-332`）先压缩存 Blob 再在重放时上传——可行性成立（IndexedDB 支持 Blob），但涉及"上传 URL 与消息体两段式入队"，复杂度翻倍；单独作为 P1.5 增强。
- 聊天加密消息不入队（密文+iv 可入队，但优先级低且 Android 端已有同类先例仅存纯文本，`ChatRepository.kt:304-338`）。

### 6.5 死信（dead-letter）

- `attempts` 超限或 4xx 校验失败的项置为 dead 状态，不出现在待同步计数里。
- 在设置页"离线与同步"入口可查看死信列表：显示 kind/摘要/错误，支持"复制内容后丢弃"。防止用户内容以不可见方式滞留。

### 6.6 全局 UI

- **离线横幅**：`MainLayout` 顶部细条（`navigator.onLine` + SW message 双信号），离线时显示；有待同步项时显示"N 项待同步 · 立即同步"。
- 入队 toast："已保存在本机，联网后自动同步"。
- 设置页新增"离线与同步"卡片：队列概览、死信入口、"清除本地离线数据"按钮。

## 7. L1 只读缓存与弱网优化（P2）

### 7.1 SW 运行时缓存（改 `web/public/sw.js`）

| 匹配 | 策略 | 限额 |
| --- | --- | --- |
| `GET /uploads/*`（图片类 content-type） | cache-first，命中即回，后台不刷新 | 独立 Cache，条目 ≤ 300，超限按最早写入删除 |
| `GET /v1/dashboard | /v1/timeline | /v1/articles | /v1/albums | /v1/checkins` | network-first，失败回退缓存副本（同时写一份 JSON 进 snapshots store 供视图层标注"离线数据 · HH:mm"） | 单 key 覆盖更新 |

**显式排除（命中即透传，绝不缓存）：** `/v1/listen/**`（R8.4）、`/v1/admin/**`、`/v1/auth/**`、`/v1/push/**`、携带 `x-content-password` 请求头的请求（SW 可读请求头，直接判断）、非 GET。

视图接入顺序：Dashboard → Timeline → Articles 列表/详情 → Albums（每处改动都是"onMounted 拉取失败或无网时读 snapshots + 顶部提示离线数据"，模式统一后逐页铺开）。

### 7.2 弱网微优化（低成本，可并入 P2）

- axios 全局默认超时：普通请求 15s、上传 60s（现状无超时，弱网下请求悬挂）。
- `uploadImageWithCompression` 失败自动重试 1 次（幂等的纯上传）。
- 富文本/相册图片统一 `loading="lazy"`（检查现有 img 标签补齐）。

### 7.3 增量拉取端点（P3，可选，暂不承诺）

若需要真正的"离线浏览全部历史 + 多端一致"，新增 `GET /v1/sync?since=<ISO8601>&scopes=timeline,articles,albums,checkins`：

```json
{ "cursor": "2026-09-27T08:00:00Z",
  "changes": [ { "type": "moment", "id": "...", "op": "upsert|delete",
                 "updated_at": "...", "version": 3, "data": { ... } } ] }
```

服务端依据：所有目标模型已有 `updated_at` + 软删除；**Album 需补 `version` 列**（一次 Alembic 迁移）。客户端把游标存 `meta` store，配合 SW 的 network-first 形成完整离线读。此项独立立项，不阻塞 P0-P2。

## 8. 安全与隐私合规

项目已有明确的持久化红线（`cottageListenAudio.js:24` R8.4），本设计把"什么允许落盘"作为显式决策：

| 数据 | 落盘？ | 说明 |
| --- | --- | --- |
| 文章草稿正文（明文 markdown） | ✅ drafts | 与 Android 端 Room 明文落盘对等；登出清除 |
| 最近日记/时光轴/相册 JSON 快照 | ✅ snapshots | 情侣双账号的私有内容，存于本机浏览器 profile |
| 相册/文章图片 | ✅ SW Cache | 与 JSON 快照同密级 |
| **一起听**音频/歌词/签名直链 | ❌ 永不 | R8.4 既有红线，SW 排除 + 视图层不写快照 |
| **密码保护内容**（X-Content-Password 请求） | ❌ 永不 | SW 请求头判断排除；视图层不写快照 |
| 聊天 E2EE 明文/密钥信封 | ❌ 不新增 | chatCrypto 既有策略不变（仅 publicMeta+proof 进 localStorage） |
| 登录态 | 不变 | cookie 会话，无 token 落盘 |

清理联动：`stores/auth.js` 的 `logout()` 中调用 `offline/wipe.js`（删 IndexedDB 三 store）+ `postMessage` 通知 SW 清空 uploads 缓存——覆盖"共用电脑"场景。

## 9. 实施计划

| 阶段 | 内容 | 依赖 | 服务端改动 | 预估 |
| --- | --- | --- | --- | --- |
| P0 | `offline/idb.js` + `drafts.js` + ArticleEditorView 接入（写入/恢复/清理） | 新依赖 `idb` | 无 | 1-2 天 |
| P1 | `outbox.js` 重放引擎 + api.js 入队收口 + 全局横幅 + 设置页入口 + 死信 | P0 | 幂等键改造（§6.3，约 1 天） | 3-4 天 |
| P2 | sw.js 运行时缓存 + snapshots 写入 + 四个视图接入 + 弱网微优化 | 无 | 无 | 2 天 |
| P3 | `/v1/sync` 增量端点 + 客户端游标 | 可选 | Album version 迁移 + 新端点 | 另行立项 |

## 10. 测试计划

- **单元（vitest + fake-indexeddb）**：草稿写入/恢复/清理时序；outbox 状态机（网络失败退避、409 保留、401 暂停、4xx 死信、幂等键复用）；SW 排除规则（用请求构造断言）。
- **手工矩阵**（Chrome DevTools）：
  - Offline + 关标签 → 重开恢复草稿；
  - 断网写时光轴 → 恢复网络自动重放 → 服务端恰好一条（幂等验证：抓包确认同一 Idempotency-Key）；
  - 断网编辑他人已改的文章 → 重放 409 → 冲突弹窗两个选项各自收敛；
  - 会话过期（清 cookie）→ 队列暂停提示登录 → 重新登录自动重放；
  - 弱网（Slow 3G）→ 请求 15s 超时而非悬挂；
  - 登出 → IndexedDB 与 SW uploads 缓存为空；
  - 回归：一起听全流程无 IndexedDB 写入（可加一条自动化断言）。
