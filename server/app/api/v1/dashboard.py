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

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_optional_user
from app.db.session import get_db
from app.models.album import Album
from app.models.article import Article
from app.models.content_visibility import ContentVisibility
from app.models.event import Event
from app.models.message import Message
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole
from app.schemas.album import AlbumSummaryResponse
from app.schemas.article import ArticleSummaryResponse
from app.schemas.dashboard import (
    CoupleInfo,
    CoupleMember,
    DashboardResponse,
    DashboardStats,
    LoveClock,
)
from app.schemas.event import EventResponse
from app.schemas.message import MessageResponse
from app.services.visibility_policy import VisibilityPolicy


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _safe_article_excerpt(article: Article, user: User | None) -> str | None:
    return VisibilityPolicy.redact_if_encrypted(article.excerpt, is_encrypted=article.is_encrypted, user=user)


def _safe_album_cover(album: Album, user: User | None) -> str | None:
    return VisibilityPolicy.redact_if_encrypted(album.cover_url, is_encrypted=album.is_encrypted, user=user)


def _build_love_clock(love_start_date: datetime | None) -> LoveClock:
    if love_start_date is None:
        return LoveClock(days=0, hours=0, minutes=0, seconds=0)

    now = datetime.now(timezone.utc)

    # Ensure timezone info is present
    if love_start_date.tzinfo is None:
        love_start_date = love_start_date.replace(tzinfo=timezone.utc)

    delta = now - love_start_date
    total_seconds = max(0, int(delta.total_seconds()))

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return LoveClock(days=days, hours=hours, minutes=minutes, seconds=seconds)


def _build_couple_member(
    role: UserRole, user: User | None, avatar: str | None
) -> CoupleMember | None:
    """Combine a partner account with their configured couple avatar.

    The avatar prefers the admin-managed couple avatar (SiteSetting) and falls
    back to the account's own ``avatar``. Returns ``None`` only when there is
    neither an account nor an avatar, so the homepage can simply skip rendering.
    """
    resolved_avatar = avatar or (user.avatar if user else None)
    if user is None and not resolved_avatar:
        return None
    return CoupleMember(
        role=role.value,
        nickname=user.nickname if user else None,
        avatar=resolved_avatar,
    )


def _build_couple_info(db: Session, setting: SiteSetting | None) -> CoupleInfo:
    partner_a_user = (
        db.query(User)
        .filter(User.role == UserRole.partner_a, User.deleted_at.is_(None))
        .first()
    )
    partner_b_user = (
        db.query(User)
        .filter(User.role == UserRole.partner_b, User.deleted_at.is_(None))
        .first()
    )
    return CoupleInfo(
        partner_a=_build_couple_member(
            UserRole.partner_a, partner_a_user, setting.partner_a_avatar if setting else None
        ),
        partner_b=_build_couple_member(
            UserRole.partner_b, partner_b_user, setting.partner_b_avatar if setting else None
        ),
    )


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


def _to_event_response(event: Event) -> EventResponse:
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


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> DashboardResponse:
    is_partner = VisibilityPolicy.is_partner(current_user)

    setting = db.query(SiteSetting).filter(SiteSetting.id == 1).first()
    love_clock = _build_love_clock(setting.love_start_date if setting else None)
    couple = _build_couple_info(db, setting)

    article_count_query = db.query(func.count(Article.id)).filter(
        Article.deleted_at.is_(None),
        VisibilityPolicy.article_query_filter(current_user),
    )
    article_count = article_count_query.scalar() or 0

    album_count_query = db.query(func.count(Album.id)).filter(
        Album.deleted_at.is_(None),
        VisibilityPolicy.album_query_filter(current_user),
    )
    album_count = album_count_query.scalar() or 0

    event_count_query = db.query(func.count(Event.id)).filter(
        Event.deleted_at.is_(None),
        VisibilityPolicy.event_query_filter(current_user),
    )
    event_count = event_count_query.scalar() or 0

    message_count_query = db.query(func.count(Message.id)).filter(
        Message.is_deleted.is_(False),
        VisibilityPolicy.message_query_filter(current_user, include_private=is_partner),
    )
    message_count = message_count_query.scalar() or 0

    events_query = (
        db.query(Event)
        .options(joinedload(Event.creator))
        .filter(Event.deleted_at.is_(None), VisibilityPolicy.event_query_filter(current_user))
    )
    events = events_query.order_by(Event.date.asc(), Event.created_at.desc()).limit(6).all()

    articles_query = (
        db.query(Article)
        .options(joinedload(Article.author))
        .filter(Article.deleted_at.is_(None), VisibilityPolicy.article_query_filter(current_user))
    )
    articles = articles_query.order_by(Article.created_at.desc()).limit(6).all()

    albums_query = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .filter(Album.deleted_at.is_(None), VisibilityPolicy.album_query_filter(current_user))
    )
    albums = albums_query.order_by(Album.created_at.desc()).limit(6).all()

    messages_query = (
        db.query(Message)
        .options(joinedload(Message.author))
        .filter(
            Message.is_deleted.is_(False),
            VisibilityPolicy.message_query_filter(current_user, include_private=is_partner),
        )
    )
    messages = messages_query.order_by(Message.created_at.desc()).limit(6).all()

    logger.debug(
        "Preparing dashboard recent events",
        extra={
            "event_count": len(events),
            "event_ids": [item.eid for item in events],
            "is_partner": is_partner,
        },
    )

    recent_events: list[EventResponse] = []
    for item in events:
        try:
            recent_events.append(_to_event_response(item))
        except ValidationError:
            logger.exception(
                "Dashboard recent event serialization failed. eid=%s is_important=%s is_yearly_repeat=%s",
                item.eid,
                item.is_important,
                item.is_yearly_repeat,
            )
            raise

    latest_articles = [
        ArticleSummaryResponse(
            aid=item.aid,
            title=item.title,
            excerpt=_safe_article_excerpt(item, current_user),
            status=item.status,
            is_encrypted=item.is_encrypted,
            partner_can_edit=item.partner_can_edit,
            visibility=item.visibility,
            requires_password=(
                item.password_hash is not None and item.visibility == ContentVisibility.password_protected
            ),
            tags=item.tags or [],
            version=item.version,
            author_uid=item.author.uid,
            author_nickname=item.author.nickname,
            published_at=item.published_at,
            created_at=item.created_at,
        )
        for item in articles
    ]

    latest_albums = [
        AlbumSummaryResponse(
            alb_id=item.alb_id,
            title=item.title,
            description=VisibilityPolicy.redact_if_encrypted(
                item.description, is_encrypted=item.is_encrypted, user=current_user
            ),
            cover_url=_safe_album_cover(item, current_user),
            is_encrypted=item.is_encrypted,
            is_public=item.is_public,
            visibility=item.visibility,
            requires_password=(
                item.password_hash is not None and item.visibility == ContentVisibility.password_protected
            ),
            tags=item.tags or [],
            author_uid=item.author.uid,
            author_nickname=item.author.nickname,
            media_count=len(item.media_items),
            created_at=item.created_at,
        )
        for item in albums
    ]

    latest_messages = [
        MessageResponse(
            msg_id=item.msg_id,
            content=item.content,
            is_public=item.is_public,
            tags=item.tags or [],
            is_deleted=item.is_deleted,
            version=item.version,
            created_at=item.created_at,
            author_uid=item.author.uid if item.author else None,
            author_nickname=item.author.nickname if item.author else None,
            visitor_name=item.visitor_name,
        )
        for item in messages
    ]

    return DashboardResponse(
        love_clock=love_clock,
        stats=DashboardStats(
            article_count=article_count,
            album_count=album_count,
            event_count=event_count,
            message_count=message_count,
        ),
        couple=couple,
        recent_events=recent_events,
        latest_articles=latest_articles,
        latest_albums=latest_albums,
        latest_messages=latest_messages,
    )
