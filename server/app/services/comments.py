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

"""通用评论服务模块"""
import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.album import Album
from app.models.article import Article
from app.models.comment import Comment, CommentTargetType
from app.models.moment import Moment
from app.models.user import User
from app.schemas.comment import CommentCreateRequest, CommentNodeResponse
from app.services.notifications import create_notification
from app.services.visibility_policy import VisibilityPolicy


_MENTION_UID_PATTERN = re.compile(r"@([0-9a-fA-F\-]{36})")
_MENTION_HANDLE_PATTERN = re.compile(r"@([\w\u4e00-\u9fa5_-]{2,50})")


def _extract_mention_uids(content: str) -> list[str]:
    """从内容中提取 @uid 格式的提及"""
    return list({matched for matched in _MENTION_UID_PATTERN.findall(content)})


def _extract_mention_handles(content: str) -> list[str]:
    """从内容中提取 @username 格式的提及"""
    return list({matched for matched in _MENTION_HANDLE_PATTERN.findall(content)})


def _resolve_mention_uids(db: Session, handles: list[str]) -> list[str]:
    """将用户名/昵称转换为 UID"""
    if not handles:
        return []

    users = db.query(User).filter(User.deleted_at.is_(None)).all()

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
    """去重字符串列表"""
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
    """将评论转换为树形节点"""
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


def build_comment_tree(comments: list[Comment]) -> list[CommentNodeResponse]:
    """构建评论树"""
    active_comments = [comment for comment in comments if comment.deleted_at is None]
    comments_by_parent: dict[int | None, list[Comment]] = {}

    for comment in active_comments:
        comments_by_parent.setdefault(comment.parent_id, []).append(comment)

    for siblings in comments_by_parent.values():
        siblings.sort(key=lambda item: item.created_at)

    roots = comments_by_parent.get(None, [])
    return [_comment_to_node(root, comments_by_parent) for root in roots]


def get_comments_for_target(
    db: Session,
    target_type: CommentTargetType,
    target_id: str,
) -> list[Comment]:
    """获取指定目标的所有评论"""
    return (
        db.query(Comment)
        .options(joinedload(Comment.author), joinedload(Comment.parent))
        .filter(
            Comment.target_type == target_type,
            Comment.target_id == target_id,
            Comment.deleted_at.is_(None),
        )
        .order_by(Comment.created_at.asc())
        .all()
    )


def create_comment(
    db: Session,
    target_type: CommentTargetType,
    target_id: str,
    payload: CommentCreateRequest,
    current_user: User,
) -> CommentNodeResponse:
    """创建评论"""
    # 验证目标是否存在并检查权限
    target_owner: User | None = None
    notification_link = "/"
    notification_title = "你的内容有新评论"

    if target_type == CommentTargetType.moment:
        moment = db.query(Moment).filter(Moment.mid == target_id, Moment.deleted_at.is_(None)).first()
        if not moment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moment not found")
        if not VisibilityPolicy.can_view_moment(moment, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to comment")
        target_owner = moment.author
        notification_link = "/timeline"
        notification_title = "你的时间轴有新评论"

    elif target_type == CommentTargetType.article:
        article = db.query(Article).filter(Article.aid == target_id, Article.deleted_at.is_(None)).first()
        if not article:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if not VisibilityPolicy.can_view_article(article, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to comment")
        target_owner = article.author
        notification_link = f"/articles/{target_id}"
        notification_title = "你的文章有新评论"

    elif target_type == CommentTargetType.album:
        album = db.query(Album).filter(Album.alb_id == target_id, Album.deleted_at.is_(None)).first()
        if not album:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
        if not VisibilityPolicy.can_view_album(album, current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to comment")
        target_owner = album.author
        notification_link = f"/albums/{target_id}"
        notification_title = "你的相册有新评论"

    # 检查父评论
    parent_comment: Comment | None = None
    if payload.parent_cid:
        parent_comment = (
            db.query(Comment)
            .filter(
                Comment.cid == payload.parent_cid,
                Comment.target_type == target_type,
                Comment.target_id == target_id,
                Comment.deleted_at.is_(None),
            )
            .first()
        )
        if parent_comment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found")

    # 创建评论
    comment = Comment(
        target_type=target_type,
        target_id=target_id,
        author_id=current_user.id,
        parent_id=parent_comment.id if parent_comment else None,
        content=payload.content,
    )

    # 处理提及
    mention_uids = list(payload.mention_uids or [])
    if not mention_uids:
        mention_uids.extend(_extract_mention_uids(payload.content))
        mention_uids.extend(_resolve_mention_uids(db, _extract_mention_handles(payload.content)))
    comment.set_mention_uids(_unique_str_values(mention_uids))

    db.add(comment)
    db.commit()

    # 重新加载评论以获取关联数据
    created = (
        db.query(Comment)
        .options(joinedload(Comment.author), joinedload(Comment.parent))
        .filter(Comment.id == comment.id)
        .first()
    )
    if created is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    # 发送通知
    if target_owner and target_owner.id != current_user.id:
        create_notification(
            db,
            recipient=target_owner,
            type="comment.created",
            title=notification_title,
            body=created.content[:160],
            link=notification_link,
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
            link=notification_link,
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
                link=notification_link,
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
