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

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Annotated, Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_optional_user
from app.core.tags import normalize_tags, parse_tag_query
from app.db.session import get_db
from app.models.album import Album
from app.models.article import Article
from app.models.event import Event
from app.models.message import Message
from app.models.moment import Moment
from app.models.user import User
from app.schemas.search import SearchContentType, SearchResponse, SearchResultItem, SearchTagMode
from app.services.visibility_policy import VisibilityPolicy


router = APIRouter(prefix="/search", tags=["search"])

ALL_SEARCH_TYPES: set[SearchContentType] = {"article", "album", "event", "moment", "message"}


def _parse_types(raw: str | None) -> list[SearchContentType]:
    if not raw:
        return sorted(ALL_SEARCH_TYPES)

    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    selected = list(dict.fromkeys(values))
    invalid = [item for item in selected if item not in ALL_SEARCH_TYPES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported search type: {', '.join(invalid)}",
        )
    return selected  # type: ignore[return-value]


def _parse_query(value: str | None) -> tuple[str | None, list[str]]:
    normalized = value.strip() if value else None
    if not normalized:
        return None, []

    terms = [item.casefold() for item in normalized.split() if item.strip()]
    return normalized, terms or [normalized.casefold()]


def _clean_text(*parts: object) -> str:
    return " ".join(str(part).strip() for part in parts if part is not None and str(part).strip())


def _matches_keyword(terms: list[str], *parts: object) -> bool:
    if not terms:
        return True
    haystack = _clean_text(*parts).casefold()
    return all(term in haystack for term in terms)


def _score(terms: list[str], title: str, tags: list[str], *body_parts: object) -> int:
    if not terms:
        return 0

    title_text = title.casefold()
    tags_text = " ".join(tags).casefold()
    body_text = _clean_text(*body_parts).casefold()
    score = 0
    for term in terms:
        if term in title_text:
            score += 60
        if term in tags_text:
            score += 35
        if term in body_text:
            score += 15
    return score


def _snippet(terms: list[str], *parts: object) -> str:
    text = _clean_text(*parts)
    if len(text) <= 180:
        return text

    lower = text.casefold()
    indexes = [lower.find(term) for term in terms if term and lower.find(term) >= 0]
    if not indexes:
        return f"{text[:180].rstrip()}..."

    center = min(indexes)
    start = max(0, center - 60)
    end = min(len(text), center + 140)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def _matches_tags(item_tags: list[str], filter_tags: list[str], tag_mode: SearchTagMode) -> bool:
    if not filter_tags:
        return True
    item_keys = {tag.casefold() for tag in item_tags}
    filter_keys = {tag.casefold() for tag in filter_tags}
    if tag_mode == "all":
        return filter_keys.issubset(item_keys)
    return bool(item_keys & filter_keys)


def _safe_tags(raw_tags: Iterable[str] | None) -> list[str]:
    try:
        return normalize_tags(list(raw_tags or []))
    except ValueError:
        return []


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _day_end(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=timezone.utc)


def _as_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _apply_datetime_window(query, column, date_from: date | None, date_to: date | None):
    if date_from is not None:
        query = query.filter(column >= _day_start(date_from))
    if date_to is not None:
        query = query.filter(column <= _day_end(date_to))
    return query


def _append_result(
    results: list[tuple[int, SearchResultItem]],
    *,
    score: int,
    item: SearchResultItem,
) -> None:
    results.append((score, item))


@router.get("", response_model=SearchResponse)
def search_content(
    q: Annotated[str | None, Query(max_length=120)] = None,
    types: Annotated[str | None, Query(description="Comma separated content types")] = None,
    tags: Annotated[str | None, Query(max_length=240)] = None,
    tag_mode: SearchTagMode = "any",
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> SearchResponse:
    if tag_mode not in {"any", "all"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported tag mode")
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid date range")

    selected_types = _parse_types(types)
    try:
        filter_tags = parse_tag_query(tags)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    normalized_q, terms = _parse_query(q)
    results: list[tuple[int, SearchResultItem]] = []

    if "article" in selected_types:
        article_date = func.coalesce(Article.published_at, Article.created_at)
        query = (
            db.query(Article)
            .options(joinedload(Article.author), joinedload(Article.blocks))
            .filter(Article.deleted_at.is_(None), VisibilityPolicy.article_query_filter(current_user))
        )
        query = _apply_datetime_window(query, article_date, date_from, date_to)
        for article in query.all():
            item_tags = _safe_tags(article.tags)
            block_text = _clean_text(*(block.content for block in article.blocks))
            if not _matches_tags(item_tags, filter_tags, tag_mode):
                continue
            if not _matches_keyword(terms, article.title, article.excerpt, block_text, *item_tags):
                continue
            item_date = article.published_at or article.created_at
            _append_result(
                results,
                score=_score(terms, article.title, item_tags, article.excerpt, block_text),
                item=SearchResultItem(
                    type="article",
                    id=article.aid,
                    title=article.title,
                    snippet=_snippet(terms, article.excerpt, block_text) or article.title,
                    url=f"/articles/{article.aid}",
                    date=_as_datetime(item_date),
                    tags=item_tags,
                    visibility=VisibilityPolicy.article_visibility(article).value,
                    is_encrypted=article.is_encrypted,
                    author_nickname=article.author.nickname,
                ),
            )

    if "album" in selected_types:
        query = (
            db.query(Album)
            .options(joinedload(Album.author))
            .filter(Album.deleted_at.is_(None), VisibilityPolicy.album_query_filter(current_user))
        )
        query = _apply_datetime_window(query, Album.created_at, date_from, date_to)
        for album in query.all():
            item_tags = _safe_tags(album.tags)
            if not _matches_tags(item_tags, filter_tags, tag_mode):
                continue
            if not _matches_keyword(terms, album.title, album.description, *item_tags):
                continue
            _append_result(
                results,
                score=_score(terms, album.title, item_tags, album.description),
                item=SearchResultItem(
                    type="album",
                    id=album.alb_id,
                    title=album.title,
                    snippet=_snippet(terms, album.description) or album.title,
                    url="/albums",
                    date=_as_datetime(album.created_at),
                    tags=item_tags,
                    visibility=VisibilityPolicy.album_visibility(album).value,
                    is_encrypted=album.is_encrypted,
                    author_nickname=album.author.nickname,
                ),
            )

    if "event" in selected_types:
        query = (
            db.query(Event)
            .options(joinedload(Event.creator))
            .filter(Event.deleted_at.is_(None), VisibilityPolicy.event_query_filter(current_user))
        )
        if date_from is not None:
            query = query.filter(Event.date >= date_from)
        if date_to is not None:
            query = query.filter(Event.date <= date_to)
        for event in query.all():
            item_tags = _safe_tags(event.tags)
            if not _matches_tags(item_tags, filter_tags, tag_mode):
                continue
            if not _matches_keyword(terms, event.title, event.type.value, *item_tags):
                continue
            _append_result(
                results,
                score=_score(terms, event.title, item_tags, event.type.value),
                item=SearchResultItem(
                    type="event",
                    id=event.eid,
                    title=event.title,
                    snippet=_snippet(terms, event.type.value, event.date.isoformat()) or event.title,
                    url="/events",
                    date=_as_datetime(event.date),
                    tags=item_tags,
                    visibility=VisibilityPolicy.event_visibility(event).value,
                    is_encrypted=VisibilityPolicy.event_visibility(event).value == "Encrypted",
                    author_nickname=event.creator.nickname,
                ),
            )

    if "moment" in selected_types:
        query = (
            db.query(Moment)
            .options(joinedload(Moment.author))
            .filter(Moment.deleted_at.is_(None), VisibilityPolicy.moment_query_filter(current_user))
        )
        query = _apply_datetime_window(query, Moment.timestamp, date_from, date_to)
        for moment in query.all():
            item_tags = _safe_tags(moment.tags)
            if not _matches_tags(item_tags, filter_tags, tag_mode):
                continue
            if not _matches_keyword(terms, moment.content, moment.location, *item_tags):
                continue
            _append_result(
                results,
                score=_score(terms, moment.content[:80], item_tags, moment.content, moment.location),
                item=SearchResultItem(
                    type="moment",
                    id=moment.mid,
                    title=moment.content[:48],
                    snippet=_snippet(terms, moment.content, moment.location),
                    url="/timeline",
                    date=_as_datetime(moment.timestamp),
                    tags=item_tags,
                    visibility=VisibilityPolicy.moment_visibility(moment).value,
                    is_encrypted=VisibilityPolicy.moment_visibility(moment).value == "Encrypted",
                    author_nickname=moment.author.nickname,
                ),
            )

    if "message" in selected_types:
        include_private = current_user is not None
        query = (
            db.query(Message)
            .options(joinedload(Message.author))
            .filter(
                Message.is_deleted.is_(False),
                VisibilityPolicy.message_query_filter(current_user, include_private=include_private),
            )
        )
        query = _apply_datetime_window(query, Message.created_at, date_from, date_to)
        for message in query.all():
            item_tags = _safe_tags(message.tags)
            author_name = message.author.nickname if message.author else message.visitor_name
            if not _matches_tags(item_tags, filter_tags, tag_mode):
                continue
            if not _matches_keyword(terms, message.content, author_name, *item_tags):
                continue
            _append_result(
                results,
                score=_score(terms, message.content[:80], item_tags, message.content, author_name),
                item=SearchResultItem(
                    type="message",
                    id=message.msg_id,
                    title=message.content[:48],
                    snippet=_snippet(terms, message.content),
                    url="/messages",
                    date=_as_datetime(message.created_at),
                    tags=item_tags,
                    visibility=VisibilityPolicy.message_visibility(message).value,
                    author_nickname=author_name,
                ),
            )

    results.sort(key=lambda pair: (pair[0], pair[1].date), reverse=True)
    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    items = [item for _, item in results[start:end]]

    return SearchResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        q=normalized_q,
        types=selected_types,
        tags=filter_tags,
        tag_mode=tag_mode,
    )
