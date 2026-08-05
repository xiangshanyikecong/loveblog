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
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    partner_a = "PartnerA"
    partner_b = "PartnerB"
    visitor = "Visitor"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    email_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.partner_a, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
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
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # 访客相关字段
    sso_source: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="SSO来源")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近登录时间")
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="是否被封禁")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="管理员备注")
    permission_status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, comment="权限状态")
    avatar_sync_record: Mapped[str | None] = mapped_column(Text, nullable=True, comment="头像/昵称同步记录")

    # 安全相关字段
    login_failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="连续登录失败次数")
    login_freeze_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="账户冻结截止时间"
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后修改密码时间"
    )
    session_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="会话版本号")
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="最后登录IP")

    moments = relationship("Moment", back_populates="author", cascade="all,delete")
    events = relationship("Event", back_populates="creator", cascade="all,delete")
    articles = relationship("Article", back_populates="author", cascade="all,delete")
    article_blocks = relationship("ArticleBlock", back_populates="author", cascade="all,delete")
    albums = relationship("Album", back_populates="author", cascade="all,delete")
    messages = relationship("Message", back_populates="author", cascade="all,delete")
    comments = relationship("Comment", back_populates="author", cascade="all,delete")
    capsules = relationship("Capsule", back_populates="author", cascade="all,delete")
    push_subscriptions = relationship("PushSubscription", back_populates="user", cascade="all,delete")
    fcm_device_tokens = relationship("FcmDeviceToken", back_populates="user", cascade="all,delete")
