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
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.capsule import Capsule
from app.models.user import User
from app.schemas.capsule import CapsuleCreateRequest, CapsuleResponse
from app.services.upload_references import (
    delete_upload_references_for,
    sync_capsule_upload_references,
)

router = APIRouter(prefix="/capsules", tags=["capsules"])


def _to_response(capsule: Capsule) -> CapsuleResponse:
    now = datetime.now(timezone.utc)
    open_at = capsule.open_at
    # SQLite (local dev / tests) returns naive datetimes even for
    # DateTime(timezone=True) columns; normalize to UTC before comparing so the
    # unlock check never raises "can't compare offset-naive and offset-aware".
    if open_at is not None and open_at.tzinfo is None:
        open_at = open_at.replace(tzinfo=timezone.utc)
    is_open = now >= open_at
    has_media = bool(capsule.media_url)

    return CapsuleResponse(
        uuid=capsule.uuid,
        # Both text and the media URL stay sealed until open_at: never hand the
        # client a way to fetch the recording before the unlock moment.
        content=capsule.content if is_open else None,
        open_at=capsule.open_at,
        created_at=capsule.created_at,
        author_uid=capsule.author.uid,
        author_nickname=capsule.author.nickname,
        is_open=is_open,
        has_media=has_media,
        media_type=capsule.media_type if has_media else None,
        media_duration_sec=capsule.media_duration_sec if has_media else None,
        media_url=capsule.media_url if (is_open and has_media) else None,
    )


@router.post("", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED)
def create_capsule(
    payload: CapsuleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CapsuleResponse:
    ensure_partner(current_user)
    content = (payload.content or "").strip() or None
    capsule = Capsule(
        author_id=current_user.id,
        content=content,
        open_at=payload.open_at,
        media_url=payload.media_url,
        media_type=payload.media_type if payload.media_url else None,
        media_duration_sec=payload.media_duration_sec if payload.media_url else None,
    )
    db.add(capsule)
    db.flush()
    # Grant the partner access to the freshly-uploaded recording through the
    # guarded /uploads route (the URL itself stays hidden until open_at).
    sync_capsule_upload_references(db, capsule)
    db.commit()
    db.refresh(capsule)

    capsule = db.query(Capsule).options(joinedload(Capsule.author)).filter(Capsule.id == capsule.id).first()
    return _to_response(capsule)


@router.get("", response_model=list[CapsuleResponse])
def list_capsules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CapsuleResponse]:
    ensure_partner(current_user)
    capsules = (
        db.query(Capsule)
        .options(joinedload(Capsule.author))
        .filter(Capsule.deleted_at.is_(None))
        .order_by(Capsule.open_at.asc())
        .all()
    )
    return [_to_response(c) for c in capsules]


@router.delete("/{uuid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_capsule(
    uuid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)

    capsule = db.query(Capsule).filter(Capsule.uuid == uuid, Capsule.deleted_at.is_(None)).first()
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    capsule.deleted_at = datetime.now(timezone.utc)
    delete_upload_references_for(db, "capsule", capsule.id)
    db.commit()
