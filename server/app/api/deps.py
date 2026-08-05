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

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.services.visibility_policy import VisibilityPolicy
from app.services.security import check_session_version


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login", auto_error=False)


def get_token_from_request(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def get_token(request: Request) -> str:
    token = get_token_from_request(request)
    if not token:
        raise _UNAUTHORIZED_EXCEPTION
    return token


def get_token_optional(request: Request) -> str | None:
    return get_token_from_request(request)


_UNAUTHORIZED_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


_FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Permission denied",
)


def _is_banned_visitor(user: User) -> bool:
    return user.role.value == "Visitor" and (user.is_banned or user.permission_status == "banned")


def get_current_user(db: Session = Depends(get_db), token: str = Depends(get_token)) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        uid: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if uid is None or token_type != "access":
            raise _UNAUTHORIZED_EXCEPTION
    except JWTError as exc:
        raise _UNAUTHORIZED_EXCEPTION from exc

    user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
    if user is None:
        raise _UNAUTHORIZED_EXCEPTION
    if _is_banned_visitor(user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is banned",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 检查 session version
    token_session_version = payload.get("session_version")
    if not check_session_version(user, token_session_version):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_user(
    db: Session = Depends(get_db), token: str | None = Depends(get_token_optional)
) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        uid: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        if uid is None or token_type != "access":
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
    if user is None:
        return None
    if _is_banned_visitor(user):
        return None

    # 检查 session version（已撤销的 token 无效）
    token_session_version = payload.get("session_version")
    if not check_session_version(user, token_session_version):
        return None

    return user


def is_partner_user(user: User) -> bool:
    return VisibilityPolicy.is_partner(user)


def ensure_partner(user: User) -> User:
    if not is_partner_user(user):
        raise _FORBIDDEN_EXCEPTION
    return user


def can_co_edit(article_author_uid: str, partner_can_edit: bool, current_user: User) -> bool:
    if current_user.uid == article_author_uid:
        return True
    return partner_can_edit and is_partner_user(current_user)
