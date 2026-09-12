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
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import auth as auth_module
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole


class AuthApiTests(unittest.TestCase):
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

        def _get_db_override():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _get_db_override
        cls.client = TestClient(app)
        # Recovery/login tests make several calls in quick succession; the
        # production rate limits would trip on the shared testclient IP.
        cls._limiter_was_enabled = auth_module.limiter.enabled
        auth_module.limiter.enabled = False

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        auth_module.limiter.enabled = cls._limiter_was_enabled
        cls.engine.dispose()

    def setUp(self) -> None:
        db = self.SessionLocal()
        try:
            db.query(User).delete()
            db.commit()
        finally:
            db.close()

    def _add_user(self, **overrides) -> User:
        fields = dict(
            username="admin",
            nickname="Admin",
            role=UserRole.partner_a,
            password_hash="old-hash",
        )
        fields.update(overrides)
        user = User(**fields)
        db = self.SessionLocal()
        try:
            db.add(user)
            db.commit()
            db.refresh(user)
            uid = user.uid
            session_version = user.session_version
        finally:
            db.close()
        return user

    def test_bootstrap_status_only_exposes_bootstrapped_state(self) -> None:
        with patch("app.api.v1.auth.settings.bootstrap_setup_token", "configured-token"):
            resp = self.client.get("/v1/auth/bootstrap-status")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        self.assertEqual(resp.json(), {"bootstrapped": False})

    def test_bootstrap_status_reports_completed_bootstrap_without_extra_flags(self) -> None:
        self._add_user()

        resp = self.client.get("/v1/auth/bootstrap-status")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        self.assertEqual(resp.json(), {"bootstrapped": True})

    # ── POST /v1/auth/password-recovery ─────────────────────────────────────

    def test_password_recovery_resets_password_and_clears_freeze(self) -> None:
        self._add_user(
            login_failed_count=5,
            login_freeze_until=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

        with patch("app.api.v1.auth.settings.bootstrap_setup_token", "configured-token"):
            resp = self.client.post(
                "/v1/auth/password-recovery",
                json={"username": "admin", "new_password": "freshPassword1"},
                headers={"X-Bootstrap-Token": "configured-token"},
            )

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        self.assertEqual(resp.json(), {"ok": True})

        db = self.SessionLocal()
        try:
            user = db.query(User).filter(User.username == "admin").one()
            self.assertEqual(user.login_failed_count, 0)
            self.assertIsNone(user.login_freeze_until)
            self.assertGreater(user.session_version, 0)
            self.assertIsNotNone(user.password_changed_at)
        finally:
            db.close()

        login = self.client.post(
            "/v1/auth/login", json={"username": "admin", "password": "freshPassword1"}
        )
        self.assertEqual(login.status_code, 200, msg=login.text)

    def test_password_recovery_rejects_invalid_token(self) -> None:
        self._add_user()

        with patch("app.api.v1.auth.settings.bootstrap_setup_token", "configured-token"):
            resp = self.client.post(
                "/v1/auth/password-recovery",
                json={"username": "admin", "new_password": "freshPassword1"},
                headers={"X-Bootstrap-Token": "wrong-token"},
            )

        self.assertEqual(resp.status_code, 401, msg=resp.text)

    def test_password_recovery_rejects_missing_token(self) -> None:
        self._add_user()

        with patch("app.api.v1.auth.settings.bootstrap_setup_token", "configured-token"):
            resp = self.client.post(
                "/v1/auth/password-recovery",
                json={"username": "admin", "new_password": "freshPassword1"},
            )

        self.assertEqual(resp.status_code, 401, msg=resp.text)

    def test_password_recovery_disabled_without_configured_token(self) -> None:
        self._add_user()

        with patch("app.api.v1.auth.settings.bootstrap_setup_token", ""):
            resp = self.client.post(
                "/v1/auth/password-recovery",
                json={"username": "admin", "new_password": "freshPassword1"},
                headers={"X-Bootstrap-Token": "configured-token"},
            )

        self.assertEqual(resp.status_code, 403, msg=resp.text)

    def test_password_recovery_unknown_user_returns_404(self) -> None:
        with patch("app.api.v1.auth.settings.bootstrap_setup_token", "configured-token"):
            resp = self.client.post(
                "/v1/auth/password-recovery",
                json={"username": "nobody", "new_password": "freshPassword1"},
                headers={"X-Bootstrap-Token": "configured-token"},
            )

        self.assertEqual(resp.status_code, 404, msg=resp.text)

    def test_password_recovery_rejects_visitor_accounts(self) -> None:
        self._add_user(role=UserRole.visitor)

        with patch("app.api.v1.auth.settings.bootstrap_setup_token", "configured-token"):
            resp = self.client.post(
                "/v1/auth/password-recovery",
                json={"username": "admin", "new_password": "freshPassword1"},
                headers={"X-Bootstrap-Token": "configured-token"},
            )

        self.assertEqual(resp.status_code, 403, msg=resp.text)

    def test_password_recovery_rejects_weak_password(self) -> None:
        self._add_user()

        with patch("app.api.v1.auth.settings.bootstrap_setup_token", "configured-token"):
            resp = self.client.post(
                "/v1/auth/password-recovery",
                json={"username": "admin", "new_password": "nodigitpassword"},
                headers={"X-Bootstrap-Token": "configured-token"},
            )

        self.assertEqual(resp.status_code, 422, msg=resp.text)


if __name__ == "__main__":
    unittest.main()
