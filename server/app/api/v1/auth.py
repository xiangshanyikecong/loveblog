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

from hmac import compare_digest
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status, Response, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import (
    access_token_expires_in_seconds,
    create_access_token,
    dummy_verify,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole
from app.api.deps import ensure_partner, get_current_user
from app.schemas.auth import (
    BootstrapRegisterRequest,
    BootstrapStatusResponse,
    LoginRequest,
    PartnerListResponse,
    PartnerRegisterRequest,
    PasswordRecoveryRequest,
    RegisterRequest,
    TokenResponse,
    UpdatePartnerRequest,
    UpdateVisitorRequest,
    UserProfile,
    VisitorListResponse,
    VisitorProfile,
)
from app.services.audit import write_audit_log
from app.services.security import (
    increment_session_version,
    is_account_frozen,
    record_failed_login,
    record_successful_login,
    reset_login_attempts,
    get_freeze_remaining_minutes,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_is_secure(request: Request) -> bool:
    """Decide the ``Secure`` flag for the auth cookie.

    Tied to the *actual* transport (via the edge proxy's ``X-Forwarded-Proto``
    header), not the ``APP_ENV`` label. Otherwise a production deployment served
    over plain HTTP would set ``Secure`` cookies that browsers silently drop,
    breaking login (the user appears logged out immediately). An explicit
    ``COOKIE_SECURE`` setting overrides the auto-detection.
    """
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    forwarded = request.headers.get("x-forwarded-proto", "")
    proto = forwarded.split(",")[0].strip().lower()
    if proto:
        return proto == "https"
    return request.url.scheme == "https"


def _get_or_create_setting(db: Session) -> SiteSetting:
    setting = db.query(SiteSetting).filter(SiteSetting.id == 1).first()
    if setting is not None:
        return setting

    setting = SiteSetting(id=1)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def _active_partner_query(db: Session):
    return db.query(User).filter(
        User.role.in_([UserRole.partner_a, UserRole.partner_b]),
        User.deleted_at.is_(None),
    )


def _visitor_query(db: Session):
    return db.query(User).filter(User.role == UserRole.visitor, User.deleted_at.is_(None))


def _is_banned_visitor(user: User) -> bool:
    return user.role == UserRole.visitor and (user.is_banned or user.permission_status == "banned")


def _apply_visitor_moderation(user: User, payload: UpdateVisitorRequest) -> list[str]:
    changed_fields: list[str] = []
    target_permission_status = user.permission_status
    target_is_banned = user.is_banned

    if payload.is_banned is not None:
        target_is_banned = payload.is_banned
        if payload.is_banned:
            target_permission_status = "banned"
        elif payload.permission_status is None and target_permission_status == "banned":
            target_permission_status = "active"

    if payload.permission_status is not None:
        target_permission_status = payload.permission_status
        target_is_banned = payload.permission_status == "banned"

    if target_is_banned != user.is_banned:
        user.is_banned = target_is_banned
        changed_fields.append("is_banned")

    if target_permission_status != user.permission_status:
        user.permission_status = target_permission_status
        changed_fields.append("permission_status")

    return changed_fields


def _create_user(db: Session, payload: RegisterRequest) -> User:
    user = User(
        username=payload.username,
        nickname=payload.nickname,
        role=payload.role,
        password_hash=get_password_hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/bootstrap-status", response_model=BootstrapStatusResponse)
def get_bootstrap_status(
    db: Session = Depends(get_db),
) -> BootstrapStatusResponse:
    """Public endpoint – expose only whether initial bootstrap is already completed."""
    partner_exists = _active_partner_query(db).first()
    return BootstrapStatusResponse(
        bootstrapped=partner_exists is not None,
    )


@router.post("/bootstrap", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
def bootstrap_register(
    payload: BootstrapRegisterRequest,
    db: Session = Depends(get_db),
    bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
) -> User:
    configured_token = settings.bootstrap_setup_token.strip()
    if not configured_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bootstrap is disabled")
    if not bootstrap_token or not compare_digest(bootstrap_token, configured_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bootstrap token")

    partner_exists = _active_partner_query(db).first()
    if partner_exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bootstrap is already completed")

    existed = db.query(User).filter(User.username == payload.username).first()
    if existed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = _create_user(db, payload)

    # Also persist site name and love start date in one shot
    setting = _get_or_create_setting(db)
    setting.site_name = payload.site_name
    if payload.love_start_date is not None:
        setting.love_start_date = payload.love_start_date
    db.commit()

    write_audit_log(
        db,
        action="auth.bootstrap_create",
        actor=user,
        resource_type="user",
        resource_id=user.uid,
        resource_name=user.username,
        detail={"role": user.role.value, "site_name": setting.site_name},
    )
    return user


@router.post("/password-recovery")
@limiter.limit("3/minute")
def password_recovery(
    request: Request,
    payload: PasswordRecoveryRequest,
    db: Session = Depends(get_db),
    bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
) -> dict:
    """Unauthenticated password reset, authorized by the instance bootstrap token.

    Self-hosted recovery path: the credential is the server-side
    ``BOOTSTRAP_SETUP_TOKEN`` from ``.env.production`` — only someone with
    server access (the instance owner) can reset a forgotten password without
    logging in. The reset revokes all existing sessions of the account and
    clears any login freeze from earlier failed attempts.
    """
    configured_token = settings.bootstrap_setup_token.strip()
    if not configured_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password recovery is disabled")
    if not bootstrap_token or not compare_digest(bootstrap_token, configured_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery token")

    user = db.query(User).filter(User.username == payload.username, User.deleted_at.is_(None)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == UserRole.visitor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Visitor passwords must be managed by a signed-in partner",
        )

    user.password_hash = get_password_hash(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    increment_session_version(db, user)
    reset_login_attempts(db, user)

    write_audit_log(
        db,
        action="account.password_recovery",
        actor=user,
        resource_type="user",
        resource_id=user.uid,
        resource_name=user.username,
        detail={"via": "bootstrap_token", "role": user.role.value},
    )
    return {"ok": True}


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
def register(
    payload: PartnerRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    # Provisioning the couple's accounts is a closed, partner-only operation:
    # a signed-in partner fills the single empty partner slot (there is exactly
    # one PartnerA and one PartnerB). It is deliberately NOT gated by
    # ``allow_registration`` — that toggle is meant for open/visitor sign-up,
    # which this endpoint does not perform (the visitor role is rejected just
    # below). Gating partner creation on a flag that defaults to False and is
    # never enabled by bootstrap stranded fresh production deployments with a
    # single partner account and no supported way to create the second.
    ensure_partner(current_user)

    # Visitor account onboarding is reserved for Hub SSO (not local register).
    if payload.role == UserRole.visitor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Visitor registration must be completed through Hub SSO",
        )

    existed_role_user = db.query(User).filter(User.role == payload.role, User.deleted_at.is_(None)).first()
    if existed_role_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{payload.role.value} already exists")

    existed = db.query(User).filter(User.username == payload.username).first()
    if existed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    user = _create_user(db, payload)
    write_audit_log(
        db,
        action="account.create_partner",
        actor=current_user,
        resource_type="user",
        resource_id=user.uid,
        resource_name=user.username,
        detail={"role": user.role.value},
    )
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.username == payload.username, User.deleted_at.is_(None)).first()

    # Unknown username: spend equivalent bcrypt time before returning the SAME
    # generic error a wrong password yields, so neither the response body nor
    # the response timing reveals whether the account exists.
    if user is None:
        dummy_verify()
        write_audit_log(
            db,
            action="auth.login",
            result="failure",
            actor_username=payload.username,
            detail={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # Freeze check stays BEFORE password verification so a locked account can't
    # be brute-forced (each attempt would otherwise pay bcrypt cost). It's only
    # reachable after the account already accrued failures, so it is not a
    # useful existence oracle for an attacker who hasn't already triggered it.
    if is_account_frozen(user):
        freeze_minutes = get_freeze_remaining_minutes(user)
        write_audit_log(
            db,
            action="auth.login",
            result="failure",
            actor_username=payload.username,
            detail={"reason": "account_frozen", "freeze_remaining_minutes": freeze_minutes},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is frozen. Try again in {freeze_minutes} minutes."
        )

    if not verify_password(payload.password, user.password_hash):
        failed_count, freeze_minutes = record_failed_login(db, user)
        write_audit_log(
            db,
            action="auth.login",
            result="failure",
            actor_username=payload.username,
            detail={"reason": "invalid_credentials", "failed_attempts": failed_count},
        )
        if freeze_minutes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Too many failed attempts. Account frozen for {freeze_minutes} minutes."
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    # Credentials are correct. Only now reveal account-state problems (ban),
    # which requires proving knowledge of the password and so cannot be used to
    # enumerate accounts.
    if _is_banned_visitor(user):
        write_audit_log(
            db,
            action="auth.login",
            result="failure",
            actor_username=payload.username,
            detail={"reason": "account_banned"},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")

    # 记录成功的登录
    record_successful_login(db, user)

    expires_in = access_token_expires_in_seconds()
    token = create_access_token(
        subject=user.uid,
        extra_claims={
            "role": user.role.value,
            "nickname": user.nickname,
        },
        session_version=user.session_version,
    )
    write_audit_log(db, action="auth.login", actor=user, detail={"role": user.role.value})

    is_secure = _cookie_is_secure(request)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=expires_in,
        secure=is_secure,
        samesite="strict",  # Security: Changed from "lax" to "strict" for CSRF protection
    )
    return TokenResponse(access_token="http-only", expires_in=expires_in, role=user.role.value)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_version = increment_session_version(db, current_user)
    write_audit_log(
        db,
        action="auth.logout",
        actor=current_user,
        detail={"new_session_version": new_version},
    )
    # Match the attributes used when the cookie was set, otherwise the browser
    # won't clear it.
    response.delete_cookie("access_token", secure=_cookie_is_secure(request), samesite="strict")
    return {"ok": True}


@router.get("/me", response_model=UserProfile)
def get_current_user_profile(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("/partners", response_model=PartnerListResponse)
def get_partners(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartnerListResponse:
    ensure_partner(current_user)
    partners = _active_partner_query(db).all()
    return PartnerListResponse(items=partners)


@router.put("/partners/{uid}", response_model=UserProfile)
def update_partner(
    uid: str,
    payload: UpdatePartnerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    ensure_partner(current_user)
    target_user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    changed_fields: list[str] = []
    if payload.username is not None and payload.username != target_user.username:
        existed = (
            db.query(User)
            .filter(
                User.username == payload.username,
                User.uid != target_user.uid,
            )
            .first()
        )
        if existed:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
        target_user.username = payload.username
        changed_fields.append("username")

    if payload.nickname is not None:
        if payload.nickname != target_user.nickname:
            changed_fields.append("nickname")
        target_user.nickname = payload.nickname

    if payload.password:
        target_user.password_hash = get_password_hash(payload.password)
        target_user.password_changed_at = datetime.now(timezone.utc)
        target_user.session_version += 1
        changed_fields.append("password")

    db.commit()
    db.refresh(target_user)
    if changed_fields:
        write_audit_log(
            db,
            action="account.update_partner",
            actor=current_user,
            resource_type="user",
            resource_id=target_user.uid,
            resource_name=target_user.username,
            detail={
                "target_role": target_user.role.value,
                "changed_fields": changed_fields,
            },
        )
    return target_user


@router.get("/visitors", response_model=VisitorListResponse)
def get_visitors(
    page: int = 1,
    page_size: int = 20,
    sso_source: str | None = None,
    is_banned: bool | None = None,
    permission_status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VisitorListResponse:
    """获取访客列表，支持分页和筛选"""
    ensure_partner(current_user)

    query = _visitor_query(db)

    if sso_source:
        query = query.filter(User.sso_source == sso_source)
    if is_banned is not None:
        query = query.filter(User.is_banned == is_banned)
    if permission_status:
        query = query.filter(User.permission_status == permission_status)

    total = query.count()
    visitors = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return VisitorListResponse(
        items=visitors,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/visitors/{uid}", response_model=VisitorProfile)
def get_visitor(
    uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """获取单个访客详情"""
    ensure_partner(current_user)
    visitor = _visitor_query(db).filter(User.uid == uid).first()
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")
    return visitor


@router.put("/visitors/{uid}", response_model=VisitorProfile)
def update_visitor(
    uid: str,
    payload: UpdateVisitorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """更新访客信息"""
    ensure_partner(current_user)
    visitor = _visitor_query(db).filter(User.uid == uid).first()
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    changed_fields: list[str] = []

    if payload.nickname is not None and payload.nickname != visitor.nickname:
        visitor.nickname = payload.nickname
        changed_fields.append("nickname")

    if payload.remark is not None:
        if payload.remark != visitor.remark:
            changed_fields.append("remark")
        visitor.remark = payload.remark

    changed_fields.extend(_apply_visitor_moderation(visitor, payload))
    changed_fields = list(dict.fromkeys(changed_fields))

    db.commit()
    db.refresh(visitor)

    if changed_fields:
        write_audit_log(
            db,
            action="account.update_visitor",
            actor=current_user,
            resource_type="user",
            resource_id=visitor.uid,
            resource_name=visitor.username,
            detail={"changed_fields": changed_fields},
        )

    return visitor


@router.post("/visitors/{uid}/toggle-ban", response_model=VisitorProfile)
def toggle_visitor_ban(
    uid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """快速切换访客封禁状态"""
    ensure_partner(current_user)
    visitor = _visitor_query(db).filter(User.uid == uid).first()
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor not found")

    visitor.is_banned = not visitor.is_banned
    visitor.permission_status = "banned" if visitor.is_banned else "active"
    db.commit()
    db.refresh(visitor)

    write_audit_log(
        db,
        action="account.toggle_visitor_ban",
        actor=current_user,
        resource_type="user",
        resource_id=visitor.uid,
        resource_name=visitor.username,
        detail={"is_banned": visitor.is_banned},
    )

    return visitor
