# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""自动暂停检查任务

定期检查双方用户是否都离线超过阈值时间，如果是则自动暂停播放并清空队列。
"""
from __future__ import annotations

import asyncio
import logging

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
            apply_event(
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
