# 一起听自动暂停功能设计

## 需求
当双方在"一起听"模式中超过10分钟都不在界面时，自动暂停播放并结束队列。

## 设计方案

### 1. 核心机制

#### 1.1 心跳检测（Heartbeat）
- 前端每30秒发送一次心跳消息到后端
- 心跳消息类型：`HEARTBEAT`
- 只有当用户在"一起听"页面时才发送心跳

#### 1.2 在线状态追踪
- 后端在Redis中记录每个用户的最后活跃时间
- Redis Key: `cottage_listen:presence:{user_uid}`
- 值：最后心跳时间戳（毫秒）
- TTL：15分钟（自动过期）

#### 1.3 自动暂停检查
- 后端定时任务每分钟检查一次
- 检查条件：
  - 当前正在播放（paused = false）
  - 双方用户最后活跃时间都超过10分钟
- 触发动作：
  - 暂停当前播放
  - 清空队列
  - 广播 `AUTO_PAUSED` 事件给所有连接的客户端

### 2. 实现细节

#### 2.1 前端改动

**文件：`web/src/stores/listenPlayer.js`**

1. 添加心跳定时器
```javascript
let heartbeatInterval = null;

onMounted(() => {
  // 启动心跳
  startHeartbeat();
});

onBeforeUnmount(() => {
  // 停止心跳
  stopHeartbeat();
});

function startHeartbeat() {
  // 立即发送一次
  sendHeartbeat();
  // 每30秒发送一次
  heartbeatInterval = setInterval(() => {
    sendHeartbeat();
  }, 30000);
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
  }
}

function sendHeartbeat() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({
      type: "HEARTBEAT",
      payload: {}
    }));
  }
}
```

2. 处理 `AUTO_PAUSED` 事件
```javascript
case "AUTO_PAUSED":
  // 显示提示信息
  errorMsg.value = "由于双方超过10分钟未在线，播放已自动暂停并清空队列";
  // 重新加载状态
  reloadState();
  break;
```

#### 2.2 后端改动

**文件：`server/app/api/v1/cottage_listen_ws.py`**

1. 处理心跳消息
```python
if type_ == "HEARTBEAT":
    # 更新用户在线状态
    from app.services.listen_together.presence import update_presence
    update_presence(redis_client, user.uid)
    # 不需要广播心跳
    continue
```

**新文件：`server/app/services/listen_together/presence.py`**

```python
"""用户在线状态管理"""
from redis import Redis
import time

PRESENCE_KEY_PREFIX = "cottage_listen:presence:"
PRESENCE_TTL = 900  # 15分钟

def update_presence(redis_client: Redis, user_uid: str) -> None:
    """更新用户最后活跃时间"""
    key = f"{PRESENCE_KEY_PREFIX}{user_uid}"
    now_ms = int(time.time() * 1000)
    redis_client.setex(key, PRESENCE_TTL, str(now_ms))

def get_last_active_time(redis_client: Redis, user_uid: str) -> int:
    """获取用户最后活跃时间（毫秒），如果不存在返回0"""
    key = f"{PRESENCE_KEY_PREFIX}{user_uid}"
    value = redis_client.get(key)
    if value:
        return int(value)
    return 0

def are_both_inactive(redis_client: Redis, partner_a_uid: str, partner_b_uid: str, threshold_ms: int) -> bool:
    """检查双方是否都不活跃超过阈值时间"""
    now_ms = int(time.time() * 1000)
    
    last_a = get_last_active_time(redis_client, partner_a_uid)
    last_b = get_last_active_time(redis_client, partner_b_uid)
    
    # 如果任何一方从未活跃过，认为不活跃
    if last_a == 0 or last_b == 0:
        return False
    
    inactive_a = (now_ms - last_a) > threshold_ms
    inactive_b = (now_ms - last_b) > threshold_ms
    
    return inactive_a and inactive_b
```

**新文件：`server/app/services/listen_together/auto_pause.py`**

```python
"""自动暂停检查任务"""
import asyncio
import logging
from typing import Any

from app.db.redis import get_redis
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.services.listen_together.room import get_state, apply_event
from app.services.listen_together.presence import are_both_inactive

logger = logging.getLogger(__name__)

# 10分钟的毫秒数
INACTIVITY_THRESHOLD_MS = 10 * 60 * 1000

async def check_and_auto_pause() -> None:
    """检查是否需要自动暂停"""
    redis_client = get_redis()
    db = SessionLocal()
    
    try:
        # 获取当前播放状态
        state = get_state(redis_client)
        current = state.get("current", {})
        
        # 如果没有在播放，不需要检查
        if not current.get("song_id") or current.get("paused"):
            return
        
        # 获取双方用户UID
        partner_a = db.query(User).filter(
            User.role == UserRole.partner_a,
            User.deleted_at.is_(None)
        ).first()
        partner_b = db.query(User).filter(
            User.role == UserRole.partner_b,
            User.deleted_at.is_(None)
        ).first()
        
        if not partner_a or not partner_b:
            return
        
        # 检查双方是否都不活跃
        if are_both_inactive(redis_client, partner_a.uid, partner_b.uid, INACTIVITY_THRESHOLD_MS):
            logger.info("Both partners inactive for >10min, auto-pausing")
            
            # 暂停播放
            pause_event = apply_event(
                redis_client,
                "PAUSE",
                {"position_ms": current.get("position_ms", 0)},
                "system"
            )
            
            # 清空队列
            clear_event = apply_event(
                redis_client,
                "QUEUE_CLEAR",
                {},
                "system"
            )
            
            # 广播自动暂停事件
            from app.api.v1.cottage_listen_ws import manager
            await manager.broadcast({
                "type": "AUTO_PAUSED",
                "payload": {
                    "reason": "Both partners inactive for more than 10 minutes"
                },
                "event_seq": pause_event["event_seq"],
                "origin_uid": "system",
                "server_ts_ms": pause_event["server_ts_ms"]
            })
            
    except Exception as e:
        logger.error(f"Error in auto-pause check: {e}", exc_info=True)
    finally:
        db.close()

async def auto_pause_loop() -> None:
    """自动暂停检查循环，每分钟执行一次"""
    while True:
        try:
            await check_and_auto_pause()
        except Exception as e:
            logger.error(f"Error in auto-pause loop: {e}", exc_info=True)
        
        # 等待60秒
        await asyncio.sleep(60)
```

**文件：`server/app/main.py`**

在应用 lifespan 中启动自动暂停检查任务：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    # ... 其他启动逻辑 ...
    from app.services.listen_together.auto_pause import auto_pause_loop
    asyncio.create_task(auto_pause_loop())
    try:
        yield
    finally:
        # 取消任务
        pass
```

### 3. 用户体验优化

#### 3.1 提示信息
- 当自动暂停触发时，前端显示友好的提示信息
- 提示内容："由于双方超过10分钟未在线，播放已自动暂停并清空队列"

#### 3.2 恢复播放
- 用户返回页面后可以重新添加歌曲到队列
- 之前的播放状态不会恢复（这是预期行为）

#### 3.3 边界情况处理
- 如果只有一方离开，不会触发自动暂停
- 如果已经暂停，不会重复触发
- 如果没有歌曲在播放，不会触发

### 4. 配置选项（可选扩展）

可以在后端配置文件中添加可配置项：

```python
# app/core/config.py
class Settings(BaseSettings):
    # ... 其他配置
    
    # 一起听自动暂停阈值（分钟）
    listen_auto_pause_minutes: int = 10
    
    # 心跳超时时间（分钟）
    listen_heartbeat_timeout_minutes: int = 15
```

### 5. 测试场景

#### 5.1 正常场景
1. 双方都在线 → 不触发自动暂停
2. 一方离开 < 10分钟 → 不触发
3. 双方都离开 > 10分钟 → 触发自动暂停

#### 5.2 边界场景
1. 已经暂停状态 → 不触发
2. 没有歌曲播放 → 不触发
3. 一方在线，一方离开 > 10分钟 → 不触发

#### 5.3 恢复场景
1. 自动暂停后，用户返回 → 可以正常添加歌曲和播放
2. 自动暂停后，队列已清空 → 需要重新添加歌曲

### 6. 监控和日志

#### 6.1 日志记录
- 记录每次心跳接收
- 记录自动暂停触发
- 记录在线状态检查结果

#### 6.2 指标（可选）
- 自动暂停触发次数
- 平均在线时长
- 心跳丢失率

## 实现优先级

1. **P0 - 核心功能**
   - 前端心跳发送
   - 后端在线状态追踪
   - 自动暂停检查和执行

2. **P1 - 用户体验**
   - 前端提示信息
   - 日志记录

3. **P2 - 可选扩展**
   - 配置选项
   - 监控指标

## 技术风险

1. **WebSocket连接稳定性**
   - 风险：网络不稳定可能导致心跳丢失
   - 缓解：使用较长的超时时间（10分钟）

2. **定时任务精度**
   - 风险：定时任务可能不够精确
   - 缓解：1分钟的检查间隔足够满足需求

3. **Redis数据一致性**
   - 风险：Redis重启可能丢失在线状态
   - 缓解：用户重新进入页面会重新发送心跳

## 部署注意事项

1. 确保Redis正常运行
2. 后端需要重启以加载新的定时任务
3. 前端需要重新构建和部署
4. 建议先在测试环境验证

## 后续优化方向

1. 支持配置不同的超时时间
2. 添加"即将自动暂停"的提前警告（如9分钟时提示）
3. 支持用户手动设置是否启用自动暂停
4. 记录自动暂停历史，供用户查看
