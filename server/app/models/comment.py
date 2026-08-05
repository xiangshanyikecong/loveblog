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

import enum
import json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CommentTargetType(str, enum.Enum):
    moment = "Moment"
    article = "Article"
    album = "Album"


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    # 支持多种内容类型的评论
    target_type: Mapped[CommentTargetType] = mapped_column(
        Enum(CommentTargetType, name="comment_target_type"),
        default=CommentTargetType.moment,
        nullable=False,
        index=True,
    )
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # 保留旧字段以兼容现有数据
    moment_id: Mapped[int | None] = mapped_column(ForeignKey("moments.id"), nullable=True, index=True)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id"), nullable=True, index=True)
    mention_uids_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    moment = relationship("Moment", back_populates="comments")
    author = relationship("User", back_populates="comments")
    parent = relationship("Comment", remote_side=[id], back_populates="replies")
    replies = relationship(
        "Comment",
        back_populates="parent",
        cascade="all,delete-orphan",
        order_by="Comment.created_at.asc()",
    )

    @property
    def mention_uids(self) -> list[str]:
        if not self.mention_uids_json:
            return []
        try:
            raw = json.loads(self.mention_uids_json)
            if isinstance(raw, list):
                return [str(item) for item in raw if str(item).strip()]
            return []
        except Exception:
            return []

    def set_mention_uids(self, uids: list[str]) -> None:
        normalized = [str(item).strip() for item in uids if str(item).strip()]
        self.mention_uids_json = json.dumps(normalized, ensure_ascii=False)
