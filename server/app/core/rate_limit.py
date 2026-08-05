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

"""Process-wide slowapi limiter.

A SINGLE shared limiter instance is used both by the global
``SlowAPIMiddleware`` (registered in ``app.main``) and by explicit
``@limiter.limit(...)`` decorators on sensitive routes (e.g. login). Keeping
one instance ensures ``app.state.limiter`` and the decorators agree, and lets
tests toggle ``limiter.enabled`` in one place.

The key function resolves the real client IP behind the edge proxy (see
``app.core.net``) so per-IP limits actually distinguish callers in production
rather than collapsing onto nginx's address.
"""
from __future__ import annotations

from slowapi import Limiter

from app.core.config import settings
from app.core.net import get_real_client_ip

limiter = Limiter(
    key_func=get_real_client_ip,
    default_limits=[settings.rate_limit_default],
)
