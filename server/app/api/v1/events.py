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

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user, get_optional_user
from app.db.session import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventCreateRequest, EventListResponse, EventResponse, EventPatchRequest
from app.services.visibility_policy import VisibilityPolicy


router = APIRouter(prefix="/events", tags=["events"])


def _calc_next_occurrence_days(event_date: date, is_yearly_repeat: bool) -> int | None:
    if not is_yearly_repeat:
        return None

    today = datetime.now(timezone.utc).date()

    try:
        candidate = event_date.replace(year=today.year)
    except ValueError:
        candidate = date(today.year, 3, 1)

    if candidate < today:
        try:
            candidate = event_date.replace(year=today.year + 1)
        except ValueError:
            candidate = date(today.year + 1, 3, 1)

    return (candidate - today).days


def _to_response(event: Event) -> EventResponse:
    return EventResponse(
        eid=event.eid,
        title=event.title,
        date=event.date,
        type=event.type,
        creator_uid=event.creator.uid,
        creator_nickname=event.creator.nickname,
        is_important=event.is_important,
        is_yearly_repeat=event.is_yearly_repeat,
        visibility=event.visibility,
        tags=event.tags or [],
        next_occurrence_days=_calc_next_occurrence_days(event.date, event.is_yearly_repeat),
        created_at=event.created_at,
    )


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventResponse:
    ensure_partner(current_user)

    event = Event(
        creator_id=current_user.id,
        title=payload.title,
        date=payload.date,
        type=payload.type,
        is_important=payload.is_important,
        is_yearly_repeat=payload.is_yearly_repeat,
        visibility=payload.visibility,
        tags=payload.tags,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    event = (
        db.query(Event)
        .options(joinedload(Event.creator))
        .filter(Event.id == event.id, Event.deleted_at.is_(None))
        .first()
    )
    return _to_response(event)


@router.get("", response_model=EventListResponse)
def list_events(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> EventListResponse:
    events = (
        db.query(Event)
        .options(joinedload(Event.creator))
        .filter(Event.deleted_at.is_(None), VisibilityPolicy.event_query_filter(current_user))
        .order_by(Event.is_important.desc(), Event.date.asc(), Event.created_at.asc())
        .all()
    )

    return EventListResponse(items=[_to_response(item) for item in events], total=len(events))


@router.put("/{eid}", response_model=EventResponse)
def update_event(
    eid: str,
    payload: EventCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventResponse:
    ensure_partner(current_user)

    event = (
        db.query(Event)
        .options(joinedload(Event.creator))
        .filter(Event.eid == eid, Event.deleted_at.is_(None))
        .first()
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    event.title = payload.title
    event.date = payload.date
    event.type = payload.type
    event.is_important = payload.is_important
    event.is_yearly_repeat = payload.is_yearly_repeat
    event.visibility = payload.visibility
    event.tags = payload.tags
    db.commit()
    db.refresh(event)
    return _to_response(event)


@router.patch("/{eid}", response_model=EventResponse)
def patch_event(
    eid: str,
    payload: EventPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventResponse:
    ensure_partner(current_user)

    event = (
        db.query(Event)
        .options(joinedload(Event.creator))
        .filter(Event.eid == eid, Event.deleted_at.is_(None))
        .first()
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "title" in update_data:
        event.title = update_data["title"]
    if "date" in update_data:
        event.date = update_data["date"]
    if "type" in update_data:
        event.type = update_data["type"]
    if "is_important" in update_data:
        event.is_important = update_data["is_important"]
    if "is_yearly_repeat" in update_data:
        event.is_yearly_repeat = update_data["is_yearly_repeat"]
    if "visibility" in update_data:
        event.visibility = update_data["visibility"]
    if "tags" in update_data:
        event.tags = update_data["tags"]

    db.commit()
    db.refresh(event)
    return _to_response(event)


@router.delete("/{eid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_event(
    eid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)

    event = db.query(Event).filter(Event.eid == eid, Event.deleted_at.is_(None)).first()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    event.deleted_at = datetime.now(timezone.utc)
    db.commit()
