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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models.user import User
from app.api.deps import ensure_partner, get_current_user
from app.schemas.security import (
    ChangePasswordRequest,
    ResetPasswordRequest,
    RevokeSessionsRequest,
    SecurityListResponse,
    SecurityProfile,
    UnlockAccountRequest,
)
from app.services.security import (
    increment_session_version,
    unlock_account,
)
from app.services.audit import write_audit_log

router = APIRouter(prefix="/security", tags=["security"])


def _get_client_ip(request: Request) -> str | None:
    """获取客户端 IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/users", response_model=SecurityListResponse)
def get_security_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SecurityListResponse:
    """获取所有用户的安全信息列表"""
    ensure_partner(current_user)

    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    items = [
        SecurityProfile(
            uid=u.uid,
            username=u.username,
            nickname=u.nickname,
            role=u.role.value,
            login_failed_count=u.login_failed_count,
            login_freeze_until=u.login_freeze_until,
            password_changed_at=u.password_changed_at,
            session_version=u.session_version,
            last_login_ip=u.last_login_ip,
            last_login_at=u.last_login_at,
        )
        for u in users
    ]
    return SecurityListResponse(items=items, total=len(items))


@router.post("/users/{uid}/change-password", response_model=SecurityProfile)
def change_password(
    uid: str,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """用户修改自己的密码"""
    if current_user.uid != uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot change other user's password")

    target_user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # 验证旧密码
    if not verify_password(payload.old_password, target_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")

    # 更新密码
    from datetime import datetime, timezone
    target_user.password_hash = get_password_hash(payload.new_password)
    target_user.password_changed_at = datetime.now(timezone.utc)
    target_user.session_version += 1  # 使所有现有会话失效
    db.commit()
    db.refresh(target_user)

    write_audit_log(
        db,
        action="security.change_password",
        actor=current_user,
        resource_type="user",
        resource_id=target_user.uid,
        resource_name=target_user.username,
        detail={"changed_by": "self"},
    )

    return target_user


@router.post("/users/{uid}/reset-password")
def reset_password(
    uid: str,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """管理员重置用户密码"""
    ensure_partner(current_user)

    target_user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    from datetime import datetime, timezone
    target_user.password_hash = get_password_hash(payload.new_password)
    target_user.password_changed_at = datetime.now(timezone.utc)
    target_user.session_version += 1  # 使所有现有会话失效
    db.commit()

    write_audit_log(
        db,
        action="security.reset_password",
        actor=current_user,
        resource_type="user",
        resource_id=target_user.uid,
        resource_name=target_user.username,
        detail={"reset_by": "admin"},
    )

    return {"message": "Password has been reset", "uid": uid}


@router.post("/users/{uid}/revoke-sessions")
def revoke_all_sessions(
    uid: str,
    payload: RevokeSessionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """撤销用户所有会话（强制退出所有设备）"""
    ensure_partner(current_user)

    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must confirm revocation")

    target_user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_version = increment_session_version(db, target_user)

    write_audit_log(
        db,
        action="security.revoke_sessions",
        actor=current_user,
        resource_type="user",
        resource_id=target_user.uid,
        resource_name=target_user.username,
        detail={"new_session_version": new_version},
    )

    return {"message": "All sessions revoked", "uid": uid, "new_session_version": new_version}


@router.post("/users/{uid}/unlock")
def unlock_user_account(
    uid: str,
    payload: UnlockAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """解锁被冻结的用户账户"""
    ensure_partner(current_user)

    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must confirm unlock")

    target_user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    unlock_account(db, target_user)

    write_audit_log(
        db,
        action="security.unlock_account",
        actor=current_user,
        resource_type="user",
        resource_id=target_user.uid,
        resource_name=target_user.username,
    )

    return {"message": "Account unlocked", "uid": uid}


@router.post("/users/{uid}/revoke-own-sessions")
def revoke_own_sessions(
    uid: str,
    payload: RevokeSessionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """用户撤销自己的其他会话"""
    if current_user.uid != uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot revoke other user's sessions")

    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must confirm revocation")

    new_version = increment_session_version(db, current_user)

    write_audit_log(
        db,
        action="security.revoke_own_sessions",
        actor=current_user,
        resource_type="user",
        resource_id=current_user.uid,
        resource_name=current_user.username,
        detail={"new_session_version": new_version},
    )

    return {"message": "Other sessions revoked", "new_session_version": new_version}
