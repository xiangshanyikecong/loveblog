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

from sqlalchemy.orm import Session

from app.models.user import User

# Login failure throttling.
MAX_LOGIN_FAILED_ATTEMPTS = 5
LOGIN_FREEZE_MINUTES = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_account_frozen(user: User) -> bool:
    """Return whether the account is still inside its freeze window."""
    freeze_until = _coerce_utc(user.login_freeze_until)
    if freeze_until is None:
        return False
    if freeze_until <= _utc_now():
        return False
    return True


def get_freeze_remaining_minutes(user: User) -> int:
    """Return remaining freeze time in minutes."""
    freeze_until = _coerce_utc(user.login_freeze_until)
    if freeze_until is None:
        return 0
    remaining = freeze_until - _utc_now()
    return max(0, int(remaining.total_seconds() / 60))


def record_failed_login(db: Session, user: User) -> tuple[int, int | None]:
    """
    Record a failed login attempt.

    Returns `(failed_count, freeze_minutes_or_none)`.
    """
    user.login_failed_count += 1

    if user.login_failed_count >= MAX_LOGIN_FAILED_ATTEMPTS:
        user.login_freeze_until = _utc_now() + timedelta(minutes=LOGIN_FREEZE_MINUTES)
        db.commit()
        return user.login_failed_count, LOGIN_FREEZE_MINUTES

    db.commit()
    return user.login_failed_count, None


def record_successful_login(db: Session, user: User, ip_address: str | None = None) -> None:
    """Clear failure counters and store the latest login metadata."""
    user.login_failed_count = 0
    user.login_freeze_until = None
    user.last_login_at = _utc_now()
    if ip_address:
        user.last_login_ip = ip_address
    db.commit()


def reset_login_attempts(db: Session, user: User) -> None:
    """Reset login failure state for the user."""
    user.login_failed_count = 0
    user.login_freeze_until = None
    db.commit()


def increment_session_version(db: Session, user: User) -> int:
    """Advance the active session version and invalidate existing sessions."""
    user.session_version += 1
    db.commit()
    db.refresh(user)
    return user.session_version


def unlock_account(db: Session, user: User) -> None:
    """Unlock a frozen account."""
    user.login_failed_count = 0
    user.login_freeze_until = None
    db.commit()


def check_session_version(user: User, token_session_version: int | None) -> bool:
    """Accept only the currently active session version for the user."""
    if token_session_version is None:
        return False
    return token_session_version == user.session_version
