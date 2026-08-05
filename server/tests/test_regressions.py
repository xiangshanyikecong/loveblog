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

import inspect
import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import create_engine, event as sqlalchemy_event
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_current_user
from app.api.v1.albums import create_album, patch_album, update_album
from app.api.v1.audit_logs import list_audit_logs
from app.api.v1.articles import create_article, delete_article, patch_article, update_article
from app.api.v1.auth import bootstrap_register, login, register, update_partner, update_visitor
from app.api.v1.cottage_plans import complete_plan, create_plan, list_plans
from app.api.v1.cottage_questions import answer_question, create_question, get_today_question
from app.api.v1.cottage_reminders import create_reminder, list_reminders, mark_reminder_done
from app.api.v1.cottage_reports import monthly_report
from app.api.v1.dashboard import get_dashboard
from app.api.v1.messages import create_message, delete_message, list_messages
from app.api.v1.recycle_bin import permanently_delete_item
from app.api.v1.search import search_content
from app.api.v1.settings import update_settings
from app.api.v1.timeline import create_comment, list_moments
from app.api.v1.uploads import _collect_referenced_upload_paths
from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.core.startup_checks import (
    has_insecure_jwt_secret,
    validate_schema_contracts,
    validate_startup_configuration,
)
from app.db.base import Base
from app.models.album import Album
from app.models.article import Article, ArticleBlock, ArticleStatus
from app.models.audit_log import AuditLog
from app.models.comment import Comment, CommentTargetType
from app.models.content_version import ContentVersion
from app.models.content_visibility import ContentVisibility
from app.models.cottage_plan import CottagePlan
from app.models.cottage_reminder import CottageReminder
from app.models.daily_question import DailyQuestion, DailyQuestionAnswer
from app.models.event import Event, Visibility
from app.models.message import Message
from app.models.moment import Moment, Visibility as MomentVisibility
from app.models.notification import Notification
from app.models.site_setting import SiteSetting
from app.models.upload_reference import UploadReference
from app.models.user import User, UserRole
from app.schemas.album import AlbumCreateRequest, AlbumPatchRequest
from app.schemas.article import ArticleCreateRequest, ArticlePatchRequest
from app.schemas.comment import CommentCreateRequest
from app.schemas.cottage_plan import CottagePlanCreateRequest, PlanChecklistItem
from app.schemas.cottage_reminder import CottageReminderCreateRequest
from app.schemas.daily_question import DailyQuestionAnswerRequest, DailyQuestionCreateRequest
from app.schemas.auth import (
    BootstrapRegisterRequest,
    LoginRequest,
    PartnerRegisterRequest,
    UpdatePartnerRequest,
    UpdateVisitorRequest,
)
from app.schemas.event import EventPatchRequest
from app.schemas.message import MessageCreateRequest
from app.schemas.site_setting import SiteSettingUpdateRequest
from app.services.security import check_session_version
from app.services.upload_references import (
    can_access_upload_reference,
    sync_site_setting_upload_references,
)
from app.services.notifications import create_due_cottage_reminders
from app.services.versioning import apply_article_snapshot, list_content_versions, version_to_response
from app.services.visibility_policy import VisibilityLevel, VisibilityPolicy
from starlette.requests import Request

from app.api.v1 import auth as _auth_module

# Rate limiting is an integration concern wired to the live app; disable it so
# the login endpoint can be exercised as a plain function in these unit tests
# (slowapi's decorator otherwise demands a fully app-bound Request).
_auth_module.limiter.enabled = False


def _make_request(headers: dict | None = None) -> Request:
    """Build a minimal Starlette Request for unit-testing the login endpoint.

    ``login`` now derives the cookie ``Secure`` flag from the request transport
    (``X-Forwarded-Proto`` / scheme), so it needs a real Request object.
    """
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": raw_headers,
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
        }
    )


class DatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, class_=Session)
        self.db = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def create_user(self, *, username: str, role: UserRole, nickname: str) -> User:
        user = User(
            username=username,
            nickname=nickname,
            role=role,
            password_hash=get_password_hash("abc12345"),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


class SchemaRegressionTests(unittest.TestCase):
    def test_event_patch_request_date_annotation_is_stable(self) -> None:
        payload = EventPatchRequest.model_validate({"date": "2026-01-01"})
        self.assertEqual(payload.date, date(2026, 1, 1))

    def test_update_partner_request_normalizes_username(self) -> None:
        payload = UpdatePartnerRequest.model_validate({"username": "  New_Name  "})
        self.assertEqual(payload.username, "new_name")

    def test_update_partner_request_rejects_weak_password(self) -> None:
        with self.assertRaises(ValidationError):
            UpdatePartnerRequest.model_validate({"password": "abcdefgh"})

    def test_partner_register_rejects_visitor_role(self) -> None:
        with self.assertRaises(ValidationError):
            PartnerRegisterRequest.model_validate(
                {
                    "username": "visitor_demo",
                    "password": "abc12345",
                    "nickname": "Visitor",
                    "role": UserRole.visitor.value,
                }
            )

    def test_message_create_request_rejects_visitor_name(self) -> None:
        with self.assertRaises(ValidationError):
            MessageCreateRequest.model_validate({"content": "hello", "visitor_name": "anonymous"})

    def test_moment_media_urls_accept_server_relative_upload_paths(self) -> None:
        # Regression: /v1/uploads/timeline returns server-relative "/uploads/..."
        # paths which the frontend posts straight back as media_urls. The
        # validator must accept them (mirroring audio_url), otherwise posting a
        # timeline photo or "save to timeline" from the shared canvas 422s.
        from app.schemas.moment import MomentCreateRequest

        payload = MomentCreateRequest.model_validate(
            {"content": "pic", "media_urls": ["/uploads/timeline/x.jpg"]}
        )
        self.assertEqual(payload.media_urls, ["/uploads/timeline/x.jpg"])

    def test_moment_media_urls_still_reject_non_upload_garbage(self) -> None:
        from app.schemas.moment import MomentCreateRequest

        with self.assertRaises(ValidationError):
            MomentCreateRequest.model_validate(
                {"content": "x", "media_urls": ["javascript:alert(1)"]}
            )


class StartupSelfCheckTests(unittest.TestCase):
    # A secret that satisfies the production entropy floor (>= 32 chars) and is
    # not a known/published value, plus a distinct cookie vault key.
    STRONG_SECRET = "prod-grade-secret-" + "a" * 24
    VAULT_KEY = "prod-grade-vault-" + "b" * 24

    def test_default_jwt_secret_is_rejected_in_development(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_startup_configuration(
                app_env="development",
                partner_count=0,
                bootstrap_setup_token="",
                jwt_secret_key="change-this-secret-before-production",
            )

    def test_published_dev_secret_allowed_in_development(self) -> None:
        # The committed dev-compose secret is fine for local dev...
        validate_startup_configuration(
            app_env="development",
            partner_count=0,
            bootstrap_setup_token="",
            jwt_secret_key="love-journal-local-dev-secret-not-for-production",
        )

    def test_published_dev_secret_rejected_in_production(self) -> None:
        # ...but must be rejected in production (it is public in the repo).
        with self.assertRaises(RuntimeError):
            validate_startup_configuration(
                app_env="production",
                partner_count=1,
                bootstrap_setup_token="",
                jwt_secret_key="love-journal-local-dev-secret-not-for-production",
                cookie_vault_key=self.VAULT_KEY,
            )

    def test_short_secret_rejected_in_production(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_startup_configuration(
                app_env="production",
                partner_count=1,
                bootstrap_setup_token="",
                jwt_secret_key="too-short",
                cookie_vault_key=self.VAULT_KEY,
            )

    def test_production_requires_cookie_vault_key(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_startup_configuration(
                app_env="production",
                partner_count=1,
                bootstrap_setup_token="",
                jwt_secret_key=self.STRONG_SECRET,
                cookie_vault_key="",
            )

    def test_production_rejects_shared_cookie_vault_key(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_startup_configuration(
                app_env="production",
                partner_count=1,
                bootstrap_setup_token="",
                jwt_secret_key=self.STRONG_SECRET,
                cookie_vault_key=self.STRONG_SECRET,
            )

    def test_production_requires_partner_or_bootstrap_token(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_startup_configuration(
                app_env="production",
                partner_count=0,
                bootstrap_setup_token="",
                jwt_secret_key=self.STRONG_SECRET,
                cookie_vault_key=self.VAULT_KEY,
            )

    def test_development_allows_empty_partner_state(self) -> None:
        validate_startup_configuration(
            app_env="development",
            partner_count=0,
            bootstrap_setup_token="",
            jwt_secret_key="test-secret",
        )

    def test_production_allows_bootstrap_with_token(self) -> None:
        validate_startup_configuration(
            app_env="production",
            partner_count=0,
            bootstrap_setup_token="setup-secret",
            jwt_secret_key=self.STRONG_SECRET,
            cookie_vault_key=self.VAULT_KEY,
        )

    def test_valid_production_config_with_partner_passes(self) -> None:
        validate_startup_configuration(
            app_env="production",
            partner_count=1,
            bootstrap_setup_token="",
            jwt_secret_key=self.STRONG_SECRET,
            cookie_vault_key=self.VAULT_KEY,
        )

    def test_has_insecure_jwt_secret_helper(self) -> None:
        self.assertTrue(has_insecure_jwt_secret(""))
        self.assertTrue(has_insecure_jwt_secret("change-this-secret-before-production"))
        # Published dev secret: acceptable in dev, rejected in production.
        self.assertFalse(
            has_insecure_jwt_secret("love-journal-local-dev-secret-not-for-production")
        )
        self.assertTrue(
            has_insecure_jwt_secret(
                "love-journal-local-dev-secret-not-for-production", production_like=True
            )
        )
        # Short secret: acceptable in dev, rejected in production.
        self.assertFalse(has_insecure_jwt_secret("short"))
        self.assertTrue(has_insecure_jwt_secret("short", production_like=True))
        # Strong secret: acceptable everywhere.
        self.assertFalse(has_insecure_jwt_secret(self.STRONG_SECRET, production_like=True))

    def test_schema_contracts_check(self) -> None:
        validate_schema_contracts()


class SessionSecurityRegressionTests(DatabaseTestCase):
    def test_session_version_requires_exact_match(self) -> None:
        user = self.create_user(username="session_admin", role=UserRole.partner_a, nickname="Session Admin")
        user.session_version = 5
        self.db.commit()
        self.db.refresh(user)

        self.assertFalse(check_session_version(user, None))
        self.assertFalse(check_session_version(user, 4))
        self.assertTrue(check_session_version(user, 5))
        self.assertFalse(check_session_version(user, 6))


class AuthFlowRegressionTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.original_bootstrap_token = settings.bootstrap_setup_token

    def tearDown(self) -> None:
        settings.bootstrap_setup_token = self.original_bootstrap_token
        super().tearDown()

    def test_bootstrap_register_creates_first_partner_only_once(self) -> None:
        settings.bootstrap_setup_token = "setup-secret"
        payload = BootstrapRegisterRequest(
            username="first_partner",
            password="abc12345",
            nickname="First Partner",
            role=UserRole.partner_a,
        )

        created = bootstrap_register(payload=payload, db=self.db, bootstrap_token="setup-secret")
        self.assertEqual(created.role, UserRole.partner_a)

        with self.assertRaises(HTTPException) as ctx:
            bootstrap_register(
                payload=BootstrapRegisterRequest(
                    username="second_partner",
                    password="abc12345",
                    nickname="Second Partner",
                    role=UserRole.partner_b,
                ),
                db=self.db,
                bootstrap_token="setup-secret",
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_bootstrap_register_rejects_invalid_token(self) -> None:
        settings.bootstrap_setup_token = "setup-secret"
        with self.assertRaises(HTTPException) as ctx:
            bootstrap_register(
                payload=BootstrapRegisterRequest(
                    username="first_partner",
                    password="abc12345",
                    nickname="First Partner",
                    role=UserRole.partner_a,
                ),
                db=self.db,
                bootstrap_token="wrong-token",
            )
        self.assertEqual(ctx.exception.status_code, 401)

    def test_bootstrap_register_requires_configured_token(self) -> None:
        settings.bootstrap_setup_token = ""
        with self.assertRaises(HTTPException) as ctx:
            bootstrap_register(
                payload=BootstrapRegisterRequest(
                    username="first_partner",
                    password="abc12345",
                    nickname="First Partner",
                    role=UserRole.partner_a,
                ),
                db=self.db,
                bootstrap_token="setup-secret",
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_partner_can_create_missing_partner_without_open_registration(self) -> None:
        # Regression: a fresh production deployment ends bootstrap with only
        # PartnerA and `allow_registration` at its default (False). The signed-in
        # partner must still be able to create the second partner account —
        # otherwise the couple app is permanently stuck with a single account.
        current_user = self.create_user(username="admin_user", role=UserRole.partner_a, nickname="Admin")
        self.assertIsNone(self.db.query(SiteSetting).filter(SiteSetting.id == 1).first())

        created = register(
            payload=PartnerRegisterRequest(
                username="partner_b_user",
                password="abc12345",
                nickname="Partner B",
                role=UserRole.partner_b,
            ),
            db=self.db,
            current_user=current_user,
        )
        self.assertEqual(created.role, UserRole.partner_b)

        # The partner slot is unique: a second PartnerB is rejected.
        with self.assertRaises(HTTPException) as ctx:
            register(
                payload=PartnerRegisterRequest(
                    username="partner_b_dup",
                    password="abc12345",
                    nickname="Partner B Dup",
                    role=UserRole.partner_b,
                ),
                db=self.db,
                current_user=current_user,
            )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_banned_visitor_cannot_login_or_reuse_existing_token(self) -> None:
        visitor = self.create_user(username="banned_guest", role=UserRole.visitor, nickname="Banned Guest")
        visitor.is_banned = True
        visitor.permission_status = "banned"
        self.db.commit()
        self.db.refresh(visitor)

        with self.assertRaises(HTTPException) as login_ctx:
            login(
                request=_make_request(),
                payload=LoginRequest(username="banned_guest", password="abc12345"),
                response=Response(),
                db=self.db,
            )
        self.assertEqual(login_ctx.exception.status_code, 403)

        token = create_access_token(visitor.uid, session_version=visitor.session_version)
        with self.assertRaises(HTTPException) as auth_ctx:
            get_current_user(db=self.db, token=token)
        self.assertEqual(auth_ctx.exception.status_code, 401)

    def test_update_visitor_keeps_ban_flags_in_sync(self) -> None:
        partner = self.create_user(username="visitor_admin", role=UserRole.partner_a, nickname="Visitor Admin")
        visitor = self.create_user(username="visitor_sync", role=UserRole.visitor, nickname="Visitor Sync")

        updated = update_visitor(
            uid=visitor.uid,
            payload=UpdateVisitorRequest(is_banned=True),
            db=self.db,
            current_user=partner,
        )
        self.assertTrue(updated.is_banned)
        self.assertEqual(updated.permission_status, "banned")

        updated = update_visitor(
            uid=visitor.uid,
            payload=UpdateVisitorRequest(is_banned=False),
            db=self.db,
            current_user=partner,
        )
        self.assertFalse(updated.is_banned)
        self.assertEqual(updated.permission_status, "active")

        updated = update_visitor(
            uid=visitor.uid,
            payload=UpdateVisitorRequest(permission_status="limited"),
            db=self.db,
            current_user=partner,
        )
        self.assertFalse(updated.is_banned)
        self.assertEqual(updated.permission_status, "limited")


class AuditLogRegressionTests(DatabaseTestCase):
    def test_login_success_and_failure_are_audited(self) -> None:
        self.create_user(username="audit_login", role=UserRole.partner_a, nickname="Audit Login")

        token = login(
            request=_make_request(),
            payload=LoginRequest(username="audit_login", password="abc12345"),
            response=Response(),
            db=self.db,
        )
        self.assertTrue(token.access_token)

        with self.assertRaises(HTTPException):
            login(
                request=_make_request(),
                payload=LoginRequest(username="audit_login", password="bad-password"),
                response=Response(),
                db=self.db,
            )

        logs = (
            self.db.query(AuditLog)
            .filter(AuditLog.action == "auth.login")
            .order_by(AuditLog.id.asc())
            .all()
        )
        self.assertEqual([item.result for item in logs], ["success", "failure"])
        self.assertEqual(logs[0].actor_username, "audit_login")
        self.assertEqual(logs[1].actor_username, "audit_login")

    def test_article_create_and_delete_are_audited(self) -> None:
        current_user = self.create_user(username="audit_author", role=UserRole.partner_a, nickname="Audit Author")

        article = create_article(
            payload=ArticleCreateRequest(
                title="Audited Article",
                status=ArticleStatus.published,
                is_encrypted=False,
            ),
            db=self.db,
            current_user=current_user,
        )
        delete_article(aid=article.aid, db=self.db, current_user=current_user)

        logs = (
            self.db.query(AuditLog)
            .filter(AuditLog.resource_type == "article")
            .order_by(AuditLog.id.asc())
            .all()
        )
        self.assertEqual([item.action for item in logs], ["article.create", "article.delete"])
        self.assertEqual(logs[0].resource_name, "Audited Article")
        self.assertEqual(logs[0].detail["status"], ArticleStatus.published.value)

    def test_partner_and_settings_updates_are_audited_and_filterable(self) -> None:
        current_user = self.create_user(username="audit_admin", role=UserRole.partner_a, nickname="Audit Admin")
        target_user = self.create_user(username="audit_partner", role=UserRole.partner_b, nickname="Audit Partner")

        update_partner(
            uid=target_user.uid,
            payload=UpdatePartnerRequest(nickname="Updated Partner", password="abc123456"),
            db=self.db,
            current_user=current_user,
        )
        update_settings(
            payload=SiteSettingUpdateRequest(site_name="Audited Site"),
            db=self.db,
            current_user=current_user,
        )

        filtered = list_audit_logs(
            action="account.update_partner",
            db=self.db,
            current_user=current_user,
        )
        self.assertEqual(filtered.total, 1)
        self.assertEqual(filtered.items[0].resource_id, target_user.uid)
        self.assertEqual(set(filtered.items[0].detail["changed_fields"]), {"nickname", "password"})

        settings_log = self.db.query(AuditLog).filter(AuditLog.action == "settings.update").one()
        self.assertEqual(settings_log.detail["changed_fields"], ["site_name"])

    def test_list_audit_logs_repairs_utf8_mojibake_strings(self) -> None:
        def _mojibake(value: str) -> str:
            return value.encode("utf-8").decode("latin-1")

        current_user = self.create_user(
            username="audit_cn_admin",
            role=UserRole.partner_a,
            nickname="Admin",
        )
        broken_nickname = _mojibake("测试管理员")
        broken_resource_name = _mojibake("安全配置")
        broken_detail_message = _mojibake("中文详情")

        log = AuditLog(
            action="settings.update",
            result="success",
            actor_id=current_user.id,
            actor_uid=current_user.uid,
            actor_username=current_user.username,
            actor_nickname=broken_nickname,
            resource_type="site_settings",
            resource_name=broken_resource_name,
            detail_json=json.dumps({"message": broken_detail_message}, ensure_ascii=False),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        response = list_audit_logs(db=self.db, current_user=current_user)
        target_item = next(item for item in response.items if item.log_id == log.log_id)

        self.assertEqual(target_item.actor_nickname, "测试管理员")
        self.assertEqual(target_item.resource_name, "安全配置")
        self.assertEqual(target_item.detail["message"], "中文详情")


class DashboardVisibilityRegressionTests(DatabaseTestCase):
    def test_public_dashboard_filters_before_limit(self) -> None:
        creator = self.create_user(username="owner_user", role=UserRole.partner_a, nickname="Owner")

        for day in range(1, 7):
            self.db.add(
                Event(
                    creator_id=creator.id,
                    title=f"private-event-{day}",
                    date=date(2026, 1, day),
                    visibility=Visibility.encrypted,
                )
            )
        self.db.add(
            Event(
                creator_id=creator.id,
                title="public-event",
                date=date(2026, 12, 31),
                visibility=Visibility.public,
            )
        )

        base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.db.add(
            Article(
                author_id=creator.id,
                title="public-article",
                status=ArticleStatus.published,
                is_encrypted=False,
                created_at=base_time,
            )
        )
        for index in range(6):
            self.db.add(
                Article(
                    author_id=creator.id,
                    title=f"private-article-{index}",
                    status=ArticleStatus.published,
                    is_encrypted=True,
                    created_at=base_time + timedelta(days=index + 1),
                )
            )

        self.db.add(
            Album(
                author_id=creator.id,
                title="public-album",
                is_public=True,
                is_encrypted=False,
                created_at=base_time,
            )
        )
        for index in range(6):
            self.db.add(
                Album(
                    author_id=creator.id,
                    title=f"private-album-{index}",
                    is_public=True,
                    is_encrypted=True,
                    created_at=base_time + timedelta(days=index + 1),
                )
            )

        self.db.commit()

        dashboard = get_dashboard(db=self.db, current_user=None)

        self.assertEqual(dashboard.stats.event_count, 1)
        self.assertEqual(len(dashboard.recent_events), 1)
        self.assertEqual(dashboard.recent_events[0].title, "public-event")

        self.assertEqual(dashboard.stats.article_count, 1)
        self.assertEqual(len(dashboard.latest_articles), 1)
        self.assertEqual(dashboard.latest_articles[0].title, "public-article")

        self.assertEqual(dashboard.stats.album_count, 1)
        self.assertEqual(len(dashboard.latest_albums), 1)
        self.assertEqual(dashboard.latest_albums[0].title, "public-album")


class MessagePolicyRegressionTests(DatabaseTestCase):
    def test_create_message_signature_requires_authenticated_user(self) -> None:
        current_user_param = inspect.signature(create_message).parameters["current_user"]
        self.assertEqual(current_user_param.annotation, User)


class SearchRegressionTests(DatabaseTestCase):
    def test_search_filters_by_visibility_keyword_tags_and_date(self) -> None:
        partner = self.create_user(username="search_partner", role=UserRole.partner_a, nickname="Search Partner")

        public_article = Article(
            author_id=partner.id,
            title="Beach Letter",
            excerpt="A public summer note",
            status=ArticleStatus.published,
            is_encrypted=False,
            tags=["travel", "summer"],
            created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        encrypted_article = Article(
            author_id=partner.id,
            title="Secret Beach Letter",
            excerpt="Hidden",
            status=ArticleStatus.published,
            is_encrypted=True,
            tags=["travel", "secret"],
            created_at=datetime(2026, 5, 2, tzinfo=timezone.utc),
        )
        public_album = Album(
            author_id=partner.id,
            title="Beach Album",
            description="Photos from the shore",
            is_public=True,
            is_encrypted=False,
            tags=["travel"],
            created_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
        )
        event = Event(
            creator_id=partner.id,
            title="Anniversary Picnic",
            date=date(2026, 5, 4),
            visibility=Visibility.public,
            tags=["anniversary"],
        )
        private_event = Event(
            creator_id=partner.id,
            title="Private Anniversary",
            date=date(2026, 5, 5),
            visibility=Visibility.encrypted,
            tags=["anniversary", "secret"],
        )
        moment = Moment(
            author_id=partner.id,
            content="Beach timeline memory",
            media_urls=[],
            visibility=MomentVisibility.public,
            tags=["travel"],
            timestamp=datetime(2026, 5, 6, tzinfo=timezone.utc),
        )
        message = Message(
            author_id=partner.id,
            content="Beach message",
            is_public=True,
            tags=["travel"],
            created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        )
        self.db.add_all([public_article, encrypted_article, public_album, event, private_event, moment, message])
        self.db.flush()
        self.db.add(
            ArticleBlock(
                article_id=public_article.id,
                author_id=partner.id,
                content="The searchable block talks about shells.",
            )
        )
        self.db.commit()

        public_response = search_content(q="Beach", db=self.db, current_user=None)
        public_pairs = {(item.type, item.id) for item in public_response.items}
        self.assertIn(("article", public_article.aid), public_pairs)
        self.assertIn(("album", public_album.alb_id), public_pairs)
        self.assertIn(("moment", moment.mid), public_pairs)
        self.assertIn(("message", message.msg_id), public_pairs)
        self.assertNotIn(("article", encrypted_article.aid), public_pairs)

        partner_response = search_content(q="Secret", db=self.db, current_user=partner)
        partner_pairs = {(item.type, item.id) for item in partner_response.items}
        self.assertIn(("article", encrypted_article.aid), partner_pairs)

        tag_response = search_content(
            types="event",
            tags="anniversary",
            date_from=date(2026, 5, 4),
            date_to=date(2026, 5, 4),
            db=self.db,
            current_user=None,
        )
        self.assertEqual(tag_response.total, 1)
        self.assertEqual(tag_response.items[0].id, event.eid)

    def test_search_private_messages_for_owner_and_partner_only(self) -> None:
        owner = self.create_user(username="search_owner", role=UserRole.visitor, nickname="Owner")
        other = self.create_user(username="search_other", role=UserRole.visitor, nickname="Other")
        partner = self.create_user(username="search_admin", role=UserRole.partner_a, nickname="Admin")

        private_message = Message(
            author_id=owner.id,
            content="private keepsake",
            is_public=False,
            tags=["secret"],
        )
        self.db.add(private_message)
        self.db.commit()

        public_response = search_content(q="keepsake", types="message", db=self.db, current_user=None)
        self.assertEqual(public_response.total, 0)

        owner_response = search_content(q="keepsake", types="message", db=self.db, current_user=owner)
        self.assertEqual(owner_response.total, 1)
        self.assertEqual(owner_response.items[0].id, private_message.msg_id)

        other_response = search_content(q="keepsake", types="message", db=self.db, current_user=other)
        self.assertEqual(other_response.total, 0)

        partner_response = search_content(q="keepsake", types="message", db=self.db, current_user=partner)
        self.assertEqual(partner_response.total, 1)


class ContentProtectionRegressionTests(DatabaseTestCase):
    def test_article_password_protection_requires_password_and_persists_on_update(self) -> None:
        partner = self.create_user(username="article_guard", role=UserRole.partner_a, nickname="Article Guard")

        with self.assertRaises(HTTPException) as create_ctx:
            create_article(
                payload=ArticleCreateRequest(
                    title="Locked article",
                    excerpt="Hidden",
                    visibility=ContentVisibility.password_protected,
                    blocks=[],
                ),
                db=self.db,
                current_user=partner,
            )
        self.assertEqual(create_ctx.exception.status_code, 400)

        created = create_article(
            payload=ArticleCreateRequest(
                title="Public article",
                excerpt="Visible",
                visibility=ContentVisibility.public,
                blocks=[],
            ),
            db=self.db,
            current_user=partner,
        )

        with self.assertRaises(HTTPException) as patch_ctx:
            patch_article(
                aid=created.aid,
                payload=ArticlePatchRequest(visibility=ContentVisibility.password_protected),
                db=self.db,
                current_user=partner,
                response=Response(),
                if_match=None,
            )
        self.assertEqual(patch_ctx.exception.status_code, 400)

        updated = update_article(
            aid=created.aid,
            payload=ArticleCreateRequest(
                title="Locked article",
                excerpt="Hidden",
                visibility=ContentVisibility.password_protected,
                password="vault-123",
                blocks=[],
            ),
            db=self.db,
            current_user=partner,
            response=Response(),
            if_match=None,
        )
        self.assertEqual(updated.visibility, ContentVisibility.password_protected)
        self.assertTrue(updated.requires_password)

    def test_article_versions_keep_password_protection_data_but_hide_hash_in_response(self) -> None:
        partner = self.create_user(username="article_history", role=UserRole.partner_a, nickname="Article History")
        created = create_article(
            payload=ArticleCreateRequest(
                title="Versioned article",
                excerpt="Encrypted",
                visibility=ContentVisibility.password_protected,
                password="vault-456",
                blocks=[],
            ),
            db=self.db,
            current_user=partner,
        )

        article = self.db.query(Article).filter(Article.aid == created.aid).first()
        versions = list_content_versions(self.db, content_type="article", content_id=created.aid)
        self.assertTrue(versions)

        response_version = version_to_response(versions[0])
        self.assertEqual(response_version["snapshot"]["visibility"], ContentVisibility.password_protected.value)
        self.assertTrue(response_version["snapshot"]["has_password"])
        self.assertNotIn("password_hash", response_version["snapshot"])

        original_hash = article.password_hash
        article.title = "Mutated"
        article.visibility = ContentVisibility.public
        article.password_hash = None
        self.db.commit()

        apply_article_snapshot(self.db, article, versions[0].snapshot, partner)
        self.assertEqual(article.title, "Versioned article")
        self.assertEqual(article.visibility, ContentVisibility.password_protected)
        self.assertEqual(article.password_hash, original_hash)

    def test_album_password_protection_requires_password_and_persists_on_update(self) -> None:
        partner = self.create_user(username="album_guard", role=UserRole.partner_a, nickname="Album Guard")

        with self.assertRaises(HTTPException) as create_ctx:
            create_album(
                payload=AlbumCreateRequest(
                    title="Locked album",
                    visibility=ContentVisibility.password_protected,
                    media_items=[],
                ),
                db=self.db,
                current_user=partner,
            )
        self.assertEqual(create_ctx.exception.status_code, 400)

        created = create_album(
            payload=AlbumCreateRequest(
                title="Public album",
                visibility=ContentVisibility.public,
                media_items=[],
            ),
            db=self.db,
            current_user=partner,
        )

        with self.assertRaises(HTTPException) as patch_ctx:
            patch_album(
                alb_id=created.alb_id,
                payload=AlbumPatchRequest(visibility=ContentVisibility.password_protected),
                db=self.db,
                current_user=partner,
            )
        self.assertEqual(patch_ctx.exception.status_code, 400)

        updated = update_album(
            alb_id=created.alb_id,
            payload=AlbumCreateRequest(
                title="Locked album",
                visibility=ContentVisibility.password_protected,
                password="vault-789",
                media_items=[],
            ),
            db=self.db,
            current_user=partner,
        )
        self.assertEqual(updated.visibility, ContentVisibility.password_protected)
        self.assertTrue(updated.requires_password)


class VisibilityPolicyRegressionTests(DatabaseTestCase):
    def test_content_visibility_enum_is_shared_by_articles_and_albums(self) -> None:
        from app.models.album import ContentVisibility as AlbumVisibility
        from app.models.article import ContentVisibility as ArticleVisibility
        from app.models.content_visibility import ContentVisibility

        self.assertIs(ArticleVisibility, ContentVisibility)
        self.assertIs(AlbumVisibility, ContentVisibility)

    def test_visibility_levels_are_centralized(self) -> None:
        owner = self.create_user(username="policy_owner", role=UserRole.visitor, nickname="Owner")
        other = self.create_user(username="policy_other", role=UserRole.visitor, nickname="Other")
        partner = self.create_user(username="policy_partner", role=UserRole.partner_a, nickname="Partner")

        self.assertEqual(VisibilityPolicy.normalize("public"), VisibilityLevel.public)
        self.assertEqual(VisibilityPolicy.normalize("partners_only"), VisibilityLevel.partners_only)
        self.assertTrue(VisibilityPolicy.can_view_level(VisibilityLevel.public, None))
        self.assertFalse(VisibilityPolicy.can_view_level(VisibilityLevel.partners_only, other))
        self.assertTrue(VisibilityPolicy.can_view_level(VisibilityLevel.partners_only, partner))
        self.assertFalse(VisibilityPolicy.can_view_level(VisibilityLevel.encrypted, None))
        self.assertTrue(VisibilityPolicy.can_view_level(VisibilityLevel.encrypted, partner))
        self.assertTrue(VisibilityPolicy.can_view_level(VisibilityLevel.private, owner, owner_id=owner.id))
        self.assertFalse(VisibilityPolicy.can_view_level(VisibilityLevel.private, other, owner_id=owner.id))
        self.assertFalse(VisibilityPolicy.can_view_level(VisibilityLevel.private, partner, owner_id=owner.id))
        self.assertTrue(
            VisibilityPolicy.can_view_level(
                VisibilityLevel.private,
                partner,
                owner_id=owner.id,
                partners_can_view_private=True,
            )
        )

    def test_article_drafts_respect_owner_and_co_edit_rules(self) -> None:
        author = self.create_user(username="draft_author", role=UserRole.partner_a, nickname="Author")
        partner = self.create_user(username="draft_partner", role=UserRole.partner_b, nickname="Partner")

        article = Article(
            author_id=author.id,
            title="private draft",
            status=ArticleStatus.draft,
            partner_can_edit=False,
        )
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)

        self.assertTrue(VisibilityPolicy.can_view_article(article, author))
        self.assertFalse(VisibilityPolicy.can_view_article(article, partner))

        article.partner_can_edit = True
        self.assertTrue(VisibilityPolicy.can_view_article(article, partner))

    def test_article_draft_query_filter_requires_owner_or_co_edit(self) -> None:
        author = self.create_user(username="draft_query_author", role=UserRole.partner_a, nickname="Author")
        partner = self.create_user(username="draft_query_partner", role=UserRole.partner_b, nickname="Partner")
        visitor = self.create_user(username="draft_query_visitor", role=UserRole.visitor, nickname="Visitor")

        private_draft = Article(
            author_id=author.id,
            title="query private draft",
            status=ArticleStatus.draft,
            partner_can_edit=False,
        )
        shared_draft = Article(
            author_id=author.id,
            title="query shared draft",
            status=ArticleStatus.draft,
            partner_can_edit=True,
        )
        self.db.add_all([private_draft, shared_draft])
        self.db.commit()

        partner_titles = {
            item.title
            for item in self.db.query(Article)
            .filter(VisibilityPolicy.article_query_filter(partner))
            .all()
        }
        self.assertNotIn("query private draft", partner_titles)
        self.assertIn("query shared draft", partner_titles)

        author_titles = {
            item.title
            for item in self.db.query(Article)
            .filter(VisibilityPolicy.article_query_filter(author))
            .all()
        }
        self.assertEqual(author_titles, {"query private draft", "query shared draft"})

        visitor_titles = {
            item.title
            for item in self.db.query(Article)
            .filter(VisibilityPolicy.article_query_filter(visitor))
            .all()
        }
        self.assertEqual(visitor_titles, set())

    def test_private_messages_are_listed_only_for_owner_or_partner(self) -> None:
        owner = self.create_user(username="message_owner", role=UserRole.visitor, nickname="Owner")
        other = self.create_user(username="message_other", role=UserRole.visitor, nickname="Other")
        partner = self.create_user(username="message_partner", role=UserRole.partner_a, nickname="Partner")

        public_message = Message(author_id=owner.id, content="public", is_public=True)
        owner_private = Message(author_id=owner.id, content="owner private", is_public=False)
        other_private = Message(author_id=other.id, content="other private", is_public=False)
        self.db.add_all([public_message, owner_private, other_private])
        self.db.commit()

        owner_response = list_messages(include_private=True, db=self.db, current_user=owner)
        self.assertEqual({item.content for item in owner_response.items}, {"public", "owner private"})

        partner_response = list_messages(include_private=True, db=self.db, current_user=partner)
        self.assertEqual({item.content for item in partner_response.items}, {"public", "owner private", "other private"})

        with self.assertRaises(HTTPException) as ctx:
            delete_message(msg_id=public_message.msg_id, db=self.db, current_user=other)
        self.assertEqual(ctx.exception.status_code, 403)


class StorageAndRecycleRegressionTests(DatabaseTestCase):
    def test_upload_reference_collector_includes_site_setting_partner_avatars(self) -> None:
        setting = SiteSetting(
            id=1,
            partner_a_avatar="http://localhost/uploads/avatars/partner-a.png",
            partner_b_avatar="/uploads/avatars/partner-b.png",
        )
        self.db.merge(setting)
        self.db.commit()

        refs = _collect_referenced_upload_paths(self.db)
        ref_paths = {path.as_posix() for path in refs}
        self.assertTrue(any(path.endswith("/uploads/avatars/partner-a.png") for path in ref_paths))
        self.assertTrue(any(path.endswith("/uploads/avatars/partner-b.png") for path in ref_paths))

    def test_couple_avatars_are_servable_to_anonymous_and_visitor_viewers(self) -> None:
        """Couple avatars live on the public homepage hero, so the media-serving
        gate must let anonymous visitors (and logged-in non-partners) load them.

        Regression: ``can_access_upload_reference`` previously required
        ``is_partner`` for ``site_setting`` refs, which made the homepage avatar
        return 401/403 for everyone who was not a partner.
        """
        setting = SiteSetting(
            id=1,
            partner_a_avatar="/uploads/avatars/partner-a.png",
            partner_b_avatar="/uploads/avatars/partner-b.png",
        )
        self.db.merge(setting)
        self.db.commit()
        stored_setting = self.db.query(SiteSetting).filter(SiteSetting.id == 1).first()
        sync_site_setting_upload_references(self.db, stored_setting)
        self.db.commit()

        avatar_refs = (
            self.db.query(UploadReference)
            .filter(UploadReference.content_kind == "site_setting")
            .all()
        )
        self.assertTrue(avatar_refs, "expected site_setting upload references to exist")

        visitor = self.create_user(username="avatar_visitor", role=UserRole.visitor, nickname="Visitor")
        partner = self.create_user(username="avatar_partner", role=UserRole.partner_a, nickname="Partner")

        for ref in avatar_refs:
            self.assertTrue(can_access_upload_reference(ref, None))
            self.assertTrue(can_access_upload_reference(ref, visitor))
            self.assertTrue(can_access_upload_reference(ref, partner))

    def test_recycle_bin_hard_delete_cascades_article_dependencies(self) -> None:
        partner = self.create_user(username="recycle_admin", role=UserRole.partner_a, nickname="Recycle Admin")
        article = Article(
            author_id=partner.id,
            title="Deleted article",
            status=ArticleStatus.published,
            deleted_at=datetime.now(timezone.utc),
        )
        self.db.add(article)
        self.db.flush()

        self.db.add(
            Comment(
                target_type=CommentTargetType.article,
                target_id=article.aid,
                author_id=partner.id,
                content="comment",
            )
        )
        self.db.add(
            ContentVersion(
                content_type="article",
                content_id=article.aid,
                version=1,
                title=article.title,
                snapshot={"title": article.title},
                actor_id=partner.id,
            )
        )
        self.db.add(
            UploadReference(
                file_path="uploads/articles/deleted.png",
                content_kind="article",
                content_id=article.id,
                slot="cover",
            )
        )
        self.db.commit()

        permanently_delete_item(type="article", id=article.aid, db=self.db, current_user=partner)

        self.assertIsNone(self.db.query(Article).filter(Article.aid == article.aid).first())
        self.assertEqual(
            self.db.query(Comment)
            .filter(Comment.target_type == CommentTargetType.article, Comment.target_id == article.aid)
            .count(),
            0,
        )
        self.assertEqual(
            self.db.query(ContentVersion)
            .filter(ContentVersion.content_type == "article", ContentVersion.content_id == article.aid)
            .count(),
            0,
        )
        self.assertEqual(
            self.db.query(UploadReference)
            .filter(UploadReference.content_kind == "article", UploadReference.content_id == article.id)
            .count(),
            0,
        )


class TimelineRegressionTests(DatabaseTestCase):
    def test_create_comment_enforces_moment_visibility(self) -> None:
        author = self.create_user(username="timeline_owner", role=UserRole.partner_a, nickname="Timeline Owner")
        visitor = self.create_user(username="timeline_guest", role=UserRole.visitor, nickname="Timeline Guest")

        moment = Moment(
            author_id=author.id,
            content="private moment",
            media_urls=[],
            visibility=MomentVisibility.partners_only,
        )
        self.db.add(moment)
        self.db.commit()
        self.db.refresh(moment)

        with self.assertRaises(HTTPException) as ctx:
            create_comment(
                mid=moment.mid,
                payload=CommentCreateRequest(content="hello"),
                db=self.db,
                current_user=visitor,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_create_comment_sets_generic_target_fields(self) -> None:
        author = self.create_user(username="timeline_target", role=UserRole.partner_a, nickname="Timeline Target")
        moment = Moment(
            author_id=author.id,
            content="public moment",
            media_urls=[],
            visibility=MomentVisibility.public,
        )
        self.db.add(moment)
        self.db.commit()
        self.db.refresh(moment)

        create_comment(
            mid=moment.mid,
            payload=CommentCreateRequest(content="hello there"),
            db=self.db,
            current_user=author,
        )

        comment = self.db.query(Comment).order_by(Comment.id.desc()).first()
        self.assertEqual(comment.target_type, CommentTargetType.moment)
        self.assertEqual(comment.target_id, moment.mid)

    def test_list_moments_pushes_visibility_and_pagination_to_sql(self) -> None:
        author = self.create_user(username="timeline_admin", role=UserRole.partner_a, nickname="Timeline Admin")

        for index in range(6):
            self.db.add(
                Moment(
                    author_id=author.id,
                    content=f"private-{index}",
                    media_urls=[],
                    visibility=MomentVisibility.partners_only,
                    timestamp=datetime(2026, 1, index + 1, tzinfo=timezone.utc),
                )
            )
        self.db.add(
            Moment(
                author_id=author.id,
                content="public-item",
                media_urls=[],
                visibility=MomentVisibility.public,
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
        )
        self.db.commit()

        statements: list[str] = []

        def _capture_sql(_, __, statement: str, ___, ____, _____) -> None:
            statements.append(statement)

        sqlalchemy_event.listen(self.engine, "before_cursor_execute", _capture_sql)
        try:
            response = list_moments(
                page=1,
                page_size=5,
                sort="desc",
                db=self.db,
                current_user=None,
            )
        finally:
            sqlalchemy_event.remove(self.engine, "before_cursor_execute", _capture_sql)

        self.assertEqual(response.total, 1)
        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].content, "public-item")

        lower_statements = [stmt.lower() for stmt in statements]
        moment_page_queries = [stmt for stmt in lower_statements if "from moments" in stmt and "order by" in stmt]
        self.assertTrue(moment_page_queries)
        self.assertTrue(any("moments.visibility" in stmt and "limit" in stmt for stmt in moment_page_queries))

        count_queries = [stmt for stmt in lower_statements if "from moments" in stmt and "count(" in stmt]
        self.assertTrue(count_queries)
        self.assertTrue(any("moments.visibility" in stmt for stmt in count_queries))


class CottageQuestionRegressionTests(DatabaseTestCase):
    def test_daily_question_stays_blind_until_both_partners_answer(self) -> None:
        partner_a = self.create_user(username="question_a", role=UserRole.partner_a, nickname="Question A")
        partner_b = self.create_user(username="question_b", role=UserRole.partner_b, nickname="Question B")

        created = create_question(
            payload=DailyQuestionCreateRequest(
                question_date=date(2026, 6, 19),
                prompt="What should we remember about today?",
            ),
            db=self.db,
            current_user=partner_a,
        )
        self.assertFalse(created.revealed)
        self.assertEqual(created.answered_count, 0)

        with self.assertRaises(HTTPException) as duplicate_ctx:
            create_question(
                payload=DailyQuestionCreateRequest(
                    question_date=date(2026, 6, 19),
                    prompt="Duplicate question",
                ),
                db=self.db,
                current_user=partner_b,
            )
        self.assertEqual(duplicate_ctx.exception.status_code, 409)

        after_a = answer_question(
            qid=created.qid,
            payload=DailyQuestionAnswerRequest(content="I loved the quiet breakfast."),
            db=self.db,
            current_user=partner_a,
        )
        self.assertFalse(after_a.revealed)
        self.assertEqual(after_a.answered_count, 1)
        mine = next(item for item in after_a.answers if item.is_self)
        other = next(item for item in after_a.answers if not item.is_self)
        self.assertTrue(mine.content_visible)
        self.assertEqual(mine.content, "I loved the quiet breakfast.")
        self.assertFalse(other.content_visible)
        self.assertIsNone(other.content)

        seen_by_b = get_today_question(
            on=date(2026, 6, 19),
            db=self.db,
            current_user=partner_b,
        ).item
        self.assertIsNotNone(seen_by_b)
        partner_a_answer = next(item for item in seen_by_b.answers if item.author_uid == partner_a.uid)
        self.assertTrue(partner_a_answer.answered)
        self.assertFalse(partner_a_answer.content_visible)
        self.assertIsNone(partner_a_answer.content)

        after_b = answer_question(
            qid=created.qid,
            payload=DailyQuestionAnswerRequest(content="Your laugh when the coffee spilled."),
            db=self.db,
            current_user=partner_b,
        )
        self.assertTrue(after_b.revealed)
        self.assertEqual(after_b.answered_count, 2)
        self.assertEqual(
            {item.content for item in after_b.answers},
            {"I loved the quiet breakfast.", "Your laugh when the coffee spilled."},
        )

    def test_daily_question_models_are_imported_for_create_all(self) -> None:
        self.assertIn(DailyQuestion.__tablename__, Base.metadata.tables)
        self.assertIn(DailyQuestionAnswer.__tablename__, Base.metadata.tables)


class CottageNewModulesRegressionTests(DatabaseTestCase):
    def test_cottage_plans_can_be_completed_and_counted(self) -> None:
        partner_a = self.create_user(username="plan_a", role=UserRole.partner_a, nickname="Plan A")
        self.create_user(username="plan_b", role=UserRole.partner_b, nickname="Plan B")

        created = create_plan(
            payload=CottagePlanCreateRequest(
                title="Weekend picnic",
                description="Bring fruit and a blanket.",
                plan_date=date(2026, 6, 20),
                checklist=[
                    PlanChecklistItem(text="Buy strawberries"),
                    PlanChecklistItem(text="Charge camera", done=True),
                ],
            ),
            db=self.db,
            current_user=partner_a,
        )
        self.assertEqual(created.status, "planned")
        self.assertEqual(len(created.checklist), 2)

        completed = complete_plan(pid=created.pid, db=self.db, current_user=partner_a)
        self.assertEqual(completed.status, "done")
        self.assertIsNotNone(completed.completed_at)

        response = list_plans(status_filter=None, db=self.db, current_user=partner_a)
        self.assertEqual(response.total, 1)
        self.assertEqual(response.completed, 1)
        self.assertEqual(response.active, 0)

    def test_due_cottage_reminder_creates_deduped_notification(self) -> None:
        partner_a = self.create_user(username="reminder_a", role=UserRole.partner_a, nickname="Reminder A")
        partner_b = self.create_user(username="reminder_b", role=UserRole.partner_b, nickname="Reminder B")

        created = create_reminder(
            payload=CottageReminderCreateRequest(
                title="Drink water",
                note="Tiny care reminder.",
                remind_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                audience="both",
            ),
            db=self.db,
            current_user=partner_a,
        )
        self.assertTrue(created.is_due)

        create_due_cottage_reminders(self.db, partner_b)
        create_due_cottage_reminders(self.db, partner_b)
        self.db.commit()

        notifications = (
            self.db.query(Notification)
            .filter(
                Notification.recipient_id == partner_b.id,
                Notification.type == "cottage_reminder.due",
                Notification.source_id == created.rid,
            )
            .all()
        )
        self.assertEqual(len(notifications), 1)

        done = mark_reminder_done(rid=created.rid, db=self.db, current_user=partner_b)
        self.assertTrue(done.is_done)
        listing = list_reminders(include_done=True, db=self.db, current_user=partner_b)
        self.assertEqual(listing.done, 1)

    def test_monthly_report_includes_new_cottage_activity(self) -> None:
        now = datetime.now(timezone.utc)
        partner_a = self.create_user(username="report_a", role=UserRole.partner_a, nickname="Report A")
        self.create_user(username="report_b", role=UserRole.partner_b, nickname="Report B")

        plan = create_plan(
            payload=CottagePlanCreateRequest(title="Finish report plan"),
            db=self.db,
            current_user=partner_a,
        )
        complete_plan(pid=plan.pid, db=self.db, current_user=partner_a)
        create_reminder(
            payload=CottageReminderCreateRequest(
                title="Report reminder",
                remind_at=now + timedelta(hours=1),
                audience="both",
            ),
            db=self.db,
            current_user=partner_a,
        )

        report = monthly_report(year=now.year, month=now.month, db=self.db, current_user=partner_a)
        self.assertGreaterEqual(report.stats["plans_created"], 1)
        self.assertGreaterEqual(report.stats["plans_completed"], 1)
        self.assertGreaterEqual(report.stats["reminders_created"], 1)
        self.assertTrue(any(item.kind == "plan" for item in report.highlights))

    def test_new_cottage_models_are_imported_for_create_all(self) -> None:
        self.assertIn(CottagePlan.__tablename__, Base.metadata.tables)
        self.assertIn(CottageReminder.__tablename__, Base.metadata.tables)


class FrontendRegressionTests(unittest.TestCase):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    def test_auth_store_bootstraps_cookie_session_state(self) -> None:
        auth_store = (self.PROJECT_ROOT / "web" / "src" / "stores" / "auth.js").read_text(encoding="utf-8")
        self.assertIn("fetchMe()", auth_store)
        self.assertIn('setAuthToken("legacy", user.role)', auth_store)
        self.assertIn('token: computed(() => isAuth.value ? "legacy" : "")', auth_store)

    def test_auth_is_initialized_before_router_mount(self) -> None:
        main_js = (self.PROJECT_ROOT / "web" / "src" / "main.js").read_text(encoding="utf-8")
        self.assertIn("initAuth()", main_js)
        self.assertIn("createApp(App)", main_js)
        self.assertLess(main_js.index("initAuth()"), main_js.index("createApp(App)"))

    def test_router_guard_checks_bootstrap_and_initializes_auth_for_protected_routes(self) -> None:
        router_js = (self.PROJECT_ROOT / "web" / "src" / "router" / "index.js").read_text(encoding="utf-8")
        self.assertIn("fetchBootstrapStatus", router_js)
        self.assertIn('next({ name: "setup" })', router_js)
        self.assertIn("const { canManageContent, token, initAuth } = useAuth();", router_js)
        self.assertIn("if (to.meta.requiresAuth || to.meta.requiresPartner)", router_js)
        self.assertIn("await initAuth();", router_js)

    def test_auth_store_clears_state_on_logout_and_unauthorized(self) -> None:
        auth_store = (self.PROJECT_ROOT / "web" / "src" / "stores" / "auth.js").read_text(encoding="utf-8")
        self.assertIn("setUnauthorizedHandler(clearAuthState)", auth_store)
        self.assertIn("clearAuthState({ disposeResources: true })", auth_store)
        self.assertIn('localStorage.setItem(LOGOUT_PENDING_KEY, "true")', auth_store)
        self.assertIn("pendingLogoutPromise = logoutApi()", auth_store)
        self.assertLess(
            auth_store.index("clearAuthState({ disposeResources: true })", auth_store.index("async function logout()")),
            auth_store.index("return retryPendingLogout()", auth_store.index("async function logout()")),
        )
        self.assertIn("return true", auth_store)
        self.assertIn("return false", auth_store)
        self.assertIn('localStorage.removeItem("love_is_auth")', auth_store)

    def test_api_normalizes_relative_and_absolute_base_urls(self) -> None:
        api_js = (self.PROJECT_ROOT / "web" / "src" / "lib" / "api.js").read_text(encoding="utf-8")
        self.assertIn("function normalizeApiBaseUrl(value)", api_js)
        self.assertIn('return "/api";', api_js)
        self.assertIn("new URL(suffix, assetBaseOrigin).toString()", api_js)

    def test_parse_error_maps_invalid_credentials_detail(self) -> None:
        helpers_js = (self.PROJECT_ROOT / "web" / "src" / "utils" / "helpers.js").read_text(encoding="utf-8")
        locale_json = (self.PROJECT_ROOT / "web" / "src" / "locales" / "zh-CN.json").read_text(
            encoding="utf-8"
        )
        self.assertIn('detail === "Could not validate credentials"', helpers_js)
        self.assertIn('return t("errors.loginWrongCredentials");', helpers_js)
        self.assertIn('"loginWrongCredentials": "账号或密码不对，请再试一次"', locale_json)


    def test_cottage_daily_questions_are_registered_in_web_app(self) -> None:
        api_js = (self.PROJECT_ROOT / "web" / "src" / "lib" / "api.js").read_text(encoding="utf-8")
        router_js = (self.PROJECT_ROOT / "web" / "src" / "router" / "index.js").read_text(encoding="utf-8")
        modules_js = (self.PROJECT_ROOT / "web" / "src" / "views" / "cottage" / "modules.js").read_text(
            encoding="utf-8"
        )
        view_path = (
            self.PROJECT_ROOT
            / "web"
            / "src"
            / "views"
            / "cottage"
            / "questions"
            / "CottageQuestionsView.vue"
        )

        self.assertIn("/v1/cottage/questions/today", api_js)
        self.assertIn("answerDailyQuestion", api_js)
        self.assertIn('path: "questions"', router_js)
        self.assertIn("CottageQuestionsView.vue", router_js)
        self.assertIn('to: "/cottage/questions"', modules_js)
        self.assertTrue(view_path.exists())

    def test_new_cottage_modules_are_registered_in_web_app(self) -> None:
        api_js = (self.PROJECT_ROOT / "web" / "src" / "lib" / "api.js").read_text(encoding="utf-8")
        router_js = (self.PROJECT_ROOT / "web" / "src" / "router" / "index.js").read_text(encoding="utf-8")
        modules_js = (self.PROJECT_ROOT / "web" / "src" / "views" / "cottage" / "modules.js").read_text(
            encoding="utf-8"
        )
        layout_vue = (self.PROJECT_ROOT / "web" / "src" / "layouts" / "MainLayout.vue").read_text(encoding="utf-8")

        for path, component, helper in (
            ("/cottage/plans", "CottagePlansView.vue", "fetchCottagePlans"),
            ("/cottage/reminders", "CottageRemindersView.vue", "fetchCottageReminders"),
            ("/cottage/reports", "CottageReportsView.vue", "fetchCottageMonthlyReport"),
        ):
            self.assertIn(path, modules_js)
            self.assertIn(component, router_js)
            self.assertIn(helper, api_js)
            self.assertTrue((self.PROJECT_ROOT / "web" / "src" / "views" / "cottage" / path.split("/")[-1] / component).exists())

        self.assertIn('"cottage-plans"', layout_vue)
        self.assertIn('"cottage-reminders"', layout_vue)
        self.assertIn('"cottage-reports"', layout_vue)


class DeploymentRegressionTests(unittest.TestCase):
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    def test_production_compose_passes_bootstrap_token_and_frontend_api_base(self) -> None:
        compose = (self.PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
        self.assertIn("BOOTSTRAP_SETUP_TOKEN", compose)
        self.assertIn("VITE_API_BASE_URL", compose)
        self.assertIn("args:", compose)

    def test_frontend_production_dockerfile_accepts_runtime_api_base_arg(self) -> None:
        dockerfile = (self.PROJECT_ROOT / "web" / "Dockerfile.prod").read_text(encoding="utf-8")
        self.assertIn("ARG VITE_API_BASE_URL=/api", dockerfile)
        self.assertIn("ENV VITE_API_BASE_URL=$VITE_API_BASE_URL", dockerfile)
        self.assertIn("RUN npm ci", dockerfile)

    def test_nginx_uses_prefix_match_for_uploads(self) -> None:
        nginx_conf = (self.PROJECT_ROOT / "nginx" / "conf.d" / "love-journal.conf").read_text(encoding="utf-8")
        self.assertIn("location ^~ /uploads/", nginx_conf)

    def test_production_compose_passes_web_push_settings_to_backend(self) -> None:
        compose = (self.PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
        self.assertIn("WEB_PUSH_ENABLED", compose)
        self.assertIn("WEB_PUSH_VAPID_PUBLIC_KEY", compose)
        self.assertIn("WEB_PUSH_VAPID_PRIVATE_KEY", compose)
        self.assertIn("WEB_PUSH_SUBJECT", compose)

    def test_nginx_does_not_immutably_cache_pwa_entrypoints(self) -> None:
        edge_nginx = (self.PROJECT_ROOT / "nginx" / "conf.d" / "love-journal.conf").read_text(encoding="utf-8")
        web_nginx = (self.PROJECT_ROOT / "web" / "nginx.conf").read_text(encoding="utf-8")

        for config_text in (edge_nginx, web_nginx):
            self.assertIn("location = /sw.js", config_text)
            self.assertIn("location = /manifest.webmanifest", config_text)
            self.assertIn("no-cache", config_text)

    def test_production_examples_and_guides_reference_bootstrap_setup(self) -> None:
        env_example = (self.PROJECT_ROOT / ".env.production.example").read_text(encoding="utf-8")
        guide = (self.PROJECT_ROOT / "DEPLOYMENT_GUIDE.md").read_text(encoding="utf-8")
        checklist = (self.PROJECT_ROOT / "DEPLOYMENT_CHECKLIST.md").read_text(encoding="utf-8")

        self.assertIn("BOOTSTRAP_SETUP_TOKEN", env_example)
        self.assertIn("VITE_API_BASE_URL=/api", env_example)
        self.assertIn("BOOTSTRAP_SETUP_TOKEN", guide)
        self.assertIn("X-Bootstrap-Token", guide)
        self.assertIn("BOOTSTRAP_SETUP_TOKEN", checklist)


class BackupRestoreRegressionTests(unittest.TestCase):
    """Guards the backup/restore schema-version contract.

    Regression: ``BACKUP_SCHEMA_VERSION`` was bumped to ``v4`` (E2EE vault) while
    ``SUPPORTED_VERSIONS`` still only listed v1–v3, so ``/export/restore`` (and
    its preflight) rejected every backup the server itself produced with
    "不支持的备份版本 'v4'". The export format must always be restorable.
    """

    def test_current_export_version_is_restorable(self) -> None:
        from app.api.v1.export import BACKUP_SCHEMA_VERSION, SUPPORTED_VERSIONS

        self.assertIn(BACKUP_SCHEMA_VERSION, SUPPORTED_VERSIONS)

    def test_preflight_accepts_backup_written_with_current_version(self) -> None:
        import tempfile
        import zipfile

        from app.api.v1.export import BACKUP_SCHEMA_VERSION, _preflight_check_zip

        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "backup.zip"
            data_payload = {
                "meta": {
                    "schema_version": BACKUP_SCHEMA_VERSION,
                    "backup_id": "regression",
                    "counts": {},
                }
            }
            manifest_payload = {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "backup_id": "regression",
            }
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("data.json", json.dumps(data_payload))
                zf.writestr("manifest.json", json.dumps(manifest_payload))
                zf.writestr("uploads/.keep", "")

            report = _preflight_check_zip(zip_path)

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["errors"], [])
