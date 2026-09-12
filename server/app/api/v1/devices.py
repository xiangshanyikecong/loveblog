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

"""Login-device management: list and revoke devices recorded at login."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.login_device import LoginDevice
from app.models.user import User
from app.schemas.devices import (
    DeviceRevokeResponse,
    DevicesRevokeAllResponse,
    LoginDeviceResponse,
)
from app.services.audit import write_audit_log
from app.services.security import increment_session_version


router = APIRouter(prefix="/auth/devices", tags=["auth"])


@router.get("", response_model=list[LoginDeviceResponse])
def list_login_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LoginDeviceResponse]:
    """Devices recorded for the current user, most recent login first."""
    devices = (
        db.query(LoginDevice)
        .filter(LoginDevice.user_id == current_user.id)
        .order_by(LoginDevice.last_login_at.desc())
        .all()
    )
    return [LoginDeviceResponse.model_validate(device) for device in devices]


@router.delete("/{did}", response_model=DeviceRevokeResponse)
def revoke_login_device(
    did: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeviceRevokeResponse:
    """Delete one of the user's device records and force re-login everywhere.

    JWTs carry no per-device revocation, so bumping the session version is the
    only way to guarantee the removed device cannot reuse its token.
    """
    device = (
        db.query(LoginDevice)
        .filter(LoginDevice.did == did, LoginDevice.user_id == current_user.id)
        .first()
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    # Capture for the audit log before the row (and its attributes) is gone.
    device_did = device.did
    device_name = device.device_name

    db.delete(device)
    db.commit()

    new_session_version = increment_session_version(db, current_user)

    write_audit_log(
        db,
        action="device.revoke",
        actor=current_user,
        resource_type="login_device",
        resource_id=device_did,
        resource_name=device_name,
        detail={"new_session_version": new_session_version},
    )

    return DeviceRevokeResponse(revoked=True, new_session_version=new_session_version)


@router.delete("", response_model=DevicesRevokeAllResponse)
def revoke_all_login_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DevicesRevokeAllResponse:
    """Delete all device records for the user and force re-login everywhere."""
    revoked = (
        db.query(LoginDevice)
        .filter(LoginDevice.user_id == current_user.id)
        .delete(synchronize_session=False)
    )
    db.commit()

    new_session_version = increment_session_version(db, current_user)

    write_audit_log(
        db,
        action="device.revoke_all",
        actor=current_user,
        resource_type="user",
        resource_id=current_user.uid,
        resource_name=current_user.username,
        detail={"revoked": revoked, "new_session_version": new_session_version},
    )

    return DevicesRevokeAllResponse(revoked=revoked)
