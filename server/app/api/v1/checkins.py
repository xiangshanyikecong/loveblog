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

"""Cottage check-in (报备) routes.

This module implements three endpoints under ``/v1/checkins``:

- ``POST /v1/checkins`` — create a new check-in (text / photos / location).
- ``GET /v1/checkins/latest`` — counterpart's most-recent check-in.
- ``GET /v1/checkins`` — counterpart's history with simple pagination.

Privacy invariants enforced here (Requirement 1.2 / 1.3 / 1.4):

- The client IP is read from ``X-Forwarded-For`` or ``request.client.host``
  *only as a function-local variable* in :func:`_resolve_location`. It is
  never written to the model, never logged, never returned in any response.
- ``latitude`` / ``longitude`` arrive in the request body, are passed to
  the geocoding provider, and then go out of scope. They never reach a
  persistent column.

"自己看不到自己" (Requirement 3.4 / 5.11 / 7.4) is enforced at every read
endpoint with the SQL filter ``CheckIn.author_id != current_user.id``.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.core.net import get_real_client_ip
from app.db.session import get_db
from app.models.checkin import CheckIn, LocationStatus
from app.models.user import User, UserRole
from app.schemas.checkin import (
    CheckInCreateRequest,
    CheckInLatestResponse,
    CheckInListResponse,
    CheckInResponse,
)
from app.services.geocoding import GeocodingProvider, get_provider
from app.services.notifications import create_notification
from app.services.upload_references import sync_checkin_upload_references


router = APIRouter(prefix="/checkins", tags=["checkins"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_client_ip(request: Request) -> str:
    """Extract the trusted client IP from request headers / transport.

    Delegates to :func:`app.core.net.get_real_client_ip`, which trusts only
    proxy-set headers (``X-Real-IP`` / the last ``X-Forwarded-For`` hop) and so
    cannot be spoofed by a client sending its own ``X-Forwarded-For`` to fake
    its location.

    The returned value lives only inside :func:`_resolve_location`'s call
    stack and is never persisted.
    """
    return get_real_client_ip(request)


def _resolve_location(
    payload: CheckInCreateRequest,
    ip: str,
    provider: GeocodingProvider,
) -> tuple[str | None, str, str | None]:
    """Decision table for ``location_text`` / ``location_status`` /
    ``location_provider``. See design.md ``Decision Table``.

    Returns a 3-tuple suitable for direct assignment to the new ``CheckIn``
    row's three location fields.
    """
    has_coords = payload.latitude is not None and payload.longitude is not None

    if not has_coords and payload.location_permission_denied:
        # User denied browser geolocation and submitted anyway.
        return None, LocationStatus.permission_denied.value, None

    if not has_coords:
        # User skipped location entirely (no consent flag, no coords).
        return None, LocationStatus.omitted.value, None

    # Coordinates provided: try geo first, then fall back to IP.
    geo_result = provider.reverse_geocode(payload.latitude, payload.longitude)
    if geo_result.success and geo_result.text:
        return geo_result.text, LocationStatus.resolved.value, geo_result.provider

    ip_result = provider.reverse_lookup_ip(ip) if ip else None
    if ip_result and ip_result.success and ip_result.text:
        return ip_result.text, LocationStatus.resolved.value, ip_result.provider

    return None, LocationStatus.lookup_failed.value, None


def _validate_at_least_one_field(payload: CheckInCreateRequest) -> None:
    """Reject empty submissions (no content, no media, no location intent)."""
    has_content = bool(payload.content)
    has_media = bool(payload.media_urls)
    has_location_intent = (
        (payload.latitude is not None and payload.longitude is not None)
        or payload.location_permission_denied
    )
    if not (has_content or has_media or has_location_intent):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="留言、照片、位置至少需要提供一项",
        )


def _resolve_counterpart(db: Session, current_user: User) -> User | None:
    """Return the *other* partner account, or None if there isn't one yet.

    The project guarantees at most two partner accounts at a time
    (PartnerA + PartnerB). We pick the first non-self partner ordered by id.
    """
    return (
        db.query(User)
        .filter(
            User.role.in_([UserRole.partner_a, UserRole.partner_b]),
            User.id != current_user.id,
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .first()
    )


def _to_response(checkin: CheckIn) -> CheckInResponse:
    return CheckInResponse(
        cid=checkin.cid,
        author_uid=checkin.author.uid,
        author_nickname=checkin.author.nickname,
        content=checkin.content,
        media_urls=list(checkin.media_urls or []),
        location_text=checkin.location_text,
        location_status=checkin.location_status,
        location_provider=checkin.location_provider,
        created_at=checkin.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=CheckInResponse, status_code=status.HTTP_201_CREATED)
def create_checkin(
    payload: CheckInCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> CheckInResponse:
    ensure_partner(current_user)
    _validate_at_least_one_field(payload)

    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Idempotency-Key")
        existing = (
            db.query(CheckIn)
            .options(joinedload(CheckIn.author))
            .filter(
                CheckIn.author_id == current_user.id,
                CheckIn.client_idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is not None:
            return _to_response(existing)

    ip = _read_client_ip(request)  # function-local only; never persisted
    provider = get_provider()
    location_text, location_status_value, location_provider = _resolve_location(
        payload, ip, provider,
    )

    checkin = CheckIn(
        author_id=current_user.id,
        content=payload.content,
        media_urls=list(payload.media_urls or []),
        location_text=location_text,
        location_status=location_status_value,
        location_provider=(
            location_provider
            if location_status_value == LocationStatus.resolved.value
            else None
        ),
        client_idempotency_key=idempotency_key,
    )
    db.add(checkin)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key is None:
            raise
        existing = (
            db.query(CheckIn)
            .options(joinedload(CheckIn.author))
            .filter(
                CheckIn.author_id == current_user.id,
                CheckIn.client_idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing is None:
            raise
        return _to_response(existing)
    db.refresh(checkin)

    # Reload with author eager-loaded for the response.
    checkin = (
        db.query(CheckIn)
        .options(joinedload(CheckIn.author))
        .filter(CheckIn.id == checkin.id)
        .first()
    )
    if checkin is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CheckIn vanished after insert",
        )

    sync_checkin_upload_references(db, checkin)

    counterpart = _resolve_counterpart(db, current_user)
    if counterpart is not None:
        # Privacy: notification body is intentionally None — the recipient
        # must open the cottage check-in page to see content / location.
        create_notification(
            db,
            recipient=counterpart,
            type="checkin.created",
            title=f"{current_user.nickname} 报备了",
            body=None,
            link="/cottage/check-in",
            source_type="checkin",
            source_id=checkin.cid,
            dedupe=True,
        )

    db.commit()
    return _to_response(checkin)


@router.get("/latest", response_model=CheckInLatestResponse)
def get_latest_checkin(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CheckInLatestResponse:
    ensure_partner(current_user)
    item = (
        db.query(CheckIn)
        .options(joinedload(CheckIn.author))
        .filter(
            CheckIn.deleted_at.is_(None),
            CheckIn.author_id != current_user.id,  # "自己看不到自己"
        )
        .order_by(CheckIn.created_at.desc())
        .first()
    )
    return CheckInLatestResponse(item=_to_response(item) if item else None)


@router.get("", response_model=CheckInListResponse)
def list_checkins(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CheckInListResponse:
    ensure_partner(current_user)
    offset = (page - 1) * page_size

    base_query = db.query(CheckIn).filter(
        CheckIn.deleted_at.is_(None),
        CheckIn.author_id != current_user.id,  # "自己看不到自己"
    )
    total = base_query.with_entities(func.count(CheckIn.id)).scalar() or 0

    items = (
        base_query
        .options(joinedload(CheckIn.author))
        .order_by(CheckIn.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return CheckInListResponse(
        items=[_to_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        has_next=(offset + page_size) < total,
    )
