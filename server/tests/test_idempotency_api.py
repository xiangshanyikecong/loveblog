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

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.api.v1.messages import create_message
from app.models import Message, Notification, SiteSetting, User
from app.schemas.message import MessageCreateRequest
from app.models.user import UserRole


class IdempotencyApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(cls.engine)
        cls.SessionLocal = sessionmaker(bind=cls.engine, class_=Session, expire_on_commit=False)
        db = cls.SessionLocal()
        cls.user = User(
            uid="idempotent-a",
            username="idempotent_a",
            nickname="A",
            role=UserRole.partner_a,
            password_hash="x",
        )
        other = User(
            uid="idempotent-b",
            username="idempotent_b",
            nickname="B",
            role=UserRole.partner_b,
            password_hash="x",
        )
        db.add_all([cls.user, other, SiteSetting(id=1, site_name="Idempotency")])
        db.commit()
        cls.token = create_access_token(
            cls.user.uid,
            session_version=cls.user.session_version,
        )
        db.close()

        def override_db():
            session = cls.SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def _headers(self, key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Idempotency-Key": key,
        }

    def test_message_retry_returns_original_without_duplicate(self) -> None:
        payload = {"content": "once", "is_public": True, "tags": ["mobile"]}
        with patch("app.services.notification_delivery.deliver_notification_payloads"):
            first = self.client.post("/v1/messages", json=payload, headers=self._headers("message-op-1"))
            second = self.client.post("/v1/messages", json=payload, headers=self._headers("message-op-1"))
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json()["msg_id"], second.json()["msg_id"])
        db = self.SessionLocal()
        self.assertEqual(db.query(Message).filter_by(client_idempotency_key="message-op-1").count(), 1)
        db.close()

        conflict = self.client.post(
            "/v1/messages",
            json={**payload, "content": "different"},
            headers=self._headers("message-op-1"),
        )
        self.assertEqual(conflict.status_code, 409)

    def test_message_commit_race_still_rejects_different_payload(self) -> None:
        existing = Message(
            author_id=self.user.id,
            content="first payload",
            is_public=True,
            tags=[],
            client_idempotency_key="racing-key",
        )
        existing.author = self.user

        class FakeQuery:
            def __init__(self, value):
                self.value = value

            def options(self, *_args):
                return self

            def filter(self, *_args):
                return self

            def first(self):
                return self.value

        class RacingSession:
            def __init__(self):
                self.query_count = 0

            def query(self, _model):
                self.query_count += 1
                return FakeQuery(None if self.query_count == 1 else existing)

            def add(self, _value):
                return None

            def flush(self):
                raise IntegrityError("insert", {}, RuntimeError("unique race"))

            def rollback(self):
                return None

        with self.assertRaises(HTTPException) as raised:
            create_message(
                MessageCreateRequest(content="different payload", is_public=True, tags=[]),
                idempotency_key="racing-key",
                db=RacingSession(),
                current_user=self.user,
            )
        self.assertEqual(raised.exception.status_code, 409)

    def test_mood_retry_does_not_emit_duplicate_notification(self) -> None:
        db = self.SessionLocal()
        before_notifications = db.query(Notification).filter(Notification.type == "mood.checkin").count()
        db.close()
        payload = {"mood_date": "2026-07-17", "mood": "happy", "emoji": ":)"}
        with patch("app.services.notification_delivery.deliver_notification_payloads"):
            first = self.client.post("/v1/cottage/mood", json=payload, headers=self._headers("mood-op-1"))
            second = self.client.post("/v1/cottage/mood", json=payload, headers=self._headers("mood-op-1"))
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["mid"], second.json()["mid"])
        db = self.SessionLocal()
        self.assertEqual(
            db.query(Notification).filter(Notification.type == "mood.checkin").count(),
            before_notifications + 1,
        )
        db.close()

    def test_mood_old_key_retry_after_new_key_does_not_rewrite_or_notify(self) -> None:
        db = self.SessionLocal()
        before_notifications = db.query(Notification).filter(Notification.type == "mood.checkin").count()
        db.close()
        first_payload = {"mood_date": "2026-07-18", "mood": "happy", "emoji": ":)"}
        second_payload = {"mood_date": "2026-07-18", "mood": "tired", "emoji": "-_-"}
        with patch("app.services.notification_delivery.deliver_notification_payloads"):
            first = self.client.post(
                "/v1/cottage/mood",
                json=first_payload,
                headers=self._headers("mood-sequence-k1"),
            )
            newer = self.client.post(
                "/v1/cottage/mood",
                json=second_payload,
                headers=self._headers("mood-sequence-k2"),
            )
            retry_old = self.client.post(
                "/v1/cottage/mood",
                json=first_payload,
                headers=self._headers("mood-sequence-k1"),
            )

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(newer.status_code, 200, newer.text)
        self.assertEqual(retry_old.status_code, 200, retry_old.text)
        # An old operation is acknowledged without reapplying its stale value.
        self.assertEqual(retry_old.json()["mood"], "tired")
        db = self.SessionLocal()
        self.assertEqual(
            db.query(Notification).filter(Notification.type == "mood.checkin").count(),
            before_notifications + 2,
        )
        db.close()

        conflict = self.client.post(
            "/v1/cottage/mood",
            json={**first_payload, "mood": "sad"},
            headers=self._headers("mood-sequence-k1"),
        )
        self.assertEqual(conflict.status_code, 409, conflict.text)


if __name__ == "__main__":
    unittest.main()
