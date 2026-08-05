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

"""Cottage love coupons (甜蜜兑换券) routes.

A coupon is issued by one partner for the other to redeem later — 「一次免做
家务券」「一个抱抱券」 and so on. Either partner may browse the shared coupon
book; only the *counterpart* (not the author) may redeem an active coupon.

Endpoints under ``/v1/cottage/coupons``:

- ``POST   /v1/cottage/coupons``              — issue a coupon for your partner
- ``GET    /v1/cottage/coupons``              — list (?box=all/received/sent, ?status)
- ``GET    /v1/cottage/coupons/{cpid}``       — single coupon
- ``PATCH  /v1/cottage/coupons/{cpid}``       — edit (author only, before redeem)
- ``POST   /v1/cottage/coupons/{cpid}/redeem``— redeem (counterpart only)
- ``DELETE /v1/cottage/coupons/{cpid}``       — soft delete
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.coupon import Coupon, CouponStatus
from app.models.user import User
from app.schemas.coupon import (
    CouponCreateRequest,
    CouponListResponse,
    CouponResponse,
    CouponUpdateRequest,
)
from app.services.notifications import create_notification, notify_partners


router = APIRouter(prefix="/cottage/coupons", tags=["cottage-coupons"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_response(coupon: Coupon, viewer: User) -> CouponResponse:
    return CouponResponse(
        cpid=coupon.cpid,
        title=coupon.title,
        description=coupon.description,
        icon=coupon.icon,
        status=coupon.status,
        author_uid=coupon.author.uid if coupon.author else "",
        author_nickname=coupon.author.nickname if coupon.author else "",
        is_mine=coupon.author_id == viewer.id,
        redeemed_at=coupon.redeemed_at,
        redeemed_by_uid=coupon.redeemed_by.uid if coupon.redeemed_by else None,
        redeemed_by_nickname=coupon.redeemed_by.nickname if coupon.redeemed_by else None,
        created_at=coupon.created_at,
    )


def _load_coupon(db: Session, cpid: str) -> Coupon:
    coupon = (
        db.query(Coupon)
        .options(joinedload(Coupon.author), joinedload(Coupon.redeemed_by))
        .filter(Coupon.cpid == cpid, Coupon.deleted_at.is_(None))
        .first()
    )
    if coupon is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coupon not found")
    return coupon


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(
    payload: CouponCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CouponResponse:
    ensure_partner(current_user)
    coupon = Coupon(
        author_id=current_user.id,
        title=payload.title,
        description=payload.description,
        icon=payload.icon,
        status=CouponStatus.active.value,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)

    notify_partners(
        db,
        type="coupon.created",
        title=f"{current_user.nickname} 送了你一张券",
        body=coupon.title[:160],
        link="/cottage/coupons",
        source_type="coupon",
        source_id=coupon.cpid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    return _to_response(_load_coupon(db, coupon.cpid), current_user)


@router.get("", response_model=CouponListResponse)
def list_coupons(
    box: Annotated[str, Query()] = "all",
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CouponListResponse:
    ensure_partner(current_user)

    base = db.query(Coupon).filter(Coupon.deleted_at.is_(None))
    if box == "received":
        base = base.filter(Coupon.author_id != current_user.id)
    elif box == "sent":
        base = base.filter(Coupon.author_id == current_user.id)

    total = base.count()
    active_count = base.filter(Coupon.status == CouponStatus.active.value).count()
    redeemed_count = total - active_count

    query = base.options(joinedload(Coupon.author), joinedload(Coupon.redeemed_by))
    if status_filter in (CouponStatus.active.value, CouponStatus.redeemed.value):
        query = query.filter(Coupon.status == status_filter)

    # Active first, then newest.
    active_first = case((Coupon.status == CouponStatus.redeemed.value, 1), else_=0)
    items = query.order_by(active_first.asc(), Coupon.created_at.desc()).all()

    return CouponListResponse(
        items=[_to_response(item, current_user) for item in items],
        total=total,
        active=active_count,
        redeemed=redeemed_count,
    )


@router.get("/{cpid}", response_model=CouponResponse)
def get_coupon(
    cpid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CouponResponse:
    ensure_partner(current_user)
    return _to_response(_load_coupon(db, cpid), current_user)


@router.patch("/{cpid}", response_model=CouponResponse)
def update_coupon(
    cpid: str,
    payload: CouponUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CouponResponse:
    ensure_partner(current_user)
    coupon = _load_coupon(db, cpid)
    if coupon.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能编辑自己送出的券")
    if coupon.status != CouponStatus.active.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已兑换的券不能编辑")

    data = payload.model_dump(exclude_unset=True)
    for field in ("title", "description", "icon"):
        if field in data:
            setattr(coupon, field, data[field])
    coupon.version += 1
    db.commit()
    return _to_response(_load_coupon(db, cpid), current_user)


@router.post("/{cpid}/redeem", response_model=CouponResponse)
def redeem_coupon(
    cpid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CouponResponse:
    ensure_partner(current_user)
    coupon = _load_coupon(db, cpid)
    if coupon.author_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能兑换自己送出的券")
    if coupon.status == CouponStatus.redeemed.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="这张券已经兑换过了")

    coupon.status = CouponStatus.redeemed.value
    coupon.redeemed_at = datetime.now(timezone.utc)
    coupon.redeemed_by_id = current_user.id
    db.commit()

    if coupon.author is not None:
        create_notification(
            db,
            recipient=coupon.author,
            type="coupon.redeemed",
            title=f"{current_user.nickname} 兑换了你的券",
            body=coupon.title[:160],
            link="/cottage/coupons",
            source_type="coupon",
            source_id=coupon.cpid,
        )
        db.commit()
    return _to_response(_load_coupon(db, cpid), current_user)


@router.delete("/{cpid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_coupon(
    cpid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)
    coupon = _load_coupon(db, cpid)
    coupon.deleted_at = datetime.now(timezone.utc)
    db.commit()
