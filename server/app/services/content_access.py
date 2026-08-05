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

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from jose import JWTError, jwt

from app.core.config import settings


CONTENT_ACCESS_TTL_SECONDS = 10 * 60


def content_access_cookie_name(content_kind: str, content_id: int) -> str:
    return f"content_access_{content_kind}_{int(content_id)}"


def _password_version(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def grant_content_access(
    response: Response,
    request: Request,
    *,
    content_kind: str,
    content_id: int,
    password_hash: str,
) -> None:
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "type": "content_access",
            "content_kind": content_kind,
            "content_id": int(content_id),
            "password_version": _password_version(password_hash),
            "iat": now,
            "exp": now + timedelta(seconds=CONTENT_ACCESS_TTL_SECONDS),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip()
    secure = settings.cookie_secure
    if secure is None:
        secure = request.url.scheme == "https" or forwarded_proto == "https"
    response.set_cookie(
        content_access_cookie_name(content_kind, content_id),
        token,
        max_age=CONTENT_ACCESS_TTL_SECONDS,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
    )


def has_content_access(
    request: Request,
    *,
    content_kind: str,
    content_id: int,
    password_hash: str | None,
) -> bool:
    if not password_hash:
        return False
    token = request.cookies.get(content_access_cookie_name(content_kind, content_id))
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return False
    return (
        payload.get("type") == "content_access"
        and payload.get("content_kind") == content_kind
        and payload.get("content_id") == int(content_id)
        and payload.get("password_version") == _password_version(password_hash)
    )
