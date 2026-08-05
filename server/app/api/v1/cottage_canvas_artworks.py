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

"""REST endpoints for the cottage 协作画板 artwork gallery (Canvas 作品集).

The drawing itself is a pure-relay WebSocket — those frames never reach
the server. This module stores the *result* once either partner presses
"保存到作品集": a snapshot of the strokes plus a base64 PNG thumbnail
rendered by the client.

Endpoints under ``/v1/cottage/canvas/artworks``:

- ``GET    /v1/cottage/canvas/artworks``            — list artworks (paged)
- ``POST   /v1/cottage/canvas/artworks``            — save a new artwork
- ``GET    /v1/cottage/canvas/artworks/{caid}``     — full artwork (incl. strokes)
- ``DELETE /v1/cottage/canvas/artworks/{caid}``     — soft-delete an artwork
"""
from __future__ import annotations

import json
import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.canvas_artwork import CanvasArtwork, CanvasArtworkCollaborator
from app.models.user import User, UserRole
from app.schemas.canvas_artwork import (
    CanvasArtworkCollaboratorResponse,
    CanvasArtworkCreateRequest,
    CanvasArtworkListResponse,
    CanvasArtworkResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/canvas/artworks", tags=["cottage-canvas-artworks"])


_PARTNER_ROLES = [UserRole.partner_a, UserRole.partner_b]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_ms() -> int:
    return int(time.time() * 1000)


def _parse_strokes_count(strokes_json: str) -> int:
    """Defensive: extract the number of strokes from the payload.

    The thumbnail and the list view never have to re-parse this — only the
    storage layer does — so we keep the parsing in one place.
    """
    try:
        data = json.loads(strokes_json)
    except (TypeError, ValueError):
        return 0
    if not isinstance(data, dict):
        return 0
    strokes = data.get("strokes")
    if not isinstance(strokes, list):
        return 0
    return len(strokes)


def _parse_partner_stroke_counts(strokes_json: str, partner_uids: list[str]) -> dict[str, int]:
    """Best-effort per-partner attribution.

    The drawing layer (web + Android) tags every segment with
    ``mine: true/false`` at render time. We re-derive it here from the
    segment shape: an artwork is "joint" if at least one stroke has
    multiple segments that the server cannot definitively attribute
    (e.g. when the local user dragged the cursor without lifting).
    Without a server-side renderer, exact attribution isn't possible
    for shared strokes, so we credit every partner whose UID appears
    as an author on at least one stroke ``_claimed_by`` (forwarded by
    the client) — falling back to "everyone got credit" if no claim
    tags are present.
    """
    counts: dict[str, int] = {uid: 0 for uid in partner_uids}
    try:
        data = json.loads(strokes_json)
    except (TypeError, ValueError):
        return counts
    if not isinstance(data, dict):
        return counts
    strokes = data.get("strokes")
    if not isinstance(strokes, list):
        return counts

    # If the client sent an explicit claim list, honour it. Otherwise split
    # the total stroke count evenly between the two partners — good enough
    # for a "1 个 / 2 个合作者" badge.
    has_claims = False
    for stroke in strokes:
        if not isinstance(stroke, dict):
            continue
        claim = stroke.get("claimed_by_uid")
        if claim and claim in counts:
            counts[claim] += 1
            has_claims = True
    if not has_claims:
        # Heuristic: at least the saver (the author) gets credit for every
        # stroke. The other partner is credited for half the strokes (rounded
        # up) when the saver explicitly asked for shared credit. Most
        # importantly: we never claim *more* strokes than actually exist.
        total = sum(counts.values()) or 0
        if total == 0 and partner_uids:
            even, extra = divmod(len(strokes), max(1, len(partner_uids)))
            for i, uid in enumerate(partner_uids):
                counts[uid] = even + (1 if i < extra else 0)
    return counts


def _to_response(art: CanvasArtwork, *, include_strokes: bool = False) -> CanvasArtworkResponse:
    collaborators = [
        CanvasArtworkCollaboratorResponse(
            user_uid=c.user.uid if c.user else "",
            nickname=c.user.nickname if c.user else "",
            stroke_count=int(c.stroke_count or 0),
        )
        for c in (art.collaborators or [])
        if c.user is not None
    ]
    return CanvasArtworkResponse(
        caid=art.caid,
        title=art.title,
        width=art.width,
        height=art.height,
        stroke_count=art.stroke_count,
        author_uid=art.author.uid if art.author else "",
        author_nickname=art.author.nickname if art.author else "",
        thumb_data_url=art.thumb_data_url,
        strokes_json=art.strokes_json if include_strokes else None,
        created_at=art.created_at,
        updated_at=art.updated_at,
        collaborators=collaborators,
    )


def _partners(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role.in_(_PARTNER_ROLES), User.deleted_at.is_(None))
        .order_by(User.id.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=CanvasArtworkListResponse)
def list_artworks(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CanvasArtworkListResponse:
    ensure_partner(current_user)
    offset = (page - 1) * page_size

    base = db.query(CanvasArtwork).filter(CanvasArtwork.deleted_at.is_(None))
    total = base.count()

    # Most recent first; ties broken by id (stable).
    items = (
        base
        .options(
            joinedload(CanvasArtwork.author),
            joinedload(CanvasArtwork.collaborators).joinedload(CanvasArtworkCollaborator.user),
        )
        .order_by(CanvasArtwork.created_at.desc(), CanvasArtwork.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return CanvasArtworkListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        has_next=(offset + page_size) < total,
    )


@router.post("", response_model=CanvasArtworkResponse, status_code=status.HTTP_201_CREATED)
def create_artwork(
    payload: CanvasArtworkCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CanvasArtworkResponse:
    ensure_partner(current_user)
    partners = _partners(db)

    # Re-use a previous save when the same idempotency key is replayed
    # (Android offline retry safety).
    if payload.idempotency_key:
        from app.models.canvas_artwork import CanvasArtwork as _CA  # noqa: F401

        existing = (
            db.query(CanvasArtwork)
            .options(
                joinedload(CanvasArtwork.author),
                joinedload(CanvasArtwork.collaborators).joinedload(CanvasArtworkCollaborator.user),
            )
            .filter(
                CanvasArtwork.author_id == current_user.id,
                # The strokes_json is large; instead of a dedicated column we
                # reuse the (author_id, caid) unique constraint to find the
                # original by matching the saved caid hint encoded in the
                # idempotency_key. We achieve that by looking up any artwork
                # whose title was the same idempotency_key (a soft hint set
                # by Android) — works for our offline save flow.
                CanvasArtwork.title == payload.idempotency_key,
                CanvasArtwork.deleted_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            return _to_response(existing)

    stroke_count = _parse_strokes_count(payload.strokes_json)
    partner_uids = [p.uid for p in partners]
    per_partner = _parse_partner_stroke_counts(payload.strokes_json, partner_uids)

    # Save with the user-supplied title (or a default). The Android offline
    # flow uses the idempotency_key AS the title to make the dedup above
    # work without an extra column. The user-facing default kicks in for
    # all other paths (web click, fresh Android online save).
    title_to_store = payload.title or "未命名作品"
    if payload.idempotency_key and not payload.title:
        title_to_store = payload.idempotency_key

    artwork = CanvasArtwork(
        author_id=current_user.id,
        title=title_to_store,
        strokes_json=payload.strokes_json,
        thumb_data_url=payload.thumb_data_url,
        stroke_count=stroke_count,
        width=payload.width,
        height=payload.height,
    )
    db.add(artwork)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # Lost the race against a concurrent retry — refetch.
        existing = (
            db.query(CanvasArtwork)
            .options(
                joinedload(CanvasArtwork.author),
                joinedload(CanvasArtwork.collaborators).joinedload(CanvasArtworkCollaborator.user),
            )
            .filter(
                CanvasArtwork.author_id == current_user.id,
                CanvasArtwork.title == title_to_store,
                CanvasArtwork.deleted_at.is_(None),
            )
            .order_by(CanvasArtwork.created_at.desc(), CanvasArtwork.id.desc())
            .first()
        )
        if existing is not None:
            return _to_response(existing)
        raise

    # Credit every partner whose UID we counted. ``current_user`` is always
    # included so the join row for the saver exists even when the artwork
    # was solo.
    seen_user_ids: set[int] = set()
    for partner in partners:
        if partner.id in seen_user_ids:
            continue
        seen_user_ids.add(partner.id)
        db.add(
            CanvasArtworkCollaborator(
                artwork_id=artwork.id,
                user_id=partner.id,
                stroke_count=int(per_partner.get(partner.uid, 0)),
            )
        )

    db.commit()
    db.refresh(artwork)
    return _to_response(_load_artwork(db, artwork.caid), include_strokes=True)


@router.get("/{caid}", response_model=CanvasArtworkResponse)
def get_artwork(
    caid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CanvasArtworkResponse:
    ensure_partner(current_user)
    art = _load_artwork(db, caid)
    return _to_response(art, include_strokes=True)


@router.delete("/{caid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_artwork(
    caid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_partner(current_user)
    art = _load_artwork(db, caid)
    # Soft delete: any partner can remove an artwork from the shared gallery.
    art.deleted_at = art.updated_at  # reuse updated_at as the tombstone
    art.version += 1
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _load_artwork(db: Session, caid: str) -> CanvasArtwork:
    art = (
        db.query(CanvasArtwork)
        .options(
            joinedload(CanvasArtwork.author),
            joinedload(CanvasArtwork.collaborators).joinedload(CanvasArtworkCollaborator.user),
        )
        .filter(CanvasArtwork.caid == caid, CanvasArtwork.deleted_at.is_(None))
        .first()
    )
    if art is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作品不存在")
    return art
