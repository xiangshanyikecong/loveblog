# 🚀 Love Journal 部署检查清单

## 部署前检查 ✅

### 服务器准备
- [ ] 服务器满足最低配置要求（2核4GB）
- [ ] 已安装 Docker 20.10+
- [ ] 已安装 Docker Compose 2.0+
- [ ] 防火墙已配置（开放 80、443、22 端口）
- [ ] 域名已解析到服务器 IP

### 配置文件
- [ ] 已复制 `.env.production.example` 为 `.env.production`
- [ ] 已设置强密码：`POSTGRES_PASSWORD`
- [ ] 已设置强密码：`REDIS_PASSWORD`
- [ ] 已生成 JWT 密钥：`JWT_SECRET_KEY`（64位以上）
- [ ] 已生成独立 Cookie Vault 密钥：`COOKIE_VAULT_KEY`（64位以上）
- [ ] `COOKIE_SECURE=true`
- [ ] 已设置首次初始化令牌：`BOOTSTRAP_SETUP_TOKEN`
- [ ] 已配置域名：`DOMAIN`
- [ ] 已配置 CORS：`CORS_ORIGINS`
- [ ] 已配置前端 API 地址：`VITE_API_BASE_URL`
- [ ] `VITE_SOURCE_CODE_URL` 匿名可访问、固定到 tag/commit，并包含本次部署版本的全部实际修改

### 目录结构
- [ ] 已创建 `nginx/ssl/` 目录
- [ ] 已创建 `server/uploads/` 目录
- [ ] 已创建 `server/backups/` 目录

---

## 部署步骤 📋

### 1. 初始部署
```bash
# 克隆项目
git clone https://github.com/xiangshanyikecong/loveblog.git love-journal
cd love-journal

# 配置环境
cp .env.production.example .env.production
nano .env.production

# 执行部署
chmod +x deploy.sh
./deploy.sh
```

### 2. 验证部署
- [ ] 所有容器都在运行：`docker-compose -f docker-compose.prod.yml ps`
- [ ] 后端健康检查通过：`curl http://localhost/api/health`
- [ ] 前端可以访问：`curl http://localhost`
- [ ] 数据库连接正常
- [ ] Redis 连接正常

### 3. 首次登录
- [ ] 访问前端页面
- [ ] 使用 `BOOTSTRAP_SETUP_TOKEN` 完成首位 Partner 初始化
- [ ] 使用刚创建的 Partner 账号登录
- [ ] 如果后来补充了另一位 Partner，立即修改其密码
- [ ] 配置站点设置（恋爱开始日期等）

---

## SSL/HTTPS 配置 🔒

### Let's Encrypt 证书
```bash
# 安装 Certbot
sudo apt install -y certbot

# 停止 Nginx
docker-compose -f docker-compose.prod.yml stop nginx

# 获取证书
sudo certbot certonly --standalone -d yourdomain.com

# 复制证书
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
sudo chown $USER:$USER nginx/ssl/*.pem

# 配置默认启用 HTTPS，证书就位后重启服务
docker-compose -f docker-compose.prod.yml up -d
```

### 验证 HTTPS
- [ ] HTTPS 可以访问：`https://yourdomain.com`
- [ ] HTTP 自动重定向到 HTTPS
- [ ] SSL 证书有效
- [ ] 浏览器显示安全锁图标

### 自动续期
```bash
# 添加 cron 任务
sudo crontab -e

# 添加以下行
0 2 1 * * certbot renew --quiet && docker-compose -f /path/to/love-journal/docker-compose.prod.yml restart nginx
```

---

## 安全加固 🛡️

### 密码安全
- [ ] 已修改所有默认密码
- [ ] 密码长度 ≥ 16 位
- [ ] 密码包含大小写字母、数字、特殊字符
- [ ] JWT 密钥长度 ≥ 64 位

### 访问控制
- [ ] 已限制 `/docs` 端点访问（生产环境）
- [ ] 已配置防火墙规则
- [ ] 已禁用不必要的端口
- [ ] 已配置 Fail2ban（可选）

### 数据安全
- [ ] 已配置自动备份
- [ ] 已测试备份恢复流程
- [ ] 已设置远程备份（推荐）
- [ ] uploads 目录权限正确（755）

---

## 备份配置 💾

### 自动备份
在管理员备份页配置并启用；确认重建 backend 容器后计划和历史仍存在。

### 手动备份测试
```bash
# 备份数据库
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U love love_node > test_backup.sql

# 备份上传文件
tar -czf test_uploads.tar.gz server/uploads/

# 测试恢复
cat test_backup.sql | docker-compose -f docker-compose.prod.yml exec -T postgres psql -U love love_node
```

- [ ] 数据库备份成功
- [ ] 文件备份成功
- [ ] 恢复测试成功
- [ ] 备份文件可以下载

---

## 监控设置 📊

### 日志检查
```bash
# 查看所有日志
docker-compose -f docker-compose.prod.yml logs -f

# 检查错误日志
docker-compose -f docker-compose.prod.yml logs | grep -i error
```

- [ ] 无严重错误日志
- [ ] 无数据库连接错误
- [ ] 无权限错误

### 性能监控
```bash
# 查看资源使用
docker stats

# 查看磁盘空间
df -h
```

- [ ] CPU 使用率 < 80%
- [ ] 内存使用率 < 80%
- [ ] 磁盘空间充足（> 20% 剩余）

---

## 功能测试 🧪

### 基础功能
- [ ] 用户登录/登出
- [ ] 创建文章
- [ ] 上传图片
- [ ] 创建相册
- [ ] 添加纪念事件
- [ ] 发布留言
- [ ] 时光胶囊

### 权限测试
- [ ] Partner A 可以访问所有内容
- [ ] Partner B 可以访问所有内容
- [ ] 访客只能看到公开内容
- [ ] 未登录用户只能看到公开内容

### 数据持久化
- [ ] 重启容器后数据不丢失
- [ ] 上传的文件不丢失
- [ ] 数据库数据完整

---

## 性能优化 ⚡

### 前端优化
- [ ] 已启用 Gzip 压缩
- [ ] 静态资源已设置缓存
- [ ] 图片已优化（压缩、懒加载）

### 后端优化
- [ ] 数据库连接池配置合理
- [ ] Redis 缓存正常工作
- [ ] API 响应时间 < 500ms

### Nginx 优化
- [ ] 已配置缓存
- [ ] 已启用 HTTP/2（HTTPS）
- [ ] 已配置 keepalive

---

## 维护计划 🔧

### 日常维护
- [ ] 每天检查日志
- [ ] 每周检查磁盘空间
- [ ] 每月检查备份完整性

### 定期更新
- [ ] 每月更新系统包
- [ ] 每季度更新 Docker 镜像
- [ ] 及时应用安全补丁

### 监控告警
- [ ] 配置磁盘空间告警（可选）
- [ ] 配置服务宕机告警（可选）
- [ ] 配置备份失败告警（可选）

---

## 文档记录 📝

### 部署信息
- 服务器 IP: _______________
- 域名: _______________
- 部署日期: _______________
- 部署人员: _______________

### 账号信息（安全保管）
- 数据库密码: _______________
- Redis 密码: _______________
- JWT 密钥: _______________
- 管理员密码: _______________

### 备份信息
- 备份位置: _______________
- 备份频率: _______________
- 保留天数: _______________

---

## 应急预案 🚨

### 服务宕机
```bash
# 1. 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 2. 查看日志
docker-compose -f docker-compose.prod.yml logs --tail=100

# 3. 重启服务
docker-compose -f docker-compose.prod.yml restart

# 4. 如果无法恢复，回滚到上一个版本
git checkout <previous-commit>
./deploy.sh
```

### 数据丢失
```bash
# 1. 停止服务
docker-compose -f docker-compose.prod.yml down

# 2. 恢复数据库
cat backup.sql | docker-compose -f docker-compose.prod.yml exec -T postgres psql -U love love_node

# 3. 恢复文件
tar -xzf uploads_backup.tar.gz -C server/

# 4. 重启服务
docker-compose -f docker-compose.prod.yml up -d
```

### 磁盘空间不足
```bash
# 1. 清理 Docker 缓存
docker system prune -a

# 2. 清理旧备份
find server/backups/ -name "*.zip" -mtime +30 -delete

# 3. 清理日志
docker-compose -f docker-compose.prod.yml logs --tail=0 -f > /dev/null
```

---

## 完成确认 ✅

- [ ] 所有检查项已完成
- [ ] 应用运行正常
- [ ] 备份配置完成
- [ ] 监控设置完成
- [ ] 文档已记录
- [ ] 团队成员已培训

**部署完成日期**: _______________

**签名**: _______________

---

**祝你的恋爱记录网站运行顺利！💕**
