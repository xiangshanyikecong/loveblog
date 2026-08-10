# 恋爱记（Love Journal）项目需求说明

## 1. 项目定位

本项目是一个面向情侣的“恋爱记录 + 博客分享”软件，支持：

- 私有化部署（每对情侣可拥有自己的 Node）
- Web 与 Android 双端记录
- 后续接入总站账号体系，实现跨站访问与评论

目标是在保证可玩性（ACG 风格）和可扩展性的前提下，先快速做出可用 MVP，再逐步增强。

## 2. 核心需求总览

- 能记录：支持发布文字、图片/GIF/WebP 等恋爱日记（Moment）。
- 能查看：支持时间轴展示历史记录。
- 能离线：Android 端可离线保存，联网后自动同步。
- 能扩展：支持从“本地模式”平滑升级到“总站 OAuth 模式”。
- 能美化：Web 端采用 ACG 风格组件化页面。
- 能部署：最终可通过 Docker 一键部署。

## 3. 系统架构需求

### 3.1 总站（The Hub）- Laravel

- 技术：Laravel + Laravel Passport
- 角色：OAuth2 Server（统一账号体系）
- 功能需求：
  - 用户注册/登录
  - App ID 分发
  - 节点健康检查（心跳包）
- 数据库：MySQL
- 存储范围：
  - 仅保存基础信息（UID、邮箱哈希、公开节点 URL）
  - 不存储情侣私密正文内容

### 3.2 私有化实例（The Node）- FastAPI + Vue3

- 后端技术：FastAPI
- 鉴权需求（双模式）：
  - 本地模式：JWT
  - 总站模式：对接 Hub OAuth
- 存储需求：
  - PostgreSQL：主业务数据
  - Redis：状态/缓存
- API 规范：
  - RESTful
  - 至少提供 `v1/timeline`、`v1/gallery` 等版本化接口
- 前端技术：Vue3 + Tailwind CSS
- 前端要求：
  - 响应式页面
  - ACG 视觉风格
  - 组件化拆分：时间轴、评论区、倒计时

### 3.3 Android 客户端 - Kotlin + Compose

- UI：Jetpack Compose
- 本地存储：Room（用于离线编辑）
- 网络层：Retrofit + OkHttp（与 Node 端通信）
- 图片处理：Coil（支持 GIF/WebP）
- 核心体验：
  - 无网可记录
  - 有网自动同步到 Node

## 4. 数据模型需求（Data Schema）

### 4.1 User

- 字段：`uid`, `nickname`, `avatar`, `role`
- 角色：`Partner A` / `Partner B` / `Visitor`
- 说明：区分情侣双方和访客身份

### 4.2 Moment

- 字段：`mid`, `content`, `media_urls`, `location`, `timestamp`
- 说明：恋爱日记核心实体（碎碎念/图文记录）

### 4.3 Comment

- 字段：`cid`, `moment_id`, `from_uid`, `content`, `origin_hub`
- 说明：支持跨站评论，并记录访客来源总站账号

### 4.4 Event

- 字段：`eid`, `title`, `date`, `type`
- 类型：`Countdown` / `Anniversary`
- 说明：用于纪念日与倒计时逻辑

## 5. MVP 分阶段需求

### 阶段 1：单机 Node 闭环（1-2 周）

- 目标：先做到“能存、能看”
- 任务：
  - 搭建 FastAPI 后端
  - 完成本地登录与发布 API
  - 搭建 Vue3 基础列表页
- 交付结果：
  - 可在浏览器发布日记并写入本地数据库

### 阶段 2：Android 时光机（约 2 周）

- 目标：提升移动端记录体验
- 任务：
  - Compose 发布页（文字 + 图片）
  - Room 离线缓存
  - 对接 Node 发布接口
- 交付结果：
  - 可在手机离线记录，联网后同步到 Web

### 阶段 3：总站 SSO 与跨站评论（约 1 周）

- 目标：支持总站账号跨站互动
- 任务：
  - 搭建 Laravel Hub OAuth 登录页
  - Node 增加总站登录开关与回调流程
  - 开放访客评论能力
- 交付结果：
  - 总站账号可登录并在 Moment 下留言

### 阶段 4：UI 打磨与 Docker 打包（约 1 周）

- 目标：可发布、可部署
- 任务：
  - 增加 ACG 元素（表情、背景、加载动画）
  - 编写 `docker-compose.yml`
  - 完善 `README` 并准备 GitHub 发布
- 交付结果：
  - 项目具备基础发布与演示条件

## 6. 质量与工程要求

- API 必须版本化（`/v1/...`）
- 鉴权必须可扩展到 Hub OAuth
- 数据模型需预留后续功能字段
- 前后端分层清晰，便于 Android 复用 API
- 文档可直接指导新成员上手开发

## 7. 当前执行约定

- 当前优先级：先保证阶段 1 完整闭环
- 阶段 2-4 在阶段 1 稳定后逐步推进
- 每阶段结束时，必须提供可演示结果（而不只是代码）

