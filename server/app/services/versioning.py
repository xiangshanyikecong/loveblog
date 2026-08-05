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

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.article import Article, ArticleBlock, ArticleBlockType, ArticleStatus
from app.models.content_version import ContentVersion
from app.models.content_visibility import ContentVisibility
from app.models.message import Message
from app.models.user import User


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def article_snapshot(article: Article) -> dict[str, Any]:
    return {
        "aid": article.aid,
        "title": article.title,
        "excerpt": article.excerpt,
        "status": article.status.value,
        "is_encrypted": article.is_encrypted,
        "is_co_created": article.is_co_created,
        "partner_can_edit": article.partner_can_edit,
        "visibility": article.visibility.value,
        "password_hash": article.password_hash,
        "cover_url": article.cover_url,
        "tags": article.tags or [],
        "published_at": _iso(article.published_at),
        "blocks": [
            {
                "bid": block.bid,
                "block_type": block.block_type.value,
                "content": block.content,
                "sort_order": block.sort_order,
                # Persist the original author id so rolling back preserves the
                # co-creator trail. The PUT endpoint also uses this to detect
                # partner-authored blocks during a full-document rewrite.
                "author_id": block.author_id,
            }
            for block in sorted(article.blocks or [], key=lambda item: item.sort_order)
        ],
    }


def message_snapshot(message: Message) -> dict[str, Any]:
    return {
        "msg_id": message.msg_id,
        "content": message.content,
        "is_public": message.is_public,
        "tags": message.tags or [],
        "visitor_name": message.visitor_name,
    }


def _record_version(
    db: Session,
    *,
    content_type: str,
    content_id: str,
    version: int,
    title: str | None,
    snapshot: dict[str, Any],
    actor: User | None,
    note: str | None,
) -> ContentVersion:
    existing = (
        db.query(ContentVersion)
        .filter(
            ContentVersion.content_type == content_type,
            ContentVersion.content_id == content_id,
            ContentVersion.version == version,
        )
        .first()
    )
    if existing is not None:
        return existing

    item = ContentVersion(
        content_type=content_type,
        content_id=content_id,
        version=version,
        title=title,
        snapshot=snapshot,
        actor_id=actor.id if actor else None,
        note=note,
    )
    db.add(item)
    return item


def record_article_version(
    db: Session, article: Article, actor: User | None, note: str | None = None
) -> ContentVersion:
    return _record_version(
        db,
        content_type="article",
        content_id=article.aid,
        version=article.version,
        title=article.title,
        snapshot=article_snapshot(article),
        actor=actor,
        note=note,
    )


def record_message_version(
    db: Session, message: Message, actor: User | None, note: str | None = None
) -> ContentVersion:
    return _record_version(
        db,
        content_type="message",
        content_id=message.msg_id,
        version=message.version,
        title=(message.content[:80] if message.content else None),
        snapshot=message_snapshot(message),
        actor=actor,
        note=note,
    )


def list_content_versions(db: Session, *, content_type: str, content_id: str) -> list[ContentVersion]:
    return (
        db.query(ContentVersion)
        .options(joinedload(ContentVersion.actor))
        .filter(ContentVersion.content_type == content_type, ContentVersion.content_id == content_id)
        .order_by(ContentVersion.version.desc(), ContentVersion.created_at.desc())
        .all()
    )


def version_to_response(item: ContentVersion) -> dict[str, Any]:
    snapshot = item.snapshot
    if item.content_type == "article" and isinstance(snapshot, dict) and "password_hash" in snapshot:
        snapshot = {**snapshot}
        snapshot["has_password"] = bool(snapshot.pop("password_hash"))

    return {
        "vid": item.vid,
        "content_type": item.content_type,
        "content_id": item.content_id,
        "version": item.version,
        "title": item.title,
        "snapshot": snapshot,
        "note": item.note,
        "actor_uid": item.actor.uid if item.actor else None,
        "actor_nickname": item.actor.nickname if item.actor else None,
        "created_at": item.created_at,
    }


def apply_article_snapshot(db: Session, article: Article, snapshot: dict[str, Any], actor: User) -> None:
    article.title = snapshot.get("title") or article.title
    article.excerpt = snapshot.get("excerpt")
    article.status = ArticleStatus(snapshot.get("status", ArticleStatus.draft.value))
    article.is_encrypted = bool(snapshot.get("is_encrypted", False))
    article.is_co_created = bool(snapshot.get("is_co_created", article.is_co_created))
    article.partner_can_edit = bool(snapshot.get("partner_can_edit", False))
    article.visibility = ContentVisibility(snapshot.get("visibility", ContentVisibility.public.value))
    article.password_hash = snapshot.get("password_hash")
    article.cover_url = snapshot.get("cover_url")
    article.tags = list(snapshot.get("tags") or [])
    published_at = snapshot.get("published_at")
    article.published_at = datetime.fromisoformat(published_at) if published_at else None
    article.version += 1

    db.query(ArticleBlock).filter(ArticleBlock.article_id == article.id).delete(synchronize_session=False)
    for block in snapshot.get("blocks") or []:
        # Older snapshots (or hand-rolled ones from import flows) may not have
        # author_id; fall back to the original article author so we never
        # stamp a rollback as the rolling user's own work.
        author_id = block.get("author_id") or article.author_id
        db.add(
            ArticleBlock(
                bid=block.get("bid"),
                article_id=article.id,
                author_id=author_id,
                block_type=ArticleBlockType(block.get("block_type", ArticleBlockType.paragraph.value)),
                content=block.get("content") or "",
                sort_order=int(block.get("sort_order") or 0),
            )
        )


def apply_message_snapshot(message: Message, snapshot: dict[str, Any]) -> None:
    message.content = snapshot.get("content") or message.content
    message.is_public = bool(snapshot.get("is_public", True))
    message.tags = list(snapshot.get("tags") or [])
    message.version += 1
