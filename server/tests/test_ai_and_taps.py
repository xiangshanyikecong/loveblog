# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Tests for the optional AI assist endpoints and the cottage tap module.

The AI HTTP layer is fully mocked (patching ``app.services.ai_client``), so
the suite validates prompt wiring, degradation (503 when unconfigured),
embedding caching and response shaping without a live LLM.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models import (  # noqa: F401 — register tables on Base.metadata
    Article,
    ArticleBlock,
    CottageTap,
    Notification,
    User,
)
from app.models.user import UserRole
from app.api.v1 import ai as ai_module
from app.api.v1.ai import (
    ai_status,
    article_polish,
    generate_questions,
    monthly_report_narrative,
    semantic_search,
)
from app.api.v1.cottage_taps import send_tap, recent_taps, MAX_TAPS_PER_HOUR
from app.schemas.ai import (
    AIMonthlyReportRequest,
    AIPolishRequest,
    AIQuestionsRequest,
    AISemanticSearchRequest,
)
from app.schemas.cottage_tap import TapCreateRequest


def _fake_embed(texts):
    """Deterministic 2-D toy vectors: 'beach' axis vs 'work' axis."""

    def vec(text: str):
        return (
            [1.0, 0.0] if "海边" in text else [0.0, 1.0] if "加班" in text else [0.5, 0.5]
        )

    return [vec(text) for text in texts]


class AITestsBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.a = self._partner("alice", UserRole.partner_a)
        self.b = self._partner("bob", UserRole.partner_b)

        # AI off by default per test; individual tests flip it on.
        self._saved = {
            name: getattr(settings, name)
            for name in (
                "ai_enabled",
                "ai_base_url",
                "ai_chat_model",
                "ai_embedding_model",
            )
        }
        settings.ai_enabled = False
        settings.ai_base_url = ""
        settings.ai_chat_model = ""
        settings.ai_embedding_model = ""

        # Shared process-wide limiter: disabled for direct handler calls
        # (same approach as tests/test_auth_api.py).
        self._limiter_was_enabled = ai_module.limiter.enabled
        ai_module.limiter.enabled = False

    def tearDown(self) -> None:
        for name, value in self._saved.items():
            setattr(settings, name, value)
        ai_module.limiter.enabled = self._limiter_was_enabled
        self.db.close()
        self.engine.dispose()

    def _partner(self, username: str, role: UserRole) -> User:
        user = User(username=username, nickname=username, role=role, password_hash="hash")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _enable_ai(self, *, embedding: bool = True) -> None:
        settings.ai_enabled = True
        settings.ai_base_url = "http://ollama-test:11434/v1"
        settings.ai_chat_model = "qwen2.5"
        settings.ai_embedding_model = "bge-m3" if embedding else ""


class AIStatusAndPolishTests(AITestsBase):
    def test_status_disabled_by_default(self) -> None:
        status = ai_status(current_user=self.a)
        self.assertFalse(status.enabled)
        self.assertEqual(status.features, [])

    def test_status_reflects_configuration(self) -> None:
        self._enable_ai()
        status = ai_status(current_user=self.a)
        self.assertTrue(status.enabled)
        self.assertIn("article_polish", status.features)
        self.assertIn("semantic_search", status.features)

    def test_polish_degrades_to_503_when_unconfigured(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            article_polish(
                request=None,
                payload=AIPolishRequest(content="今天很开心", mode="polish"),
                db=self.db,
                current_user=self.a,
            )
        self.assertEqual(ctx.exception.status_code, 503)

    def test_polish_returns_model_text(self) -> None:
        self._enable_ai()
        with mock.patch(
            "app.services.ai_client.chat_completion", return_value="润色后的文字"
        ) as chat:
            result = article_polish(
                request=None,
                payload=AIPolishRequest(content="今天很开心", mode="polish"),
                db=self.db,
                current_user=self.a,
            )
        self.assertEqual(result.text, "润色后的文字")
        system_prompt = chat.call_args[0][0][0]["content"]
        self.assertIn("润色", system_prompt)
        self.assertEqual(chat.call_args[0][0][1]["content"], "今天很开心")

    def test_polish_visitor_forbidden(self) -> None:
        visitor = User(
            username="guest", nickname="guest", role=UserRole.visitor, password_hash="hash"
        )
        self.db.add(visitor)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            article_polish(
                request=None,
                payload=AIPolishRequest(content="x" * 10, mode="continue"),
                db=self.db,
                current_user=visitor,
            )
        self.assertEqual(ctx.exception.status_code, 403)


class AISemanticSearchTests(AITestsBase):
    def _seed_articles(self) -> None:
        beach = Article(author_id=self.a.id, title="海边的一天")
        self.db.add(beach)
        self.db.flush()
        self.db.add(
            ArticleBlock(
                article_id=beach.id,
                author_id=self.a.id,
                block_type="Paragraph",
                content="我们去海边散步，浪花打湿了鞋子。",
            )
        )
        work = Article(author_id=self.b.id, title="加班的一周", is_encrypted=False)
        self.db.add(work)
        self.db.flush()
        self.db.add(
            ArticleBlock(
                article_id=work.id,
                author_id=self.b.id,
                block_type="Paragraph",
                content="这周都在加班，好累。",
            )
        )
        # Encrypted article must be excluded from the corpus.
        secret = Article(author_id=self.a.id, title="密文", is_encrypted=True)
        self.db.add(secret)
        self.db.flush()
        self.db.add(
            ArticleBlock(
                article_id=secret.id,
                author_id=self.a.id,
                block_type="Paragraph",
                content="海边海边",
            )
        )
        self.db.commit()

    def test_semantic_search_ranking_and_cache(self) -> None:
        self._enable_ai()
        self._seed_articles()

        with mock.patch(
            "app.services.ai_client.embed_texts", side_effect=_fake_embed
        ) as embed:
            first = semantic_search(
                request=None,
                payload=AISemanticSearchRequest(query="想去海边玩"),
                db=self.db,
                current_user=self.a,
            )
            self.assertEqual(first.indexed_count, 2)
            self.assertEqual(first.results[0].title, "海边的一天")
            self.assertGreater(first.results[0].score, 0.99)
            self.assertEqual(len(first.results), 2)

            # Second search: corpus embeddings served from cache → only the
            # query embedding call remains.
            calls_after_first = embed.call_count
            second = semantic_search(
                request=None,
                payload=AISemanticSearchRequest(query="最近总在加班"),
                db=self.db,
                current_user=self.b,
            )
            self.assertEqual(embed.call_count, calls_after_first + 1)
            self.assertEqual(second.results[0].title, "加班的一周")

        from app.models.article_embedding import ArticleEmbedding

        self.assertEqual(self.db.query(ArticleEmbedding).count(), 2)

    def test_semantic_search_requires_embedding_model(self) -> None:
        self._enable_ai(embedding=False)
        with self.assertRaises(HTTPException) as ctx:
            semantic_search(
                request=None,
                payload=AISemanticSearchRequest(query="海边"),
                db=self.db,
                current_user=self.a,
            )
        self.assertEqual(ctx.exception.status_code, 503)


class AIMonthlyAndQuestionsTests(AITestsBase):
    def test_monthly_report_prompt_contains_stats(self) -> None:
        self._enable_ai()
        year, month = datetime.now().year, datetime.now().month
        with mock.patch(
            "app.services.ai_client.chat_completion", return_value="这个月你们……"
        ) as chat:
            result = monthly_report_narrative(
                request=None,
                payload=AIMonthlyReportRequest(year=year, month=month),
                db=self.db,
                current_user=self.a,
            )
        self.assertEqual(result.text, "这个月你们……")
        prompt = chat.call_args[0][0][0]["content"]
        self.assertIn(f"{year} 年 {month} 月", prompt)
        self.assertIn("报备次数", prompt)

    def test_question_parsing_strips_numbering(self) -> None:
        self._enable_ai()
        raw = "1. 你们第一次约会去了哪里？\n2. 最想一起学的一项新技能是什么？\n- 如果明天放假，你们会做什么？"
        with mock.patch("app.services.ai_client.chat_completion", return_value=raw):
            result = generate_questions(
                request=None,
                payload=AIQuestionsRequest(count=3),
                db=self.db,
                current_user=self.a,
            )
        self.assertEqual(
            result.questions,
            [
                "你们第一次约会去了哪里？",
                "最想一起学的一项新技能是什么？",
                "如果明天放假，你们会做什么？",
            ],
        )

    def test_question_failure_maps_to_502(self) -> None:
        self._enable_ai()
        from app.services.ai_client import AIServiceError

        with mock.patch(
            "app.services.ai_client.chat_completion",
            side_effect=AIServiceError(502, "empty"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                generate_questions(
                    request=None,
                    payload=AIQuestionsRequest(count=2),
                    db=self.db,
                    current_user=self.a,
                )
            self.assertEqual(ctx.exception.status_code, 502)


class CottageTapTests(AITestsBase):
    def test_send_tap_creates_row_and_partner_notification(self) -> None:
        result = send_tap(
            payload=TapCreateRequest(kind="tap"), db=self.db, current_user=self.a
        )
        self.assertEqual(result.from_nickname, "alice")
        self.assertEqual(result.to_nickname, "bob")
        self.assertEqual(result.kind, "tap")

        note = (
            self.db.query(Notification)
            .filter(Notification.type == "cottage.tap", Notification.recipient_id == self.b.id)
            .count()
        )
        self.assertEqual(note, 1)
        self.assertEqual(self.db.query(CottageTap).count(), 1)

    def test_heartbeat_kind_title(self) -> None:
        send_tap(payload=TapCreateRequest(kind="heartbeat"), db=self.db, current_user=self.b)
        note = (
            self.db.query(Notification)
            .filter(Notification.recipient_id == self.a.id)
            .first()
        )
        self.assertIn("心跳", note.title)

    def test_rate_guard(self) -> None:
        now = datetime.now(timezone.utc)
        for _ in range(MAX_TAPS_PER_HOUR):
            self.db.add(
                CottageTap(
                    sender_id=self.a.id,
                    recipient_id=self.b.id,
                    kind="tap",
                    created_at=now,
                )
            )
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            send_tap(payload=TapCreateRequest(kind="tap"), db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_recent_taps_lists_couple_only(self) -> None:
        now = datetime.now(timezone.utc)
        self.db.add(
            CottageTap(
                sender_id=self.a.id,
                recipient_id=self.b.id,
                kind="tap",
                created_at=now - timedelta(days=1),
            )
        )
        # A tap between two outsiders must never appear for the couple.
        outsider = self._partner("carol", UserRole.visitor)
        self.db.add(
            CottageTap(
                sender_id=outsider.id,
                recipient_id=outsider.id,
                kind="tap",
                created_at=now,
            )
        )
        self.db.commit()

        result = recent_taps(limit=10, db=self.db, current_user=self.b)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].from_nickname, "alice")

    def test_visitor_forbidden(self) -> None:
        visitor = User(
            username="guest", nickname="guest", role=UserRole.visitor, password_hash="hash"
        )
        self.db.add(visitor)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            send_tap(payload=TapCreateRequest(kind="tap"), db=self.db, current_user=visitor)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
