# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Login-device bookkeeping: upsert on every successful login, list/revoke via API."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.login_device import LoginDevice

_MAX_UA_LENGTH = 512


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else None


def _device_hash(user_agent: str | None, ip: str | None) -> str:
    # The fingerprint deliberately excludes the IP for mobile browsers whose
    # UA is stable — we combine UA (normalized) and /24 of the IP so the same
    # phone on the same home network maps to one row.
    ua = re.sub(r"\s+", " ", (user_agent or "").strip())[:_MAX_UA_LENGTH]
    ip_prefix = (ip or "").rsplit(".", 1)[0] if ip and ip.count(".") == 3 else (ip or "")
    return hashlib.sha256(f"{ua}|{ip_prefix}".encode("utf-8")).hexdigest()


def _friendly_device_name(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    os_name = "Unknown OS"
    if "windows" in ua:
        os_name = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "macOS"
    elif "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        os_name = "iOS"
    elif "linux" in ua:
        os_name = "Linux"

    browser = "Browser"
    if "edg/" in ua:
        browser = "Edge"
    elif "micromessenger" in ua:
        browser = "WeChat"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "chrome" in ua:
        browser = "Chrome"
    elif "safari" in ua:
        browser = "Safari"

    return f"{browser} · {os_name}"


def record_login_device(db: Session, user, request: Request) -> LoginDevice:
    """Insert or refresh the device row for this login. Caller commits if needed."""
    user_agent = (request.headers.get("User-Agent") or "")[:_MAX_UA_LENGTH] or None
    ip = _client_ip(request)
    dhash = _device_hash(user_agent, ip)

    device = (
        db.query(LoginDevice)
        .filter(LoginDevice.user_id == user.id, LoginDevice.device_hash == dhash)
        .first()
    )
    now = datetime.now(timezone.utc)
    if device is None:
        device = LoginDevice(
            user_id=user.id,
            device_hash=dhash,
            device_name=_friendly_device_name(user_agent),
            user_agent=user_agent,
            ip=ip,
            first_seen_at=now,
            last_login_at=now,
        )
        db.add(device)
    else:
        device.user_agent = user_agent
        device.ip = ip
        device.last_login_at = now
    db.commit()
    db.refresh(device)
    return device
