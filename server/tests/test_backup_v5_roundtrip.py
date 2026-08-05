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

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.export import (
    BACKUP_SCHEMA_VERSION,
    _build_json_payload,
    _build_manifest,
    _import_data_json,
    _load_all_data,
)
from app.db.base import Base
from app.models import (
    ChatKey,
    ChatMessage,
    ChatMessageFavorite,
    ChatPinnedQuote,
    Coupon,
    FcmDeviceToken,
    LedgerEntry,
    ListenLocalTrack,
    Notification,
    PeriodCycle,
    PushSubscription,
    SiteSetting,
    UploadReference,
    User,
)
from app.models.user import UserRole


class BackupV6RoundTripTests(unittest.TestCase):
    def _session_factory(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        return engine, sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    def test_remaining_modules_and_chat_metadata_round_trip(self) -> None:
        source_engine, SourceSession = self._session_factory()
        target_engine, TargetSession = self._session_factory()
        try:
            source = SourceSession()
            a = User(
                uid="user-a",
                username="backup_a",
                nickname="A",
                role=UserRole.partner_a,
                password_hash="x",
            )
            b = User(
                uid="user-b",
                username="backup_b",
                nickname="B",
                role=UserRole.partner_b,
                password_hash="x",
            )
            source.add_all([a, b, SiteSetting(id=1, site_name="Round trip")])
            source.flush()

            verifier_cipher = "c2hhcmVkLXZlcmlmaWVy"
            source.add(
                ChatKey(
                    user_id=a.id,
                    salt="c2hhcmVkLXNhbHQ=",
                    verifier_iv="c2hhcmVkLWl2",
                    verifier_cipher=verifier_cipher,
                    verifier_hash=hashlib.sha256(verifier_cipher.encode()).hexdigest(),
                )
            )
            root = ChatMessage(
                mid="chat-root",
                sender_id=a.id,
                type="voice",
                media_url="/uploads/chat/root.weba",
                audio_duration_sec=17,
                visible_at=datetime.now(timezone.utc) + timedelta(hours=1),
                released_at=None,
            )
            source.add(root)
            source.flush()
            reply = ChatMessage(
                mid="chat-reply",
                sender_id=b.id,
                type="text",
                content="must-not-leak-from-e2ee-backup",
                is_encrypted=True,
                iv="cmVwbHktaXY=",
                ciphertext="cmVwbHktY2lwaGVy",
                algo="AES-GCM",
                reply_to_message_id=root.id,
                visible_at=datetime.now(timezone.utc),
                released_at=datetime.now(timezone.utc),
                recalled_at=datetime.now(timezone.utc),
            )
            source.add(reply)
            source.flush()
            source.add_all(
                [
                    ChatMessageFavorite(user_id=a.id, message_id=reply.id),
                    ChatPinnedQuote(user_id=b.id, message_id=root.id),
                    Coupon(
                        cpid="coupon-1",
                        author_id=a.id,
                        title="A hug",
                        status="redeemed",
                        redeemed_by_id=b.id,
                        redeemed_at=datetime.now(timezone.utc),
                    ),
                    LedgerEntry(
                        leid="ledger-1",
                        author_id=a.id,
                        payer_id=b.id,
                        title="Dinner",
                        amount_cents=12345,
                        split_type="aa",
                        spent_on=date(2026, 7, 17),
                    ),
                    PeriodCycle(
                        pcid="period-1",
                        author_id=a.id,
                        start_date=date(2026, 7, 1),
                        end_date=date(2026, 7, 5),
                        note="note",
                    ),
                    ListenLocalTrack(
                        tid="track-1",
                        name="Local song",
                        artists_json='["A", "B"]',
                        audio_url="/uploads/listen/song.mp3",
                        uploaded_by_uid=a.uid,
                    ),
                    PushSubscription(
                        sid="push-1",
                        user_id=a.id,
                        endpoint="https://push.example/one",
                        p256dh="p256dh",
                        auth="auth",
                    ),
                    FcmDeviceToken(
                        tid="fcm-1",
                        user_id=b.id,
                        token="fcm-token",
                        platform="android",
                    ),
                    Notification(
                        nid="notification-1",
                        recipient_id=b.id,
                        type="test",
                        title="Delivered",
                        delivery_status="delivered",
                        delivery_attempts=2,
                    ),
                ]
            )
            source.commit()

            data = _load_all_data(source)
            manifest = _build_manifest(data, "backup-v6", a.uid)
            payload = _build_json_payload(data, manifest)
            self.assertEqual(BACKUP_SCHEMA_VERSION, "v6")
            exported_reply = next(
                item for item in payload["chat_messages"] if item["mid"] == "chat-reply"
            )
            self.assertIsNone(exported_reply["content"])
            for section in (
                "coupons",
                "ledger_entries",
                "period_cycles",
                "listen_local_tracks",
                "push_subscriptions",
                "fcm_device_tokens",
                "chat_favorites",
                "chat_pinned_quotes",
                "chat_key",
            ):
                self.assertEqual(manifest["counts"][section], 1)

            target = TargetSession()
            result = _import_data_json(target, payload)
            target.commit()

            restored_reply = target.query(ChatMessage).filter_by(mid="chat-reply").one()
            self.assertEqual(restored_reply.reply_to.mid, "chat-root")
            self.assertIsNotNone(restored_reply.recalled_at)
            self.assertTrue(restored_reply.is_encrypted)
            self.assertEqual(restored_reply.ciphertext, "cmVwbHktY2lwaGVy")
            self.assertEqual(restored_reply.algo, "AES-GCM")
            self.assertEqual(target.query(ChatKey).one().salt, "c2hhcmVkLXNhbHQ=")
            self.assertEqual(
                target.query(ChatMessage).filter_by(mid="chat-root").one().audio_duration_sec,
                17,
            )
            self.assertEqual(target.query(ChatMessageFavorite).count(), 1)
            self.assertEqual(target.query(ChatPinnedQuote).count(), 1)
            self.assertEqual(target.query(Coupon).one().redeemed_by.uid, "user-b")
            self.assertEqual(target.query(LedgerEntry).one().amount_cents, 12345)
            self.assertEqual(target.query(PeriodCycle).one().end_date, date(2026, 7, 5))
            self.assertEqual(target.query(ListenLocalTrack).one().artists, ["A", "B"])
            self.assertEqual(target.query(PushSubscription).count(), 1)
            self.assertEqual(target.query(FcmDeviceToken).count(), 1)
            self.assertEqual(target.query(Notification).one().delivery_status, "delivered")
            self.assertEqual(result["listen_local_tracks"]["created"], 1)

            local_ref = target.query(UploadReference).filter_by(content_kind="listen").one()
            self.assertEqual(local_ref.file_path, "/uploads/listen/song.mp3")

            second = _import_data_json(target, payload)
            target.commit()
            self.assertEqual(second["coupons"]["created"], 0)
            self.assertFalse(second["chat_key"]["restored"])
            self.assertEqual(target.query(Coupon).count(), 1)
            self.assertEqual(target.query(ChatMessageFavorite).count(), 1)
        finally:
            source_engine.dispose()
            target_engine.dispose()


if __name__ == "__main__":
    unittest.main()
