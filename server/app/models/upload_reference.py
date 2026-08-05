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

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UploadReference(Base):
    __tablename__ = "upload_references"
    __table_args__ = (
        UniqueConstraint("file_path", "content_kind", "content_id", "slot", name="uq_upload_reference_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_path: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    content_kind: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    content_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    slot: Mapped[str] = mapped_column(String(32), nullable=False)

    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    visibility: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ref_is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    partner_can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
