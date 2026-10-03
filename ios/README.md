# LoveJournal iOS（SwiftUI 客户端）

恋爱记的 iOS 原生客户端，目标为对齐 Android 端的全功能实现，按里程碑分期交付。

## 工程结构

```
ios/
  project.yml                  # XcodeGen 工程定义（不提交 .xcodeproj）
  LoveCore/                    # 平台无关的协议层（Foundation only）
    Sources/LoveCore/
      ServerAddress.swift      # 自托管地址归一化（1:1 移植 Android ServerAddress.kt）
      Networking/              # LoveAPIClient（Cookie 会话）+ APIError（FastAPI detail 双形态解析）
      DTOs/                    # /v1 契约 DTO（宽容解码：未知字段忽略）
      Sync/                    # 离线 outbox 引擎 + 小组件快照（App Group 镜像）
    Tests/                     # swift test（macOS/Linux 均可跑，是 CI 的核心质量闸门）
  LoveJournal/                 # App target（SwiftUI，MVVM + Repository）
    App/                       # 组合根、会话管理、Keychain、服务器设置、离线同步器
    DesignSystem/              # 设计 tokens（与 Android theme 1:1）与通用组件
    Features/                  # 按功能分组的 Screen + ViewModel
    Resources/                 # Localizable.xcstrings（zh-Hans/en/ja 三语）、Assets
  LoveJournalTests/            # App 层冒烟测试（模拟器）
  LoveWidget/                  # 桌面小组件扩展（在一起天数，WidgetKit）
```

## 里程碑

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | 工程骨架、地址配置、登录（TOTP/冻结）、bootstrap、会话管理、主 Tab、CI | ✅ |
| M1 | Dashboard、文章、相册、纪念日、留言板、时间线、搜索、通知中心 | ✅ |
| M2 | 写入：文章编辑（ETag/If-Match）、上传管线、评论、胶囊 | ✅ |
| M3 | E2EE 悄悄话（PBKDF2 + AES-GCM，与 Web/Android 互通 KAT）、心情、报备、心愿、每日一问 | ✅ |
| M4 | 一起听 / 一起看（WS 同步 + AVPlayer） | ✅ |
| M5 | 五个小游戏、你画我猜、协作画板、兑换券、账本、提醒、计划 | ✅ |
| M6 | 生理期、足迹地图、月报年报、保险箱、回收站、隐私中心、安全设置 | ✅ |
| M6 收尾 | 离线 outbox、桌面小组件 | ✅ |
| M7 | APNs 推送（依赖服务端 provider 与付费开发者账号） | 🚧 |

## 已知差距（与 Android 对齐待办）

- **App 图标与上架素材**：`AppIcon.appiconset` 目前只有占位 Contents.json（无实际
  图），`CFBundleShortVersionString` 仍为 0.1.0，TestFlight / App Store 材料未备

推送说明：服务端目前只有 FCM（data-only）与 Web Push，没有 APNs 支持，且 APNs
需要付费 Apple 开发者账号——因此在服务端补充 APNs provider 之前，iOS 端使用前台
WebSocket + 手动刷新，不做推送。

## 在 Mac 上开发

```bash
brew install xcodegen            # 工程生成器（一次性）
cd ios
xcodegen generate                # 生成 LoveJournal.xcodeproj（勿手动编辑、勿提交）
open LoveJournal.xcodeproj
```

- Run（⌘R）即可在模拟器运行；Debug 构建允许连局域网 `http://192.168.x.x:8000` 与
  `http://localhost:8000`（ATS 仅放行本地网络，公网域名仍强制 HTTPS，策略与 Android 一致）。
- 测试：⌘U 运行 App 冒烟测试；LoveCore 纯逻辑测试在终端跑：

```bash
cd ios/LoveCore && swift test
```

## CI

`.github/workflows/ios.yml` 在 GitHub Actions macOS runner 上：
LoveCore `swift test` → XcodeGen 生成 → 模拟器构建 + 单测 → SwiftLint（建议级）。
所有修改必须以 CI 全绿为合并前提。

## 约定

- 所有 Swift 源文件带 AGPL-3.0 头注释（与 Android 一致）。
- UI 文案一律走 `Localizable.xcstrings`（zh-Hans 为源文案，en/ja 同步维护）；
  运行时错误消息暂由 LoveCore 以中文返回，后续引入错误码再目录化。
- 协议以 Web/Android 实现为准：地址归一化、Cookie 会话、`Idempotency-Key` 幂等、
  E2EE 参数（PBKDF2-HMAC-SHA256 210000 轮 / AES-256-GCM / base64(ct‖tag)）。
- 最低支持 iOS 17；运行时零第三方依赖。
