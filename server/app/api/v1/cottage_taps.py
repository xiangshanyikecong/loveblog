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

"""Cottage tap (轻触回应 / 敲一敲) endpoints.

A tap is a one-tap "thinking of you" signal aimed at the partner's devices
(Phone + Apple Watch). Delivery rides the existing notification pipeline
(in-app + web push + FCM); this module only adds the append-only signal log
and a catch-up feed for clients that were offline.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.cottage_tap import CottageTap
from app.models.user import User, UserRole
from app.schemas.cottage_tap import TapCreateRequest, TapListResponse, TapResponse
from app.services.notifications import create_notification

router = APIRouter(prefix="/cottage/taps", tags=["cottage-taps"])

# Anti-spam: max taps one partner may send per hour; plus how many rows are
# kept for the couple (pruned opportunistically on send).
MAX_TAPS_PER_HOUR = 60
TAP_LOG_KEEP = 500

TAP_KIND_TITLES = {
    "tap": "敲了敲你",
    "heartbeat": "给你发来了心跳",
}


def _partner(db: Session, current_user: User) -> User:
    partner = (
        db.query(User)
        .filter(
            User.role.in_([UserRole.partner_a, UserRole.partner_b]),
            User.id != current_user.id,
            User.deleted_at.is_(None),
        )
        .first()
    )
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Partner account not found"
        )
    return partner


def _to_response(tap: CottageTap) -> TapResponse:
    return TapResponse(
        tid=tap.tid,
        kind=tap.kind,
        from_uid=tap.sender.uid if tap.sender else "",
        from_nickname=tap.sender.nickname if tap.sender else "",
        to_uid=tap.recipient.uid if tap.recipient else "",
        to_nickname=tap.recipient.nickname if tap.recipient else "",
        created_at=tap.created_at,
    )


@router.post("", response_model=TapResponse, status_code=status.HTTP_201_CREATED)
def send_tap(
    payload: TapCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TapResponse:
    ensure_partner(current_user)
    partner = _partner(db, current_user)

    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = (
        db.query(func.count(CottageTap.id))
        .filter(CottageTap.sender_id == current_user.id, CottageTap.created_at >= hour_ago)
        .scalar()
        or 0
    )
    if recent >= MAX_TAPS_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many taps, please slow down",
        )

    tap = CottageTap(
        sender_id=current_user.id, recipient_id=partner.id, kind=payload.kind
    )
    db.add(tap)
    db.flush()

    create_notification(
        db,
        recipient=partner,
        type="cottage.tap",
        title=f"{current_user.nickname} {TAP_KIND_TITLES.get(payload.kind, TAP_KIND_TITLES['tap'])}",
        body=payload.kind,
        link="/cottage/taps",
        source_type="cottage_tap",
        source_id=tap.tid,
    )

    # Opportunistic prune: keep the log bounded.
    total = db.query(func.count(CottageTap.id)).scalar() or 0
    if total > TAP_LOG_KEEP:
        stale = db.query(CottageTap.id).order_by(CottageTap.created_at.desc())
        cutoff_ids = [row[0] for row in stale.offset(TAP_LOG_KEEP).all()]
        if cutoff_ids:
            db.query(CottageTap).filter(CottageTap.id.in_(cutoff_ids)).delete(
                synchronize_session=False
            )

    db.commit()
    db.refresh(tap)
    return _to_response(tap)


@router.get("/recent", response_model=TapListResponse)
def recent_taps(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TapListResponse:
    ensure_partner(current_user)
    partner = _partner(db, current_user)

    taps = (
        db.query(CottageTap)
        .options(joinedload(CottageTap.sender), joinedload(CottageTap.recipient))
        .filter(
            or_(
                CottageTap.sender_id.in_([current_user.id, partner.id]),
                CottageTap.recipient_id.in_([current_user.id, partner.id]),
            )
        )
        .order_by(CottageTap.created_at.desc())
        .limit(limit)
        .all()
    )
    total_kept = db.query(func.count(CottageTap.id)).scalar() or 0
    return TapListResponse(
        items=[_to_response(tap) for tap in taps], total_kept=int(total_kept)
    )
