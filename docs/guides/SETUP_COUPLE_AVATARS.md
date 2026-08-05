# 情侣头像功能 - 部署指南

## 快速开始

### 1. 运行数据库迁移

#### 方法 A: 使用 Alembic（推荐）

```bash
# 进入后端目录
cd 私有服务器端

# 激活虚拟环境（如果使用）
# Windows:
.venv\Scripts\activate
# Linux/Mac:
# source .venv/bin/activate

# 运行迁移
python -m alembic upgrade head
```

#### 方法 B: 手动添加字段（如果 Alembic 不可用）

如果 Alembic 迁移失败，可以手动在数据库中执行以下 SQL：

**PostgreSQL:**
```sql
ALTER TABLE site_settings 
ADD COLUMN IF NOT EXISTS partner_a_avatar VARCHAR(255),
ADD COLUMN IF NOT EXISTS partner_b_avatar VARCHAR(255);
```

**SQLite:**
```sql
ALTER TABLE site_settings ADD COLUMN partner_a_avatar VARCHAR(255);
ALTER TABLE site_settings ADD COLUMN partner_b_avatar VARCHAR(255);
```

### 2. 测试数据库字段

运行测试脚本验证字段是否正确添加：

```bash
cd 私有服务器端
python test_couple_avatars.py
```

预期输出：
```
============================================================
情侣头像功能测试
============================================================

✓ 站点设置记录存在
✓ partner_a_avatar 字段: 存在
✓ partner_b_avatar 字段: 存在

当前值:
  Partner A 头像: (未设置)
  Partner B 头像: (未设置)

测试设置头像...
✓ 设置成功:
  Partner A 头像: uploads/avatars/test_a.jpg
  Partner B 头像: uploads/avatars/test_b.jpg

✓ 测试完成，已清除测试数据

============================================================
✓ 所有测试通过！
============================================================
```

### 3. 重启服务

#### Docker 环境:
```bash
docker compose down
docker compose up --build
```

#### 本地开发环境:

**后端:**
```bash
cd 私有服务器端
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**前端:**
```bash
cd 网页
npm run dev
```

### 4. 使用功能

1. **登录后台**
   - 访问 `http://localhost:5173`
   - 使用 Partner 账号登录

2. **设置头像**
   - 点击顶部导航的"后台"或"Admin"
   - 找到"站点设置"区域
   - 在"💑 情侣头像设置"部分上传头像
   - 支持的格式: JPEG, PNG, WebP, GIF
   - 最大文件大小: 5MB

3. **查看效果**
   - 返回首页（Dashboard）
   - 在页面顶部会看到情侣双方的头像展示

## 故障排除

### 问题 1: 迁移失败 - "table site_settings does not exist"

**解决方案:**
```bash
# 运行所有迁移
cd 私有服务器端
python -m alembic upgrade head
```

### 问题 2: 上传头像后显示 404

**可能原因:**
- uploads 目录权限问题
- 静态文件服务未正确配置

**解决方案:**
```bash
# 检查 uploads 目录是否存在
cd 私有服务器端
mkdir -p uploads/avatars

# 检查权限（Linux/Mac）
chmod -R 755 uploads
```

### 问题 3: 前端显示"Failed to load settings"

**可能原因:**
- 后端未运行
- CORS 配置问题
- 认证 token 过期

**解决方案:**
1. 确认后端正在运行: `http://localhost:8000/health`
2. 检查浏览器控制台的错误信息
3. 重新登录

### 问题 4: 头像上传后首页不显示

**可能原因:**
- 首页未刷新设置数据
- 头像 URL 路径错误

**解决方案:**
1. 刷新首页（F5）
2. 检查浏览器控制台的网络请求
3. 确认头像 URL 格式正确（应该是完整的 URL 或相对路径）

## 验证清单

- [ ] 数据库迁移成功运行
- [ ] 测试脚本通过
- [ ] 后端服务正常启动
- [ ] 前端服务正常启动
- [ ] 可以访问后台设置页面
- [ ] 可以成功上传 Partner A 头像
- [ ] 可以成功上传 Partner B 头像
- [ ] 首页正确显示两个头像
- [ ] 头像悬停时有放大效果
- [ ] 心形图标有心跳动画
- [ ] 移动端显示正常

## API 端点

### 获取站点设置
```
GET /v1/settings
Authorization: Bearer <token>

Response:
{
  "site_name": "恋爱记",
  "partner_a_avatar": "http://localhost:8000/uploads/avatars/xxx.jpg",
  "partner_b_avatar": "http://localhost:8000/uploads/avatars/yyy.jpg",
  ...
}
```

### 更新站点设置
```
PUT /v1/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "partner_a_avatar": "uploads/avatars/xxx.jpg",
  "partner_b_avatar": "uploads/avatars/yyy.jpg"
}
```

### 上传头像
```
POST /v1/uploads/avatars
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <image file>

Response:
{
  "url": "http://localhost:8000/uploads/avatars/xxx.jpg",
  "file_name": "avatar.jpg",
  "content_type": "image/jpeg",
  "size": 12345
}
```

## 文件结构

```
私有服务器端/
├── app/
│   ├── models/
│   │   └── site_setting.py          # 添加了头像字段
│   ├── schemas/
│   │   └── site_setting.py          # 添加了头像 schema
│   ├── api/v1/
│   │   ├── settings.py              # 更新了设置 API
│   │   └── uploads.py               # 已有头像上传端点
│   └── ...
├── migrations/versions/
│   └── 20260501_add_couple_avatars.py  # 新增迁移文件
└── test_couple_avatars.py           # 测试脚本

网页/
├── src/
│   ├── views/
│   │   ├── DashboardView.vue        # 首页头像展示
│   │   └── AdminView.vue            # 后台头像设置
│   └── lib/
│       └── api.js                   # 添加了 uploadFile 函数
└── ...
```

## 下一步

功能已经完全实现！你可以：

1. 自定义头像样式（修改 CSS）
2. 添加更多动画效果
3. 实现头像裁剪功能
4. 添加情侣昵称显示
5. 支持从相册选择头像

如有问题，请查看 `COUPLE_AVATARS_FEATURE.md` 了解更多技术细节。
