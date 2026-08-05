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

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from urllib.parse import urlsplit

from fastapi import WebSocket

from app.core.config import settings


logger = logging.getLogger(__name__)


def _normalize_origin(origin: str | None) -> str | None:
    if not origin:
        return None

    parsed = urlsplit(origin.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def allowed_websocket_origins() -> set[str]:
    return {
        normalized
        for origin in settings.cors_origin_list
        if (normalized := _normalize_origin(origin)) is not None
    }


def websocket_origin_allowed(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin") or ws.headers.get("Origin")
    # Native (non-browser) clients — notably the Android app — do not send an
    # Origin header. Allowing a *missing* Origin does not open a CSRF hole:
    # browser-driven CSRF relies on the browser auto-attaching cookies on a
    # cross-site request, and browsers ALWAYS set Origin on WebSocket
    # handshakes — so a genuinely malicious cross-origin browser attempt would
    # be caught by the allowlist branch below. The socket additionally stays
    # protected by the per-endpoint JWT + session_version + partner-role checks.
    # A *present* Origin must still be in the CORS allowlist (browser path
    # unchanged).
    if not origin:
        return True
    normalized_origin = _normalize_origin(origin)
    if normalized_origin is None:
        return False
    return normalized_origin in allowed_websocket_origins()


async def close_when_session_revoked(
    ws: WebSocket,
    token: str,
    resolve_user: Callable[[str], object | None],
    *,
    interval_seconds: float = 15,
    close_code: int = 4401,
) -> None:
    """Close even a completely idle socket shortly after session revocation."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            user = await asyncio.to_thread(resolve_user, token)
        except Exception:
            # Authentication storage becoming unavailable cannot leave an
            # already-privileged socket open indefinitely.
            logger.warning("WebSocket session revalidation failed; closing socket", exc_info=True)
            user = None
        if user is not None:
            continue
        try:
            await ws.close(code=close_code)
        except Exception:
            pass
        return


async def stop_session_watchdog(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        # Cleanup must still reach manager.disconnect even if the watchdog had
        # already failed before the endpoint entered its finally block.
        logger.warning("WebSocket session watchdog failed", exc_info=True)
