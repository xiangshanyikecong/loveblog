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

"""Tests for cottage-listen history storage."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.services.listen_together import history as listen_history


def test_record_play_skips_recent_duplicate() -> None:
    latest = MagicMock()
    latest.song_id = "186016"
    latest.played_at = datetime.now(timezone.utc)

    query = MagicMock()
    query.order_by.return_value.first.return_value = latest

    db = MagicMock()
    db.query.return_value = query

    class FakeSessionLocal:
        def __call__(self):
            return db

    original = listen_history.SessionLocal
    listen_history.SessionLocal = lambda: db
    try:
        listen_history.record_play(
            song_id="186016",
            song_meta={"name": "稻香", "artists": ["周杰伦"]},
            started_by_uid="uid-a",
        )
    finally:
        listen_history.SessionLocal = original

    db.add.assert_not_called()


def test_list_history_maps_rows() -> None:
    row = MagicMock()
    row.song_id = "1"
    row.name = "Song"
    row.artists = ["A"]
    row.album = None
    row.duration_ms = 1000
    row.cover_url = None
    row.played_at = datetime(2026, 6, 20, tzinfo=timezone.utc)
    row.started_by_uid = "u1"

    db = MagicMock()
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [row]

    items = listen_history.list_history(db, limit=10)
    assert len(items) == 1
    assert items[0]["song_id"] == "1"
    assert items[0]["artists"] == ["A"]
