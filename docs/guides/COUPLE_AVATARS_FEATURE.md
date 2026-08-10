# 情侣头像功能实现说明

## 功能概述
在首页展示情侣双方的头像，并在后台设置页面提供头像上传和管理功能。

## 已完成的更改

### 1. 后端数据库模型 (Backend Database Model)

#### 文件: `私有服务器端/app/models/site_setting.py`
- 添加了两个新字段：
  - `partner_a_avatar: Mapped[str | None]` - Partner A 的头像 URL
  - `partner_b_avatar: Mapped[str | None]` - Partner B 的头像 URL

#### 文件: `私有服务器端/migrations/versions/20260501_add_couple_avatars.py`
- 创建了新的数据库迁移文件
- 添加 `partner_a_avatar` 和 `partner_b_avatar` 列到 `site_settings` 表

### 2. 后端 API Schema (Backend API Schema)

#### 文件: `私有服务器端/app/schemas/site_setting.py`
- `SiteSettingResponse`: 添加了 `partner_a_avatar` 和 `partner_b_avatar` 字段
- `SiteSettingUpdateRequest`: 添加了这两个字段的验证规则

#### 文件: `私有服务器端/app/api/v1/settings.py`
- 更新了 `_SIMPLE_FIELDS` 元组，包含新的头像字段
- 更新了 `_to_response` 函数，返回头像数据

### 3. 前端首页展示 (Frontend Dashboard Display)

#### 文件: `网页/src/views/DashboardView.vue`
- 添加了情侣头像展示区域
- 特性：
  - 显示 Partner A 和 Partner B 的头像
  - 如果没有头像，显示带字母的占位符（A 或 B）
  - 中间显示心形图标（💕）并带有心跳动画
  - 响应式设计，移动端自适应
  - 渐变背景和阴影效果
  - 悬停时头像放大效果

### 4. 后台设置页面 (Admin Settings Page)

#### 文件: `网页/src/views/AdminView.vue`
- 添加了"💑 情侣头像设置"区域
- 功能：
  - 为 Partner A 和 Partner B 分别上传头像
  - 实时预览头像
  - 清除头像功能
  - 上传时自动保存到服务器
  - 文件类型验证（仅图片）
  - 文件大小限制（最大 5MB）
  - 上传状态提示

### 5. 前端 API 函数 (Frontend API Functions)

#### 文件: `网页/src/lib/api.js`
- 添加了通用的 `uploadFile(file, destination)` 函数
- 支持上传到不同的目标目录（avatars, albums, timeline 等）

## 使用说明

### 运行数据库迁移

在部署或本地开发时，需要运行数据库迁移来添加新字段：

```bash
cd 私有服务器端
python -m alembic upgrade head
```

或者如果使用虚拟环境：

```bash
cd 私有服务器端
.venv\Scripts\activate  # Windows
# 或
source .venv/bin/activate  # Linux/Mac

python -m alembic upgrade head
```

### 设置情侣头像

1. 登录后台管理页面
2. 进入"站点设置"区域
3. 找到"💑 情侣头像设置"部分
4. 点击"选择图片"按钮上传 Partner A 和 Partner B 的头像
5. 上传成功后会自动保存并显示预览
6. 如需更换，重新上传即可
7. 如需清除，点击"清除"按钮

### 查看效果

1. 返回首页（Dashboard）
2. 在页面顶部会看到情侣双方的头像展示
3. 头像之间有心形图标，带有心跳动画效果

## 技术细节

### 头像存储
- 头像文件存储在 `uploads/avatars/` 目录
- 文件名使用 UUID 生成，确保唯一性
- 支持自动压缩和 EXIF 清除（根据媒体策略设置）

### 安全性
- 仅 Partner 角色可以上传和管理头像
- 文件类型白名单验证
- 文件大小限制
- 路径遍历防护

### 响应式设计
- 桌面端：头像 120x120px
- 移动端：头像 90x90px
- 自适应间距和布局

## 样式特点

- 圆形头像，白色边框
- 渐变背景（粉色到蓝色）
- 柔和阴影效果
- 悬停时放大动画
- 心形图标心跳动画
- 占位符使用渐变背景和大写字母

## 后续优化建议

1. 添加头像裁剪功能
2. 支持从相册选择已有图片作为头像
3. 添加头像历史记录
4. 支持设置情侣昵称（显示在头像下方）
5. 添加更多动画效果选项
