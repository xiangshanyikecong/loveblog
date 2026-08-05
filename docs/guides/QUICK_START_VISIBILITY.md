# 快速启动：隐私分级系统

## 一键部署

### 1. 应用数据库迁移

```bash
cd 私有服务器端
alembic upgrade head
```

预期输出：
```
INFO  [alembic.runtime.migration] Running upgrade ... -> add_visibility_pwd, add visibility and password protection
```

### 2. 重启服务

```bash
# 如果使用uvicorn
uvicorn app.main:app --reload

# 或使用你的启动脚本
python -m app.main
```

## 快速测试

### 测试1：创建公开文章

```bash
curl -X POST "http://localhost:8000/api/v1/articles" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "公开文章",
    "visibility": "public",
    "status": "Published",
    "blocks": []
  }'
```

### 测试2：创建密码保护文章

```bash
curl -X POST "http://localhost:8000/api/v1/articles" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "密码保护文章",
    "visibility": "password_protected",
    "password": "test123",
    "status": "Published",
    "blocks": []
  }'
```

### 测试3：访问密码保护文章

```bash
# 获取文章ID后
curl -X GET "http://localhost:8000/api/v1/articles/{aid}?password=test123"
```

## 可见性级别速查

| 级别 | 值 | 说明 |
|-----|---|------|
| 🔒 私有 | `private` | 仅作者可见 |
| 💑 两人 | `partners_only` | 仅伴侣可见 |
| 👥 访客 | `guest_viewable` | 登录用户可见 |
| 🌍 公开 | `public` | 所有人可见 |
| 🔐 密码 | `password_protected` | 需要密码 |

## API字段说明

### 创建/更新时

```json
{
  "visibility": "password_protected",  // 可见性级别
  "password": "your_password"          // 密码（可选）
}
```

### 响应中

```json
{
  "visibility": "password_protected",  // 可见性级别
  "requires_password": true            // 是否需要密码
}
```

## 常见问题

### Q: 如何清除密码？
A: 传递空字符串：`{"password": ""}`

### Q: 伴侣需要密码吗？
A: 不需要，伴侣和作者可以直接访问

### Q: 旧数据会怎样？
A: 自动迁移：
- 加密内容 → `partners_only`
- 公开内容 → `public`
- 私有内容 → `private`

### Q: 密码安全吗？
A: 使用bcrypt加密存储，不会明文保存

## 完整文档

详细文档请查看：
- `VISIBILITY_PRIVACY_GUIDE.md` - 完整功能说明
- `test_visibility_manual.md` - 测试指南
- `VISIBILITY_IMPLEMENTATION_SUMMARY.md` - 实现总结
