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

"""
Tests for the upload absolute-URL host-leak bugfix.

Spec: .kiro/specs/upload-absolute-url-host-leak/

Two test classes mirror the design's two correctness properties:

* ``BugConditionExplorationTests`` — Property 1: response ``url`` is server-relative
  and request-header-independent. Designed to FAIL on the unfixed code (every
  successful upload returns ``http://<host>/uploads/...``) and to PASS after the
  fix lands. Failures here are the counterexamples that confirm the bug exists.

* ``PreservationTests`` — Property 2: every observable other than ``url``'s
  textual form is unchanged. PASSES on unfixed code (locking in the baseline)
  and must continue to PASS after the fix.
"""

from __future__ import annotations

import io
import re
import unittest
from pathlib import Path
from typing import Iterable
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_optional_user, get_token, get_token_optional
from app.api.v1.uploads import (
    BACKEND_ROOT,
    DEFAULT_UPLOADS_ROOT,
    _cleanup_orphan_upload_files,
)
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.article import Article, ArticleStatus
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole


# ---------------------------------------------------------------------------
# Test infrastructure
# ---------------------------------------------------------------------------

# Deterministic stems so we can predict the stored filename and assert on the
# exact response url.
_FIXED_STEM_HEX = "abcdef0123456789abcdef0123456789"


def _make_png_bytes(size: tuple[int, int] = (2, 2)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=(200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def _mp4_stub_bytes() -> bytes:
    # Minimal "looks like a file" payload for a video upload. Backend does not
    # parse the bytes; only Content-Type and size matter for the upload pipeline.
    return b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8


_HEADER_TABLE = [
    pytest_id := "default",  # placeholder so flake8/IDE don't reorder
]


class _UploadTestBase(unittest.TestCase):
    """In-memory SQLite + dependency overrides + TestClient."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(
            bind=cls.engine, autoflush=False, autocommit=False, class_=Session,
        )

        # Seed a partner user and the default SiteSetting row. We capture
        # plain integer IDs so subsequent dependency-override callbacks do not
        # touch detached SQLAlchemy instances.
        db = cls.SessionLocal()
        try:
            partner = User(
                username="upload_partner",
                nickname="Upload Partner",
                role=UserRole.partner_a,
                password_hash="x",
            )
            db.add(partner)
            db.add(SiteSetting(id=1, site_name="Test Site"))
            db.commit()
            db.refresh(partner)
            cls.partner_id = int(partner.id)

            visitor = User(
                username="upload_visitor",
                nickname="Upload Visitor",
                role=UserRole.visitor,
                password_hash="x",
            )
            db.add(visitor)
            db.commit()
            db.refresh(visitor)
            cls.visitor_id = int(visitor.id)
        finally:
            db.close()

        # Override DB and auth dependencies on the live FastAPI app for the
        # duration of this test class.
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
                # Detach so callers can read attributes after the session closes.
                if user is not None:
                    db.expunge(user)
                return user
            finally:
                db.close()

        def _get_optional_user_override():
            return _get_current_user_override()

        # Bypass token extraction entirely.
        def _get_token_override():
            return "test-token"

        def _get_token_optional_override():
            return "test-token"

        app.dependency_overrides[get_db] = _get_db_override
        app.dependency_overrides[get_current_user] = _get_current_user_override
        app.dependency_overrides[get_optional_user] = _get_optional_user_override
        app.dependency_overrides[get_token] = _get_token_override
        app.dependency_overrides[get_token_optional] = _get_token_optional_override
        cls._get_current_user_override = staticmethod(_get_current_user_override)

        cls.client = TestClient(app)

        # Track files created during tests so we can clean up.
        cls._created_files: list[Path] = []

    @classmethod
    def tearDownClass(cls) -> None:
        # Clean up any files we created.
        for path in cls._created_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        cls.client.close()
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def _track_uploaded_file(self, response_url: str) -> Path | None:
        """Locate the file the backend just stored from a response URL.

        Works whether the URL is absolute (legacy) or server-relative (post-fix).
        """
        marker = "/uploads/"
        idx = response_url.find(marker)
        if idx < 0:
            return None
        rel = response_url[idx + 1:]  # 'uploads/...'
        candidate = (BACKEND_ROOT / rel).resolve()
        try:
            candidate.relative_to(DEFAULT_UPLOADS_ROOT)
        except ValueError:
            return None
        if candidate.is_file():
            self._created_files.append(candidate)
            # Also clean up the thumbnail companion if present.
            thumb = candidate.with_name(
                candidate.stem + "_thumb" + candidate.suffix
            )
            if thumb.is_file():
                self._created_files.append(thumb)
        return candidate


# ---------------------------------------------------------------------------
# Property 1: Bug Condition Exploration
# ---------------------------------------------------------------------------

# Header table — small, concrete, deterministic. Each entry is a label plus the
# headers to send.
_HEADER_CASES: list[tuple[str, dict[str, str]]] = [
    ("default", {}),
    ("malicious_host", {"Host": "malicious.example"}),
    ("loopback_alt_port", {"Host": "127.0.0.1:9999"}),
    (
        "x_forwarded",
        {
            "Host": "internal.svc",
            "X-Forwarded-Host": "x.example",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Port": "8443",
        },
    ),
]


# Image endpoints share the same upload pipeline. Each tuple is
# (endpoint_path, expected_url_dir_substring).
_IMAGE_ENDPOINTS: list[tuple[str, str]] = [
    ("/v1/uploads/albums", "/uploads/albums/"),
    ("/v1/uploads/articles", "/uploads/articles/"),
    ("/v1/uploads/avatars", "/uploads/avatars/"),
    ("/v1/uploads/timeline", "/uploads/timeline/"),
]


class BugConditionExplorationTests(_UploadTestBase):
    """Property 1 — response url is server-relative and header-independent.

    These tests are the bug-condition exploration tests. They are EXPECTED TO
    FAIL on the unfixed branch (where ``_build_public_url`` prepends
    ``request.base_url``); on the fixed branch they all pass.

    Counterexample produced by the unfixed code:
        Expected: "/uploads/albums/<uuid>.png"
        Actual:   "http://testserver/uploads/albums/<uuid>.png"
        (or, with Host: malicious.example,
         "http://malicious.example/uploads/albums/<uuid>.png")
    """

    def _post_image(
        self,
        endpoint: str,
        headers: dict[str, str],
    ) -> tuple[int, dict]:
        png = _make_png_bytes()
        response = self.client.post(
            endpoint,
            files={"file": ("sample.png", png, "image/png")},
            headers=headers,
        )
        return response.status_code, (response.json() if response.content else {})

    def test_image_uploads_return_server_relative_url(self) -> None:
        """For every image endpoint × header case, ``url`` must be relative
        and must equal ``/uploads/`` + the file's path under
        ``DEFAULT_UPLOADS_ROOT``.
        """
        for endpoint, expected_dir in _IMAGE_ENDPOINTS:
            for label, headers in _HEADER_CASES:
                with self.subTest(endpoint=endpoint, header_case=label):
                    status_code, body = self._post_image(endpoint, headers)
                    self.assertEqual(status_code, 201, msg=body)
                    url = body.get("url", "")

                    # Property 1 clause 1: server-relative.
                    self.assertFalse(
                        url.startswith(("http://", "https://")),
                        msg=f"url leaked scheme/host: {url!r}",
                    )
                    self.assertTrue(
                        url.startswith(expected_dir),
                        msg=f"url not under {expected_dir!r}: {url!r}",
                    )

                    # Property 1 clause 2: independent of Host. The Host value
                    # we sent must NOT appear in the response url.
                    sent_host = headers.get("Host")
                    if sent_host:
                        self.assertNotIn(
                            sent_host, url,
                            msg=f"url leaked Host {sent_host!r}: {url!r}",
                        )
                    fwd_host = headers.get("X-Forwarded-Host")
                    if fwd_host:
                        self.assertNotIn(
                            fwd_host, url,
                            msg=(
                                f"url leaked X-Forwarded-Host {fwd_host!r}: "
                                f"{url!r}"
                            ),
                        )

                    # Filesystem ↔ url agreement.
                    stored = self._track_uploaded_file(url)
                    self.assertIsNotNone(
                        stored, msg=f"could not resolve stored file from {url!r}",
                    )
                    self.assertTrue(stored.exists(), msg=str(stored))
                    expected_url = (
                        "/uploads/"
                        + stored.relative_to(DEFAULT_UPLOADS_ROOT).as_posix()
                    )
                    self.assertEqual(url, expected_url)

    def test_video_upload_returns_server_relative_url(self) -> None:
        """Video endpoint variant of the same property."""
        for label, headers in _HEADER_CASES:
            with self.subTest(header_case=label):
                response = self.client.post(
                    "/v1/uploads/videos",
                    files={"file": ("sample.mp4", _mp4_stub_bytes(), "video/mp4")},
                    headers=headers,
                )
                self.assertEqual(
                    response.status_code, 201,
                    msg=response.text,
                )
                url = response.json()["url"]
                self.assertFalse(
                    url.startswith(("http://", "https://")),
                    msg=f"url leaked scheme/host: {url!r}",
                )
                self.assertTrue(
                    url.startswith("/uploads/videos/"),
                    msg=f"url not under videos directory: {url!r}",
                )
                stored = self._track_uploaded_file(url)
                self.assertIsNotNone(stored)
                expected_url = (
                    "/uploads/"
                    + stored.relative_to(DEFAULT_UPLOADS_ROOT).as_posix()
                )
                self.assertEqual(url, expected_url)
                # mp4 extension preservation.
                self.assertTrue(stored.suffix == ".mp4")

    def test_url_is_byte_for_byte_identical_across_headers(self) -> None:
        """Two uploads of the same payload to the same endpoint must produce
        the same ``url`` value when only the request headers differ.

        We pin ``uuid4`` to a fixed value so the two stored filenames are
        identical, isolating the header-dependence we want to catch.
        """
        fixed = mock.MagicMock()
        fixed.hex = _FIXED_STEM_HEX

        png = _make_png_bytes()

        with mock.patch("app.api.v1.uploads.uuid4", return_value=fixed):
            r1 = self.client.post(
                "/v1/uploads/albums",
                files={"file": ("a.png", png, "image/png")},
                headers={"Host": "host-a.example"},
            )
            url_a = r1.json().get("url", "") if r1.status_code == 201 else ""
            self._track_uploaded_file(url_a)

            r2 = self.client.post(
                "/v1/uploads/albums",
                files={"file": ("a.png", png, "image/png")},
                headers={"Host": "host-b.example"},
            )
            url_b = r2.json().get("url", "") if r2.status_code == 201 else ""
            self._track_uploaded_file(url_b)

        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(
            url_a, url_b,
            msg=(
                "Response url depends on the request Host header. "
                f"With Host=host-a.example: {url_a!r}; "
                f"with Host=host-b.example: {url_b!r}"
            ),
        )
        # And it must be the server-relative form.
        self.assertEqual(
            url_a,
            f"/uploads/albums/{_FIXED_STEM_HEX}.png",
        )


# ---------------------------------------------------------------------------
# Property 2: Preservation
# ---------------------------------------------------------------------------


class PreservationTests(_UploadTestBase):
    """Property 2 — non-url observables are unchanged by the fix.

    These tests pass on the unfixed branch (locking in baseline values) and
    must continue to pass after the fix.
    """

    def test_auth_unauthenticated_is_rejected(self) -> None:
        """3.1 — without auth the endpoint must reject."""
        # Temporarily clear the auth override so the real dependency runs.
        original = app.dependency_overrides.pop(get_current_user, None)
        original_token = app.dependency_overrides.pop(get_token, None)
        try:
            response = self.client.post(
                "/v1/uploads/albums",
                files={"file": ("a.png", _make_png_bytes(), "image/png")},
            )
        finally:
            if original is not None:
                app.dependency_overrides[get_current_user] = original
            if original_token is not None:
                app.dependency_overrides[get_token] = original_token

        # Without a token, get_token raises 401.
        self.assertEqual(response.status_code, 401)

    def test_auth_visitor_is_forbidden(self) -> None:
        """3.1 — a visitor user must be rejected with 403."""
        # Swap the override to return the visitor user.
        original = app.dependency_overrides[get_current_user]

        def _visitor_override():
            db = self.SessionLocal()
            try:
                user = db.query(User).filter(User.id == self.visitor_id).first()
                if user is not None:
                    db.expunge(user)
                return user
            finally:
                db.close()

        try:
            app.dependency_overrides[get_current_user] = _visitor_override
            response = self.client.post(
                "/v1/uploads/albums",
                files={"file": ("a.png", _make_png_bytes(), "image/png")},
            )
        finally:
            app.dependency_overrides[get_current_user] = original

        self.assertEqual(response.status_code, 403)

    def test_mime_whitelist_rejects_octet_stream(self) -> None:
        """3.2 — non-whitelisted MIME types return HTTP 400."""
        response = self.client.post(
            "/v1/uploads/albums",
            files={
                "file": ("a.bin", b"random bytes", "application/octet-stream"),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的文件类型", response.json()["detail"])

    def test_empty_image_body_returns_400(self) -> None:
        """3.3 — empty body returns 400."""
        response = self.client.post(
            "/v1/uploads/albums",
            files={"file": ("a.png", b"", "image/png")},
        )
        self.assertEqual(response.status_code, 400)

    def test_oversize_video_returns_413(self) -> None:
        """3.3 — 101 MB video returns 413.

        We don't actually send 101 MB; we send just over the ceiling so we
        exercise the size check without slowing tests down. The endpoint's
        check is exact (``> MAX_VIDEO_SIZE_BYTES``).
        """
        from app.api.v1.uploads import MAX_VIDEO_SIZE_BYTES

        oversized = b"\x00" * (MAX_VIDEO_SIZE_BYTES + 1)
        response = self.client.post(
            "/v1/uploads/videos",
            files={"file": ("big.mp4", oversized, "video/mp4")},
        )
        self.assertEqual(response.status_code, 413)

    def test_image_processing_strips_exif_and_writes_thumbnail(self) -> None:
        """3.4 — image is re-encoded, EXIF stripped, thumbnail written."""
        png = _make_png_bytes((16, 16))
        response = self.client.post(
            "/v1/uploads/albums",
            files={"file": ("a.png", png, "image/png")},
        )
        self.assertEqual(response.status_code, 201, msg=response.text)
        body = response.json()
        url = body["url"]
        stored = self._track_uploaded_file(url)
        self.assertIsNotNone(stored)
        self.assertTrue(stored.exists())

        # response.size matches on-disk size.
        self.assertEqual(body["size"], stored.stat().st_size)

        # Thumbnail companion exists alongside.
        thumb = stored.with_name(stored.stem + "_thumb" + stored.suffix)
        self.assertTrue(
            thumb.exists(),
            msg=f"thumbnail not generated alongside {stored}",
        )

        # No EXIF on the stored file (we created the source without one,
        # and the pipeline strips anyway — assert the post-condition).
        with Image.open(stored) as img:
            exif = img.getexif()
            self.assertEqual(
                len(exif), 0,
                msg=f"EXIF survived processing: {dict(exif)!r}",
            )

    def test_video_bytes_round_trip(self) -> None:
        """3.5 — video stored bytes equal input bytes; extension is .mp4."""
        payload = _mp4_stub_bytes()
        response = self.client.post(
            "/v1/uploads/videos",
            files={"file": ("clip.mp4", payload, "video/mp4")},
        )
        self.assertEqual(response.status_code, 201, msg=response.text)
        url = response.json()["url"]
        stored = self._track_uploaded_file(url)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.suffix, ".mp4")
        self.assertEqual(stored.read_bytes(), payload)

    def test_response_field_shape(self) -> None:
        """3.6 — file_name, content_type, size carry expected values."""
        response = self.client.post(
            "/v1/uploads/albums",
            files={"file": ("original-name.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(response.status_code, 201, msg=response.text)
        body = response.json()
        self.assertEqual(body["file_name"], "original-name.png")
        self.assertEqual(body["content_type"], "image/png")
        self.assertIsInstance(body["size"], int)
        self.assertGreater(body["size"], 0)
        self._track_uploaded_file(body["url"])

    def test_orphan_cleanup_recognizes_server_relative_url(self) -> None:
        """3.7 — orphan cleanup classifies ``/uploads/...`` URLs as referenced.

        This works on both the unfixed and fixed branches because
        ``_to_abs_path_from_url`` matches on the ``/uploads/`` substring. We
        assert the contract continues to hold on the fixed branch where new
        rows store server-relative URLs.
        """
        # First, upload an article image so we have a real file on disk.
        response = self.client.post(
            "/v1/uploads/articles",
            files={"file": ("a.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(response.status_code, 201, msg=response.text)
        body = response.json()
        url = body["url"]
        stored = self._track_uploaded_file(url)
        self.assertIsNotNone(stored)

        # Compute a server-relative form regardless of whether the response
        # came back absolute (unfixed) or relative (fixed). Cleanup logic
        # should classify both as referenced.
        relative_url = (
            "/uploads/"
            + stored.relative_to(DEFAULT_UPLOADS_ROOT).as_posix()
        )

        db = self.SessionLocal()
        try:
            article = Article(
                author_id=self.partner_id,
                title="Cleanup target",
                cover_url=relative_url,
                status=ArticleStatus.published,
                is_encrypted=False,
            )
            db.add(article)
            db.commit()

            result = _cleanup_orphan_upload_files(db, dry_run=True)
            stored_rel = stored.resolve().relative_to(BACKEND_ROOT).as_posix()
            self.assertNotIn(
                stored_rel, result.deleted_files,
                msg=(
                    "Server-relative URL was not recognized as a reference; "
                    "cleanup would have deleted it."
                ),
            )
        finally:
            db.close()

    def test_static_mount_serves_uploaded_file(self) -> None:
        """3.8 — the /uploads/<path> mount serves the just-uploaded file.

        For the unfixed branch the response url is absolute; we strip to a
        path before issuing the GET. After the fix the url is already a
        path so the strip is a no-op.
        """
        response = self.client.post(
            "/v1/uploads/albums",
            files={"file": ("a.png", _make_png_bytes(), "image/png")},
        )
        self.assertEqual(response.status_code, 201, msg=response.text)
        url = response.json()["url"]
        self._track_uploaded_file(url)

        marker = "/uploads/"
        idx = url.find(marker)
        self.assertGreaterEqual(idx, 0)
        path = url[idx:]

        # The static mount itself uses upload-references to authorize. For
        # this test we only need to confirm the mount resolves a file path
        # — uploads always insert a corresponding UploadReference at the
        # API layer, but the test bypasses that layer's caller. We check
        # that the route either succeeds (200) or rejects on access (403)
        # — anything other than 404 means the route resolves the path.
        response = self.client.get(path)
        self.assertNotEqual(
            response.status_code, 404,
            msg=f"static mount could not resolve {path!r}",
        )


if __name__ == "__main__":
    unittest.main()
