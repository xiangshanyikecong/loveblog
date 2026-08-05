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

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import can_co_edit, ensure_partner, get_current_user, get_optional_user
from app.core.i18n import get_message
from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models.article import Article, ArticleBlock, ArticleStatus
from app.models.comment import CommentTargetType
from app.models.content_visibility import ContentVisibility
from app.models.user import User
from app.schemas.article import (
    ArticleCreateRequest,
    ArticleDetailResponse,
    ArticleListResponse,
    ArticleSummaryResponse,
    ArticleBlockResponse,
    ArticlePatchRequest,
)
from app.schemas.comment import CommentCreateRequest, CommentNodeResponse
from app.schemas.version import ContentVersionListResponse
from app.services.audit import write_audit_log
from app.services.comments import build_comment_tree, create_comment, get_comments_for_target
from app.services.content_access import grant_content_access, has_content_access
from app.services.upload_references import delete_upload_references_for, sync_article_upload_references
from app.services.versioning import (
    apply_article_snapshot,
    list_content_versions,
    record_article_version,
    version_to_response,
)
from app.services.visibility_policy import VisibilityPolicy


router = APIRouter(prefix="/articles", tags=["articles"])


def _password_hash_for_visibility(
    *,
    visibility: ContentVisibility,
    password: str | None,
    existing_hash: str | None = None,
) -> str | None:
    if visibility != ContentVisibility.password_protected:
        return existing_hash
    if password:
        return get_password_hash(password)
    if existing_hash:
        return existing_hash
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Password is required when visibility is password_protected",
    )


def _mask_if_encrypted(text: str | None, article: Article, user: User | None) -> str | None:
    return VisibilityPolicy.redact_if_encrypted(text, is_encrypted=article.is_encrypted, user=user)


def _block_to_response(block: ArticleBlock, article: Article, user: User | None) -> ArticleBlockResponse:
    content = block.content
    if article.is_encrypted and not VisibilityPolicy.can_reveal_encrypted(user):
        content = "加密内容，请登录后查看"

    return ArticleBlockResponse(
        bid=block.bid,
        block_type=block.block_type,
        content=content,
        sort_order=block.sort_order,
        author_uid=block.author.uid,
        author_nickname=block.author.nickname,
    )


def _collect_collaborator_uids(article: Article) -> list[str]:
    """Return unique uids of all users who ever saved a block on this article.

    The original author is always included so the UI can render their avatar
    even if they never edited after the first publish. Partner edits will
    automatically extend this list, which is what powers the "共同创作" badge
    and the collaborators row in the detail view.
    """
    uids: set[str] = set()
    if article.author is not None:
        uids.add(article.author.uid)
    for block in article.blocks:
        if block.author is not None:
            uids.add(block.author.uid)
    return sorted(uids)


def _article_to_summary(article: Article, user: User | None) -> ArticleSummaryResponse:
    excerpt = _mask_if_encrypted(article.excerpt, article, user)

    return ArticleSummaryResponse(
        aid=article.aid,
        title=article.title,
        excerpt=excerpt,
        status=article.status,
        is_encrypted=article.is_encrypted,
        is_co_created=article.is_co_created,
        partner_can_edit=article.partner_can_edit,
        visibility=article.visibility,
        requires_password=(
            article.password_hash is not None
            and article.visibility == ContentVisibility.password_protected
        ),
        tags=article.tags or [],
        version=article.version,
        author_uid=article.author.uid,
        author_nickname=article.author.nickname,
        published_at=article.published_at,
        created_at=article.created_at,
        collaborator_uids=_collect_collaborator_uids(article),
    )


def _article_to_detail(article: Article, user: User | None, db: Session) -> ArticleDetailResponse:
    summary = _article_to_summary(article, user)
    blocks = [_block_to_response(item, article, user) for item in article.blocks]

    # 获取评论
    comments = get_comments_for_target(db, CommentTargetType.article, article.aid)
    comment_tree = build_comment_tree(comments)

    return ArticleDetailResponse(
        **summary.model_dump(),
        blocks=blocks,
        comments=comment_tree,
    )


def _parse_if_match(if_match: str | None) -> int | None:
    """Parse an ``If-Match`` header value into a version int.

    Accepts either a bare integer (``"If-Match: 5"``) or a quoted ETag
    (``'If-Match: "5"'``). Returns ``None`` when the header is absent, blank,
    malformed, or non-positive — in which case the caller should treat the
    request as an unconditional write.
    """
    if not if_match:
        return None
    raw = if_match.strip().strip('"').strip("'")
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _ensure_if_match(article: Article, if_match: str | None) -> None:
    """Raise 409 when the client sent ``If-Match`` that no longer matches.

    This is a lightweight optimistic-concurrency guard so two partners editing
    the same article at the same time don't silently clobber each other. If
    the client didn't send ``If-Match`` at all we don't enforce it — the
    request is treated as "last write wins" so older integrations keep
    working.
    """
    expected = _parse_if_match(if_match)
    if expected is None:
        return
    if expected != article.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "article_version_conflict",
                "message": get_message("error.article_version_conflict"),
                "current_version": article.version,
                "expected_version": expected,
            },
        )


@router.post("", response_model=ArticleDetailResponse, status_code=status.HTTP_201_CREATED)
def create_article(
    payload: ArticleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailResponse:
    ensure_partner(current_user)

    password_hash = _password_hash_for_visibility(
        visibility=payload.visibility,
        password=payload.password,
    )

    article = Article(
        author_id=current_user.id,
        title=payload.title,
        excerpt=payload.excerpt,
        status=payload.status,
        is_encrypted=payload.is_encrypted,
        is_co_created=payload.is_co_created,
        partner_can_edit=payload.partner_can_edit,
        visibility=payload.visibility,
        password_hash=password_hash,
        cover_url=payload.cover_url,
        tags=payload.tags,
        published_at=datetime.now(timezone.utc) if payload.status == ArticleStatus.published else None,
    )
    db.add(article)
    db.flush()

    blocks: list[ArticleBlock] = []
    for item in payload.blocks:
        blocks.append(
            ArticleBlock(
                article_id=article.id,
                author_id=current_user.id,
                block_type=item.block_type,
                content=item.content,
                sort_order=item.sort_order,
            )
        )
    db.add_all(blocks)
    db.commit()

    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.id == article.id, Article.deleted_at.is_(None))
        .first()
    )
    sync_article_upload_references(db, article)
    db.commit()
    response = _article_to_detail(article, current_user, db)
    record_article_version(db, article, current_user, "created")
    write_audit_log(
        db,
        action="article.create",
        actor=current_user,
        resource_type="article",
        resource_id=article.aid,
        resource_name=article.title,
        detail={
            "status": article.status.value,
            "is_encrypted": article.is_encrypted,
            "is_co_created": article.is_co_created,
            "visibility": article.visibility.value,
            "block_count": len(article.blocks),
        },
    )
    return response


@router.get("", response_model=ArticleListResponse)
def list_articles(
    only_published: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ArticleListResponse:
    query = (
        db.query(Article)
        .options(joinedload(Article.author))
        .filter(Article.deleted_at.is_(None), VisibilityPolicy.article_query_filter(current_user))
        .order_by(Article.created_at.desc())
    )

    if only_published:
        query = query.filter(Article.status == ArticleStatus.published)

    visible = query.all()
    return ArticleListResponse(
        items=[_article_to_summary(item, current_user) for item in visible],
        total=len(visible),
    )


@router.get("/{aid}", response_model=ArticleDetailResponse)
def get_article(
    aid: str,
    request: Request,
    response: Response,
    content_password: str | None = Header(default=None, alias="X-Content-Password"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ArticleDetailResponse:
    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.aid == aid, Article.deleted_at.is_(None))
        .first()
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    # 检查密码保护
    password_verified = has_content_access(
        request,
        content_kind="article",
        content_id=article.id,
        password_hash=article.password_hash,
    )
    password_granted_now = False
    if article.visibility == ContentVisibility.password_protected and article.password_hash:
        # 伴侣和作者可以直接访问
        if not (
            VisibilityPolicy.is_partner(current_user)
            or VisibilityPolicy.is_owner(current_user, owner_id=article.author_id)
        ):
            if not password_verified and not content_password:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Password required for this content"
                )
            if not password_verified and not verify_password(content_password or "", article.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Incorrect password"
                )
            if not password_verified:
                grant_content_access(
                    response,
                    request,
                    content_kind="article",
                    content_id=article.id,
                    password_hash=article.password_hash,
                )
                password_verified = True
                password_granted_now = True

    if not VisibilityPolicy.can_view_article(article, current_user, password_verified=password_verified):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to view article")

    # Expose the article's current version as an ETag so clients that send
    # `If-Match` on subsequent writes can detect mid-air collisions with
    # co-editing partners without having to track the version themselves.
    response.headers["ETag"] = f'"{article.version}"'
    result = _article_to_detail(article, current_user, db)
    if password_granted_now:
        write_audit_log(
            db,
            action="content.access",
            actor=current_user,
            resource_type="article",
            resource_id=article.aid,
            resource_name=article.title,
            detail={"method": "content_password"},
        )
    return result


@router.put("/{aid}", response_model=ArticleDetailResponse)
def update_article(
    aid: str,
    payload: ArticleCreateRequest,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailResponse:
    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.aid == aid, Article.deleted_at.is_(None))
        .first()
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    if not can_co_edit(article.author.uid, article.partner_can_edit, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to edit article")

    _ensure_if_match(article, if_match)
    record_article_version(db, article, current_user, "before update")
    article.title = payload.title
    article.excerpt = payload.excerpt
    article.status = payload.status
    article.is_encrypted = payload.is_encrypted
    article.is_co_created = payload.is_co_created
    article.partner_can_edit = payload.partner_can_edit
    article.visibility = payload.visibility
    article.password_hash = _password_hash_for_visibility(
        visibility=payload.visibility,
        password=payload.password,
        existing_hash=article.password_hash,
    )
    article.cover_url = payload.cover_url
    article.tags = payload.tags
    if payload.status == ArticleStatus.published and article.published_at is None:
        article.published_at = datetime.now(timezone.utc)
    article.version += 1

    db.query(ArticleBlock).filter(ArticleBlock.article_id == article.id).delete(synchronize_session=False)
    is_partner_edit = article.author_id != current_user.id
    for item in payload.blocks:
        # Preserve the original block's author when the partner didn't touch
        # the line: comparing by `bid` keeps a stable authorship trail across
        # full-document rewrites so collaborator_uids stays accurate.
        existing = next(
            (b for b in article.blocks if b.bid == item.bid), None
        ) if item.bid else None
        block_author_id = existing.author_id if existing else current_user.id
        db.add(
            ArticleBlock(
                article_id=article.id,
                author_id=block_author_id,
                block_type=item.block_type,
                content=item.content,
                sort_order=item.sort_order,
            )
        )

    # A partner actually writing content turns the article into a co-creation
    # regardless of the payload flag, so we don't silently lose the audit
    # trail of who contributed. The original author can still flip it off
    # later via PATCH if they really want to.
    if is_partner_edit and not article.is_co_created:
        article.is_co_created = True

    db.commit()

    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.id == article.id, Article.deleted_at.is_(None))
        .first()
    )
    sync_article_upload_references(db, article)
    db.commit()
    record_article_version(db, article, current_user, "updated")
    db.commit()
    response.headers["ETag"] = f'"{article.version}"'
    return _article_to_detail(article, current_user, db)


@router.patch("/{aid}", response_model=ArticleDetailResponse)
def patch_article(
    aid: str,
    payload: ArticlePatchRequest,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailResponse:
    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.aid == aid, Article.deleted_at.is_(None))
        .first()
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    if not can_co_edit(article.author.uid, article.partner_can_edit, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to edit article")

    _ensure_if_match(article, if_match)
    record_article_version(db, article, current_user, "before patch")
    update_data = payload.model_dump(exclude_unset=True)
    if "title" in update_data:
        article.title = update_data["title"]
    if "excerpt" in update_data:
        article.excerpt = update_data["excerpt"]
    if "status" in update_data:
        new_status = update_data["status"]
        article.status = new_status
        if new_status == ArticleStatus.published and article.published_at is None:
            article.published_at = datetime.now(timezone.utc)
    if "is_encrypted" in update_data:
        article.is_encrypted = update_data["is_encrypted"]
    if "is_co_created" in update_data:
        article.is_co_created = update_data["is_co_created"]
    if "partner_can_edit" in update_data:
        article.partner_can_edit = update_data["partner_can_edit"]
    if "visibility" in update_data:
        article.visibility = update_data["visibility"]
    if "password" in update_data:
        # 处理密码更新
        password_value = update_data["password"]
        if password_value == "":
            # 空字符串表示清除密码
            article.password_hash = None
        elif password_value:
            # 设置新密码
            article.password_hash = get_password_hash(password_value)
    if "cover_url" in update_data:
        article.cover_url = update_data["cover_url"]
    if "tags" in update_data:
        article.tags = update_data["tags"]
    if article.visibility == ContentVisibility.password_protected and not article.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required when visibility is password_protected",
        )
    article.version += 1

    db.commit()
    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.id == article.id, Article.deleted_at.is_(None))
        .first()
    )
    sync_article_upload_references(db, article)
    db.commit()
    record_article_version(db, article, current_user, "patched")
    db.commit()
    response.headers["ETag"] = f'"{article.version}"'
    return _article_to_detail(article, current_user, db)


@router.get("/{aid}/versions", response_model=ContentVersionListResponse)
def list_article_versions(
    aid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContentVersionListResponse:
    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.aid == aid, Article.deleted_at.is_(None))
        .first()
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    if not can_co_edit(article.author.uid, article.partner_can_edit, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to view article history")

    record_article_version(db, article, current_user, "current snapshot")
    db.commit()
    versions = list_content_versions(db, content_type="article", content_id=aid)
    return ContentVersionListResponse(
        items=[version_to_response(item) for item in versions],
        total=len(versions),
    )


@router.post("/{aid}/versions/{version}/rollback", response_model=ArticleDetailResponse)
def rollback_article_version(
    aid: str,
    version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArticleDetailResponse:
    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.aid == aid, Article.deleted_at.is_(None))
        .first()
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    if not can_co_edit(article.author.uid, article.partner_can_edit, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to rollback article")

    record_article_version(db, article, current_user, "before rollback")
    target = next(
        (item for item in list_content_versions(db, content_type="article", content_id=aid) if item.version == version),
        None,
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

    apply_article_snapshot(db, article, target.snapshot, current_user)
    db.commit()

    article = (
        db.query(Article)
        .options(joinedload(Article.author), joinedload(Article.blocks).joinedload(ArticleBlock.author))
        .filter(Article.id == article.id, Article.deleted_at.is_(None))
        .first()
    )
    record_article_version(db, article, current_user, f"rollback to v{version}")
    write_audit_log(
        db,
        action="article.rollback",
        actor=current_user,
        resource_type="article",
        resource_id=article.aid,
        resource_name=article.title,
        detail={"target_version": version, "new_version": article.version},
    )
    return _article_to_detail(article, current_user, db)


@router.delete("/{aid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_article(
    aid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    article = db.query(Article).filter(Article.aid == aid, Article.deleted_at.is_(None)).first()
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")

    if not can_co_edit(article.author.uid, article.partner_can_edit, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to delete article")

    article.deleted_at = datetime.now(timezone.utc)
    delete_upload_references_for(db, "article", article.id)
    deleted_aid = article.aid
    deleted_title = article.title
    db.commit()
    write_audit_log(
        db,
        action="article.delete",
        actor=current_user,
        resource_type="article",
        resource_id=deleted_aid,
        resource_name=deleted_title,
    )


@router.post("/{aid}/comments", response_model=CommentNodeResponse, status_code=status.HTTP_201_CREATED)
def create_article_comment(
    aid: str,
    payload: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentNodeResponse:
    """为文章创建评论"""
    return create_comment(db, CommentTargetType.article, aid, payload, current_user)
