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

"""Smoke tests for chat enhancement features:

- Message favorites (收藏消息)
- Pinned quotes (置顶一句)
- Future messages (发送给未来的消息)
- Chat keywords (聊天关键词)
- Memory card (聊天纪念卡)

The endpoint handlers are plain functions whose FastAPI ``Depends`` defaults can
be overridden by passing ``db`` / ``current_user`` directly, so we exercise the
real business logic against an in-memory SQLite database.
"""
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
# Import model modules so their tables register on Base.metadata.
from app.models import ChatMessage, ChatMessageFavorite, ChatPinnedQuote  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.user import User, UserRole

from app.api.v1.cottage_chat import (
    chat_state,
    clear_pinned_quote,
    favorite_message,
    get_media_panel,
    get_keywords,
    get_memory_card,
    get_pinned_quote,
    list_favorites,
    list_messages,
    list_future_messages,
    recall_message,
    send_message,
    set_pinned_quote,
    unfavorite_message,
)
from app.schemas.cottage_chat import ChatSendRequest, ChatPinnedQuoteRequest
from app.services.chat_features import release_due_future_messages


class ChatEnhancementsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.queue_delivery_patcher = patch(
            "app.services.notifications.queue_notification_delivery",
            lambda db, item: None,
        )
        self.queue_delivery_patcher.start()
        self.db = self.Session()
        self.a = self._partner("alice", UserRole.partner_a)
        self.b = self._partner("bob", UserRole.partner_b)

    def tearDown(self) -> None:
        self.db.close()
        self.queue_delivery_patcher.stop()
        self.engine.dispose()

    def _partner(self, username: str, role: UserRole) -> User:
        user = User(username=username, nickname=username, role=role, password_hash="hash")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _send_test_message(self, content: str, sender: User, visible_at: datetime | None = None) -> ChatMessage:
        req = ChatSendRequest(type="text", content=content, visible_at=visible_at)
        resp = send_message(payload=req, db=self.db, current_user=sender)
        msg = self.db.query(ChatMessage).filter(ChatMessage.mid == resp.mid).first()
        assert msg is not None
        return msg

    def _send_raw(self, payload: ChatSendRequest, sender: User):
        return send_message(payload=payload, db=self.db, current_user=sender)

    # ── message favorites ──────────────────────────────────────────────────
    def test_favorite_and_unfavorite_message(self) -> None:
        msg = self._send_test_message("Hello 世界!", self.a)

        # Alice favorites the message
        favorite_message(mid=msg.mid, db=self.db, current_user=self.a)
        favorites = list_favorites(db=self.db, current_user=self.a)
        self.assertEqual(len(favorites.items), 1)
        self.assertEqual(favorites.items[0].content, "Hello 世界!")
        self.assertTrue(favorites.items[0].is_favorite)

        # Unfavorite it
        unfavorite_message(mid=msg.mid, db=self.db, current_user=self.a)
        favorites = list_favorites(db=self.db, current_user=self.a)
        self.assertEqual(len(favorites.items), 0)

    def test_favorite_idempotent(self) -> None:
        msg = self._send_test_message("Hello again!", self.a)

        # Favorite twice should not error or create duplicates
        favorite_message(mid=msg.mid, db=self.db, current_user=self.a)
        favorite_message(mid=msg.mid, db=self.db, current_user=self.a)

        count = self.db.query(ChatMessageFavorite).count()
        self.assertEqual(count, 1)

    def test_favorite_nonexistent_message(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            favorite_message(mid="not-exist", db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 404)

    # ── pinned quotes ──────────────────────────────────────────────────────
    def test_set_and_get_pinned_quote(self) -> None:
        msg = self._send_test_message("我爱你", self.b)

        # Alice pins Bob's message
        set_pinned_quote(payload=ChatPinnedQuoteRequest(mid=msg.mid), db=self.db, current_user=self.a)
        pinned = get_pinned_quote(db=self.db, current_user=self.a)
        self.assertIsNotNone(pinned.message)
        self.assertEqual(pinned.message.content, "我爱你")

        # Clear it
        clear_pinned_quote(db=self.db, current_user=self.a)
        pinned = get_pinned_quote(db=self.db, current_user=self.a)
        self.assertIsNone(pinned.message)

    def test_pinned_quote_replace(self) -> None:
        msg1 = self._send_test_message("First message", self.b)
        msg2 = self._send_test_message("Second message", self.b)

        set_pinned_quote(payload=ChatPinnedQuoteRequest(mid=msg1.mid), db=self.db, current_user=self.a)
        set_pinned_quote(payload=ChatPinnedQuoteRequest(mid=msg2.mid), db=self.db, current_user=self.a)

        pinned = get_pinned_quote(db=self.db, current_user=self.a)
        self.assertEqual(pinned.message.content, "Second message")

    def test_cannot_pin_non_text_message(self) -> None:
        req = ChatSendRequest(type="image", media_url="/uploads/test.jpg")
        resp = send_message(payload=req, db=self.db, current_user=self.b)

        with self.assertRaises(HTTPException) as ctx:
            set_pinned_quote(payload=ChatPinnedQuoteRequest(mid=resp.mid), db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 400)

    # ── future messages ────────────────────────────────────────────────────
    def test_future_message_creation_and_release(self) -> None:
        future_time = datetime.now(timezone.utc) + timedelta(hours=24)
        msg = self._send_test_message("To my future self", self.a, visible_at=future_time)

        # Initially not released
        self.assertIsNone(msg.released_at)
        future_list = list_future_messages(db=self.db, current_user=self.a)
        self.assertEqual(len(future_list.items), 1)

        # Fast-forward time and release
        msg.visible_at = datetime.now(timezone.utc) - timedelta(hours=1)
        self.db.commit()
        released = release_due_future_messages(self.db)
        self.assertEqual(released, 1)
        self.db.refresh(msg)
        self.assertIsNotNone(msg.released_at)

    def test_future_message_not_visible_to_others(self) -> None:
        future_time = datetime.now(timezone.utc) + timedelta(hours=24)
        self._send_test_message("Secret future message", self.a, visible_at=future_time)

        # Bob only sees his own future messages, so Alice's future note stays hidden.
        future_list = list_future_messages(db=self.db, current_user=self.b)
        self.assertEqual(len(future_list.items), 0)

    # ── reply / recall / media / state ─────────────────────────────────────
    def test_reply_message_round_trip(self) -> None:
        source = self._send_test_message("原消息", self.a)
        reply = self._send_raw(
            ChatSendRequest(type="text", content="回复内容", reply_to_mid=source.mid),
            self.b,
        )
        self.assertIsNotNone(reply.reply_to)
        self.assertEqual(reply.reply_to.mid, source.mid)
        self.assertEqual(reply.reply_to.content, "原消息")

        history = list_messages(db=self.db, current_user=self.a)
        replied = next(item for item in history.items if item.mid == reply.mid)
        self.assertIsNotNone(replied.reply_to)
        self.assertEqual(replied.reply_to.mid, source.mid)

    def test_recall_message_updates_viewer_specific_content(self) -> None:
        message = self._send_test_message("马上撤回", self.a)
        recalled = recall_message(mid=message.mid, db=self.db, current_user=self.a)
        self.assertTrue(recalled.is_recalled)
        self.assertEqual(recalled.content, "你撤回了一条消息")
        self.assertIsNone(recalled.media_url)
        self.assertFalse(recalled.can_recall)

        owner_history = list_messages(db=self.db, current_user=self.a)
        partner_history = list_messages(db=self.db, current_user=self.b)
        owner_item = next(item for item in owner_history.items if item.mid == message.mid)
        partner_item = next(item for item in partner_history.items if item.mid == message.mid)
        self.assertEqual(owner_item.content, "你撤回了一条消息")
        self.assertEqual(partner_item.content, "Ta 撤回了一条消息")

    def test_media_panel_groups_voice_and_favorites(self) -> None:
        image = self._send_raw(
            ChatSendRequest(type="image", media_url="/uploads/chat/test-image.jpg"),
            self.a,
        )
        self._send_raw(
            ChatSendRequest(type="sticker", media_url="/uploads/chat/test-sticker.png"),
            self.b,
        )
        voice = self._send_raw(
            ChatSendRequest(
                type="voice",
                media_url="/uploads/chat/test-voice.weba",
                audio_duration_sec=9,
            ),
            self.a,
        )
        favorite_message(mid=image.mid, db=self.db, current_user=self.a)

        panel = get_media_panel(db=self.db, current_user=self.a)
        self.assertEqual(len(panel.images), 1)
        self.assertEqual(len(panel.stickers), 1)
        self.assertEqual(len(panel.voices), 1)
        self.assertEqual(panel.voices[0].audio_duration_sec, 9)
        self.assertEqual(panel.voices[0].mid, voice.mid)
        self.assertEqual(len(panel.favorites), 1)
        self.assertEqual(panel.favorites[0].mid, image.mid)

    def test_chat_state_exposes_presence_times(self) -> None:
        online_since = datetime.now(timezone.utc) - timedelta(minutes=10)
        last_active = datetime.now(timezone.utc) - timedelta(minutes=1)
        with patch("app.api.v1.cottage_chat.manager.is_online") as is_online, patch(
            "app.api.v1.cottage_chat.manager.online_since"
        ) as online_since_mock, patch(
            "app.api.v1.cottage_chat.manager.last_active_at"
        ) as last_active_mock:
            is_online.side_effect = lambda uid: uid in {self.a.uid, self.b.uid}
            online_since_mock.side_effect = lambda uid: online_since if uid == self.b.uid else None
            last_active_mock.side_effect = lambda uid: last_active if uid == self.b.uid else None

            state = chat_state(db=self.db, current_user=self.a)

        self.assertEqual(state.partner_uid, self.b.uid)
        self.assertTrue(state.partner_online)
        self.assertTrue(state.self_online)
        self.assertEqual(state.partner_online_since, online_since)
        self.assertEqual(state.partner_last_active_at, last_active)

    # ── keywords ───────────────────────────────────────────────────────────
    def test_keyword_extraction(self) -> None:
        today = date.today()
        now = datetime.now(timezone.utc)

        self._send_test_message("今天天气真好", self.a, visible_at=now)
        self._send_test_message("是的，我们去散步吧", self.b, visible_at=now)
        self._send_test_message("好啊，散步很开心", self.a, visible_at=now)

        keywords = get_keywords(on=today, db=self.db, current_user=self.a)
        self.assertEqual(keywords.on, today)
        self.assertTrue(any(item.keyword == "散步" for item in keywords.items))

    def test_keyword_filter_stopwords(self) -> None:
        today = date.today()
        now = datetime.now(timezone.utc)

        self._send_test_message("我们今天真的很开心", self.a, visible_at=now)
        self._send_test_message("是的，是的", self.b, visible_at=now)

        keywords = get_keywords(on=today, db=self.db, current_user=self.a)
        # Stopwords like "我们", "今天", "真的" should be filtered out
        self.assertTrue(all(k.keyword not in ["我们", "今天", "真的"] for k in keywords.items))

    # ── memory card ────────────────────────────────────────────────────────
    def test_memory_card_generation(self) -> None:
        today = date.today()
        now = datetime.now(timezone.utc)

        msg1 = self._send_test_message("早安！", self.a, visible_at=now)
        msg2 = self._send_test_message("早上好呀", self.b, visible_at=now)
        msg3 = self._send_test_message("今天一起吃饭吧", self.a, visible_at=now)

        # Alice favorites msg3
        favorite_message(mid=msg3.mid, db=self.db, current_user=self.a)
        # Alice pins msg2
        set_pinned_quote(payload=ChatPinnedQuoteRequest(mid=msg2.mid), db=self.db, current_user=self.a)

        card = get_memory_card(on=today, db=self.db, current_user=self.a)
        self.assertEqual(card.on, today)
        self.assertEqual(card.total_messages, 3)
        self.assertEqual(card.self_messages, 2)
        self.assertEqual(card.partner_messages, 1)
        self.assertEqual(card.favorite_count, 1)
        self.assertIsNotNone(card.first_message)
        self.assertIsNotNone(card.last_message)
        self.assertIsNotNone(card.pinned_quote)
        self.assertEqual(card.first_message.content, "早安！")
        self.assertEqual(card.last_message.content, "今天一起吃饭吧")
        self.assertEqual(card.pinned_quote.content, "早上好呀")
        self.assertTrue(any(item.keyword for item in card.keywords))

    def test_empty_memory_card(self) -> None:
        yesterday = date.today() - timedelta(days=1)
        card = get_memory_card(on=yesterday, db=self.db, current_user=self.a)
        self.assertEqual(card.total_messages, 0)
        self.assertEqual(card.self_messages, 0)
        self.assertEqual(card.partner_messages, 0)
        self.assertIsNone(card.first_message)
        self.assertIsNone(card.last_message)
        self.assertIsNone(card.pinned_quote)


if __name__ == "__main__":
    unittest.main()
