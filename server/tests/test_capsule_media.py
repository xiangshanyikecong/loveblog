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

"""Tests for voice / video time capsules and voice-diary moments.

Covers two correctness properties added with the media feature:

* A capsule's recording is sealed exactly like its text: ``media_url`` is
  ``None`` until ``open_at`` and present afterwards, while ``has_media`` /
  ``media_type`` are always visible so the UI can show a "locked recording"
  affordance.
* A moment (碎碎念 / time-line) may be a pure voice diary — created with an
  ``audio_url`` and no text body.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_optional_user, get_token, get_token_optional
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class CapsuleMediaTests(unittest.TestCase):
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
                username="cap_partner",
                nickname="Capsule Partner",
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

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def test_sealed_capsule_masks_media_url_until_open(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=3650)
        resp = self.client.post(
            "/v1/capsules",
            json={
                "content": "未来见",
                "open_at": _iso(future),
                "media_url": "/uploads/capsule/secret.weba",
                "media_type": "audio",
                "media_duration_sec": 12,
            },
        )
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        body = resp.json()
        # Sealed: neither text nor the recording URL leak before open_at.
        self.assertFalse(body["is_open"])
        self.assertIsNone(body["content"])
        self.assertIsNone(body["media_url"])
        # But the existence + type of a recording is advertised for the UI.
        self.assertTrue(body["has_media"])
        self.assertEqual(body["media_type"], "audio")

    def test_open_capsule_reveals_media_url(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(seconds=5)
        resp = self.client.post(
            "/v1/capsules",
            json={
                "open_at": _iso(past),
                "media_url": "/uploads/capsule/now.weba",
                "media_type": "audio",
                "media_duration_sec": 8,
            },
        )
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        body = resp.json()
        self.assertTrue(body["is_open"])
        self.assertEqual(body["media_url"], "/uploads/capsule/now.weba")
        self.assertTrue(body["has_media"])

    def test_capsule_requires_text_or_media(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=1)
        resp = self.client.post("/v1/capsules", json={"open_at": _iso(future)})
        self.assertEqual(resp.status_code, 422, msg=resp.text)

    def test_voice_diary_moment_without_text(self) -> None:
        resp = self.client.post(
            "/v1/timeline",
            json={
                "audio_url": "/uploads/capsule/diary.weba",
                "audio_duration_sec": 30,
            },
        )
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        body = resp.json()
        self.assertEqual(body["audio_url"], "/uploads/capsule/diary.weba")
        self.assertEqual(body["audio_duration_sec"], 30)
        self.assertEqual(body["content"], "")


if __name__ == "__main__":
    unittest.main()
