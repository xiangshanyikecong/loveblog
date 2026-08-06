# 系统健康检查 - 架构图

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 UI 层                               │
│                  (web/src/views/AdminView.vue)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              🏥 系统健康检查区域                          │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │                                                           │  │
│  │  ┌─────────────┐  ┌──────────────────────────────────┐  │  │
│  │  │  健康评分    │  │  整体状态 & 运行时间              │  │  │
│  │  │   圆形显示   │  │  • healthy / degraded / unhealthy │  │  │
│  │  │   0-100分    │  │  • 运行时间：X天 X小时            │  │  │
│  │  └─────────────┘  └──────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌───────────────────────────────────────────────────┐  │  │
│  │  │           组件检查网格 (6个卡片)                   │  │  │
│  │  ├───────────────────────────────────────────────────┤  │  │
│  │  │  🗄️ 数据库    ⚡ Redis     💾 磁盘空间            │  │  │
│  │  │  🧠 内存      ⚙️ CPU       📁 上传目录             │  │  │
│  │  │                                                    │  │  │
│  │  │  每个卡片显示：                                     │  │  │
│  │  │  • 状态徽章（正常/警告/错误）                       │  │  │
│  │  │  • 状态消息                                        │  │  │
│  │  │  • 响应时间（如果有）                              │  │  │
│  │  └───────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌───────────────────────────────────────────────────┐  │  │
│  │  │           💡 优化建议列表                          │  │  │
│  │  ├───────────────────────────────────────────────────┤  │  │
│  │  │  • 🔴 数据库连接失败，请检查数据库服务             │  │  │
│  │  │  • 🟡 磁盘空间不足，建议清理旧备份                 │  │  │
│  │  │  • ✅ 系统运行良好，无需优化                       │  │  │
│  │  └───────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  [刷新按钮]  最后检查: 2026-05-01 10:30:00              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↕ HTTP
┌─────────────────────────────────────────────────────────────────┐
│                      API 客户端层                                │
│                   (web/src/lib/api.js)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  fetchSystemHealth()                                             │
│    ↓                                                             │
│  GET /health/system                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↕ HTTP
┌─────────────────────────────────────────────────────────────────┐
│                      后端 API 层                                 │
│              (server/app/api/v1/health.py)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  @router.get("/health/system")                                  │
│  def system_health_check():                                     │
│    ↓                                                             │
│    执行 6 项检查                                                 │
│    ↓                                                             │
│    计算健康评分                                                  │
│    ↓                                                             │
│    生成优化建议                                                  │
│    ↓                                                             │
│    返回 SystemHealthResponse                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                      健康检查逻辑层                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ _check_database  │  │  _check_redis    │                    │
│  │ • 连接测试        │  │  • 连接测试       │                    │
│  │ • 响应时间        │  │  • 响应时间       │                    │
│  │ • 阈值: >1000ms  │  │  • 阈值: >500ms  │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ _check_disk_space│  │  _check_memory   │                    │
│  │ • 使用率监控      │  │  • 使用率监控     │                    │
│  │ • 警告: >80%     │  │  • 警告: >80%    │                    │
│  │ • 错误: >90%     │  │  • 错误: >90%    │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ _check_cpu       │  │  _check_uploads  │                    │
│  │ • 使用率监控      │  │  • 目录存在性     │                    │
│  │ • 警告: >80%     │  │  • 写权限检查     │                    │
│  │ • 错误: >90%     │  │                  │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                      评分与建议生成层                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  _calculate_health_score(checks)                                │
│    ↓                                                             │
│    根据组件权重计算总分：                                         │
│    • 数据库: 25分                                                │
│    • Redis: 20分                                                │
│    • 磁盘空间: 15分                                              │
│    • 内存: 15分                                                  │
│    • CPU: 15分                                                   │
│    • 上传目录: 10分                                              │
│    ↓                                                             │
│    返回 0-100 分                                                 │
│                                                                  │
│  _determine_overall_status(checks)                              │
│    ↓                                                             │
│    判断整体状态：                                                 │
│    • 有错误 → unhealthy                                         │
│    • 有警告 → degraded                                          │
│    • 全正常 → healthy                                           │
│                                                                  │
│  _generate_recommendations(checks)                              │
│    ↓                                                             │
│    根据检查结果生成建议：                                         │
│    • 🔴 错误级别建议                                             │
│    • 🟡 警告级别建议                                             │
│    • ✅ 正常状态提示                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                      系统资源层                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ PostgreSQL│  │  Redis   │  │  psutil  │  │ 文件系统  │       │
│  │          │  │          │  │          │  │          │       │
│  │ 数据库    │  │  缓存    │  │ 系统监控  │  │ 上传目录  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 数据流

### 1. 前端请求流程

```
用户点击刷新
    ↓
loadSystemHealth()
    ↓
fetchSystemHealth()
    ↓
GET /health/system
    ↓
等待响应
    ↓
更新 systemHealth.value
    ↓
Vue 响应式更新 UI
```

### 2. 后端处理流程

```
接收 GET /health/system 请求
    ↓
system_health_check()
    ↓
并行执行 6 项检查
    ├─ _check_database(db)
    ├─ _check_redis()
    ├─ _check_disk_space()
    ├─ _check_memory()
    ├─ _check_cpu()
    └─ _check_uploads_directory()
    ↓
收集所有检查结果
    ↓
_calculate_health_score(checks)
    ↓
_determine_overall_status(checks)
    ↓
_generate_recommendations(checks)
    ↓
计算运行时间 (time.time() - START_TIME)
    ↓
构建 SystemHealthResponse
    ↓
返回 JSON 响应
```

### 3. 评分计算流程

```
输入: checks = [check1, check2, ..., check6]
    ↓
初始化 total_score = 0
    ↓
遍历每个 check:
    ├─ 获取组件权重 (weights[component])
    ├─ 根据状态计算得分:
    │   ├─ ok: 得分 = 权重 × 1.0
    │   ├─ warning: 得分 = 权重 × 0.5
    │   └─ error: 得分 = 0
    └─ total_score += 得分
    ↓
返回 int(total_score)  # 0-100
```

### 4. 建议生成流程

```
输入: checks = [check1, check2, ..., check6]
    ↓
初始化 recommendations = []
    ↓
遍历每个 check:
    ├─ 如果 status == "error":
    │   └─ 添加 🔴 错误级别建议
    ├─ 如果 status == "warning":
    │   └─ 添加 🟡 警告级别建议
    └─ 如果 status == "ok":
        └─ 跳过
    ↓
如果 recommendations 为空:
    └─ 添加 "✅ 系统运行良好，无需优化"
    ↓
返回 recommendations
```

## 🎨 UI 组件结构

```
AdminView.vue
├─ <article class="glass-card section-block">
│  ├─ <div class="section-header">
│  │  ├─ <h2>🏥 系统健康检查</h2>
│  │  └─ <button @click="loadSystemHealth">刷新</button>
│  │
│  └─ <div class="health-layout">
│     │
│     ├─ <div class="health-score-card">
│     │  ├─ <div class="score-circle">
│     │  │  ├─ <div class="score-value">{{ score }}</div>
│     │  │  └─ <div class="score-label">健康评分</div>
│     │  │
│     │  └─ <div class="score-info">
│     │     ├─ <div class="status-badge">{{ status }}</div>
│     │     └─ <div class="uptime-text">运行时间: {{ uptime }}</div>
│     │
│     ├─ <div class="checks-grid">
│     │  ├─ <div class="check-card" v-for="check in checks">
│     │  │  ├─ <div class="check-header">
│     │  │  │  ├─ <span class="check-icon">{{ icon }}</span>
│     │  │  │  ├─ <span class="check-name">{{ name }}</span>
│     │  │  │  └─ <span class="check-status-badge">{{ status }}</span>
│     │  │  │
│     │  │  ├─ <div class="check-message">{{ message }}</div>
│     │  │  └─ <div class="check-response-time">{{ time }}</div>
│     │
│     ├─ <div class="recommendations-section">
│     │  ├─ <h3>💡 优化建议</h3>
│     │  └─ <ul>
│     │     └─ <li v-for="rec in recommendations">{{ rec }}</li>
│     │
│     └─ <div class="health-timestamp">
│        └─ 最后检查: {{ timestamp }}
```

## 🔄 状态管理

### Vue 响应式数据

```javascript
// 加载状态
const healthLoading = ref(false)

// 健康数据
const systemHealth = ref(null)

// 数据结构
systemHealth.value = {
  overall_status: "healthy",      // 整体状态
  health_score: 95,                // 健康评分
  checks: [                        // 检查结果数组
    {
      component: "database",
      status: "ok",
      message: "数据库连接正常",
      response_time_ms: 12.5
    },
    // ... 其他检查
  ],
  recommendations: [               // 建议数组
    "✅ 系统运行良好，无需优化"
  ],
  uptime_seconds: 3600.5,         // 运行时间（秒）
  timestamp: "2026-05-01T10:30:00Z" // 时间戳
}
```

### 计算属性和方法

```javascript
// 评分颜色类
function getScoreClass(score) {
  if (score >= 90) return "score-excellent"  // 绿色
  if (score >= 70) return "score-good"       // 蓝色
  if (score >= 50) return "score-warning"    // 橙色
  return "score-critical"                    // 红色
}

// 状态文本
function getStatusText(status) {
  return {
    healthy: "健康",
    degraded: "降级",
    unhealthy: "异常"
  }[status]
}

// 组件图标
function getComponentIcon(component) {
  return {
    database: "🗄️",
    redis: "⚡",
    disk_space: "💾",
    memory: "🧠",
    cpu: "⚙️",
    uploads_directory: "📁"
  }[component]
}

// 运行时间格式化
function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  if (days > 0) return `${days}天 ${hours}小时`
  if (hours > 0) return `${hours}小时 ${minutes}分钟`
  return `${minutes}分钟`
}
```

## 🎯 关键特性

### 1. 实时性
- 页面加载时自动检查
- 手动刷新功能
- 响应时间测量

### 2. 可视化
- 圆形评分显示
- 颜色编码状态
- 渐变色设计
- 图标化组件

### 3. 智能化
- 权重评分算法
- 自动状态判断
- 智能建议生成
- 阈值预警

### 4. 用户友好
- 中文界面
- 直观显示
- 响应式设计
- 加载状态反馈

### 5. 可扩展性
- 模块化检查函数
- 可配置权重
- 可添加新检查项
- 可自定义阈值

## 📈 性能优化

### 后端优化
- 并行执行检查（不阻塞）
- 超时控制（Redis 2秒，数据库默认）
- 缓存启动时间（避免重复计算）
- 异常捕获（不影响其他检查）

### 前端优化
- 按需加载（点击刷新才请求）
- 响应式数据（Vue 3 性能优化）
- CSS 动画（GPU 加速）
- 懒加载图标（按需渲染）

## 🔒 安全考虑

### 权限控制
- 需要伴侣登录（PartnerA / PartnerB）
- JWT 令牌验证
- 仅伴侣角色可访问

### 信息安全
- 不暴露敏感路径
- 不显示详细错误堆栈
- 响应时间脱敏（四舍五入）

### 资源保护
- 检查操作轻量级
- 不影响系统性能
- 超时保护

---

**架构版本**: 1.0
**创建时间**: 2026-05-01
**维护者**: 开发团队
