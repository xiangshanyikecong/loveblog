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

"""TOTP two-factor-authentication management for the logged-in user."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.totp import (
    TotpDisableRequest,
    TotpEnableRequest,
    TotpEnableResponse,
    TotpSetupResponse,
    TotpStatusResponse,
)
from app.services.audit import write_audit_log
from app.services.totp import (
    generate_recovery_codes,
    generate_secret,
    hash_recovery_code,
    provisioning_uri,
    verify_totp,
)


router = APIRouter(prefix="/auth/totp", tags=["auth"])


def _verify_second_factor(db: Session, user: User, code: str) -> bool:
    """Verify a TOTP code or burn a one-time recovery code.

    Mirrors ``app.api.v1.auth._verify_second_factor``: TOTP wins first, then a
    recovery-code match removes that code from the user's list immediately.
    """
    if verify_totp(user.totp_secret or "", code.strip()):
        return True

    if user.totp_recovery_codes:
        try:
            remaining = json.loads(user.totp_recovery_codes)
        except (TypeError, ValueError, json.JSONDecodeError):
            remaining = []
        code_hash = hash_recovery_code(code)
        if code_hash in remaining:
            remaining.remove(code_hash)
            user.totp_recovery_codes = json.dumps(remaining)
            db.commit()
            return True
    return False


def _recovery_codes_remaining(user: User) -> int:
    """Length of the stored recovery-code hash list (0 when unset/corrupt)."""
    if not user.totp_recovery_codes:
        return 0
    try:
        remaining = json.loads(user.totp_recovery_codes)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 0
    return len(remaining) if isinstance(remaining, list) else 0


@router.post("/setup", response_model=TotpSetupResponse)
def setup_totp(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TotpSetupResponse:
    """Generate a fresh TOTP secret without enabling it yet.

    The user scans the URI (or types the secret) and confirms a code via
    ``POST /enable`` before the second factor takes effect.
    """
    if current_user.totp_enabled:
        # Rotating the secret while 2FA is live would silently deactivate the
        # user's verified second factor — require disable first instead.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP is already enabled; disable it first",
        )

    secret = generate_secret()
    current_user.totp_secret = secret
    current_user.totp_enabled = False  # stays disabled until verified
    db.commit()

    write_audit_log(
        db,
        action="totp.setup",
        actor=current_user,
        resource_type="user",
        resource_id=current_user.uid,
        resource_name=current_user.username,
    )

    return TotpSetupResponse(
        secret=secret,
        uri=provisioning_uri(secret, current_user.username),
    )


@router.post("/enable", response_model=TotpEnableResponse)
def enable_totp(
    payload: TotpEnableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TotpEnableResponse:
    """Confirm the authenticator app, then activate 2FA and issue recovery codes."""
    if not current_user.totp_secret or not verify_totp(
        current_user.totp_secret, payload.code.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code"
        )

    current_user.totp_enabled = True
    recovery_codes = generate_recovery_codes()
    current_user.totp_recovery_codes = json.dumps(
        [hash_recovery_code(code) for code in recovery_codes]
    )
    db.commit()

    write_audit_log(
        db,
        action="totp.enable",
        actor=current_user,
        resource_type="user",
        resource_id=current_user.uid,
        resource_name=current_user.username,
        detail={"recovery_codes_issued": len(recovery_codes)},
    )

    # Plaintext recovery codes are returned exactly once.
    return TotpEnableResponse(enabled=True, recovery_codes=recovery_codes)


@router.post("/disable", response_model=TotpStatusResponse)
def disable_totp(
    payload: TotpDisableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TotpStatusResponse:
    """Turn 2FA off; requires a valid second factor AND the account password."""
    # Password is checked first so a typo cannot burn a one-time recovery code.
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password")

    if not _verify_second_factor(db, current_user, payload.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code"
        )

    current_user.totp_enabled = False
    current_user.totp_secret = None
    current_user.totp_recovery_codes = None
    db.commit()

    write_audit_log(
        db,
        action="totp.disable",
        actor=current_user,
        resource_type="user",
        resource_id=current_user.uid,
        resource_name=current_user.username,
    )

    return TotpStatusResponse(enabled=False, recovery_codes_remaining=0)


@router.get("/status", response_model=TotpStatusResponse)
def totp_status(
    current_user: User = Depends(get_current_user),
) -> TotpStatusResponse:
    """Current 2FA state for the account."""
    return TotpStatusResponse(
        enabled=current_user.totp_enabled,
        recovery_codes_remaining=_recovery_codes_remaining(current_user),
    )
