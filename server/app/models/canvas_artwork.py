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

"""Models for the cottage 协作画板 artwork gallery (Canvas 作品集).

A canvas artwork is the *persisted* result of a collaborative drawing
session on the cottage 双人协作画板. The realtime drawing frames are
still pure-relay over the existing ``/cottage/canvas/ws`` channel — the
gallery only stores the snapshot both partners agreed to save.

Schema notes
------------
- ``strokes_json`` is a JSON string of the form
  ``{"width": 960, "height": 600, "strokes": [{"sid": "...", "segs": [...]}]}``.
  The shape matches ``SharedCanvas.getSyncPayload()`` in the web frontend
  and ``CanvasViewModel.buildSyncPayload()`` on Android so the existing
  drawing layer can save and replay without any translation.
- ``thumb_data_url`` is a base64-encoded PNG of the rasterized artwork,
  scaled down so the gallery list can render thumbnails without any
  download round trip. The original PNG (960x600) is small enough to
  inline here without bloating the row (<200 KB).
- ``CanvasArtworkCollaborator`` is a small many-to-many so the same
  artwork can be credited to either partner depending on who pressed
  the save button, with the joiner in the URL kept for traceability.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CanvasArtwork(Base):
    """One saved collaborative drawing."""

    __tablename__ = "canvas_artworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    caid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    # Whoever pressed the save button. The collaborator join table records
    # which partner accounts appear in the strokes.
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Optional human title; falls back to "未命名作品" in the UI.
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Serialized strokes; the blob is large enough to make JSONB worth the
    # schema split, but a single TEXT column keeps SQLite and Postgres
    # symmetric and the read paths cheap.
    strokes_json: Mapped[str] = mapped_column(Text, nullable=False)
    # Inline PNG thumbnail (960x600 white-background raster).
    thumb_data_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Stroke count and last-touched stroke count are denormalized so the
    # gallery list view doesn't have to JSON-parse every row.
    stroke_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=960, nullable=False)
    height: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    author = relationship("User", foreign_keys=[author_id])
    collaborators = relationship(
        "CanvasArtworkCollaborator",
        back_populates="artwork",
        cascade="all, delete-orphan",
    )


class CanvasArtworkCollaborator(Base):
    """Many-to-many: which partner accounts contributed strokes to the artwork.

    The first canvas save typically credits both partners; the join row is
    the durable record of "this artwork belongs to both of us".
    """

    __tablename__ = "canvas_artwork_collaborators"
    __table_args__ = (
        UniqueConstraint("artwork_id", "user_id", name="uq_canvas_artwork_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    artwork_id: Mapped[int] = mapped_column(
        ForeignKey("canvas_artworks.id"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Distinct stroke count this partner contributed; recomputed on save.
    stroke_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    artwork = relationship("CanvasArtwork", back_populates="collaborators")
    user = relationship("User", foreign_keys=[user_id])
