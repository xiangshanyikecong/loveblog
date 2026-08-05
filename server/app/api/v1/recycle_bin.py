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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.album import Album
from app.models.article import Article
from app.models.comment import Comment, CommentTargetType
from app.models.content_version import ContentVersion
from app.models.event import Event
from app.models.message import Message
from app.models.moment import Moment
from app.models.notification import Notification
from app.models.user import User
from app.services.audit import write_audit_log
from app.services.upload_references import (
    delete_upload_references_for,
    sync_album_upload_references,
    sync_article_upload_references,
    sync_moment_upload_references,
)

router = APIRouter(prefix="/recycle-bin", tags=["recycle-bin"])


class RecycleBinItem(BaseModel):
    id: str
    type: str
    title: str
    deleted_at: datetime | None


class RecycleBinResponse(BaseModel):
    items: list[RecycleBinItem]
    total: int


def _delete_comments_for_target(db: Session, *, target_type: CommentTargetType, target_id: str) -> None:
    comments = (
        db.query(Comment)
        .filter(Comment.target_type == target_type, Comment.target_id == target_id)
        .order_by(Comment.parent_id.desc(), Comment.id.desc())
        .all()
    )
    for comment in comments:
        db.delete(comment)


def _delete_comments_for_moment(db: Session, moment: Moment) -> None:
    comments = (
        db.query(Comment)
        .filter(
            or_(
                Comment.moment_id == moment.id,
                (Comment.target_type == CommentTargetType.moment) & (Comment.target_id == moment.mid),
            )
        )
        .order_by(Comment.parent_id.desc(), Comment.id.desc())
        .all()
    )
    for comment in comments:
        db.delete(comment)


def _restore_deleted_item(db: Session, *, item_type: str, item_id: str) -> bool:
    if item_type == "article":
        article = db.query(Article).filter(Article.aid == item_id, Article.deleted_at.isnot(None)).first()
        if article is None:
            return False
        article.deleted_at = None
        db.flush()
        sync_article_upload_references(db, article)
        return True

    if item_type == "album":
        album = db.query(Album).filter(Album.alb_id == item_id, Album.deleted_at.isnot(None)).first()
        if album is None:
            return False
        album.deleted_at = None
        db.flush()
        sync_album_upload_references(db, album)
        return True

    if item_type == "event":
        event = db.query(Event).filter(Event.eid == item_id, Event.deleted_at.isnot(None)).first()
        if event is None:
            return False
        event.deleted_at = None
        return True

    if item_type == "moment":
        moment = db.query(Moment).filter(Moment.mid == item_id, Moment.deleted_at.isnot(None)).first()
        if moment is None:
            return False
        moment.deleted_at = None
        db.flush()
        sync_moment_upload_references(db, moment)
        return True

    if item_type == "message":
        message = db.query(Message).filter(Message.msg_id == item_id, Message.is_deleted.is_(True)).first()
        if message is None:
            return False
        message.is_deleted = False
        return True

    return False


def _hard_delete_item(db: Session, *, item_type: str, item_id: str) -> bool:
    if item_type == "article":
        article = db.query(Article).filter(Article.aid == item_id, Article.deleted_at.isnot(None)).first()
        if article is None:
            return False
        _delete_comments_for_target(db, target_type=CommentTargetType.article, target_id=article.aid)
        db.query(ContentVersion).filter(
            ContentVersion.content_type == "article",
            ContentVersion.content_id == article.aid,
        ).delete(synchronize_session=False)
        delete_upload_references_for(db, "article", article.id)
        db.delete(article)
        return True

    if item_type == "album":
        album = db.query(Album).filter(Album.alb_id == item_id, Album.deleted_at.isnot(None)).first()
        if album is None:
            return False
        _delete_comments_for_target(db, target_type=CommentTargetType.album, target_id=album.alb_id)
        delete_upload_references_for(db, "album", album.id)
        db.delete(album)
        return True

    if item_type == "event":
        event = db.query(Event).filter(Event.eid == item_id, Event.deleted_at.isnot(None)).first()
        if event is None:
            return False
        db.query(Notification).filter(
            Notification.source_type == "event",
            Notification.source_id.like(f"{event.eid}:%"),
        ).delete(synchronize_session=False)
        db.delete(event)
        return True

    if item_type == "moment":
        moment = db.query(Moment).filter(Moment.mid == item_id, Moment.deleted_at.isnot(None)).first()
        if moment is None:
            return False
        _delete_comments_for_moment(db, moment)
        delete_upload_references_for(db, "moment", moment.id)
        db.delete(moment)
        return True

    if item_type == "message":
        message = db.query(Message).filter(Message.msg_id == item_id, Message.is_deleted.is_(True)).first()
        if message is None:
            return False
        db.query(ContentVersion).filter(
            ContentVersion.content_type == "message",
            ContentVersion.content_id == message.msg_id,
        ).delete(synchronize_session=False)
        db.query(Notification).filter(
            Notification.source_type == "message",
            Notification.source_id == message.msg_id,
        ).delete(synchronize_session=False)
        db.delete(message)
        return True

    return False


@router.get("", response_model=RecycleBinResponse)
def get_recycle_bin(
    type: str = Query(None, description="Filter by type: article, album, event, moment, message"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_partner(current_user)

    items: list[RecycleBinItem] = []

    if type in [None, "article"]:
        for article in db.query(Article).filter(Article.deleted_at.isnot(None)).all():
            items.append(
                RecycleBinItem(
                    id=article.aid,
                    type="article",
                    title=article.title,
                    deleted_at=article.deleted_at,
                )
            )

    if type in [None, "album"]:
        for album in db.query(Album).filter(Album.deleted_at.isnot(None)).all():
            items.append(
                RecycleBinItem(
                    id=album.alb_id,
                    type="album",
                    title=album.title,
                    deleted_at=album.deleted_at,
                )
            )

    if type in [None, "event"]:
        for event in db.query(Event).filter(Event.deleted_at.isnot(None)).all():
            items.append(
                RecycleBinItem(
                    id=event.eid,
                    type="event",
                    title=event.title,
                    deleted_at=event.deleted_at,
                )
            )

    if type in [None, "moment"]:
        for moment in db.query(Moment).filter(Moment.deleted_at.isnot(None)).all():
            title = moment.content[:50] + "..." if len(moment.content) > 50 else moment.content
            items.append(
                RecycleBinItem(
                    id=moment.mid,
                    type="moment",
                    title=title,
                    deleted_at=moment.deleted_at,
                )
            )

    if type in [None, "message"]:
        for message in db.query(Message).filter(Message.is_deleted.is_(True)).all():
            title = message.content[:50] + "..." if len(message.content) > 50 else message.content
            items.append(
                RecycleBinItem(
                    id=message.msg_id,
                    type="message",
                    title=title,
                    deleted_at=message.updated_at,
                )
            )

    items.sort(key=lambda item: item.deleted_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return RecycleBinResponse(items=items, total=len(items))


@router.post("/{type}/{id}/restore", status_code=status.HTTP_200_OK)
def restore_item(
    type: str,
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_partner(current_user)
    if _restore_deleted_item(db, item_type=type, item_id=id):
        db.commit()
        return {"detail": "Restored successfully"}
    raise HTTPException(status_code=404, detail="Item not found or not deleted")


@router.delete("/{type}/{id}", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_item(
    type: str,
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_partner(current_user)
    if _hard_delete_item(db, item_type=type, item_id=id):
        db.commit()
        return
    raise HTTPException(status_code=404, detail="Item not found or not deleted")


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_recycle_bin(
    type: str = Query(None, description="Type to clear, or omit to clear all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_partner(current_user)

    type_names = [type] if type else ["article", "album", "event", "moment", "message"]
    for item_type in type_names:
        if item_type == "article":
            item_ids = [item.aid for item in db.query(Article).filter(Article.deleted_at.isnot(None)).all()]
        elif item_type == "album":
            item_ids = [item.alb_id for item in db.query(Album).filter(Album.deleted_at.isnot(None)).all()]
        elif item_type == "event":
            item_ids = [item.eid for item in db.query(Event).filter(Event.deleted_at.isnot(None)).all()]
        elif item_type == "moment":
            item_ids = [item.mid for item in db.query(Moment).filter(Moment.deleted_at.isnot(None)).all()]
        elif item_type == "message":
            item_ids = [item.msg_id for item in db.query(Message).filter(Message.is_deleted.is_(True)).all()]
        else:
            raise HTTPException(status_code=400, detail="Unsupported recycle bin type")

        for item_id in item_ids:
            _hard_delete_item(db, item_type=item_type, item_id=item_id)

    db.commit()
    write_audit_log(
        db,
        action="recycle_bin.clear",
        actor=current_user,
        resource_type="recycle_bin",
        resource_id="all",
        resource_name="Clear Recycle Bin",
        detail={"cleared_type": type if type else "all"},
    )
