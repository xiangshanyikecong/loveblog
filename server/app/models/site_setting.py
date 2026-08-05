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

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SiteSetting(Base):
    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    site_name: Mapped[str] = mapped_column(String(120), default="恋爱记", nullable=False)
    love_start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploads_root: Mapped[str] = mapped_column(String(255), default="uploads", nullable=False)
    articles_path: Mapped[str] = mapped_column(String(255), default="uploads/articles", nullable=False)
    albums_path: Mapped[str] = mapped_column(String(255), default="uploads/albums", nullable=False)
    avatar_path: Mapped[str] = mapped_column(String(255), default="uploads/avatars", nullable=False)
    timeline_path: Mapped[str] = mapped_column(String(255), default="uploads/timeline", nullable=False)
    videos_path: Mapped[str] = mapped_column(String(255), default="uploads/videos", nullable=False)
    allow_registration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Couple avatars ────────────────────────────────────────────────────
    partner_a_avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partner_b_avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Media policy ──────────────────────────────────────────────────────
    # Maximum size (KB) for images after compression. 0 = no limit.
    max_image_kb: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    # Thumbnail longest-side width in pixels. 0 = skip thumbnail generation.
    thumb_width: Mapped[int] = mapped_column(Integer, default=400, nullable=False)
    # JPEG/WebP compression quality 1-95.
    compress_quality: Mapped[int] = mapped_column(Integer, default=82, nullable=False)
    # Strip EXIF metadata from uploaded images.
    strip_exif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Comma-separated list of allowed MIME types for image uploads.
    allowed_image_types: Mapped[str] = mapped_column(
        String(512),
        default="image/jpeg,image/png,image/webp,image/gif",
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
