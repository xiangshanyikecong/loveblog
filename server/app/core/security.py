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

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def dummy_verify() -> None:
    """Perform a throwaway hash verification.

    Called on the "unknown username" login path so that a non-existent user and
    a wrong password take indistinguishable time, preventing username
    enumeration via response timing.
    """
    pwd_context.dummy_verify()


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def access_token_expires_in_seconds(expires_minutes: int | None = None) -> int:
    minutes = (
        expires_minutes if expires_minutes is not None else settings.jwt_access_token_expire_minutes
    )
    return int(minutes * 60)


def create_access_token(
    subject: str,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
    session_version: int | None = None,
) -> str:
    expire_seconds = access_token_expires_in_seconds(expires_minutes)
    now = datetime.now(timezone.utc)
    expire = now + timedelta(seconds=expire_seconds)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": now,
        "type": "access",
    }
    if session_version is not None:
        payload["session_version"] = session_version
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
