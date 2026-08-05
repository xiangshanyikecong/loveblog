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

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user, get_optional_user
from app.core.security import get_password_hash, verify_password
from app.db.session import get_db
from app.models.album import Album, AlbumMedia
from app.models.comment import CommentTargetType
from app.models.content_visibility import ContentVisibility
from app.models.user import User
from app.schemas.album import (
    AlbumCreateRequest,
    AlbumDetailResponse,
    AlbumListResponse,
    AlbumMediaResponse,
    AlbumSummaryResponse,
    AlbumPatchRequest,
)
from app.schemas.comment import CommentCreateRequest, CommentNodeResponse
from app.services.comments import build_comment_tree, create_comment, get_comments_for_target
from app.services.audit import write_audit_log
from app.services.content_access import grant_content_access, has_content_access
from app.services.upload_references import delete_upload_references_for, sync_album_upload_references
from app.services.visibility_policy import VisibilityPolicy


router = APIRouter(prefix="/albums", tags=["albums"])


def _ensure_album_write_access(
    album: Album,
    current_user: User,
    *,
    target_is_public: bool | None = None,
    target_visibility: ContentVisibility | None = None,
) -> None:
    if album.author_id == current_user.id:
        return
    becomes_private = (
        target_is_public is False
        or (
            target_visibility is not None
            and target_visibility != ContentVisibility.public
        )
    )
    if not album.is_public or album.visibility != ContentVisibility.public or becomes_private:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the author can modify a private album",
        )


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


def _mask_if_encrypted(value: str | None, album: Album, user: User | None) -> str | None:
    return VisibilityPolicy.redact_if_encrypted(value, is_encrypted=album.is_encrypted, user=user)


def _media_to_response(item: AlbumMedia, album: Album, user: User | None) -> AlbumMediaResponse:
    can_reveal = not item.is_encrypted or VisibilityPolicy.can_reveal_encrypted(user)

    return AlbumMediaResponse(
        media_id=item.media_id,
        media_type=item.media_type,
        file_url=item.file_url if can_reveal else "",
        thumbnail_url=item.thumbnail_url if can_reveal else None,
        file_size=item.file_size if can_reveal else None,
        mime_type=item.mime_type if can_reveal else None,
        is_encrypted=item.is_encrypted,
    )


def _album_to_summary(album: Album, user: User | None) -> AlbumSummaryResponse:
    return AlbumSummaryResponse(
        alb_id=album.alb_id,
        title=album.title,
        description=_mask_if_encrypted(album.description, album, user),
        cover_url=_mask_if_encrypted(album.cover_url, album, user),
        is_encrypted=album.is_encrypted,
        is_public=album.is_public,
        visibility=album.visibility,
        requires_password=album.password_hash is not None and album.visibility == ContentVisibility.password_protected,
        tags=album.tags or [],
        author_uid=album.author.uid,
        author_nickname=album.author.nickname,
        media_count=len(album.media_items),
        created_at=album.created_at,
    )


def _album_to_detail(album: Album, user: User | None, db: Session) -> AlbumDetailResponse:
    summary = _album_to_summary(album, user)

    # 获取评论
    comments = get_comments_for_target(db, CommentTargetType.album, album.alb_id)
    comment_tree = build_comment_tree(comments)

    return AlbumDetailResponse(
        **summary.model_dump(),
        media_items=[_media_to_response(item, album, user) for item in album.media_items],
        comments=comment_tree,
    )


@router.post("", response_model=AlbumDetailResponse, status_code=status.HTTP_201_CREATED)
def create_album(
    payload: AlbumCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlbumDetailResponse:
    ensure_partner(current_user)

    password_hash = _password_hash_for_visibility(
        visibility=payload.visibility,
        password=payload.password,
    )

    album = Album(
        author_id=current_user.id,
        title=payload.title,
        description=payload.description,
        cover_url=payload.cover_url,
        is_encrypted=payload.is_encrypted,
        is_public=payload.is_public,
        visibility=payload.visibility,
        password_hash=password_hash,
        tags=payload.tags,
    )
    db.add(album)
    db.flush()

    for item in payload.media_items:
        db.add(
            AlbumMedia(
                album_id=album.id,
                media_type=item.media_type,
                file_url=item.file_url,
                thumbnail_url=item.thumbnail_url,
                file_size=item.file_size,
                mime_type=item.mime_type,
                is_encrypted=item.is_encrypted,
            )
        )

    db.commit()

    album = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .filter(Album.id == album.id, Album.deleted_at.is_(None))
        .first()
    )
    sync_album_upload_references(db, album)
    db.commit()
    return _album_to_detail(album, current_user, db)


@router.get("", response_model=AlbumListResponse)
def list_albums(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> AlbumListResponse:
    items = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .filter(Album.deleted_at.is_(None), VisibilityPolicy.album_query_filter(current_user))
        .order_by(Album.created_at.desc())
        .all()
    )

    return AlbumListResponse(
        items=[_album_to_summary(item, current_user) for item in items],
        total=len(items),
    )


@router.get("/{alb_id}", response_model=AlbumDetailResponse)
def get_album(
    alb_id: str,
    request: Request,
    response: Response,
    content_password: str | None = Header(default=None, alias="X-Content-Password"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> AlbumDetailResponse:
    album = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .filter(Album.alb_id == alb_id, Album.deleted_at.is_(None))
        .first()
    )
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    # 检查密码保护
    password_verified = has_content_access(
        request,
        content_kind="album",
        content_id=album.id,
        password_hash=album.password_hash,
    )
    password_granted_now = False
    if album.visibility == ContentVisibility.password_protected and album.password_hash:
        # 伴侣和作者可以直接访问
        if not (
            VisibilityPolicy.is_partner(current_user)
            or VisibilityPolicy.is_owner(current_user, owner_id=album.author_id)
        ):
            if not password_verified and not content_password:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Password required for this content"
                )
            if not password_verified and not verify_password(content_password or "", album.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Incorrect password"
                )
            if not password_verified:
                grant_content_access(
                    response,
                    request,
                    content_kind="album",
                    content_id=album.id,
                    password_hash=album.password_hash,
                )
                password_verified = True
                password_granted_now = True

    if not VisibilityPolicy.can_view_album(album, current_user, password_verified=password_verified):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to view album")

    result = _album_to_detail(album, current_user, db)
    if password_granted_now:
        write_audit_log(
            db,
            action="content.access",
            actor=current_user,
            resource_type="album",
            resource_id=album.alb_id,
            resource_name=album.title,
            detail={"method": "content_password"},
        )
    return result


@router.put("/{alb_id}", response_model=AlbumDetailResponse)
def update_album(
    alb_id: str,
    payload: AlbumCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlbumDetailResponse:
    ensure_partner(current_user)

    album = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .filter(Album.alb_id == alb_id, Album.deleted_at.is_(None))
        .first()
    )
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    _ensure_album_write_access(
        album,
        current_user,
        target_is_public=payload.is_public,
        target_visibility=payload.visibility,
    )

    album.title = payload.title
    album.description = payload.description
    album.cover_url = payload.cover_url
    album.is_encrypted = payload.is_encrypted
    album.is_public = payload.is_public
    album.visibility = payload.visibility
    album.password_hash = _password_hash_for_visibility(
        visibility=payload.visibility,
        password=payload.password,
        existing_hash=album.password_hash,
    )
    album.tags = payload.tags

    db.query(AlbumMedia).filter(AlbumMedia.album_id == album.id).delete(synchronize_session=False)
    for item in payload.media_items:
        db.add(
            AlbumMedia(
                album_id=album.id,
                media_type=item.media_type,
                file_url=item.file_url,
                thumbnail_url=item.thumbnail_url,
                file_size=item.file_size,
                mime_type=item.mime_type,
                is_encrypted=item.is_encrypted,
            )
        )

    db.commit()

    album = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .filter(Album.id == album.id, Album.deleted_at.is_(None))
        .first()
    )
    sync_album_upload_references(db, album)
    db.commit()
    return _album_to_detail(album, current_user, db)


@router.patch("/{alb_id}", response_model=AlbumDetailResponse)
def patch_album(
    alb_id: str,
    payload: AlbumPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlbumDetailResponse:
    ensure_partner(current_user)

    album = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .filter(Album.alb_id == alb_id, Album.deleted_at.is_(None))
        .first()
    )
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    update_data = payload.model_dump(exclude_unset=True)
    _ensure_album_write_access(
        album,
        current_user,
        target_is_public=update_data.get("is_public"),
        target_visibility=update_data.get("visibility"),
    )
    if "title" in update_data:
        album.title = update_data["title"]
    if "description" in update_data:
        album.description = update_data["description"]
    if "cover_url" in update_data:
        album.cover_url = update_data["cover_url"]
    if "is_encrypted" in update_data:
        album.is_encrypted = update_data["is_encrypted"]
    if "is_public" in update_data:
        album.is_public = update_data["is_public"]
    if "visibility" in update_data:
        album.visibility = update_data["visibility"]
    if "password" in update_data:
        # 处理密码更新
        password_value = update_data["password"]
        if password_value == "":
            # 空字符串表示清除密码
            album.password_hash = None
        elif password_value:
            # 设置新密码
            album.password_hash = get_password_hash(password_value)
    if "tags" in update_data:
        album.tags = update_data["tags"]
    if album.visibility == ContentVisibility.password_protected and not album.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required when visibility is password_protected",
        )

    db.commit()
    album = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .filter(Album.id == album.id, Album.deleted_at.is_(None))
        .first()
    )
    sync_album_upload_references(db, album)
    db.commit()
    return _album_to_detail(album, current_user, db)


@router.delete("/{alb_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_album(
    alb_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)
    album = db.query(Album).filter(Album.alb_id == alb_id, Album.deleted_at.is_(None)).first()
    if album is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")

    _ensure_album_write_access(album, current_user)

    album.deleted_at = datetime.now(timezone.utc)
    delete_upload_references_for(db, "album", album.id)
    db.commit()


@router.post("/{alb_id}/comments", response_model=CommentNodeResponse, status_code=status.HTTP_201_CREATED)
def create_album_comment(
    alb_id: str,
    payload: CommentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentNodeResponse:
    """为相册创建评论"""
    return create_comment(db, CommentTargetType.album, alb_id, payload, current_user)
