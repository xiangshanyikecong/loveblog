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

"""PostgreSQL-backed listen history for cottage-listen-together."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.listen_history import ListenHistoryEntry

logger = logging.getLogger(__name__)

HISTORY_MAX = 100
_DEDUP_WINDOW_MS = 30_000


def _now_ms() -> int:
    return int(time.time() * 1000)


def _artists_json(artists: list[str]) -> str:
    return json.dumps(artists, ensure_ascii=False)


def record_play(
    *,
    song_id: str,
    song_meta: dict[str, Any] | None,
    started_by_uid: str,
) -> None:
    """Persist one play event. Opens its own DB session (safe from Redis room layer)."""
    song_id = str(song_id or "").strip()
    if not song_id:
        return

    meta = song_meta if isinstance(song_meta, dict) else {}
    artists = meta.get("artists") or []
    if not isinstance(artists, list):
        artists = []
    artists = [str(a) for a in artists if a]

    db = SessionLocal()
    try:
        latest = (
            db.query(ListenHistoryEntry)
            .order_by(ListenHistoryEntry.played_at.desc(), ListenHistoryEntry.id.desc())
            .first()
        )
        if latest and latest.song_id == song_id:
            played_ms = int(latest.played_at.timestamp() * 1000) if latest.played_at else 0
            if _now_ms() - played_ms < _DEDUP_WINDOW_MS:
                return

        entry = ListenHistoryEntry(
            song_id=song_id,
            name=str(meta.get("name") or ""),
            artists_json=_artists_json(artists),
            album=meta.get("album"),
            duration_ms=meta.get("duration_ms"),
            cover_url=meta.get("cover_url"),
            started_by_uid=started_by_uid,
            played_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.flush()

        overflow = (
            db.query(ListenHistoryEntry.id)
            .order_by(ListenHistoryEntry.played_at.desc(), ListenHistoryEntry.id.desc())
            .offset(HISTORY_MAX)
            .all()
        )
        if overflow:
            db.query(ListenHistoryEntry).filter(
                ListenHistoryEntry.id.in_([row[0] for row in overflow])
            ).delete(synchronize_session=False)

        db.commit()
    except Exception:
        db.rollback()
        logger.warning("[cottage-listen] failed to record listen history (non-fatal)", exc_info=True)
    finally:
        db.close()


def list_history(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent history entries newest-first."""
    limit = max(1, min(limit, HISTORY_MAX))
    rows = (
        db.query(ListenHistoryEntry)
        .order_by(ListenHistoryEntry.played_at.desc(), ListenHistoryEntry.id.desc())
        .limit(limit)
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        played_ms = int(row.played_at.timestamp() * 1000) if row.played_at else 0
        out.append(
            {
                "song_id": row.song_id,
                "name": row.name,
                "artists": row.artists,
                "album": row.album,
                "duration_ms": row.duration_ms,
                "cover_url": row.cover_url,
                "played_at_ms": played_ms,
                "started_by_uid": row.started_by_uid,
            }
        )
    return out
