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

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole


class HealthApiTests(unittest.TestCase):
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
            partner = User(
                username="health_partner",
                nickname="Health Partner",
                role=UserRole.partner_a,
                password_hash="x",
            )
            db.add(partner)
            db.add(SiteSetting(id=1, site_name="Test Site"))
            db.commit()
            db.refresh(partner)
            cls.partner_id = int(partner.id)
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
                user = db.query(User).filter(User.id == cls.partner_id).first()
                if user is not None:
                    db.expunge(user)
                return user
            finally:
                db.close()

        app.dependency_overrides[get_db] = _get_db_override
        app.dependency_overrides[get_current_user] = _get_current_user_override
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def test_basic_health_check_stays_public(self) -> None:
        # 暂时移除 get_current_user 的覆盖，测试公开接口
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        resp = self.client.get("/health")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        body = resp.json()
        self.assertIn("app", body)
        self.assertIn("database", body)
        self.assertIn("redis", body)

    def test_system_health_requires_authentication(self) -> None:
        # 暂时移除 get_current_user 的覆盖，测试未授权的情况
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        resp = self.client.get("/health/system")

        self.assertEqual(resp.status_code, 401, msg=resp.text)

    def test_system_health_allows_authenticated_partner(self) -> None:
        # 确保 get_current_user 的覆盖在
        def _get_current_user_override():
            db = self.SessionLocal()
            try:
                user = db.query(User).filter(User.id == self.partner_id).first()
                if user is not None:
                    db.expunge(user)
                return user
            finally:
                db.close()

        app.dependency_overrides[get_current_user] = _get_current_user_override

        resp = self.client.get("/health/system")

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        body = resp.json()
        self.assertIn("overall_status", body)
        self.assertIn("health_score", body)
        self.assertIn("checks", body)

    def test_system_health_rejects_invalid_components(self) -> None:
        resp = self.client.get("/health/system", params={"components": "database,unknown_component"})

        self.assertEqual(resp.status_code, 400, msg=resp.text)
        body = resp.json()
        self.assertIn("Unsupported components", body["detail"])
        self.assertIn("unknown_component", body["detail"])

    def test_system_health_limits_checks_to_requested_components(self) -> None:
        resp = self.client.get("/health/system", params={"components": "database,redis"})

        self.assertEqual(resp.status_code, 200, msg=resp.text)
        body = resp.json()
        self.assertEqual(
            [check["component"] for check in body["checks"]],
            ["database", "redis"],
        )


if __name__ == "__main__":
    unittest.main()
