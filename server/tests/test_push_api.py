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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_optional_user, get_token, get_token_optional
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.fcm_device_token import FcmDeviceToken
from app.models.push_subscription import PushSubscription
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole


class PushApiTests(unittest.TestCase):
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
                username="push_user",
                nickname="Push User",
                role=UserRole.partner_a,
                password_hash="x",
            )
            other = User(
                username="push_other",
                nickname="Push Other",
                role=UserRole.visitor,
                password_hash="x",
            )
            db.add(user)
            db.add(other)
            db.add(SiteSetting(id=1, site_name="Test Site"))
            db.commit()
            db.refresh(user)
            db.refresh(other)
            cls.user_id = int(user.id)
            cls.other_user_id = int(other.id)
        finally:
            db.close()

        def _get_db_override():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def _make_user_override(user_id: int):
            def _override():
                db = cls.SessionLocal()
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user is not None:
                        db.expunge(user)
                    return user
                finally:
                    db.close()

            return _override

        app.dependency_overrides[get_db] = _get_db_override
        app.dependency_overrides[get_current_user] = _make_user_override(cls.user_id)
        app.dependency_overrides[get_optional_user] = _make_user_override(cls.user_id)
        app.dependency_overrides[get_token] = lambda: "test-token"
        app.dependency_overrides[get_token_optional] = lambda: "test-token"
        cls.client = TestClient(app)
        cls._make_user_override = staticmethod(_make_user_override)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self) -> None:
        db = self.SessionLocal()
        try:
            db.execute(text("DELETE FROM push_subscriptions"))
            db.execute(text("DELETE FROM fcm_device_tokens"))
            db.commit()
        finally:
            db.close()
        app.dependency_overrides[get_current_user] = self._make_user_override(self.user_id)
        app.dependency_overrides[get_optional_user] = self._make_user_override(self.user_id)

    def test_public_key_reflects_server_configuration(self) -> None:
        with patch.object(settings, "web_push_enabled", True), patch.object(
            settings, "web_push_vapid_public_key", "public"
        ), patch.object(settings, "web_push_vapid_private_key", "private"), patch.object(
            settings, "web_push_subject", "mailto:test@example.com"
        ), patch(
            "app.api.v1.push.web_push_runtime_ready",
            return_value=True,
        ):
            resp = self.client.get("/v1/push/public-key")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        body = resp.json()
        self.assertTrue(body["enabled"])
        self.assertEqual(body["public_key"], "public")

    def test_push_status_defaults_to_disabled(self) -> None:
        resp = self.client.get("/v1/push/status")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        body = resp.json()
        self.assertFalse(body["fcm"]["enabled"])
        self.assertFalse(body["fcm"]["configured"])
        self.assertFalse(body["fcm"]["runtime_ready"])
        self.assertFalse(body["web_push"]["enabled"])

    def test_push_status_reflects_fcm_configuration(self) -> None:
        with patch.object(settings, "fcm_push_enabled", True), patch.object(
            settings, "fcm_service_account_json", '{"project_id":"demo"}'
        ), patch(
            "app.api.v1.push.fcm_runtime_ready",
            return_value=True,
        ), patch(
            "app.api.v1.push.fcm_dependency_available",
            return_value=True,
        ):
            resp = self.client.get("/v1/push/status")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        body = resp.json()
        self.assertTrue(body["fcm"]["enabled"])
        self.assertTrue(body["fcm"]["configured"])
        self.assertTrue(body["fcm"]["dependency_available"])
        self.assertTrue(body["fcm"]["runtime_ready"])

    def test_push_status_skips_runtime_probe_when_unconfigured(self) -> None:
        with patch.object(settings, "fcm_push_enabled", True), patch.object(
            settings, "fcm_service_account_json", ""
        ), patch(
            "app.api.v1.push.fcm_runtime_ready",
            side_effect=AssertionError("runtime probe must be skipped"),
        ):
            resp = self.client.get("/v1/push/status")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        body = resp.json()
        self.assertTrue(body["fcm"]["enabled"])
        self.assertFalse(body["fcm"]["configured"])
        self.assertFalse(body["fcm"]["runtime_ready"])

    def test_subscription_lifecycle(self) -> None:
        payload = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/subscription",
            "expiration_time": None,
            "keys": {
                "p256dh": "key-p256dh",
                "auth": "key-auth",
            },
            "user_agent": "UnitTest",
        }

        saved = self.client.put("/v1/push/subscriptions", json=payload)
        self.assertEqual(saved.status_code, 200, msg=saved.text)
        self.assertEqual(saved.json()["endpoint"], payload["endpoint"])

        listed = self.client.get("/v1/push/subscriptions")
        self.assertEqual(listed.status_code, 200, msg=listed.text)
        self.assertEqual(len(listed.json()["items"]), 1)
        self.assertTrue(listed.json()["items"][0]["is_active"])

        removed = self.client.request(
            "DELETE",
            "/v1/push/subscriptions",
            json={"endpoint": payload["endpoint"]},
        )
        self.assertEqual(removed.status_code, 200, msg=removed.text)
        self.assertEqual(removed.json()["removed"], 1)

        listed_again = self.client.get("/v1/push/subscriptions")
        self.assertEqual(listed_again.status_code, 200, msg=listed_again.text)
        self.assertEqual(listed_again.json()["items"], [])

    def _subscription_payload(self, endpoint: str) -> dict:
        return {
            "endpoint": endpoint,
            "expiration_time": None,
            "keys": {"p256dh": "key-p256dh", "auth": "key-auth"},
            "user_agent": "UnitTest",
        }

    def test_subscription_rejects_ssrf_endpoints(self) -> None:
        """The server POSTs here, so internal/non-https destinations must fail."""
        rejected = [
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata, plain http
            "https://169.254.169.254/latest/meta-data/",  # IP literal
            "https://127.0.0.1:8000/internal",  # loopback
            "https://10.0.0.5/push",  # RFC1918
            "https://[::1]/push",  # IPv6 loopback
            "https://localhost/push",  # local name
            "https://redis:6379/",  # single-label docker service name
            "https://evil.example.com/push",  # not a push provider
            "https://fcm.googleapis.com.evil.test/push",  # suffix confusion
        ]
        for endpoint in rejected:
            with self.subTest(endpoint=endpoint):
                resp = self.client.put(
                    "/v1/push/subscriptions", json=self._subscription_payload(endpoint)
                )
                self.assertEqual(resp.status_code, 400, msg=f"{endpoint}: {resp.text}")

        listed = self.client.get("/v1/push/subscriptions")
        self.assertEqual(listed.json()["items"], [])

    def test_subscription_accepts_supported_providers(self) -> None:
        accepted = [
            "https://fcm.googleapis.com/fcm/send/abc",
            "https://updates.push.services.mozilla.com/wpush/v2/abc",
            "https://web.push.apple.com/QGVsbG8",
            "https://wns2-par02p.notify.windows.com/w/?token=abc",
        ]
        for endpoint in accepted:
            with self.subTest(endpoint=endpoint):
                resp = self.client.put(
                    "/v1/push/subscriptions", json=self._subscription_payload(endpoint)
                )
                self.assertEqual(resp.status_code, 200, msg=f"{endpoint}: {resp.text}")

    def test_subscription_endpoint_cannot_be_rebound_to_another_account(self) -> None:
        endpoint = "https://fcm.googleapis.com/fcm/send/shared-device"
        first = self.client.put("/v1/push/subscriptions", json=self._subscription_payload(endpoint))
        self.assertEqual(first.status_code, 200, msg=first.text)
        owner_before = first.json()["sid"]

        app.dependency_overrides[get_current_user] = self._make_user_override(self.other_user_id)
        app.dependency_overrides[get_optional_user] = self._make_user_override(self.other_user_id)

        second = self.client.put("/v1/push/subscriptions", json=self._subscription_payload(endpoint))
        self.assertEqual(second.status_code, 409, msg=second.text)

        # Ownership must be untouched: the victim keeps the subscription.
        db = self.SessionLocal()
        try:
            row = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).one()
            self.assertEqual(row.sid, owner_before)
            self.assertEqual(int(row.user_id), self.user_id)
        finally:
            db.close()

    def test_fcm_token_cannot_be_rebound_to_another_account(self) -> None:
        token = "fcm-token-shared-device"
        first = self.client.put("/v1/push/fcm-tokens", json={"token": token, "platform": "android"})
        self.assertEqual(first.status_code, 200, msg=first.text)

        app.dependency_overrides[get_current_user] = self._make_user_override(self.other_user_id)
        app.dependency_overrides[get_optional_user] = self._make_user_override(self.other_user_id)

        second = self.client.put("/v1/push/fcm-tokens", json={"token": token, "platform": "android"})
        self.assertEqual(second.status_code, 409, msg=second.text)

        db = self.SessionLocal()
        try:
            row = db.query(FcmDeviceToken).filter(FcmDeviceToken.token == token).one()
            self.assertEqual(int(row.user_id), self.user_id)
        finally:
            db.close()

    def test_subscription_cap_per_account(self) -> None:
        with patch.object(settings, "push_max_devices_per_user", 2):
            for index in range(2):
                resp = self.client.put(
                    "/v1/push/subscriptions",
                    json=self._subscription_payload(f"https://fcm.googleapis.com/fcm/send/{index}"),
                )
                self.assertEqual(resp.status_code, 200, msg=resp.text)

            overflow = self.client.put(
                "/v1/push/subscriptions",
                json=self._subscription_payload("https://fcm.googleapis.com/fcm/send/overflow"),
            )
            self.assertEqual(overflow.status_code, 409, msg=overflow.text)

    def test_fcm_token_cap_per_account(self) -> None:
        with patch.object(settings, "push_max_devices_per_user", 1):
            first = self.client.put("/v1/push/fcm-tokens", json={"token": "cap-token-1"})
            self.assertEqual(first.status_code, 200, msg=first.text)
            overflow = self.client.put("/v1/push/fcm-tokens", json={"token": "cap-token-2"})
            self.assertEqual(overflow.status_code, 409, msg=overflow.text)


if __name__ == "__main__":
    unittest.main()
