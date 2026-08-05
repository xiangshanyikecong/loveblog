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

"""Presence tracking for cottage 一起看 (watch-together).

A short-lived Redis key per partner marks them as "currently in the watch
room". Refreshed on WS connect and on each heartbeat; expires automatically so
a crashed / closed tab stops counting as online without an explicit cleanup.
"""
from __future__ import annotations

import time

from redis import Redis

PRESENCE_KEY_PREFIX = "cottage_watch:presence:"
# Slightly longer than the frontend heartbeat interval (30s) so a single missed
# beat doesn't flap the partner offline.
PRESENCE_TTL = 90


def _key(user_uid: str) -> str:
    return f"{PRESENCE_KEY_PREFIX}{user_uid}"


def mark_online(redis_client: Redis, user_uid: str) -> None:
    redis_client.setex(_key(user_uid), PRESENCE_TTL, str(int(time.time() * 1000)))


def mark_offline(redis_client: Redis, user_uid: str) -> None:
    redis_client.delete(_key(user_uid))


def is_online(redis_client: Redis, user_uid: str) -> bool:
    try:
        return bool(redis_client.exists(_key(user_uid)))
    except Exception:
        return False
