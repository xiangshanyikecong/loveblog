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

"""用户在线状态管理

追踪"一起听"功能中用户的在线状态，用于自动暂停检测。
"""
from __future__ import annotations

import time

from redis import Redis

PRESENCE_KEY_PREFIX = "cottage_listen:presence:"
PRESENCE_TTL = 900  # 15分钟（秒）


def update_presence(redis_client: Redis, user_uid: str) -> None:
    """更新用户最后活跃时间

    Args:
        redis_client: Redis客户端
        user_uid: 用户UID
    """
    key = f"{PRESENCE_KEY_PREFIX}{user_uid}"
    now_ms = int(time.time() * 1000)
    redis_client.setex(key, PRESENCE_TTL, str(now_ms))


def get_last_active_time(redis_client: Redis, user_uid: str) -> int:
    """获取用户最后活跃时间（毫秒）

    Args:
        redis_client: Redis客户端
        user_uid: 用户UID

    Returns:
        最后活跃时间戳（毫秒），如果不存在返回0
    """
    key = f"{PRESENCE_KEY_PREFIX}{user_uid}"
    value = redis_client.get(key)
    if value:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    return 0


def are_both_inactive(
    redis_client: Redis,
    partner_a_uid: str,
    partner_b_uid: str,
    threshold_ms: int
) -> bool:
    """检查双方是否都不活跃超过阈值时间

    Args:
        redis_client: Redis客户端
        partner_a_uid: 伴侣A的UID
        partner_b_uid: 伴侣B的UID
        threshold_ms: 不活跃阈值（毫秒）

    Returns:
        如果双方都超过阈值时间未活跃，返回True
    """
    now_ms = int(time.time() * 1000)

    last_a = get_last_active_time(redis_client, partner_a_uid)
    last_b = get_last_active_time(redis_client, partner_b_uid)

    # 如果任何一方从未活跃过，认为不满足条件
    if last_a == 0 or last_b == 0:
        return False

    inactive_a = (now_ms - last_a) > threshold_ms
    inactive_b = (now_ms - last_b) > threshold_ms

    return inactive_a and inactive_b
