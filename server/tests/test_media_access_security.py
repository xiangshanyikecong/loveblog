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
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.uploads import DEFAULT_UPLOADS_ROOT, _collect_referenced_upload_paths
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Album, Article, Capsule, ChatMessage, CheckIn, SiteSetting, UploadReference, User
from app.models.article import ArticleStatus
from app.models.content_visibility import ContentVisibility
from app.models.user import UserRole
from app.services.upload_references import (
    register_pending_upload,
    rebuild_upload_references,
    sync_article_upload_references,
    sync_capsule_upload_references,
)


class MediaAccessSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, class_=Session, expire_on_commit=False)
        db = self.SessionLocal()
        self.partner = User(
            uid="media-partner",
            username=f"media_{uuid4().hex[:8]}",
            nickname="Media",
            role=UserRole.partner_a,
            password_hash="x",
        )
        self.other_partner = User(
            uid="media-partner-b",
            username=f"media_b_{uuid4().hex[:8]}",
            nickname="Media B",
            role=UserRole.partner_b,
            password_hash="x",
        )
        db.add_all([self.partner, self.other_partner, SiteSetting(id=1, site_name="Media")])
        db.commit()
        self.partner_id = self.partner.id
        self.token = create_access_token(
            self.partner.uid,
            session_version=self.partner.session_version,
        )
        self.other_token = create_access_token(
            self.other_partner.uid,
            session_version=self.other_partner.session_version,
        )
        db.close()

        def override_db():
            session = self.SessionLocal()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.created_files: list[Path] = []

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()
        for path in self.created_files:
            path.unlink(missing_ok=True)
        self.engine.dispose()

    def _file(self, subdir: str, name: str) -> tuple[Path, str]:
        path = DEFAULT_UPLOADS_ROOT / subdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"media")
        self.created_files.append(path)
        return path, f"/uploads/{subdir}/{name}"

    def test_pending_upload_is_immediately_previewable_by_uploader(self) -> None:
        _path, url = self._file("security-tests", f"pending-{uuid4().hex}.jpg")
        db = self.SessionLocal()
        register_pending_upload(db, file_url=url, owner_user_id=self.partner_id)
        db.close()

        response = self.client.get(url, headers={"Authorization": f"Bearer {self.token}"})
        self.assertEqual(response.status_code, 200, response.text)

    def test_rebuild_prunes_expired_pending_upload_lease(self) -> None:
        _path, url = self._file("security-tests", f"stale-{uuid4().hex}.jpg")
        db = self.SessionLocal()
        register_pending_upload(db, file_url=url, owner_user_id=self.partner_id)
        lease = db.query(UploadReference).filter_by(file_path=url, content_kind="pending").one()
        lease.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.commit()
        rebuild_upload_references(db)
        db.commit()
        self.assertIsNone(
            db.query(UploadReference).filter_by(file_path=url, content_kind="pending").first()
        )
        db.close()

    def test_password_challenge_cookie_authorizes_detail_and_media(self) -> None:
        _path, url = self._file("security-tests", f"password-{uuid4().hex}.jpg")
        db = self.SessionLocal()
        article = Article(
            aid="password-article",
            author_id=self.partner_id,
            title="Protected",
            status=ArticleStatus.published,
            visibility=ContentVisibility.password_protected,
            password_hash=get_password_hash("correct horse"),
            cover_url=url,
        )
        db.add(article)
        db.commit()
        sync_article_upload_references(db, article)
        db.commit()
        db.close()

        self.assertEqual(self.client.get("/v1/articles/password-article").status_code, 401)
        challenged = self.client.get(
            "/v1/articles/password-article",
            headers={"X-Content-Password": "correct horse"},
        )
        self.assertEqual(challenged.status_code, 200, challenged.text)
        self.assertIn("content_access_article_", challenged.headers.get("set-cookie", ""))
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_raw_capsule_media_remains_sealed_until_open_at(self) -> None:
        _path, url = self._file("security-tests", f"capsule-{uuid4().hex}.weba")
        db = self.SessionLocal()
        capsule = Capsule(
            uuid="sealed-capsule",
            author_id=self.partner_id,
            media_url=url,
            media_type="audio",
            open_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        db.add(capsule)
        db.commit()
        register_pending_upload(db, file_url=url, owner_user_id=self.partner_id)
        sync_capsule_upload_references(db, capsule)
        db.commit()

        headers = {"Authorization": f"Bearer {self.token}"}
        self.assertEqual(self.client.get(url, headers=headers).status_code, 403)
        capsule.open_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        self.assertEqual(self.client.get(url, headers=headers).status_code, 200)
        db.close()

    def test_cleanup_collector_includes_checkin_and_chat_attachments(self) -> None:
        checkin_path, checkin_url = self._file("security-tests", f"checkin-{uuid4().hex}.jpg")
        chat_path, chat_url = self._file("security-tests", f"chat-{uuid4().hex}.weba")
        db = self.SessionLocal()
        db.add_all(
            [
                CheckIn(
                    author_id=self.partner_id,
                    media_urls=[checkin_url],
                    location_status="omitted",
                ),
                ChatMessage(
                    sender_id=self.partner_id,
                    type="voice",
                    media_url=chat_url,
                    visible_at=datetime.now(timezone.utc),
                ),
            ]
        )
        db.commit()
        referenced = _collect_referenced_upload_paths(db)
        self.assertIn(checkin_path.resolve(), referenced)
        self.assertIn(chat_path.resolve(), referenced)
        db.close()

    def test_private_album_cannot_be_modified_by_other_partner(self) -> None:
        db = self.SessionLocal()
        album = Album(
            alb_id="private-album",
            author_id=self.partner_id,
            title="Private",
            is_public=False,
            visibility=ContentVisibility.private,
        )
        db.add(album)
        db.commit()
        db.close()
        response = self.client.patch(
            "/v1/albums/private-album",
            json={"title": "Taken over"},
            headers={"Authorization": f"Bearer {self.other_token}"},
        )
        self.assertEqual(response.status_code, 403, response.text)

    def test_banned_visitor_token_cannot_fetch_public_media(self) -> None:
        _path, url = self._file("security-tests", f"banned-{uuid4().hex}.jpg")
        db = self.SessionLocal()
        visitor = User(
            uid="banned-media-visitor",
            username=f"banned_{uuid4().hex[:8]}",
            nickname="Banned",
            role=UserRole.visitor,
            password_hash="x",
            is_banned=True,
            permission_status="banned",
        )
        db.add(visitor)
        db.flush()
        article = Article(
            aid="public-media-article",
            author_id=self.partner_id,
            title="Public",
            status=ArticleStatus.published,
            visibility=ContentVisibility.public,
            cover_url=url,
        )
        db.add(article)
        db.commit()
        sync_article_upload_references(db, article)
        db.commit()
        token = create_access_token(visitor.uid, session_version=visitor.session_version)
        db.close()
        response = self.client.get(url, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 401, response.text)


if __name__ == "__main__":
    unittest.main()
