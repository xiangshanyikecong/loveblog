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

"""Regressions for the security-hardening fixes:

* login-device IP extraction must ignore client-forgeable XFF first hops;
* upload storage extensions must derive from the validated MIME type, never
  the client-supplied original filename;
* the media policy whitelist must be clamped to types the pipeline supports.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

from starlette.requests import Request as StarletteRequest

from app.core.media import ALL_IMAGE_TYPES, MediaPolicy, extension_for_mime
from app.db.base import Base
from app.models import SiteSetting, User
from app.models.user import UserRole
from app.services.login_devices import record_login_device


def _make_request(headers: dict[str, str], client=("10.0.0.1", 1234)) -> StarletteRequest:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/auth/login",
        "query_string": b"",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "client": client,
    }
    return StarletteRequest(scope)


class _InMemoryDbTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session, sessionmaker
        from sqlalchemy.pool import StaticPool

        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, class_=Session, expire_on_commit=False)

    def tearDown(self) -> None:
        self.engine.dispose()


class LoginDeviceIpExtractionTests(_InMemoryDbTestCase):
    def test_ignores_client_forged_xff_first_hop(self) -> None:
        db = self.SessionLocal()
        try:
            user = User(
                uid="ip-partner",
                username=f"ip_{uuid4().hex[:8]}",
                nickname="IP",
                role=UserRole.partner_a,
                password_hash="x",
            )
            db.add(user)
            db.commit()

            # First XFF hop is attacker-controlled and must be ignored; the
            # proxy-set X-Real-IP wins.
            request = _make_request(
                {
                    "X-Forwarded-For": "1.2.3.4, 5.6.7.8",
                    "X-Real-IP": "9.9.9.9",
                    "User-Agent": "pytest",
                }
            )
            device = record_login_device(db, user, request)
            self.assertEqual(device.ip, "9.9.9.9")

            # Without X-Real-IP, the trusted proxy's XFF *last* hop wins.
            request = _make_request({"X-Forwarded-For": "1.2.3.4, 5.6.7.8", "User-Agent": "pytest"})
            device = record_login_device(db, user, request)
            self.assertEqual(device.ip, "5.6.7.8")

            # With neither, the transport peer is used.
            request = _make_request({"User-Agent": "pytest"})
            device = record_login_device(db, user, request)
            self.assertEqual(device.ip, "10.0.0.1")
        finally:
            db.close()


class UploadExtensionTests(_InMemoryDbTestCase):
    def test_extension_derives_from_mime_not_filename(self) -> None:
        from app.api.v1 import uploads as uploads_module

        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            with mock.patch.object(uploads_module, "BACKEND_ROOT", tmp_root), \
                    mock.patch.object(uploads_module, "DEFAULT_UPLOADS_ROOT", tmp_root / "uploads"), \
                    mock.patch.object(
                        uploads_module,
                        "process_image",
                        side_effect=RuntimeError("Pillow is not installed"),
                    ):
                db = self.SessionLocal()
                try:
                    # original filename carries an executable extension; the
                    # declared content type is a whitelisted bitmap.
                    response = uploads_module._persist_image_bytes(
                        b"not-really-an-image",
                        "image/png",
                        "evil.html",
                        db,
                        "albums_path",
                    )
                finally:
                    db.close()

            self.assertTrue(response.url.startswith("/uploads/albums/"))
            self.assertTrue(response.url.endswith(".png"), response.url)
            self.assertFalse(response.url.endswith(".html"))

    def test_extension_for_mime_falls_back_safely(self) -> None:
        self.assertEqual(extension_for_mime("image/png"), ".png")
        self.assertEqual(extension_for_mime("image/jpeg"), ".jpg")
        self.assertEqual(extension_for_mime("image/svg+xml"), ".jpg")


class MediaPolicyWhitelistTests(_InMemoryDbTestCase):
    def test_setting_whitelist_is_clamped_to_supported_types(self) -> None:
        setting = SiteSetting(id=1, allowed_image_types="image/svg+xml,image/png,image/gif")
        policy = MediaPolicy.from_setting(setting)
        self.assertEqual(policy.allowed_mime_types, ["image/png", "image/gif"])

    def test_empty_or_unsupported_whitelist_falls_back_to_defaults(self) -> None:
        policy = MediaPolicy.from_setting(SiteSetting(id=1, allowed_image_types="image/svg+xml"))
        self.assertEqual(sorted(policy.allowed_mime_types), sorted(ALL_IMAGE_TYPES))
        policy = MediaPolicy.from_setting(SiteSetting(id=1, allowed_image_types=""))
        self.assertEqual(sorted(policy.allowed_mime_types), sorted(ALL_IMAGE_TYPES))


if __name__ == "__main__":
    unittest.main()
