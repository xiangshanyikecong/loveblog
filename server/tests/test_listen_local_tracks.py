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

"""Tests for cottage-listen local (uploaded) tracks.

Local tracks let the couple play music without a NetEase scan-login: an
uploaded file is registered with a synthetic ``local:<tid>`` song id, and
``/songs/<id>/url`` resolves it straight to the stored upload URL — no cookie,
no 409.
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_optional_user, get_token, get_token_optional
from app.db.base import Base
from app.db.redis import get_redis
from app.db.session import get_db
from app.main import app
from app.models.listen_local_track import ListenLocalTrack
from app.models.site_setting import SiteSetting
from app.models.upload_reference import UploadReference
from app.models.user import User, UserRole
from app.schemas.upload import UploadResponse


class ListenLocalTrackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(
            bind=cls.engine, autoflush=False, autocommit=False, class_=Session
        )

        db = cls.SessionLocal()
        try:
            partner = User(
                uid="uid-partner-a",
                username="listen_partner",
                nickname="Listen Partner",
                role=UserRole.partner_a,
                password_hash="x",
            )
            db.add(partner)
            db.add(SiteSetting(id=1, site_name="Test Site"))
            db.commit()
            db.refresh(partner)
            cls.partner_id = int(partner.id)
        finally:
            db.close()

        def _get_db_override():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def _get_current_user_override():
            db = cls.SessionLocal()
            try:
                user = db.query(User).filter(User.id == cls.partner_id).first()
                if user is not None:
                    db.expunge(user)
                return user
            finally:
                db.close()

        app.dependency_overrides[get_db] = _get_db_override
        app.dependency_overrides[get_current_user] = _get_current_user_override
        app.dependency_overrides[get_optional_user] = _get_current_user_override
        app.dependency_overrides[get_token] = lambda: "test-token"
        app.dependency_overrides[get_token_optional] = lambda: "test-token"
        app.dependency_overrides[get_redis] = lambda: None

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def _upload(self, name: str = "Our Song", artist: str = "甲, 乙") -> dict:
        fake = UploadResponse(
            url="/uploads/listen/our-song.mp3",
            file_name="our-song.mp3",
            content_type="audio/mpeg",
            size=1234,
        )
        with patch(
            "app.api.v1.cottage_listen.process_audio_upload",
            new=AsyncMock(return_value=fake),
        ):
            resp = self.client.post(
                "/v1/cottage/listen/local-tracks",
                files={"file": ("our-song.mp3", b"fake-bytes", "audio/mpeg")},
                data={"name": name, "artist": artist, "duration_ms": "200000"},
            )
        return resp

    def test_upload_lists_and_resolves_without_cookie(self) -> None:
        resp = self._upload()
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        meta = resp.json()
        song_id = meta["song_id"]
        self.assertTrue(song_id.startswith("local:"))
        self.assertEqual(meta["name"], "Our Song")
        self.assertEqual(meta["artists"], ["甲", "乙"])
        self.assertEqual(meta["duration_ms"], 200000)

        # Listed back
        listed = self.client.get("/v1/cottage/listen/local-tracks")
        self.assertEqual(listed.status_code, 200, msg=listed.text)
        ids = [item["song_id"] for item in listed.json()["items"]]
        self.assertIn(song_id, ids)

        # Resolves straight to the stored URL — provider local, no 409.
        url_resp = self.client.get(f"/v1/cottage/listen/songs/{song_id}/url")
        self.assertEqual(url_resp.status_code, 200, msg=url_resp.text)
        body = url_resp.json()
        self.assertEqual(body["provider"], "local")
        self.assertEqual(body["url"], "/uploads/listen/our-song.mp3")

        # Lyric short-circuits to empty for local tracks.
        lyric = self.client.get(f"/v1/cottage/listen/songs/{song_id}/lyric")
        self.assertEqual(lyric.status_code, 200, msg=lyric.text)
        self.assertEqual(lyric.json()["kind"], "none")

    def test_upload_registers_media_reference(self) -> None:
        """A served-media UploadReference must exist so /uploads/... won't 403."""
        meta = self._upload(name="Has Ref", artist="Z").json()
        tid = meta["song_id"].split(":", 1)[1]
        db = self.SessionLocal()
        try:
            track = (
                db.query(ListenLocalTrack)
                .filter(ListenLocalTrack.tid == tid)
                .first()
            )
            self.assertIsNotNone(track)
            content_id = int(track.id)
            ref = (
                db.query(UploadReference)
                .filter(
                    UploadReference.content_kind == "listen",
                    UploadReference.content_id == content_id,
                )
                .first()
            )
            self.assertIsNotNone(ref)
            self.assertEqual(ref.slot, "media")
            self.assertEqual(ref.file_path, "/uploads/listen/our-song.mp3")

            # Deleting the track removes its media reference.
            self.client.delete(f"/v1/cottage/listen/local-tracks/{tid}")
            db.expire_all()
            remaining = (
                db.query(UploadReference)
                .filter(
                    UploadReference.content_kind == "listen",
                    UploadReference.content_id == content_id,
                )
                .count()
            )
            self.assertEqual(remaining, 0)
        finally:
            db.close()

    def test_delete_soft_removes_track(self) -> None:
        meta = self._upload(name="To Delete", artist="X").json()
        song_id = meta["song_id"]
        tid = song_id.split(":", 1)[1]

        deleted = self.client.delete(f"/v1/cottage/listen/local-tracks/{tid}")
        self.assertEqual(deleted.status_code, 204, msg=deleted.text)

        listed = self.client.get("/v1/cottage/listen/local-tracks")
        ids = [item["song_id"] for item in listed.json()["items"]]
        self.assertNotIn(song_id, ids)

        # A deleted track no longer resolves to a URL.
        url_resp = self.client.get(f"/v1/cottage/listen/songs/{song_id}/url")
        self.assertEqual(url_resp.status_code, 200, msg=url_resp.text)
        self.assertIsNone(url_resp.json()["url"])
        self.assertEqual(url_resp.json()["error_kind"], "unavailable")

    def test_delete_missing_track_returns_404(self) -> None:
        resp = self.client.delete("/v1/cottage/listen/local-tracks/does-not-exist")
        self.assertEqual(resp.status_code, 404, msg=resp.text)


if __name__ == "__main__":
    unittest.main()
