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

"""Redis client singleton.

Project-wide Redis connection pool. Created lazily — connect failures don't
block backend startup (they surface only when a feature actually needs Redis).

Used by:
- cottage-listen-together: room state, queue, encrypted NetEase cookies.
"""
from __future__ import annotations

import redis

from app.core.config import settings

_pool = redis.ConnectionPool.from_url(
    settings.resolved_redis_url,
    decode_responses=True,
    max_connections=20,
)


def get_redis() -> redis.Redis:
    """Return a Redis client backed by the shared connection pool.

    The client is cheap to construct; share the underlying pool. Each caller
    can use the returned client for the lifetime of one request.
    """
    return redis.Redis(connection_pool=_pool)
