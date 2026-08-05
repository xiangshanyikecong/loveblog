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

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.capsule import Capsule
from app.models.cottage_reminder import CottageReminder
from app.models.event import Event, Visibility
from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.models.user import User, UserRole
from app.services import notification_delivery
from app.services.notification_delivery import (
    DELIVERY_STATUS_DELIVERED,
    DELIVERY_STATUS_FAILED,
    NotificationDeliveryPayload,
    deliver_notification_payloads,
    retry_pending_notification_deliveries,
)
from app.services.notification_scheduler import run_notification_scheduler_tick
from app.services.notifications import (
    create_notification,
    create_due_capsule_reminders,
    run_scheduled_due_notifications,
)


class NotificationSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.notification_delivery_sessionlocal_patcher = patch.object(
            notification_delivery,
            "SessionLocal",
            self.Session,
        )
        self.notification_delivery_sessionlocal_patcher.start()
        self.db = self.Session()

    def tearDown(self) -> None:
        self.db.close()
        self.notification_delivery_sessionlocal_patcher.stop()
        self.engine.dispose()

    def _create_partner(self, *, username: str, role: UserRole) -> User:
        user = User(
            username=username,
            nickname=username,
            role=role,
            password_hash="hash",
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def test_capsule_open_creates_deduped_notification_for_both_partners(self) -> None:
        partner_a = self._create_partner(username="cap_a", role=UserRole.partner_a)
        partner_b = self._create_partner(username="cap_b", role=UserRole.partner_b)

        capsule = Capsule(
            author_id=partner_a.id,
            content="secret message",
            open_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        self.db.add(capsule)
        self.db.commit()
        self.db.refresh(capsule)

        created_a = create_due_capsule_reminders(self.db, partner_a)
        created_b = create_due_capsule_reminders(self.db, partner_b)
        self.db.commit()

        self.assertEqual(len(created_a), 1)
        self.assertEqual(len(created_b), 1)
        self.assertEqual(created_a[0].type, "capsule.open")
        self.assertEqual(created_a[0].source_id, capsule.uuid)

        create_due_capsule_reminders(self.db, partner_a)
        create_due_capsule_reminders(self.db, partner_b)
        self.db.commit()

        total = (
            self.db.query(Notification)
            .filter(Notification.type == "capsule.open", Notification.source_id == capsule.uuid)
            .count()
        )
        self.assertEqual(total, 2)

    def test_scheduler_creates_due_reminders(self) -> None:
        partner_a = self._create_partner(username="sched_a", role=UserRole.partner_a)
        partner_b = self._create_partner(username="sched_b", role=UserRole.partner_b)

        event = Event(
            creator_id=partner_a.id,
            title="First date",
            date=date.today(),
            visibility=Visibility.public,
            is_yearly_repeat=True,
        )
        reminder = CottageReminder(
            author_id=partner_a.id,
            title="Take a break",
            note="Stretch together.",
            remind_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            audience="both",
        )
        self.db.add_all([event, reminder])
        self.db.commit()

        created = run_scheduled_due_notifications(self.db)
        self.db.commit()

        self.assertGreaterEqual(len(created), 1)
        types = {item.type for item in created}
        self.assertIn("cottage_reminder.due", types)

        partner_b_notifications = (
            self.db.query(Notification)
            .filter(Notification.recipient_id == partner_b.id)
            .all()
        )
        self.assertTrue(partner_b_notifications)

    @patch("app.services.notification_delivery.deliver_notification_payloads")
    @patch("app.services.notification_delivery.SessionLocal")
    @patch("app.services.notification_scheduler.SessionLocal")
    def test_scheduler_tick_commits_and_delivers(
        self,
        scheduler_session_local_mock,
        delivery_session_local_mock,
        deliver_mock,
    ) -> None:
        scheduler_session_local_mock.return_value = self.db
        delivery_session_local_mock.side_effect = self.Session
        partner_a = self._create_partner(username="tick_a", role=UserRole.partner_a)
        self._create_partner(username="tick_b", role=UserRole.partner_b)

        capsule = Capsule(
            author_id=partner_a.id,
            content="hello future",
            open_at=datetime.now(timezone.utc) - timedelta(seconds=30),
        )
        self.db.add(capsule)
        self.db.commit()
        # Cache the business key now: run_notification_scheduler_tick() closes the
        # (mocked) shared session in its finally block, which detaches `capsule`,
        # so reading capsule.uuid afterwards would raise DetachedInstanceError.
        capsule_uuid = capsule.uuid

        count = run_notification_scheduler_tick()
        self.assertGreaterEqual(count, 1)
        deliver_mock.assert_called_once()
        persisted = (
            self.db.query(Notification)
            .filter(Notification.type == "capsule.open", Notification.source_id == capsule_uuid)
            .count()
        )
        self.assertEqual(persisted, 2)

    @patch("app.services.notification_scheduler.run_scheduled_due_notifications", return_value=[])
    @patch("app.services.notification_scheduler.retry_pending_notification_deliveries", return_value=1)
    @patch("app.services.notification_scheduler.SessionLocal")
    def test_scheduler_tick_retries_pending_deliveries_before_generating(
        self,
        session_local_mock,
        retry_mock,
        scheduled_mock,
    ) -> None:
        session_local_mock.return_value = self.db

        count = run_notification_scheduler_tick()

        self.assertEqual(count, 0)
        retry_mock.assert_called_once_with()
        scheduled_mock.assert_called_once_with(self.db, days_ahead=7)

    def test_web_push_gone_subscription_is_deactivated(self) -> None:
        partner = self._create_partner(username="push_a", role=UserRole.partner_a)
        subscription = PushSubscription(
            user_id=partner.id,
            endpoint="https://push.example.test/subscription",
            p256dh="key-p256dh",
            auth="key-auth",
            is_active=True,
        )
        self.db.add(subscription)
        self.db.commit()

        payload = NotificationDeliveryPayload(
            nid="nid-1",
            recipient_id=partner.id,
            type="message.new",
            title="Hello",
            body="World",
            link="/messages",
            source_type="message",
            source_id="msg-1",
        )

        class DummyResponse:
            status_code = 410

        class DummyWebPushException(Exception):
            def __init__(self, response):
                super().__init__("gone")
                self.response = response

        with patch.object(notification_delivery, "SessionLocal", self.Session), patch.object(
            notification_delivery.settings, "web_push_enabled", True
        ), patch.object(
            notification_delivery.settings, "web_push_vapid_public_key", "public"
        ), patch.object(notification_delivery.settings, "web_push_vapid_private_key", "private"), patch.object(
            notification_delivery.settings, "web_push_subject", "mailto:test@example.com"
        ), patch.object(notification_delivery, "WebPushException", DummyWebPushException), patch.object(
            notification_delivery,
            "webpush",
            side_effect=DummyWebPushException(DummyResponse()),
        ):
            deliver_notification_payloads([payload])

        self.db.expire_all()
        refreshed = self.db.query(PushSubscription).filter(PushSubscription.id == subscription.id).first()
        self.assertIsNotNone(refreshed)
        self.assertFalse(refreshed.is_active)
        self.assertEqual(refreshed.fail_count, 1)

    def test_after_commit_failure_marks_notification_for_retry(self) -> None:
        partner = self._create_partner(username="retry_a", role=UserRole.partner_a)

        with patch.object(notification_delivery, "SessionLocal", self.Session), patch.object(
            notification_delivery,
            "deliver_notification_payload",
            side_effect=RuntimeError("delivery exploded"),
        ):
            created = create_notification(
                self.db,
                recipient=partner,
                type="capsule.open",
                title="Retry me",
                source_type="capsule",
                source_id="capsule-retry",
                queue_delivery=True,
            )
            self.assertIsNotNone(created)
            self.db.commit()

        self.db.expire_all()
        notification = (
            self.db.query(Notification)
            .filter(Notification.source_id == "capsule-retry")
            .first()
        )
        self.assertIsNotNone(notification)
        self.assertEqual(notification.delivery_status, DELIVERY_STATUS_FAILED)
        self.assertEqual(notification.delivery_attempts, 1)
        self.assertIn("delivery exploded", notification.delivery_last_error)
        self.assertIsNone(notification.delivery_completed_at)

    def test_single_device_failure_does_not_mark_notification_delivered(self) -> None:
        partner = self._create_partner(username="device_failure", role=UserRole.partner_a)
        notification = Notification(
            nid="device-failure-notification",
            recipient_id=partner.id,
            type="message.new",
            title="Retry device",
            delivery_status="pending",
        )
        subscription = PushSubscription(
            user_id=partner.id,
            endpoint="https://push.example.test/failing-device",
            p256dh="key-p256dh",
            auth="key-auth",
        )
        self.db.add_all([notification, subscription])
        self.db.commit()

        payload = NotificationDeliveryPayload(
            nid=notification.nid,
            recipient_id=partner.id,
            type=notification.type,
            title=notification.title,
            body=None,
            link=None,
            source_type=None,
            source_id=None,
        )

        with patch.object(notification_delivery, "SessionLocal", self.Session), patch.object(
            notification_delivery.settings, "web_push_enabled", True
        ), patch.object(
            notification_delivery.settings, "web_push_vapid_public_key", "public"
        ), patch.object(notification_delivery.settings, "web_push_vapid_private_key", "private"), patch.object(
            notification_delivery.settings, "web_push_subject", "mailto:test@example.com"
        ), patch.object(notification_delivery, "webpush", side_effect=RuntimeError("device failed")):
            deliver_notification_payloads([payload])

        self.db.expire_all()
        refreshed = self.db.query(Notification).filter_by(nid=notification.nid).one()
        self.assertEqual(refreshed.delivery_status, DELIVERY_STATUS_FAILED)
        self.assertEqual(refreshed.delivery_attempts, 1)
        self.assertIn("web push failed", refreshed.delivery_last_error)

    def test_retry_pending_notification_deliveries_recovers_failed_notification(self) -> None:
        partner = self._create_partner(username="retry_b", role=UserRole.partner_a)
        notification = Notification(
            recipient_id=partner.id,
            type="capsule.open",
            title="Retry success",
            source_type="capsule",
            source_id="capsule-success",
            delivery_status=DELIVERY_STATUS_FAILED,
            delivery_attempts=1,
            delivery_last_error="previous failure",
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        with patch.object(notification_delivery, "SessionLocal", self.Session), patch.object(
            notification_delivery,
            "deliver_notification_payload",
            return_value=None,
        ) as deliver_mock:
            retried = retry_pending_notification_deliveries()

        self.assertEqual(retried, 1)
        deliver_mock.assert_called_once()

        self.db.expire_all()
        refreshed = self.db.query(Notification).filter(Notification.id == notification.id).first()
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed.delivery_status, DELIVERY_STATUS_DELIVERED)
        self.assertEqual(refreshed.delivery_attempts, 2)
        self.assertIsNone(refreshed.delivery_last_error)
        self.assertIsNotNone(refreshed.delivery_completed_at)


if __name__ == "__main__":
    unittest.main()
