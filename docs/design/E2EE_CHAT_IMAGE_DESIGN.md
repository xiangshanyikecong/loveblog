# E2EE 聊天图片支持设计（Android 补齐，与 Web 互通）

> 状态：设计稿（未实施）。目标：Android 端加密聊天支持图片消息，复用 Web 端与服务端已就绪的协议，**服务端零改动**。

## 1. 背景与现状

加密聊天初始化后，Android 端发送图片被直接拦截（`Android/app/src/main/java/com/lovejournal/app/ui/cottage/chat/ChatViewModel.kt:317-320`，即 UI 评审指出的 ChatViewModel.kt:315 拦截点）。根本原因有两层：

1. **服务端强制**：一旦初始化 chat key，所有 `is_encrypted=false` 的消息（含媒体）一律 400 `error.encrypted_chat_no_plaintext`（`server/app/api/v1/cottage_chat.py:318-322`）——现行的"明文上传 + 明文 media_url"链路必被拒绝；
2. **Android 未接入加密媒体链路**：未对接 `/v1/uploads/chat-encrypted-media` 端点，接收侧图片气泡直接 `AsyncImage(resolvedUrl)`，无法处理 `.enc` 密文（`ui/cottage/chat/ChatScreen.kt:371-385`）。

**Web 端已有完整加密图片链路**（这正是两端不对称的来源）：

| 环节 | Web 实现 |
| --- | --- |
| 发送 | `onPickImage`：`file.arrayBuffer()` → `encryptChatRaw()` 得 `{iv, cipherBuffer}` → 包成 octet-stream Blob → `uploadChatEncryptedMedia` POST `/v1/uploads/chat-encrypted-media` → 发送 `{type:"image", media_url, is_encrypted:true, iv, algo:"AES-GCM"}`；发送者用原文件 blob URL 本地即时预览（`web/src/views/cottage/chat/CottageChatView.vue:1623-1683`） |
| 接收 | `enqueueMediaDecrypt`（并发限 3）：fetch media_url → `decryptChatBytes(iv, bytes)` → 魔数 `detectMimeType` → blob URL + LRU 内存缓存（同文件 `:875-955,898-941`） |

**服务端协议已就绪**（无需任何改动）：

- 信封校验器（`server/app/schemas/cottage_chat.py:62-90`）：`is_encrypted=true` 时必须 `algo=="AES-GCM"` + 有 `iv` + **`content` 必须为 null（即禁止明文 caption）**；`type=="image"` 时必须有 `media_url`（指向服务端上的密文文件）且不得携带内联 `ciphertext`。
- 密文文件上传端点（`server/app/api/v1/uploads.py:637-673`）：无 MIME 白名单（密文即随机字节）、上限 25MB、存为 `uploads/chat/{uuid}.enc`、`application/octet-stream`；媒体读取需 JWT + UploadReference 授权（`server/app/main.py:775-861`）。
- 密文透传、服务端永不解密（`server/app/models/chat_message.py:58-63` 注释）。

**Android 已具备的积木**：

- 字节级加解密原语已存在但无人调用：`ChatCrypto.encryptBytes/decryptBytes`（`data/crypto/ChatCrypto.kt:90-102`），与 Web `encryptChatRaw/decryptChatBytes` 算法参数逐项一致（PBKDF2-SHA256 210,000 轮 / AES-256-GCM / 12B IV / tag 128bit / 标准 base64）。
- 图片压缩：`UploadRepository.compressImage`（两遍 decode 下采样至最长边 1600、JPEG q85，`data/repository/UploadRepository.kt:78-100`）。
- 加密发送请求体字段齐全：`ChatSendRequest` 已含 `media_url/is_encrypted/iv/algo`，`buildSendRequest` 已会组装信封（`data/remote/dto/ChatDto.kt:31-47`、`data/repository/ChatRepository.kt:267-291`）——目前只用于文本。
- 带鉴权 cookie 的 OkHttp 客户端（WS 与 REST 共享 cookie jar，`data/remote/CottageWebSocket.kt:51-53`）。

## 2. 关键决策：不做分块加密

评审提出的"分块加密传图"，经核实**不应采用**，理由如下：

1. **协议契约是单文件单信封**：服务端 schema 要求加密媒体消息"一个 media_url + 一个 iv、无内联 ciphertext"（`cottage_chat.py:81-87`）；Web 接收侧按整文件 AES-GCM 一次性解密后做魔数嗅探。引入分块意味着自定义分块清单（manifest）格式 + Web/Android 两端同步升级 + 版本协商字段，破坏"与 Web 逐字节互通"这一最大优势。
2. **没有真实约束需要分块**：经 `compressImage` 压缩后的图片典型为 100-500KB，远小于 25MB 服务端上限；单次 GCM 的内存峰值约为明文+密文 ≈ 2×文件大小，对现代设备完全可接受（现状上传链路本来也是整字节读入）。
3. **正确的大文件演进路径是独立提案**：未来若支持视频/原图，再做"流式 AEAD 加密 + 服务端分片/断点续传端点 + 消息协议版本字段"，与本需求解耦。

**结论**：v1 = 整文件 AES-GCM（与 Web 逐字节一致），上限沿用 25MB，超限走客户端降质重压链（§3.3）。

## 3. 发送链路设计

### 3.1 流程

```
PhotoPicker 选图（沿用现有入口）
  → compressImage(uri)                        // 1600px / q85，产出 JPEG bytes
  → ChatCrypto.encryptBytes(key, bytes)       // 已有原语，返回 iv + ciphertext
  → POST /v1/uploads/chat-encrypted-media     // 新端点接入，octet-stream，文件名 image.enc
  → repository.send(type="image",
        content = null,                       // 关键：schema 禁止明文 caption
        mediaUrl = upload.url,
        isEncrypted = true, iv = iv, algo = "AES-GCM")
  → 服务端回包 content=null，UI 用本地 Uri 即时预览（与 Web 的 blob URL 策略一致，
    不做"上传→下载→解密"回环）
```

### 3.2 caption（图片说明）的处理

- schema 强制加密消息 `content=null`（`cottage_chat.py:73-74`），Web 端同样不发 caption。
- **决策：E2EE 模式下隐藏聊天输入框的"图片说明"输入**，附一句占位提示"加密模式下图片不支持附带文字"。与 Web 行为严格对齐。
- 若后续需要，增强方案是发送图片成功后自动追加一条独立的加密文本消息（互通无损）；v1 不做。

### 3.3 超限降级链

服务端 25MB 上限（`uploads.py:658-660`，HTTP 413）。上传收到 413 时按固定阶梯重压重试：

```
(1600, 85) → (1280, 70) → (1024, 55) → 提示"图片过大，请缩小后重试"
```

每级重新走 compress → encrypt → upload，413 判定基于响应码而非本地预估（密文大小 ≈ 明文 + 16B tag，可忽略）。

### 3.4 离线与失败语义

- 与现状一致（`ChatViewModel.kt:310-312` 注释）：图片消息仅在线可用，上传/发送失败 toast 提示重试，**不入 Room SyncQueue**（队列按设计只存纯文本载荷；密文图片入队涉及队列体积与重放上传，列为后续增强 `CHAT_SEND_IMAGE`，不阻塞本设计）。
- `uploadingImage` 防连点保留；E2EE 分支同样置于其保护之下。

## 4. 接收链路设计

### 4.1 气泡渲染分支

`ChatScreen.kt` 图片气泡处增加分支：

```
msg.is_encrypted && msg.type == "image"
  → EncryptedChatImage(mid, iv, mediaUrl)     // 新组件，走解密管线
否则维持 AsyncImage(resolvedUrl) 明文路径不变
```

### 4.2 ChatMediaDecryptor（新类）

仿照 Web 的 `enqueueMediaDecrypt`：

- 单例，内部 `Channel` + 并发上限 **3** 的解密队列，避免一次拉满几十条历史消息时打爆内存/网络。
- 每项流程：共享 cookie jar 的 OkHttp 客户端 `GET mediaBase() + media_url`（密文文件访问需 JWT 授权，`main.py:855-859`）→ `ChatCrypto.decryptBytes(iv, bytes)` → 解码为 `ImageBitmap`（**经 Coil 从 ByteArray 加载**，以兼容 GIF 动图显示首帧/动帧，而非手工 BitmapFactory 只取首帧）→ 回调 UI。
- **内存 LRU 缓存**：key = `"$mid@$iv"`（与 Web/文本解密缓存 `ChatRepository.kt:117` 的 key 规则一致），总预算 64MB 或 40 条取先到；`onTrimMemory` 时收缩。
- 结果状态：`Loading`（shimmer 占位）/ `Ready` / `Locked`（E2EE 未解锁，显示锁形占位）/ `Failed`（占位 + 点击重试）。
- 解锁状态变化（`observeKeySession`，`ChatViewModel.kt:108-116`）→ 清空整个缓存并重新入队可见消息，对齐现有 `decryptAll` 的重解密行为。
- **不落盘**：明文 Bitmap 仅内存；密文不做磁盘缓存。与"密钥仅进程内存、冷启动需重新解锁"的既有安全姿态一致（`ChatRepository.kt:101-104`）。

### 4.3 边界情况

| 场景 | 行为 |
| --- | --- |
| 收到时未解锁 | Locked 占位；解锁后自动重解 |
| 解密失败（密钥轮换后旧消息等） | Failed 占位可重试，与加密文本消息的失败占位行为一致（`ChatRepository.kt:123-132` 返回 null 的现有处理） |
| 服务端 413/超时/断网 | Failed 占位，点击重试 |
| 寄给未来（visible_at 未释放） | 现有 `is_future` 流程不变，释放前不解密 |
| 收藏/长按菜单 | 不变——收藏是服务端元数据（`chat_message_meta.py`），不涉密文 |
| 本地 E2EE 搜索 | 不变（仅匹配解密后的文本，`ChatViewModel.kt:243-250`），图片无文本参与 |

## 5. 改动文件清单（Android，服务端与 Web 零改动）

| 文件 | 改动 |
| --- | --- |
| `data/remote/api/LoveApiService.kt` | 新增 `@Multipart @POST("uploads/chat-encrypted-media")`，octet-stream 字段 |
| `data/repository/UploadRepository.kt` | 新增 `uploadEncryptedChatMedia(cipherBytes)`；新增 413 降级重压循环（§3.3） |
| `data/repository/ChatRepository.kt` | `send()`/`buildSendRequest` 支持加密媒体组合（iv + media_url + content=null）——参数已齐，仅接线 |
| `ui/cottage/chat/ChatViewModel.kt` | `sendImage()` 拆出 E2EE 分支（替换 L317-320 的拦截）；发送者本地预览用原 Uri |
| `ui/cottage/chat/ChatScreen.kt` | 气泡加密分支接 `EncryptedChatImage`；E2EE 时隐藏 caption 输入 |
| 新增 `ui/cottage/chat/EncryptedChatImage.kt` | 状态机组件（Loading/Ready/Locked/Failed） |
| 新增 `data/chat/ChatMediaDecryptor.kt` | 并发限流解密队列 + 内存 LRU |

## 6. 服务端零改动清单（复核证据）

| 契约点 | 位置 |
| --- | --- |
| 加密媒体消息校验（type=image 必须有 media_url、禁 content、禁内联 ciphertext） | `server/app/schemas/cottage_chat.py:62-90` |
| 密文文件上传端点（25MB、.enc、octet-stream、UploadReference 登记） | `server/app/api/v1/uploads.py:637-673` |
| 密文透传存储与 WS 原样下发 | `server/app/models/chat_message.py:58-67`、`server/app/services/chat_features.py:63-88` |
| 媒体访问鉴权 | `server/app/main.py:775-861` |

## 7. 实施里程碑

1. **M1 发送端到端自测**：端点接入 + 发送分支 + 降级链，Android 自发自收。
2. **M2 双端互通**：Web 发→Android 收、Android 发→Web 收全矩阵通过。
3. **M3 边界打磨**：解锁前接收、轮换后历史、内存预算、弱网重试。

预估总工作量 2-3 天（复用面大：加密原语、压缩、DTO、服务端全部现成）。

## 8. 测试计划

- **互通矩阵**：`{web, android} × {web, android}` 收发双向；JPEG / PNG / HEIC（经压缩统一为 JPEG）/ GIF（Web 发原样字节 → Android 经 Coil 显示动图；Android 发 → 压缩后为静帧 JPEG，两端显示一致）。
- **协议红线**：E2EE 下尝试带 caption 发送 → 客户端 UI 已禁止；直接 curl 绕过 → 服务端 422（schema 拒绝）。
- **大小边界**：>25MB 原图 → 降级链逐级重压至成功或最终提示；恰好 25MB 密文边界值。
- **状态边界**：未解锁收图（Locked → 解锁自动恢复）；对方 rekey 后旧图（Failed 占位）；断网点击重试；后台/旋转/快速滚动时队列与缓存表现。
- **内存**：50+ 条加密图片的会话连续滚动，RSS 增长受 LRU 预算约束（Macrobenchmark 或 Profiler 抽查）。
- **回归**：明文聊天（未初始化 E2EE）的图片链路行为不变；加密文本消息收发不变。
