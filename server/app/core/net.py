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

"""Trusted client-IP extraction for requests behind the edge proxy.

In production the FastAPI backend is only reachable through nginx on the
internal docker network. nginx sets ``X-Real-IP`` to the real TCP peer
(``$remote_addr``) and appends it to ``X-Forwarded-For`` via
``$proxy_add_x_forwarded_for``. We therefore trust:

1. ``X-Real-IP`` (set by our own proxy), then
2. the LAST entry of ``X-Forwarded-For`` (the hop our proxy appended — earlier
   entries can be forged by the client and must NOT be trusted), then
3. the transport peer address.

Taking the *first* XFF segment (the previous, naive behavior) let any client
spoof their apparent IP by sending their own ``X-Forwarded-For`` header — which
both defeated per-IP rate limiting and allowed check-in location spoofing.
"""
from __future__ import annotations

from starlette.requests import Request


def get_real_client_ip(request: Request) -> str:
    """Best-effort real client IP, resistant to client-supplied XFF spoofing."""
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        parts = [segment.strip() for segment in forwarded.split(",") if segment.strip()]
        if parts:
            # Last hop is the one appended by our trusted proxy.
            return parts[-1]

    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"
