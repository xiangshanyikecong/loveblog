# 内容可见性隐私分级系统

## 概述

本系统为文章（Articles）和相册（Albums）提供了细粒度的隐私控制，支持5种可见性级别。

## 可见性级别

### 1. `private` - 仅作者可见
- 只有内容创建者本人可以查看
- 适用场景：草稿、私人笔记

### 2. `partners_only` - 仅两人可见
- 只有系统中的两位伴侣（partner_a 和 partner_b）可以查看
- 适用场景：情侣之间的私密内容

### 3. `guest_viewable` - 访客可见
- 任何已登录用户都可以查看
- 适用场景：需要登录才能查看的半公开内容

### 4. `public` - 公开
- 所有人都可以查看，包括未登录用户
- 适用场景：完全公开的内容

### 5. `password_protected` - 密码保护
- 需要输入正确密码才能查看
- 伴侣和作者可以直接访问，无需密码
- 适用场景：需要特定密码才能访问的内容

## API 使用示例

### 创建带密码保护的文章

```json
POST /api/v1/articles
{
  "title": "我的秘密文章",
  "excerpt": "这是一篇需要密码的文章",
  "visibility": "password_protected",
  "password": "my_secret_password",
  "status": "Published",
  "blocks": [
    {
      "block_type": "Paragraph",
      "content": "这是文章内容",
      "sort_order": 0
    }
  ]
}
```

### 访问密码保护的内容

```http
GET /api/v1/articles/{aid}?password=my_secret_password
```

如果密码错误，将返回 403 Forbidden。

### 更新可见性设置

```json
PATCH /api/v1/articles/{aid}
{
  "visibility": "guest_viewable"
}
```

### 修改或清除密码

设置新密码：
```json
PATCH /api/v1/articles/{aid}
{
  "password": "new_password"
}
```

清除密码：
```json
PATCH /api/v1/articles/{aid}
{
  "password": ""
}
```

## 数据库迁移

运行以下命令应用数据库迁移：

```bash
cd 私有服务器端
alembic upgrade head
```

迁移会自动将现有数据转换为新的可见性系统：
- `is_encrypted=true` → `partners_only`
- 已发布且未加密 → `public`
- 草稿 → `private`

## 响应字段说明

### ArticleSummaryResponse / AlbumSummaryResponse

新增字段：
- `visibility`: 可见性级别（枚举值）
- `requires_password`: 是否需要密码（布尔值）

示例响应：
```json
{
  "aid": "123e4567-e89b-12d3-a456-426614174000",
  "title": "我的文章",
  "visibility": "password_protected",
  "requires_password": true,
  "...": "其他字段"
}
```

## 权限规则总结

| 可见性级别 | 未登录用户 | 访客用户 | 作者 | 伴侣 | 需要密码 |
|-----------|----------|---------|-----|------|---------|
| private | ❌ | ❌ | ✅ | ❌ | ❌ |
| partners_only | ❌ | ❌ | ✅ | ✅ | ❌ |
| guest_viewable | ❌ | ✅ | ✅ | ✅ | ❌ |
| public | ✅ | ✅ | ✅ | ✅ | ❌ |
| password_protected | 需要密码 | 需要密码 | ✅ | ✅ | ✅ |

## 兼容性说明

系统保留了旧的 `is_encrypted` 和 `is_public` 字段以保持向后兼容，但新代码应优先使用 `visibility` 字段。

## 注意事项

1. **密码安全**：密码使用 bcrypt 加密存储，不会以明文形式保存
2. **伴侣特权**：伴侣始终可以访问对方的所有内容（除了 `private`）
3. **列表查询**：密码保护的内容会显示在列表中，但查看详情时需要密码
4. **密码验证**：密码通过 URL 查询参数传递：`?password=xxx`
