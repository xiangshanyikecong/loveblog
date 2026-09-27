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

"""Idempotency-Key replay behaviour for the offline write queue endpoints.

Covers the generic registry introduced for the web outbox (articles and
comments). Moment/CheckIn/Chat have their own column-based replay paths and
are covered by their respective suites.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_optional_user, get_token, get_token_optional
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole


class WriteIdempotencyTests(unittest.TestCase):
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

        db = cls.SessionLocal()
        try:
            user = User(
                username="idem_user",
                nickname="Idem User",
                role=UserRole.partner_a,
                password_hash="x",
            )
            db.add(user)
            db.add(SiteSetting(id=1, site_name="Test Site"))
            db.commit()
            db.refresh(user)
            cls.user_id = int(user.id)
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
                user = db.query(User).filter(User.id == cls.user_id).first()
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
        db = self.SessionLocal()
        try:
            db.execute(text("DELETE FROM idempotency_records"))
            db.execute(text("DELETE FROM comments"))
            db.execute(text("DELETE FROM article_blocks"))
            db.execute(text("DELETE FROM articles"))
            db.execute(text("DELETE FROM moments"))
            db.commit()
        finally:
            db.close()

    def _article_payload(self, title: str = "Offline draft") -> dict:
        return {
            "title": title,
            "status": "Draft",
            "visibility": "public",
            "blocks": [{"block_type": "Paragraph", "content": "hello", "sort_order": 0}],
        }

    def test_article_create_replays_same_key_to_original_resource(self) -> None:
        headers = {"Idempotency-Key": "key-article-1"}

        first = self.client.post("/v1/articles", json=self._article_payload(), headers=headers)
        self.assertEqual(first.status_code, 201, msg=first.text)
        aid = first.json()["aid"]

        replay = self.client.post(
            "/v1/articles", json=self._article_payload("Rewritten title"), headers=headers
        )
        self.assertEqual(replay.status_code, 201, msg=replay.text)
        self.assertEqual(replay.json()["aid"], aid)

        # 列表接口默认可能只返回已发布文章，直接按 DB 计数断言无重复。
        db = self.SessionLocal()
        try:
            count = db.execute(text("SELECT COUNT(*) FROM articles")).scalar_one()
            title = db.execute(text("SELECT title FROM articles")).scalar_one()
        finally:
            db.close()
        self.assertEqual(count, 1)
        self.assertEqual(title, "Offline draft")

    def test_article_create_different_keys_create_distinct_articles(self) -> None:
        first = self.client.post(
            "/v1/articles", json=self._article_payload(), headers={"Idempotency-Key": "key-a"}
        )
        second = self.client.post(
            "/v1/articles", json=self._article_payload(), headers={"Idempotency-Key": "key-b"}
        )
        self.assertEqual(first.status_code, 201, msg=first.text)
        self.assertEqual(second.status_code, 201, msg=second.text)
        self.assertNotEqual(first.json()["aid"], second.json()["aid"])

    def test_invalid_idempotency_key_is_rejected(self) -> None:
        resp = self.client.post(
            "/v1/articles",
            json=self._article_payload(),
            headers={"Idempotency-Key": "x" * 200},
        )
        self.assertEqual(resp.status_code, 400, msg=resp.text)

    def test_moment_comment_replays_same_key_to_original_comment(self) -> None:
        moment = self.client.post(
            "/v1/timeline",
            json={"content": "moment for comments"},
        )
        self.assertEqual(moment.status_code in (200, 201), True, msg=moment.text)
        mid = moment.json()["mid"]

        headers = {"Idempotency-Key": "key-comment-1"}
        first = self.client.post(
            f"/v1/timeline/{mid}/comments", json={"content": "nice"}, headers=headers
        )
        self.assertEqual(first.status_code in (200, 201), True, msg=first.text)
        cid = first.json()["cid"]

        replay = self.client.post(
            f"/v1/timeline/{mid}/comments",
            json={"content": "edited text"},
            headers=headers,
        )
        self.assertEqual(replay.status_code in (200, 201), True, msg=replay.text)
        self.assertEqual(replay.json()["cid"], cid)

    def test_article_comment_replays_via_shared_service(self) -> None:
        article = self.client.post(
            "/v1/articles", json=self._article_payload("Comment target")
        )
        self.assertEqual(article.status_code, 201, msg=article.text)
        aid = article.json()["aid"]

        headers = {"Idempotency-Key": "key-article-comment"}
        first = self.client.post(
            f"/v1/articles/{aid}/comments", json={"content": "great"}, headers=headers
        )
        self.assertEqual(first.status_code in (200, 201), True, msg=first.text)
        cid = first.json()["cid"]

        replay = self.client.post(
            f"/v1/articles/{aid}/comments",
            json={"content": "great"},
            headers=headers,
        )
        self.assertEqual(replay.status_code in (200, 201), True, msg=replay.text)
        self.assertEqual(replay.json()["cid"], cid)

    def test_status_endpoint_still_enabled_flag_untouched(self) -> None:
        # Guard against accidental coupling: the settings toggle is unrelated
        # to write idempotency.
        with patch.object(settings, "fcm_push_enabled", False):
            resp = self.client.get("/v1/push/status")
        self.assertEqual(resp.status_code, 200, msg=resp.text)


if __name__ == "__main__":
    unittest.main()
