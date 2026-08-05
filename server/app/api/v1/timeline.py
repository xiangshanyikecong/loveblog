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

import re
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user, get_optional_user
from app.db.session import get_db
from app.models.comment import Comment, CommentTargetType
from app.models.moment import Moment
from app.models.user import User
from app.schemas.comment import CommentCreateRequest, CommentNodeResponse
from app.schemas.moment import MomentCreateRequest, MomentResponse, TimelineListResponse, TimelineSort
from app.services.notifications import create_notification
from app.services.upload_references import delete_upload_references_for, sync_moment_upload_references
from app.services.visibility_policy import VisibilityPolicy


router = APIRouter(prefix="/timeline", tags=["timeline"])


_MENTION_UID_PATTERN = re.compile(r"@([0-9a-fA-F\-]{36})")
_MENTION_HANDLE_PATTERN = re.compile(r"@([\w\u4e00-\u9fa5_-]{2,50})")


def _extract_mention_uids(content: str) -> list[str]:
    return list({matched for matched in _MENTION_UID_PATTERN.findall(content)})


def _extract_mention_handles(content: str) -> list[str]:
    return list({matched for matched in _MENTION_HANDLE_PATTERN.findall(content)})


def _resolve_mention_uids(db: Session, handles: list[str]) -> list[str]:
    if not handles:
        return []

    users = (
        db.query(User)
        .filter(User.deleted_at.is_(None))
        .all()
    )

    normalized = {item.strip().lower() for item in handles if item.strip()}
    mention_uids: list[str] = []
    seen: set[str] = set()
    for user in users:
        username = (user.username or "").strip().lower()
        nickname = (user.nickname or "").strip().lower()
        if username in normalized or nickname in normalized:
            if user.uid not in seen:
                seen.add(user.uid)
                mention_uids.append(user.uid)
    return mention_uids


def _unique_str_values(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _comment_to_node(comment: Comment, comments_by_parent: dict[int | None, list[Comment]]) -> CommentNodeResponse:
    children = comments_by_parent.get(comment.id, [])
    return CommentNodeResponse(
        cid=comment.cid,
        parent_cid=comment.parent.cid if comment.parent else None,
        content=comment.content,
        author_uid=comment.author.uid,
        author_nickname=comment.author.nickname,
        mention_uids=comment.mention_uids,
        created_at=comment.created_at,
        replies=[_comment_to_node(child, comments_by_parent) for child in children],
    )


def _build_comment_tree(comments: list[Comment]) -> list[CommentNodeResponse]:
    active_comments = [comment for comment in comments if comment.deleted_at is None]
    comments_by_parent: dict[int | None, list[Comment]] = {}

    for comment in active_comments:
        comments_by_parent.setdefault(comment.parent_id, []).append(comment)

    for siblings in comments_by_parent.values():
        siblings.sort(key=lambda item: item.created_at)

    roots = comments_by_parent.get(None, [])
    return [_comment_to_node(root, comments_by_parent) for root in roots]


def _to_response(moment: Moment) -> MomentResponse:
    return MomentResponse(
        mid=moment.mid,
        author_uid=moment.author.uid,
        author_nickname=moment.author.nickname,
        content=moment.content,
        media_urls=moment.media_urls,
        audio_url=moment.audio_url,
        audio_duration_sec=moment.audio_duration_sec,
        location=moment.location,
        visibility=moment.visibility,
        tags=moment.tags or [],
        timestamp=moment.timestamp,
        comments=_build_comment_tree(list(moment.comments or [])),
    )


@router.post("", response_model=MomentResponse, status_code=status.HTTP_201_CREATED)
def create_moment(
    payload: MomentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> MomentResponse:
    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Idempotency-Key")
        existing = (
            db.query(Moment)
            .options(
                joinedload(Moment.author),
                joinedload(Moment.comments).joinedload(Comment.author),
                joinedload(Moment.comments).joinedload(Comment.parent),
            )
            .filter(
                Moment.author_id == current_user.id,
                Moment.client_idempotency_key == idempotency_key,
                Moment.deleted_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            return _to_response(existing)

    moment = Moment(
        author_id=current_user.id,
        content=payload.content,
        media_urls=payload.media_urls,
        audio_url=payload.audio_url,
        audio_duration_sec=payload.audio_duration_sec if payload.audio_url else None,
        location=payload.location,
        visibility=payload.visibility,
        tags=payload.tags,
        client_idempotency_key=idempotency_key,
    )
    db.add(moment)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if idempotency_key is None:
            raise
        existing = (
            db.query(Moment)
            .options(
                joinedload(Moment.author),
                joinedload(Moment.comments).joinedload(Comment.author),
                joinedload(Moment.comments).joinedload(Comment.parent),
            )
            .filter(
                Moment.author_id == current_user.id,
                Moment.client_idempotency_key == idempotency_key,
                Moment.deleted_at.is_(None),
            )
            .first()
        )
        if existing is None:
            raise
        return _to_response(existing)

    db.refresh(moment)

    moment = (
        db.query(Moment)
        .options(
            joinedload(Moment.author),
            joinedload(Moment.comments).joinedload(Comment.author),
            joinedload(Moment.comments).joinedload(Comment.parent),
        )
        .filter(Moment.id == moment.id, Moment.deleted_at.is_(None))
        .first()
    )
    if moment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moment not found")
    sync_moment_upload_references(db, moment)
    db.commit()
    return _to_response(moment)


@router.get("", response_model=TimelineListResponse)
def list_moments(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    sort: TimelineSort = "desc",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> TimelineListResponse:
    order_clause = Moment.timestamp.desc() if sort == "desc" else Moment.timestamp.asc()
    offset = (page - 1) * page_size

    base_query = db.query(Moment).filter(
        Moment.deleted_at.is_(None),
        VisibilityPolicy.moment_query_filter(current_user),
    )

    total = base_query.with_entities(func.count(Moment.id)).scalar() or 0
    moments = (
        base_query
        .options(
            joinedload(Moment.author),
            joinedload(Moment.comments).joinedload(Comment.author),
            joinedload(Moment.comments).joinedload(Comment.parent),
        )
        .order_by(order_clause)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return TimelineListResponse(
        items=[_to_response(moment) for moment in moments],
        page=page,
        page_size=page_size,
        total=total,
        has_next=(offset + page_size) < total,
        sort=sort,
    )


@router.post("/{mid}/comments", response_model=CommentNodeResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    mid: str,
    payload: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentNodeResponse:
    moment = db.query(Moment).filter(Moment.mid == mid, Moment.deleted_at.is_(None)).first()
    if not moment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moment not found")
    if not VisibilityPolicy.can_view_moment(moment, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to comment on this moment")

    parent_comment: Comment | None = None
    if payload.parent_cid:
        parent_comment = (
            db.query(Comment)
            .filter(
                Comment.cid == payload.parent_cid,
                Comment.moment_id == moment.id,
                Comment.deleted_at.is_(None),
            )
            .first()
        )
        if parent_comment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found")

    comment = Comment(
        target_type=CommentTargetType.moment,
        target_id=mid,
        moment_id=moment.id,
        author_id=current_user.id,
        parent_id=parent_comment.id if parent_comment else None,
        content=payload.content,
    )
    mention_uids = list(payload.mention_uids or [])
    if not mention_uids:
        mention_uids.extend(_extract_mention_uids(payload.content))
        mention_uids.extend(_resolve_mention_uids(db, _extract_mention_handles(payload.content)))
    comment.set_mention_uids(_unique_str_values(mention_uids))

    db.add(comment)
    db.commit()

    created = (
        db.query(Comment)
        .options(joinedload(Comment.author), joinedload(Comment.parent))
        .filter(Comment.id == comment.id)
        .first()
    )
    if created is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    if moment.author_id != current_user.id:
        create_notification(
            db,
            recipient=moment.author,
            type="comment.created",
            title="你的时间轴有新评论",
            body=created.content[:160],
            link="/timeline",
            source_type="comment",
            source_id=created.cid,
            dedupe=True,
        )
    if parent_comment and parent_comment.author_id != current_user.id:
        create_notification(
            db,
            recipient=parent_comment.author,
            type="comment.reply",
            title="有人回复了你的评论",
            body=created.content[:160],
            link="/timeline",
            source_type="comment",
            source_id=f"reply:{created.cid}",
            dedupe=True,
        )
    if created.mention_uids:
        mentioned_users = db.query(User).filter(User.uid.in_(created.mention_uids), User.deleted_at.is_(None)).all()
        for user in mentioned_users:
            if user.id == current_user.id:
                continue
            create_notification(
                db,
                recipient=user,
                type="comment.mention",
                title="有人在评论里提到了你",
                body=created.content[:160],
                link="/timeline",
                source_type="comment",
                source_id=f"mention:{created.cid}:{user.uid}",
                dedupe=True,
            )
    db.commit()

    return CommentNodeResponse(
        cid=created.cid,
        parent_cid=created.parent.cid if created.parent else None,
        content=created.content,
        author_uid=created.author.uid,
        author_nickname=created.author.nickname,
        mention_uids=created.mention_uids,
        created_at=created.created_at,
        replies=[],
    )


@router.get("/memories", response_model=list[MomentResponse])
def list_memories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MomentResponse]:
    """获取今日回忆：历年今日"""
    _ = current_user
    now = datetime.now(timezone.utc)
    from sqlalchemy import extract

    moments = (
        db.query(Moment)
        .options(
            joinedload(Moment.author),
            joinedload(Moment.comments).joinedload(Comment.author),
            joinedload(Moment.comments).joinedload(Comment.parent),
        )
        .filter(
            Moment.deleted_at.is_(None),
            extract("month", Moment.timestamp) == now.month,
            extract("day", Moment.timestamp) == now.day,
            extract("year", Moment.timestamp) < now.year,
        )
        .order_by(Moment.timestamp.desc())
        .all()
    )

    visible = [item for item in moments if VisibilityPolicy.can_view_moment(item, current_user)]
    return [_to_response(moment) for moment in visible]


@router.delete("/{mid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_moment(
    mid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)

    moment = db.query(Moment).filter(Moment.mid == mid, Moment.deleted_at.is_(None)).first()
    if moment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moment not found")

    moment.deleted_at = datetime.now(timezone.utc)
    delete_upload_references_for(db, "moment", moment.id)
    db.commit()
