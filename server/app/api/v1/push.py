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

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
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
    PushSubscriptionDeleteRequest,
    PushSubscriptionListResponse,
    PushSubscriptionResponse,
    PushSubscriptionUpsertRequest,
)
from app.services.notification_delivery import web_push_runtime_ready

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/public-key", response_model=PushPublicKeyResponse)
def get_push_public_key() -> PushPublicKeyResponse:
    enabled = settings.web_push_enabled and settings.web_push_configured and web_push_runtime_ready()
    return PushPublicKeyResponse(
        enabled=enabled,
        public_key=settings.web_push_vapid_public_key if enabled else None,
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
    now = datetime.now(timezone.utc)
    item = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    if item is None:
        item = PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
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
        item.user_id = current_user.id
        item.p256dh = payload.keys.p256dh
        item.auth = payload.keys.auth
        item.expiration_time = payload.expiration_time
        item.user_agent = payload.user_agent
        item.is_active = True
        item.fail_count = 0
        item.last_seen_at = now

    db.commit()
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
        item.user_id = current_user.id
        item.platform = payload.platform
        item.device_name = payload.device_name
        item.app_version = payload.app_version
        item.is_active = True
        item.fail_count = 0
        item.last_seen_at = now

    db.commit()
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
