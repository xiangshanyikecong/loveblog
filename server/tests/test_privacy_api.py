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

import hashlib
import unittest
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_optional_user, get_token, get_token_optional
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.album import Album
from app.models.article import Article, ArticleStatus
from app.models.capsule import Capsule
from app.models.chat_key import ChatKey
from app.models.chat_message import ChatMessage
from app.models.content_visibility import ContentVisibility
from app.models.event import Event, EventType, Visibility as EventVisibility
from app.models.message import Message
from app.models.moment import Moment, Visibility as MomentVisibility
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole
from app.models.vault import VaultEntry, VaultMeta


def _chat_setup(salt: str = "c2hhcmVkLXNhbHQtMDE=") -> dict:
    verifier_cipher = "c2hhcmVkLXZlcmlmaWVyLWNpcGhlcg=="
    return {
        "salt": salt,
        "kdf": "PBKDF2",
        "kdf_hash": "SHA-256",
        "iterations": 210_000,
        "algo": "AES-GCM",
        "verifier_iv": "c2hhcmVkLWl2LTEy",
        "verifier_cipher": verifier_cipher,
        "verifier_hash": hashlib.sha256(verifier_cipher.encode("utf-8")).hexdigest(),
    }


class PrivacyApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(
            bind=cls.engine,
            autoflush=False,
            autocommit=False,
            class_=Session,
        )
        cls.current_user_id: int | None = None

        def _get_db_override():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def _get_current_user_override():
            db = cls.SessionLocal()
            try:
                user = db.query(User).filter(User.id == cls.current_user_id).first()
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

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        db = self.SessionLocal()
        try:
            partner_a = User(
                uid="partner-a",
                username="privacy_a",
                nickname="A",
                role=UserRole.partner_a,
                password_hash="x",
                last_login_ip="203.0.113.10",
                last_login_at=datetime.now(timezone.utc),
            )
            partner_b = User(
                uid="partner-b",
                username="privacy_b",
                nickname="B",
                role=UserRole.partner_b,
                password_hash="x",
            )
            visitor = User(
                uid="visitor",
                username="privacy_visitor",
                nickname="Visitor",
                role=UserRole.visitor,
                password_hash="x",
            )
            db.add_all([partner_a, partner_b, visitor, SiteSetting(id=1, site_name="Privacy")])
            db.commit()
            db.refresh(partner_a)
            db.refresh(partner_b)
            db.refresh(visitor)
            self.partner_a_id = int(partner_a.id)
            self.partner_b_id = int(partner_b.id)
            self.visitor_id = int(visitor.id)
            type(self).current_user_id = self.partner_a_id
        finally:
            db.close()

    def test_summary_separates_access_scope_from_e2ee_protection(self) -> None:
        db = self.SessionLocal()
        try:
            db.add_all(
                [
                    Article(
                        author_id=self.partner_a_id,
                        title="Public",
                        status=ArticleStatus.published,
                        visibility=ContentVisibility.public,
                    ),
                    Article(
                        author_id=self.partner_a_id,
                        title="Password",
                        status=ArticleStatus.published,
                        visibility=ContentVisibility.password_protected,
                        password_hash="hash",
                    ),
                    Article(
                        author_id=self.partner_a_id,
                        title="Legacy masked",
                        status=ArticleStatus.published,
                        visibility=ContentVisibility.public,
                        is_encrypted=True,
                    ),
                    Article(
                        author_id=self.partner_a_id,
                        title="Draft",
                        status=ArticleStatus.draft,
                        visibility=ContentVisibility.public,
                    ),
                    Album(
                        author_id=self.partner_a_id,
                        title="Public album",
                        visibility=ContentVisibility.public,
                    ),
                    Moment(
                        author_id=self.partner_a_id,
                        content="Masked moment",
                        visibility=MomentVisibility.encrypted,
                    ),
                    Event(
                        creator_id=self.partner_a_id,
                        title="Private event",
                        date=date.today(),
                        type=EventType.anniversary,
                        visibility=EventVisibility.partners_only,
                    ),
                    Message(
                        author_id=self.partner_a_id,
                        content="Private message",
                        is_public=False,
                    ),
                    Capsule(
                        author_id=self.partner_a_id,
                        content="Future",
                        open_at=datetime.now(timezone.utc) + timedelta(days=1),
                    ),
                    ChatMessage(
                        sender_id=self.partner_a_id,
                        type="text",
                        is_encrypted=True,
                        iv="aXY=",
                        ciphertext="Y2lwaGVy",
                        algo="AES-GCM",
                    ),
                    ChatMessage(
                        sender_id=self.partner_b_id,
                        type="text",
                        content="Plaintext",
                    ),
                    ChatMessage(
                        sender_id=self.partner_b_id,
                        type="text",
                        content="Invalid encrypted marker",
                        is_encrypted=True,
                    ),
                    VaultMeta(
                        id=1,
                        salt="dmF1bHQtc2FsdA==",
                        verifier_iv="dmF1bHQtaXY=",
                        verifier_cipher="dmF1bHQtY2lwaGVy",
                    ),
                ]
            )
            chat = _chat_setup()
            db.add(ChatKey(user_id=self.partner_a_id, **chat))
            db.flush()
            db.add(VaultEntry(author_id=self.partner_a_id, iv="dmF1bHQtaXY=", ciphertext="Y2lwaGVy"))
            db.commit()
        finally:
            db.close()

        response = self.client.get("/v1/privacy/summary")
        self.assertEqual(response.status_code, 200, msg=response.text)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        body = response.json()
        self.assertEqual(body["totals"]["public"], 2)
        self.assertEqual(body["totals"]["password"], 1)
        self.assertEqual(body["totals"]["author_only"], 1)
        self.assertEqual(body["totals"]["partners"], 9)
        self.assertEqual(body["protection"]["end_to_end_encrypted"], 2)
        self.assertEqual(body["protection"]["server_masked"], 2)
        self.assertEqual(body["protection"]["server_readable"], 11)
        self.assertEqual(body["account"]["last_login_ip"], "203.0.113.10")

        chat_state = next(item for item in body["encryption"] if item["scope"] == "chat")
        self.assertTrue(chat_state["initialized"])
        self.assertEqual(chat_state["item_count"], 3)
        self.assertEqual(chat_state["encrypted_count"], 1)
        self.assertNotIn("salt", chat_state)
        self.assertNotIn("verifier_cipher", chat_state)

    def test_summary_rejects_visitors(self) -> None:
        type(self).current_user_id = self.visitor_id
        response = self.client.get("/v1/privacy/summary")
        self.assertEqual(response.status_code, 403, msg=response.text)

    def test_shared_chat_key_and_safe_rekey_guard(self) -> None:
        setup = self.client.post("/v1/cottage/chat/keys/setup", json=_chat_setup())
        self.assertEqual(setup.status_code, 201, msg=setup.text)

        type(self).current_user_id = self.partner_b_id
        meta = self.client.get("/v1/cottage/chat/keys/meta")
        self.assertEqual(meta.status_code, 200, msg=meta.text)
        self.assertEqual(meta.json()["salt"], _chat_setup()["salt"])
        self.assertIsNotNone(meta.json()["verifier_cipher"])

        db = self.SessionLocal()
        try:
            db.add(
                ChatMessage(
                    sender_id=self.partner_a_id,
                    type="text",
                    is_encrypted=True,
                    iv="aXY=",
                    ciphertext="Y2lwaGVy",
                    algo="AES-GCM",
                )
            )
            db.commit()
        finally:
            db.close()

        rotated = _chat_setup("bmV3LXNoYXJlZC1zYWx0")
        rekey = self.client.post(
            "/v1/cottage/chat/keys/rekey",
            json={
                **rotated,
                "new_salt": rotated["salt"],
                "new_verifier_iv": rotated["verifier_iv"],
                "new_verifier_cipher": rotated["verifier_cipher"],
                "new_verifier_hash": rotated["verifier_hash"],
            },
        )
        self.assertEqual(rekey.status_code, 409, msg=rekey.text)

    def test_encrypted_chat_api_accepts_only_complete_ciphertext_envelopes(self) -> None:
        setup = self.client.post("/v1/cottage/chat/keys/setup", json=_chat_setup())
        self.assertEqual(setup.status_code, 201, msg=setup.text)

        envelope = {
            "type": "text",
            "content": None,
            "is_encrypted": True,
            "iv": "Y2hhdC1pdi0xMg==",
            "ciphertext": "b3BhcXVlLWNpcGhlcnRleHQ=",
            "algo": "AES-GCM",
        }
        sent = self.client.post("/v1/cottage/chat/messages", json=envelope)
        self.assertEqual(sent.status_code, 201, msg=sent.text)
        self.assertTrue(sent.json()["is_encrypted"])
        self.assertIsNone(sent.json()["content"])
        self.assertEqual(sent.json()["ciphertext"], envelope["ciphertext"])

        missing_algorithm = self.client.post(
            "/v1/cottage/chat/messages",
            json={key: value for key, value in envelope.items() if key != "algo"},
        )
        self.assertEqual(missing_algorithm.status_code, 422, msg=missing_algorithm.text)

        plaintext_leak = self.client.post(
            "/v1/cottage/chat/messages",
            json={**envelope, "content": "must not be accepted"},
        )
        self.assertEqual(plaintext_leak.status_code, 422, msg=plaintext_leak.text)

    def test_recovery_events_are_metadata_only_and_appear_in_activity(self) -> None:
        recorded = self.client.post(
            "/v1/privacy/recovery-events",
            json={"scope": "vault", "event": "kit_created"},
        )
        self.assertEqual(recorded.status_code, 200, msg=recorded.text)
        self.assertEqual(recorded.json(), {"recorded": True})

        summary = self.client.get("/v1/privacy/summary").json()
        self.assertEqual(summary["recent_activity"][0]["action"], "privacy.recovery_kit_created")
        self.assertNotIn("detail", summary["recent_activity"][0])


if __name__ == "__main__":
    unittest.main()
