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

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.push_endpoint import PushEndpointError, validate_web_push_endpoint
from app.db.session import get_db
from app.models.fcm_device_token import FcmDeviceToken
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.schemas.push import (
    FcmTokenDeleteRequest,
    FcmTokenListResponse,
    FcmTokenResponse,
    FcmTokenUpsertRequest,
    PushPublicKeyResponse,
    PushStatusResponse,
    PushSubscriptionDeleteRequest,
    PushSubscriptionListResponse,
    PushSubscriptionResponse,
    PushSubscriptionUpsertRequest,
    WebPushStatusInfo,
    FcmStatusInfo,
)
from app.services.notification_delivery import (
    fcm_dependency_available,
    fcm_runtime_ready,
    web_push_runtime_ready,
)

router = APIRouter(prefix="/push", tags=["push"])


def _enforce_device_cap(db: Session, model, user_id: int) -> None:
    """Refuse registrations beyond ``push_max_devices_per_user``.

    Delivery fans out to every stored destination, so an unbounded table is
    both an amplification vector and an SSRF payload multiplier.
    """
    cap = max(1, int(settings.push_max_devices_per_user))
    current = db.query(model).filter(model.user_id == user_id).count()
    if current >= cap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device registration limit reached ({cap})",
        )


def _commit_or_conflict(db: Session, detail: str) -> None:
    """Commit, mapping a concurrent duplicate registration to HTTP 409.

    The unique constraint on ``endpoint`` / ``token`` is the only race-free
    arbiter; the pre-checks above narrow the window but cannot close it.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


@router.get("/public-key", response_model=PushPublicKeyResponse)
def get_push_public_key() -> PushPublicKeyResponse:
    enabled = settings.web_push_enabled and settings.web_push_configured and web_push_runtime_ready()
    return PushPublicKeyResponse(
        enabled=enabled,
        public_key=settings.web_push_vapid_public_key if enabled else None,
    )


@router.get("/status", response_model=PushStatusResponse)
def get_push_status() -> PushStatusResponse:
    """推送配置状态（仅布尔值）：供 Android 应用内 FCM 配置向导判断缺哪一端。"""
    fcm_ready = False
    if settings.fcm_push_enabled and settings.fcm_configured:
        # 仅在开关与凭据齐备时探测运行时（避免未配置时反复尝试初始化刷日志）。
        fcm_ready = fcm_runtime_ready()
    return PushStatusResponse(
        fcm=FcmStatusInfo(
            enabled=settings.fcm_push_enabled,
            configured=settings.fcm_configured,
            dependency_available=fcm_dependency_available(),
            runtime_ready=fcm_ready,
        ),
        web_push=WebPushStatusInfo(
            enabled=settings.web_push_enabled
            and settings.web_push_configured
            and web_push_runtime_ready(),
            vapid_configured=settings.web_push_configured,
        ),
    )


@router.get("/subscriptions", response_model=PushSubscriptionListResponse)
def list_push_subscriptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PushSubscriptionListResponse:
    items = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == current_user.id)
        .order_by(PushSubscription.updated_at.desc(), PushSubscription.id.desc())
        .all()
    )
    return PushSubscriptionListResponse(items=items)


@router.put(
    "/subscriptions",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_200_OK,
)
def upsert_push_subscription(
    payload: PushSubscriptionUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PushSubscriptionResponse:
    # The server POSTs to this URL on every delivery, so the destination policy
    # is enforced at registration: https, a DNS name (never an IP literal), no
    # local/single-label host, and a recognized push-provider suffix.
    try:
        endpoint = validate_web_push_endpoint(payload.endpoint)
    except PushEndpointError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    now = datetime.now(timezone.utc)
    item = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if item is None:
        _enforce_device_cap(db, PushSubscription, current_user.id)
        item = PushSubscription(
            user_id=current_user.id,
            endpoint=endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            expiration_time=payload.expiration_time,
            user_agent=payload.user_agent,
            is_active=True,
            fail_count=0,
            last_seen_at=now,
        )
        db.add(item)
    else:
        # A subscription belongs to the account that registered it. Without this
        # check anyone holding another user's endpoint (a leaked backup, a shared
        # browser profile) could rebind it to themselves and have the server
        # deliver attacker-controlled notification content to the victim's
        # device — a ready-made phishing channel.
        if item.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Push endpoint is already registered to another account",
            )
        item.p256dh = payload.keys.p256dh
        item.auth = payload.keys.auth
        item.expiration_time = payload.expiration_time
        item.user_agent = payload.user_agent
        item.is_active = True
        item.fail_count = 0
        item.last_seen_at = now

    _commit_or_conflict(db, "Push endpoint is already registered")
    db.refresh(item)
    return item


@router.delete(
    "/subscriptions",
    response_model=dict,
)
def delete_push_subscription(
    payload: PushSubscriptionDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    item = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == current_user.id,
            PushSubscription.endpoint == payload.endpoint,
        )
        .first()
    )
    if item is None:
        return {"removed": 0}

    db.delete(item)
    db.commit()
    return {"removed": 1}


@router.get("/fcm-tokens", response_model=FcmTokenListResponse)
def list_fcm_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FcmTokenListResponse:
    items = (
        db.query(FcmDeviceToken)
        .filter(FcmDeviceToken.user_id == current_user.id)
        .order_by(FcmDeviceToken.updated_at.desc(), FcmDeviceToken.id.desc())
        .all()
    )
    return FcmTokenListResponse(items=items)


@router.put(
    "/fcm-tokens",
    response_model=FcmTokenResponse,
    status_code=status.HTTP_200_OK,
)
def upsert_fcm_token(
    payload: FcmTokenUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FcmTokenResponse:
    now = datetime.now(timezone.utc)
    item = db.query(FcmDeviceToken).filter(FcmDeviceToken.token == payload.token).first()
    if item is None:
        _enforce_device_cap(db, FcmDeviceToken, current_user.id)
        item = FcmDeviceToken(
            user_id=current_user.id,
            token=payload.token,
            platform=payload.platform,
            device_name=payload.device_name,
            app_version=payload.app_version,
            is_active=True,
            fail_count=0,
            last_seen_at=now,
        )
        db.add(item)
    else:
        # Device tokens are per-installation secrets: rebinding someone else's
        # token would route their pushes to an account we control. FCM token
        # rotation on the *same* device is handled by the client deleting the
        # old token first (see PushRepository.unregisterFcmToken).
        if item.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="FCM token is already registered to another account",
            )
        item.platform = payload.platform
        item.device_name = payload.device_name
        item.app_version = payload.app_version
        item.is_active = True
        item.fail_count = 0
        item.last_seen_at = now

    _commit_or_conflict(db, "FCM token is already registered")
    db.refresh(item)
    return item


@router.delete("/fcm-tokens", response_model=dict)
def delete_fcm_token(
    payload: FcmTokenDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    item = (
        db.query(FcmDeviceToken)
        .filter(
            FcmDeviceToken.user_id == current_user.id,
            FcmDeviceToken.token == payload.token,
        )
        .first()
    )
    if item is None:
        return {"removed": 0}

    db.delete(item)
    db.commit()
    return {"removed": 1}
