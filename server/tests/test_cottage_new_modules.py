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

"""Smoke tests for the new cottage modules:

- 甜蜜兑换券 (coupons)
- 情侣账本 / AA 记账 (ledger)
- 生理期记录与关怀提醒 (period tracker + scheduler reminder)

The endpoint handlers are plain functions whose FastAPI ``Depends`` defaults can
be overridden by passing ``db`` / ``current_user`` directly, so we exercise the
real business logic against an in-memory SQLite database.
"""
import unittest
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
# Import model modules so their tables register on Base.metadata.
from app.models import Coupon, LedgerEntry, PeriodCycle  # noqa: F401
from app.models.user import User, UserRole

from app.api.v1.cottage_coupons import create_coupon, list_coupons, redeem_coupon
from app.api.v1.cottage_ledger import create_entry, ledger_summary
from app.api.v1.cottage_period import create_cycle, period_summary
from app.schemas.coupon import CouponCreateRequest
from app.schemas.ledger import LedgerCreateRequest
from app.schemas.period_cycle import PeriodCreateRequest
from app.services.notifications import create_due_period_reminders
from app.models.notification import Notification


class CottageNewModulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.a = self._partner("alice", UserRole.partner_a)
        self.b = self._partner("bob", UserRole.partner_b)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _partner(self, username: str, role: UserRole) -> User:
        user = User(username=username, nickname=username, role=role, password_hash="hash")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    # ── coupons ────────────────────────────────────────────────────────────
    def test_coupon_redeem_flow(self) -> None:
        created = create_coupon(
            payload=CouponCreateRequest(title="一次免做家务券", icon="🧹"),
            db=self.db,
            current_user=self.a,
        )
        self.assertEqual(created.status, "active")
        self.assertTrue(created.is_mine)  # author viewing own coupon

        # Author cannot redeem their own coupon.
        with self.assertRaises(HTTPException) as ctx:
            redeem_coupon(cpid=created.cpid, db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 400)

        # Partner can; it becomes redeemed and notifies the author.
        redeemed = redeem_coupon(cpid=created.cpid, db=self.db, current_user=self.b)
        self.assertEqual(redeemed.status, "redeemed")
        self.assertEqual(redeemed.redeemed_by_nickname, "bob")

        note = (
            self.db.query(Notification)
            .filter(Notification.type == "coupon.redeemed", Notification.recipient_id == self.a.id)
            .count()
        )
        self.assertEqual(note, 1)

        # Double redeem is rejected.
        with self.assertRaises(HTTPException):
            redeem_coupon(cpid=created.cpid, db=self.db, current_user=self.b)

        received = list_coupons(box="received", db=self.db, current_user=self.b)
        self.assertEqual(received.total, 1)
        self.assertEqual(received.redeemed, 1)

    # ── ledger ─────────────────────────────────────────────────────────────
    def test_ledger_balance_aa_and_full(self) -> None:
        today = date.today()
        # Alice paid 100.00, split AA → Bob owes Alice 50.00.
        create_entry(
            payload=LedgerCreateRequest(
                title="晚饭", amount_cents=10000, payer="me", split_type="aa", spent_on=today
            ),
            db=self.db,
            current_user=self.a,
        )
        # Alice paid 30.00 for Bob fully → Bob owes Alice another 30.00.
        create_entry(
            payload=LedgerCreateRequest(
                title="打车", amount_cents=3000, payer="me", split_type="owed_full", spent_on=today
            ),
            db=self.db,
            current_user=self.a,
        )
        # Alice treats 20.00 → no debt change.
        create_entry(
            payload=LedgerCreateRequest(
                title="奶茶", amount_cents=2000, payer="me", split_type="treat", spent_on=today
            ),
            db=self.db,
            current_user=self.a,
        )

        summary = ledger_summary(month=None, db=self.db, current_user=self.a)
        self.assertEqual(summary.total_spent_cents, 15000)
        self.assertEqual(summary.entry_count, 3)
        self.assertFalse(summary.balance.settled)
        self.assertEqual(summary.balance.creditor_nickname, "alice")
        self.assertEqual(summary.balance.debtor_nickname, "bob")
        self.assertEqual(summary.balance.amount_cents, 8000)  # 5000 + 3000

    # ── period ─────────────────────────────────────────────────────────────
    def test_period_prediction_and_care_reminder(self) -> None:
        today = date.today()
        # Two cycles 28 days apart; last start 27 days ago → next predicted tomorrow.
        create_cycle(
            payload=PeriodCreateRequest(start_date=today - timedelta(days=55)),
            db=self.db,
            current_user=self.a,
        )
        create_cycle(
            payload=PeriodCreateRequest(start_date=today - timedelta(days=27)),
            db=self.db,
            current_user=self.a,
        )

        summary = period_summary(db=self.db, current_user=self.a)
        self.assertEqual(summary.cycle_count, 2)
        self.assertEqual(summary.avg_cycle_days, 28)
        self.assertEqual(summary.predicted_next_start, today + timedelta(days=1))
        self.assertEqual(summary.predicted_days_until, 1)
        self.assertEqual(summary.phase, "due_soon")

        # Bob (the non-tracking partner) gets a care reminder; Alice does not.
        created_b = create_due_period_reminders(self.db, self.b)
        self.db.commit()
        self.assertEqual(len(created_b), 1)
        self.assertEqual(created_b[0].type, "period.care")
        self.assertEqual(created_b[0].recipient_id, self.b.id)

        created_a = create_due_period_reminders(self.db, self.a)
        self.db.commit()
        self.assertEqual(len(created_a), 0)

        # Idempotent: running again for Bob creates no duplicate.
        create_due_period_reminders(self.db, self.b)
        self.db.commit()
        total = self.db.query(Notification).filter(Notification.type == "period.care").count()
        self.assertEqual(total, 1)


if __name__ == "__main__":
    unittest.main()
