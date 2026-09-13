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

"""Best-effort Redis cache for expensive aggregate endpoints.

Used by the dashboard and the monthly/annual report endpoints, whose
responses each fan out into a dozen COUNT/GROUP-BY queries. Everything is
best-effort: any Redis failure simply falls back to computing directly.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.db.redis import get_redis

logger = logging.getLogger(__name__)


def cache_get_json(key: str) -> Any | None:
    """Return the deserialized JSON value stored under *key*, or None."""
    try:
        raw = get_redis().get(key)
    except Exception:
        logger.debug("Cache read failed for %s", key, exc_info=True)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        logger.warning("Corrupted cache entry for %s; ignoring", key)
        return None


def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    """Store *value* under *key* with an expiry. Failures are logged only."""
    try:
        get_redis().setex(
            key,
            ttl_seconds,
            json.dumps(value, ensure_ascii=False, default=str),
        )
    except Exception:
        logger.debug("Cache write failed for %s", key, exc_info=True)
