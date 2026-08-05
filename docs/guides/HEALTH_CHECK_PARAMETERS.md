# 系统健康检查 - 参数说明

## 📋 概述

系统健康检查 API 现在支持多个可选参数，让你可以根据需求灵活地获取健康状态信息。

## 🔧 API 参数

### 端点
```
GET /health/system
```

### 参数列表

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `components` | string | 全部 | 指定要检查的组件，逗号分隔 |
| `include_recommendations` | boolean | true | 是否包含优化建议 |
| `detailed` | boolean | true | 是否返回详细信息（响应时间等） |

### 1. components（组件选择）

**用途**：只检查指定的组件，提高响应速度

**可选值**：
- `database` - 数据库
- `redis` - Redis 缓存
- `disk_space` - 磁盘空间
- `memory` - 内存
- `cpu` - CPU
- `uploads_directory` - 上传目录

**示例**：

```bash
# 只检查数据库和 Redis
GET /health/system?components=database,redis

# 只检查系统资源（磁盘、内存、CPU）
GET /health/system?components=disk_space,memory,cpu

# 只检查数据库
GET /health/system?components=database
```

**使用场景**：
- 🚀 **快速检查**：只检查关键组件，减少响应时间
- 🎯 **针对性监控**：只关注特定组件的状态
- 📊 **分组监控**：分别监控数据库层、系统资源层等

### 2. include_recommendations（优化建议）

**用途**：控制是否返回优化建议

**可选值**：
- `true` - 包含优化建议（默认）
- `false` - 不包含优化建议

**示例**：

```bash
# 不包含优化建议（减少响应体积）
GET /health/system?include_recommendations=false

# 包含优化建议
GET /health/system?include_recommendations=true
```

**使用场景**：
- 📈 **监控面板**：不需要建议，只需要状态数据
- 🤖 **自动化监控**：程序化处理，不需要人类可读的建议
- 💾 **减少带宽**：在网络受限环境下减少数据传输

### 3. detailed（详细信息）

**用途**：控制是否返回详细信息（如响应时间）

**可选值**：
- `true` - 返回详细信息（默认）
- `false` - 只返回基本状态

**示例**：

```bash
# 只返回基本状态（不包含响应时间）
GET /health/system?detailed=false

# 返回详细信息
GET /health/system?detailed=true
```

**使用场景**：
- 🎨 **简化 UI**：只显示状态，不显示技术细节
- 📊 **状态概览**：快速了解整体状态
- 🔒 **安全考虑**：不暴露响应时间等技术细节

## 💡 组合使用示例

### 示例 1：快速数据库检查
```bash
GET /health/system?components=database&detailed=false&include_recommendations=false
```

**响应**：
```json
{
  "overall_status": "healthy",
  "health_score": 25,
  "checks": [
    {
      "component": "database",
      "status": "ok",
      "message": "数据库连接正常",
      "response_time_ms": null
    }
  ],
  "recommendations": [],
  "uptime_seconds": 3600.5,
  "timestamp": "2026-05-03T14:00:00Z"
}
```

### 示例 2：系统资源监控
```bash
GET /health/system?components=disk_space,memory,cpu&include_recommendations=false
```

**响应**：
```json
{
  "overall_status": "healthy",
  "health_score": 45,
  "checks": [
    {
      "component": "disk_space",
      "status": "ok",
      "message": "磁盘空间充足 (60.9% 已使用)",
      "response_time_ms": null
    },
    {
      "component": "memory",
      "status": "ok",
      "message": "内存使用正常 (70.7% 已使用)",
      "response_time_ms": null
    },
    {
      "component": "cpu",
      "status": "ok",
      "message": "CPU 使用正常 (4.1%)",
      "response_time_ms": null
    }
  ],
  "recommendations": [],
  "uptime_seconds": 3600.5,
  "timestamp": "2026-05-03T14:00:00Z"
}
```

### 示例 3：完整检查（默认）
```bash
GET /health/system
```

**响应**：包含所有组件、优化建议和详细信息

## 🎯 前端使用方法

### JavaScript/Vue 示例

```javascript
import { fetchSystemHealth } from '@/lib/api';

// 1. 默认：检查所有组件
const health = await fetchSystemHealth();

// 2. 只检查数据库和 Redis
const dbHealth = await fetchSystemHealth({
  components: ['database', 'redis']
});

// 3. 快速检查（无建议、无详细信息）
const quickHealth = await fetchSystemHealth({
  includeRecommendations: false,
  detailed: false
});

// 4. 只检查系统资源
const resourceHealth = await fetchSystemHealth({
  components: ['disk_space', 'memory', 'cpu']
});

// 5. 组合使用
const customHealth = await fetchSystemHealth({
  components: ['database', 'redis'],
  includeRecommendations: true,
  detailed: false
});
```

### 在 AdminView.vue 中使用

```javascript
// 当前实现（检查所有组件）
async function loadSystemHealth() {
  healthLoading.value = true;
  try {
    systemHealth.value = await fetchSystemHealth();
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    healthLoading.value = false;
  }
}

// 快速检查（只检查关键组件）
async function quickHealthCheck() {
  healthLoading.value = true;
  try {
    systemHealth.value = await fetchSystemHealth({
      components: ['database', 'redis'],
      detailed: false
    });
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    healthLoading.value = false;
  }
}
```

## 📊 性能对比

### 完整检查
```bash
GET /health/system
```
- **检查项目**：6 个组件
- **响应时间**：~1-2 秒（包含 CPU 检查的 0.5 秒延迟）
- **响应大小**：~1KB

### 快速检查
```bash
GET /health/system?components=database,redis&detailed=false&include_recommendations=false
```
- **检查项目**：2 个组件
- **响应时间**：~50-100ms
- **响应大小**：~300 字节

### 性能提升
- ⚡ **速度提升**：10-20 倍
- 💾 **带宽节省**：70%
- 🎯 **针对性强**：只检查需要的组件

## 🔍 使用场景建议

### 1. 管理后台（完整检查）
```javascript
// 用户手动点击"刷新"时
fetchSystemHealth()
```
- 显示所有组件状态
- 包含优化建议
- 显示详细信息

### 2. 监控面板（定时轮询）
```javascript
// 每 30 秒自动检查
setInterval(() => {
  fetchSystemHealth({
    includeRecommendations: false,
    detailed: false
  })
}, 30000)
```
- 不需要建议（减少数据量）
- 不需要详细信息（只看状态）
- 减少服务器负载

### 3. 数据库健康监控
```javascript
// 专门监控数据库
fetchSystemHealth({
  components: ['database'],
  detailed: true
})
```
- 只检查数据库
- 显示响应时间
- 用于性能分析

### 4. 系统资源告警
```javascript
// 监控系统资源
fetchSystemHealth({
  components: ['disk_space', 'memory', 'cpu'],
  includeRecommendations: true
})
```
- 只检查系统资源
- 包含优化建议
- 用于资源告警

### 5. 容器健康检查
```bash
# 简单快速的健康检查
GET /health
```
- 最快速的检查
- 只返回基本状态
- 用于容器编排（Kubernetes、Docker）

## 🎨 UI 增强建议

### 添加快速检查按钮

在 `AdminView.vue` 中添加多个检查选项：

```vue
<div class="section-header">
  <h2>🏥 系统健康检查</h2>
  <div class="health-actions">
    <button class="ghost-btn" @click="quickCheck">快速检查</button>
    <button class="ghost-btn" @click="fullCheck">完整检查</button>
  </div>
</div>
```

```javascript
// 快速检查（只检查关键组件）
async function quickCheck() {
  healthLoading.value = true;
  try {
    systemHealth.value = await fetchSystemHealth({
      components: ['database', 'redis'],
      detailed: false
    });
    showMessage?.('快速检查完成');
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    healthLoading.value = false;
  }
}

// 完整检查（所有组件）
async function fullCheck() {
  healthLoading.value = true;
  try {
    systemHealth.value = await fetchSystemHealth();
    showMessage?.('完整检查完成');
  } catch (error) {
    showMessage?.(parseError(error));
  } finally {
    healthLoading.value = false;
  }
}
```

### 添加组件选择器

```vue
<div class="component-selector">
  <label v-for="comp in availableComponents" :key="comp">
    <input type="checkbox" v-model="selectedComponents" :value="comp" />
    {{ componentNames[comp] }}
  </label>
  <button @click="checkSelected">检查选中组件</button>
</div>
```

## 📈 监控集成示例

### Prometheus 风格的监控

```javascript
// 定期收集指标
async function collectMetrics() {
  const health = await fetchSystemHealth({
    detailed: true,
    includeRecommendations: false
  });
  
  // 发送到监控系统
  metrics.gauge('health_score', health.health_score);
  metrics.gauge('uptime_seconds', health.uptime_seconds);
  
  health.checks.forEach(check => {
    metrics.gauge(`component_status_${check.component}`, 
      check.status === 'ok' ? 1 : 0
    );
    
    if (check.response_time_ms) {
      metrics.histogram(`component_response_time_${check.component}`, 
        check.response_time_ms
      );
    }
  });
}
```

### 告警系统集成

```javascript
// 检查关键组件并触发告警
async function checkAndAlert() {
  const health = await fetchSystemHealth({
    components: ['database', 'redis'],
    includeRecommendations: true
  });
  
  health.checks.forEach(check => {
    if (check.status === 'error') {
      sendAlert({
        level: 'critical',
        component: check.component,
        message: check.message
      });
    } else if (check.status === 'warning') {
      sendAlert({
        level: 'warning',
        component: check.component,
        message: check.message
      });
    }
  });
}
```

## 🔒 安全考虑

### 1. 权限控制

建议在后端添加权限检查：

```python
from app.api.deps import get_current_user

@router.get("/health/system")
def system_health_check(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),  # 需要登录
    components: str | None = None,
    # ...
):
    # 只有管理员可以访问
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    # ...
```

### 2. 速率限制

防止频繁请求：

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/health/system")
@limiter.limit("10/minute")  # 每分钟最多 10 次
def system_health_check(...):
    # ...
```

### 3. 敏感信息过滤

在 `detailed=false` 时不返回响应时间等技术细节。

## 📝 总结

### 新增参数的优势

1. **灵活性** ⚡
   - 按需检查组件
   - 控制返回信息的详细程度
   - 适应不同使用场景

2. **性能优化** 🚀
   - 减少不必要的检查
   - 降低响应时间
   - 节省带宽

3. **可扩展性** 🔧
   - 易于添加新组件
   - 支持自定义检查策略
   - 便于集成监控系统

4. **用户体验** 🎨
   - 快速检查选项
   - 减少等待时间
   - 更好的交互体验

### 最佳实践

- ✅ **管理后台**：使用完整检查（默认参数）
- ✅ **定时监控**：使用快速检查（指定组件 + 无建议）
- ✅ **性能分析**：使用详细模式（detailed=true）
- ✅ **告警系统**：使用组件过滤 + 建议
- ✅ **容器健康检查**：使用 `/health` 端点

---

**文档版本**：1.0
**更新时间**：2026-05-03
**作者**：开发团队
