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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

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

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self) -> None:
        db = self.SessionLocal()
        try:
            db.query(User).delete()
            db.commit()
        finally:
            db.close()

    def test_bootstrap_status_only_exposes_bootstrapped_state(self) -> None:
        with patch("app.api.v1.auth.settings.bootstrap_setup_token", "configured-token"):
            resp = self.client.get("/v1/auth/bootstrap-status")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        self.assertEqual(resp.json(), {"bootstrapped": False})

    def test_bootstrap_status_reports_completed_bootstrap_without_extra_flags(self) -> None:
        db = self.SessionLocal()
        try:
            db.add(
                User(
                    username="partner_a",
                    nickname="Partner A",
                    role=UserRole.partner_a,
                    password_hash="hash",
                )
            )
            db.commit()
        finally:
            db.close()

        resp = self.client.get("/v1/auth/bootstrap-status")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        self.assertEqual(resp.json(), {"bootstrapped": True})


if __name__ == "__main__":
    unittest.main()
