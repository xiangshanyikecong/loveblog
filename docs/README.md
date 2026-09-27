# 文档索引

项目文档按用途归类。本目录收纳使用指南。

## 根目录保留的标准文件

- [`README.md`](../README.md) - 项目总览
- [`PROJECT_GUIDE_ZH.md`](./PROJECT_GUIDE_ZH.md) - 中文项目说明、安装、使用与运维主手册
- [`PROJECT_REQUIREMENTS.md`](../PROJECT_REQUIREMENTS.md) - 需求总纲
- [`DEPLOYMENT_GUIDE.md`](../DEPLOYMENT_GUIDE.md) - 部署指南
- [`DEPLOYMENT_CHECKLIST.md`](../DEPLOYMENT_CHECKLIST.md) - 部署检查清单

## `guides/` - 使用与功能指南

- 单人和双人模式说明
- 健康检查：`HEALTH_CHECK_ARCHITECTURE.md`、`HEALTH_CHECK_PARAMETERS.md`
- 一起听自动暂停：`AUTO_PAUSE_DESIGN.md`

## `design/` - 功能设计稿

- Web 端离线与弱网（IndexedDB 草稿 + 离线写入队列 + 只读缓存）：`WEB_OFFLINE_WEAK_NETWORK_DESIGN.md`
- E2EE 聊天图片支持（Android 补齐，与 Web 互通）：`E2EE_CHAT_IMAGE_DESIGN.md`
- FCM 推送应用内引导式配置（自托管友好）：`FCM_IN_APP_SETUP_DESIGN.md`
