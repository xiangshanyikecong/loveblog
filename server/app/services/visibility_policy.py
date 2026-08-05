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

from enum import Enum
from typing import TypeVar

from sqlalchemy import and_, false, or_, true
from sqlalchemy.sql.elements import ColumnElement

from app.models.album import Album, AlbumMedia
from app.models.article import Article, ArticleStatus
from app.models.content_visibility import ContentVisibility
from app.models.event import Event, Visibility as EventVisibility
from app.models.message import Message
from app.models.moment import Moment, Visibility as MomentVisibility
from app.models.user import User, UserRole


class VisibilityLevel(str, Enum):
    public = "Public"
    guest_viewable = "GuestViewable"
    partners_only = "PartnersOnly"
    encrypted = "Encrypted"
    private = "Private"
    password_protected = "PasswordProtected"


T = TypeVar("T")


class VisibilityPolicy:
    partner_roles = {UserRole.partner_a, UserRole.partner_b}

    @classmethod
    def is_partner(cls, user: User | None) -> bool:
        return user is not None and user.role in cls.partner_roles

    @classmethod
    def is_guest(cls, user: User | None) -> bool:
        """判断是否为访客（已登录但非伴侣）"""
        return user is not None and user.role not in cls.partner_roles

    @staticmethod
    def is_owner(user: User | None, *, owner_id: int | None = None, owner_uid: str | None = None) -> bool:
        if user is None:
            return False
        if owner_id is not None and user.id == owner_id:
            return True
        return owner_uid is not None and user.uid == owner_uid

    @classmethod
    def normalize(cls, visibility: VisibilityLevel | EventVisibility | MomentVisibility | str) -> VisibilityLevel:
        raw_value = visibility.value if isinstance(visibility, Enum) else visibility
        try:
            return VisibilityLevel(raw_value)
        except ValueError:
            db_value_map = {
                "public": VisibilityLevel.public,
                "guest_viewable": VisibilityLevel.guest_viewable,
                "partners_only": VisibilityLevel.partners_only,
                "encrypted": VisibilityLevel.encrypted,
                "private": VisibilityLevel.private,
                "password_protected": VisibilityLevel.password_protected,
            }
            try:
                return db_value_map[str(raw_value)]
            except KeyError as exc:
                raise ValueError(f"Unsupported visibility value: {raw_value!r}") from exc

    @classmethod
    def can_view_by_visibility(
        cls,
        visibility: ContentVisibility,
        user: User | None,
        *,
        owner_id: int | None = None,
        owner_uid: str | None = None,
    ) -> bool:
        """根据新的ContentVisibility枚举判断是否可见"""
        if visibility == ContentVisibility.public:
            return True
        elif visibility == ContentVisibility.guest_viewable:
            # 访客可见：任何已登录用户都可以查看
            return user is not None
        elif visibility == ContentVisibility.partners_only:
            # 仅两人可见
            return cls.is_partner(user)
        elif visibility == ContentVisibility.private:
            # 仅作者可见
            return cls.is_owner(user, owner_id=owner_id, owner_uid=owner_uid)
        elif visibility == ContentVisibility.password_protected:
            # 密码保护：需要额外验证，这里先返回基础权限（伴侣和作者可以直接访问）
            return cls.is_partner(user) or cls.is_owner(user, owner_id=owner_id, owner_uid=owner_uid)
        return False

    @classmethod
    def can_view_level(
        cls,
        visibility: VisibilityLevel | EventVisibility | MomentVisibility | str,
        user: User | None,
        *,
        owner_id: int | None = None,
        owner_uid: str | None = None,
        partners_can_view_private: bool = False,
    ) -> bool:
        level = cls.normalize(visibility)

        if level == VisibilityLevel.public:
            return True
        if level == VisibilityLevel.guest_viewable:
            return user is not None
        if level in {VisibilityLevel.partners_only, VisibilityLevel.encrypted}:
            return cls.is_partner(user)
        if level == VisibilityLevel.private:
            return cls.is_owner(user, owner_id=owner_id, owner_uid=owner_uid) or (
                partners_can_view_private and cls.is_partner(user)
            )
        if level == VisibilityLevel.password_protected:
            return cls.is_owner(user, owner_id=owner_id, owner_uid=owner_uid) or cls.is_partner(user)
        return False

    @classmethod
    def can_reveal_encrypted(cls, user: User | None) -> bool:
        return cls.is_partner(user)

    @classmethod
    def redact_if_encrypted(cls, value: T | None, *, is_encrypted: bool, user: User | None) -> T | None:
        if not is_encrypted or cls.can_reveal_encrypted(user):
            return value
        return None

    @classmethod
    def event_visibility(cls, event: Event) -> VisibilityLevel:
        return cls.normalize(event.visibility)

    @classmethod
    def moment_visibility(cls, moment: Moment) -> VisibilityLevel:
        return cls.normalize(moment.visibility)

    @classmethod
    def article_visibility(cls, article: Article) -> VisibilityLevel:
        if article.status != ArticleStatus.published:
            return VisibilityLevel.partners_only if article.partner_can_edit else VisibilityLevel.private
        if article.is_encrypted:
            return VisibilityLevel.encrypted
        if hasattr(article, "visibility") and article.visibility:
            return cls.normalize(article.visibility.value)
        return VisibilityLevel.public

    @classmethod
    def album_visibility(cls, album: Album) -> VisibilityLevel:
        if not album.is_public:
            return VisibilityLevel.private
        if album.is_encrypted:
            return VisibilityLevel.encrypted
        if hasattr(album, "visibility") and album.visibility:
            return cls.normalize(album.visibility.value)
        return VisibilityLevel.public

    @classmethod
    def album_media_visibility(cls, media: AlbumMedia) -> VisibilityLevel:
        return VisibilityLevel.encrypted if media.is_encrypted else VisibilityLevel.public

    @classmethod
    def message_visibility(cls, message: Message) -> VisibilityLevel:
        return VisibilityLevel.public if message.is_public else VisibilityLevel.private

    @classmethod
    def can_view_event(cls, event: Event, user: User | None) -> bool:
        return cls.can_view_level(cls.event_visibility(event), user)

    @classmethod
    def can_view_moment(cls, moment: Moment, user: User | None) -> bool:
        return cls.can_view_level(cls.moment_visibility(moment), user)

    @classmethod
    def can_view_article(cls, article: Article, user: User | None, password_verified: bool = False) -> bool:
        if article.status != ArticleStatus.published:
            return cls.is_owner(
                user,
                owner_id=article.author_id,
                owner_uid=getattr(article.author, "uid", None),
            ) or (article.partner_can_edit and cls.is_partner(user))

        if article.is_encrypted and not cls.can_reveal_encrypted(user):
            return False

        if hasattr(article, "visibility") and article.visibility == ContentVisibility.password_protected:
            if cls.is_partner(user) or cls.is_owner(user, owner_id=article.author_id):
                return True
            return password_verified

        if hasattr(article, "visibility") and article.visibility:
            return cls.can_view_by_visibility(
                article.visibility,
                user,
                owner_id=article.author_id,
                owner_uid=getattr(article.author, "uid", None),
            )

        return cls.can_view_level(cls.article_visibility(article), user)

    @classmethod
    def can_view_album(cls, album: Album, user: User | None, password_verified: bool = False) -> bool:
        if not album.is_public and not (
            cls.is_owner(user, owner_id=album.author_id, owner_uid=getattr(album.author, "uid", None))
        ):
            return False

        if album.is_encrypted and not cls.can_reveal_encrypted(user):
            return False

        if hasattr(album, "visibility") and album.visibility == ContentVisibility.password_protected:
            if cls.is_partner(user) or cls.is_owner(user, owner_id=album.author_id):
                return True
            return password_verified

        if hasattr(album, "visibility") and album.visibility:
            return cls.can_view_by_visibility(
                album.visibility,
                user,
                owner_id=album.author_id,
                owner_uid=getattr(album.author, "uid", None),
            )

        return cls.can_view_level(
            cls.album_visibility(album),
            user,
            owner_id=album.author_id,
            owner_uid=getattr(album.author, "uid", None),
            partners_can_view_private=True,
        )

    @classmethod
    def can_view_message(cls, message: Message, user: User | None) -> bool:
        return cls.can_view_level(
            cls.message_visibility(message),
            user,
            owner_id=message.author_id,
            owner_uid=getattr(message.author, "uid", None),
            partners_can_view_private=True,
        )

    @classmethod
    def can_manage_message(cls, message: Message, user: User | None) -> bool:
        return cls.is_owner(
            user,
            owner_id=message.author_id,
            owner_uid=getattr(message.author, "uid", None),
        ) or cls.is_partner(user)

    @classmethod
    def event_query_filter(cls, user: User | None) -> ColumnElement[bool]:
        if cls.is_partner(user):
            return true()
        return Event.visibility == EventVisibility.public

    @classmethod
    def moment_query_filter(cls, user: User | None) -> ColumnElement[bool]:
        if cls.is_partner(user):
            return true()
        return Moment.visibility == MomentVisibility.public

    @classmethod
    def article_query_filter(cls, user: User | None) -> ColumnElement[bool]:
        published = Article.status == ArticleStatus.published
        not_encrypted = Article.is_encrypted.is_(False)

        published_filters: list[ColumnElement[bool]] = [
            and_(published, not_encrypted, Article.visibility == ContentVisibility.public),
        ]

        if user is not None:
            published_filters.extend(
                [
                    and_(published, not_encrypted, Article.visibility == ContentVisibility.guest_viewable),
                    and_(published, Article.visibility == ContentVisibility.private, Article.author_id == user.id),
                    and_(
                        published,
                        Article.visibility == ContentVisibility.password_protected,
                        Article.author_id == user.id,
                    ),
                ]
            )

        if cls.is_partner(user):
            published_filters.extend(
                [
                    and_(published, Article.visibility == ContentVisibility.partners_only),
                    and_(published, Article.visibility == ContentVisibility.password_protected),
                    and_(
                        published,
                        Article.is_encrypted.is_(True),
                        Article.visibility != ContentVisibility.private,
                    ),
                ]
            )

        draft_filters: list[ColumnElement[bool]] = []
        if user is not None:
            draft_filters.append(and_(Article.status != ArticleStatus.published, Article.author_id == user.id))
        if cls.is_partner(user):
            draft_filters.append(
                and_(Article.status != ArticleStatus.published, Article.partner_can_edit.is_(True))
            )

        return or_(*(published_filters + draft_filters))

    @classmethod
    def album_query_filter(cls, user: User | None) -> ColumnElement[bool]:
        public_base = and_(Album.is_public.is_(True), Album.is_encrypted.is_(False))
        filters: list[ColumnElement[bool]] = [
            and_(public_base, Album.visibility == ContentVisibility.public),
        ]

        if user is not None:
            filters.extend(
                [
                    and_(public_base, Album.visibility == ContentVisibility.guest_viewable),
                    and_(Album.visibility == ContentVisibility.private, Album.author_id == user.id),
                    and_(Album.visibility == ContentVisibility.password_protected, Album.author_id == user.id),
                ]
            )

        if cls.is_partner(user):
            filters.extend(
                [
                    and_(Album.is_public.is_(True), Album.visibility == ContentVisibility.partners_only),
                    and_(Album.is_public.is_(True), Album.visibility == ContentVisibility.password_protected),
                    and_(
                        Album.is_public.is_(True),
                        Album.is_encrypted.is_(True),
                        Album.visibility != ContentVisibility.private,
                    ),
                ]
            )

        return or_(*filters)

    @classmethod
    def message_query_filter(cls, user: User | None, *, include_private: bool = False) -> ColumnElement[bool]:
        public_filter = Message.is_public.is_(True)
        if not include_private:
            return public_filter
        if user is None:
            return false()
        if cls.is_partner(user):
            return true()
        return or_(public_filter, Message.author_id == user.id)
