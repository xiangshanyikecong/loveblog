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

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import get_password_hash
from app.core.startup_checks import validate_schema_contracts, validate_startup_configuration
from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from jose import jwt, JWTError
from app.services.security import check_session_version
from app.models import (
    Album,
    AlbumMedia,
    Article,
    ArticleBlock,
    AuditLog,
    Capsule,
    ChatMessage,
    ChatMessageFavorite,
    ChatPinnedQuote,
    CheckIn,
    Comment,
    ContentVersion,
    CottagePlan,
    CottageReminder,
    Coupon,
    DailyQuestion,
    DailyQuestionAnswer,
    Event,
    FcmDeviceToken,
    GameMatch,
    HealthSnapshot,
    LedgerEntry,
    ListenHistoryEntry,
    Message,
    Moment,
    MoodCheckin,
    MoodIdempotencyRecord,
    Notification,
    PeriodCycle,
    SiteSetting,
    UploadReference,
    User,
    VaultEntry,
    VaultMeta,
    WatchSource,
    Wish,
)
from app.models.user import UserRole
from app.services.notification_delivery import fcm_runtime_ready, web_push_runtime_ready
from app.services.content_access import has_content_access
from app.services.upload_references import can_access_upload_reference, rebuild_upload_references


logger = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[1]
UPLOADS_ROOT = BACKEND_ROOT / "uploads"
ALBUMS_UPLOAD_ROOT = UPLOADS_ROOT / "albums"
ARTICLES_UPLOAD_ROOT = UPLOADS_ROOT / "articles"
AVATARS_UPLOAD_ROOT = UPLOADS_ROOT / "avatars"
TIMELINE_UPLOAD_ROOT = UPLOADS_ROOT / "timeline"
VIDEOS_UPLOAD_ROOT = UPLOADS_ROOT / "videos"


def _run_migrations() -> None:
    """Apply all pending Alembic migrations at startup.

    Falls back to ``Base.metadata.create_all`` when the engine is SQLite
    (local dev mode without PostgreSQL) because Alembic's autogenerate
    migrations target PostgreSQL dialect features.
    """
    db_url: str = str(engine.url)
    if db_url.startswith("sqlite"):
        # Dev / offline fallback: SQLite doesn't need migration scripts.
        logger.info("SQLite engine detected – using create_all instead of Alembic.")
        _ = (
            User,
            Moment,
            Comment,
            Event,
            Article,
            ArticleBlock,
            AuditLog,
            ContentVersion,
            CottagePlan,
            CottageReminder,
            DailyQuestion,
            DailyQuestionAnswer,
            FcmDeviceToken,
            Notification,
            Album,
            AlbumMedia,
            Message,
            Capsule,
            SiteSetting,
            UploadReference,
            WatchSource,
            ChatMessage,
            ChatMessageFavorite,
            ChatPinnedQuote,
            MoodCheckin,
            MoodIdempotencyRecord,
            CheckIn,
            Wish,
            GameMatch,
            ListenHistoryEntry,
            Coupon,
            LedgerEntry,
            PeriodCycle,
            VaultMeta,
            VaultEntry,
            HealthSnapshot,
        )
        Base.metadata.create_all(bind=engine)
        return

    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig

        alembic_cfg = AlembicConfig(str(BACKEND_ROOT / "alembic.ini"))
        # Override script_location to an absolute path so it works regardless
        # of the current working directory (e.g. inside Docker).
        alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
        alembic_cfg.set_main_option(
            "sqlalchemy.url", settings.resolved_database_url.replace("%", "%%")
        )
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied successfully.")
    except Exception:
        logger.exception("Alembic migration failed; refusing to start with an unknown schema state.")
        raise


def _ensure_sqlite_compatibility() -> None:
    db_url: str = str(engine.url)
    if not db_url.startswith("sqlite"):
        return

    # Security: Whitelist of allowed table names to prevent SQL injection
    allowed_tables = frozenset({
        "comments", "events", "moments", "articles", "albums",
        "messages", "site_settings", "users", "capsules", "notifications",
        "audit_logs", "content_versions", "upload_references", "album_media",
        "daily_questions", "daily_question_answers", "cottage_plans", "cottage_reminders",
        "checkins", "wishes", "chat_messages", "mood_checkins", "watch_sources",
        "game_matches", "listen_history", "coupons", "ledger_entries", "period_cycles",
        "chat_message_favorites", "chat_pinned_quotes", "chat_keys",
    })

    def _validate_table_name(table_name: str) -> None:
        """Validate table name against whitelist to prevent SQL injection."""
        if table_name not in allowed_tables:
            raise ValueError(f"Invalid table name: {table_name}. Not in whitelist.")

    def _table_columns(connection, table_name: str) -> set[str]:
        _validate_table_name(table_name)
        # Safe to use f-string here because table_name is validated against whitelist
        return {
            row[1]
            for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
        }

    with engine.begin() as connection:
        comment_columns = _table_columns(connection, "comments")

        if comment_columns and "parent_id" not in comment_columns:
            connection.execute(text("ALTER TABLE comments ADD COLUMN parent_id INTEGER"))
            logger.info("Added SQLite compatibility column comments.parent_id")

        if comment_columns and "mention_uids_json" not in comment_columns:
            connection.execute(text("ALTER TABLE comments ADD COLUMN mention_uids_json TEXT"))
            logger.info("Added SQLite compatibility column comments.mention_uids_json")

        message_columns = _table_columns(connection, "messages")
        if message_columns and "client_idempotency_key" not in message_columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN client_idempotency_key VARCHAR(128)"))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_message_author_idempotency "
                "ON messages(author_id, client_idempotency_key)"
            ))

        event_columns = _table_columns(connection, "events")
        if event_columns and "visibility" not in event_columns:
            connection.execute(text("ALTER TABLE events ADD COLUMN visibility VARCHAR(32) DEFAULT 'public' NOT NULL"))
            logger.info("Added SQLite compatibility column events.visibility")

        moment_columns = _table_columns(connection, "moments")
        if moment_columns and "visibility" not in moment_columns:
            connection.execute(text("ALTER TABLE moments ADD COLUMN visibility VARCHAR(32) DEFAULT 'public' NOT NULL"))
            logger.info("Added SQLite compatibility column moments.visibility")
        if moment_columns and "audio_url" not in moment_columns:
            connection.execute(text("ALTER TABLE moments ADD COLUMN audio_url VARCHAR(512)"))
            logger.info("Added SQLite compatibility column moments.audio_url")
        if moment_columns and "audio_duration_sec" not in moment_columns:
            connection.execute(text("ALTER TABLE moments ADD COLUMN audio_duration_sec INTEGER"))
            logger.info("Added SQLite compatibility column moments.audio_duration_sec")

        article_columns = _table_columns(connection, "articles")
        if article_columns and "visibility" not in article_columns:
            connection.execute(text("ALTER TABLE articles ADD COLUMN visibility VARCHAR(32)"))
            logger.info("Added SQLite compatibility column articles.visibility")
            article_columns = _table_columns(connection, "articles")

        if article_columns and "password_hash" not in article_columns:
            connection.execute(text("ALTER TABLE articles ADD COLUMN password_hash VARCHAR(255)"))
            logger.info("Added SQLite compatibility column articles.password_hash")

        if article_columns and "visibility" in article_columns:
            connection.execute(
                text(
                    """
                    UPDATE articles
                    SET visibility = CASE
                        WHEN is_encrypted = 1 THEN 'partners_only'
                        WHEN status = 'Published' AND is_encrypted = 0 THEN 'public'
                        ELSE 'private'
                    END
                    WHERE visibility IS NULL
                    """
                )
            )

        album_columns = _table_columns(connection, "albums")
        if album_columns and "visibility" not in album_columns:
            connection.execute(text("ALTER TABLE albums ADD COLUMN visibility VARCHAR(32)"))
            logger.info("Added SQLite compatibility column albums.visibility")
            album_columns = _table_columns(connection, "albums")

        if album_columns and "password_hash" not in album_columns:
            connection.execute(text("ALTER TABLE albums ADD COLUMN password_hash VARCHAR(255)"))
            logger.info("Added SQLite compatibility column albums.password_hash")

        if album_columns and "visibility" in album_columns:
            connection.execute(
                text(
                    """
                    UPDATE albums
                    SET visibility = CASE
                        WHEN is_encrypted = 1 THEN 'partners_only'
                        WHEN is_public = 1 AND is_encrypted = 0 THEN 'public'
                        ELSE 'private'
                    END
                    WHERE visibility IS NULL
                    """
                )
            )

        capsule_columns = _table_columns(connection, "capsules")
        if capsule_columns and "media_url" not in capsule_columns:
            connection.execute(text("ALTER TABLE capsules ADD COLUMN media_url VARCHAR(512)"))
            logger.info("Added SQLite compatibility column capsules.media_url")
        if capsule_columns and "media_type" not in capsule_columns:
            connection.execute(text("ALTER TABLE capsules ADD COLUMN media_type VARCHAR(16)"))
            logger.info("Added SQLite compatibility column capsules.media_type")
        if capsule_columns and "media_duration_sec" not in capsule_columns:
            connection.execute(text("ALTER TABLE capsules ADD COLUMN media_duration_sec INTEGER"))
            logger.info("Added SQLite compatibility column capsules.media_duration_sec")

        notification_columns = _table_columns(connection, "notifications")
        if notification_columns and "delivery_status" not in notification_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications ADD COLUMN delivery_status "
                    "VARCHAR(24) DEFAULT 'not_queued' NOT NULL"
                )
            )
            logger.info("Added SQLite compatibility column notifications.delivery_status")
            notification_columns = _table_columns(connection, "notifications")
        if notification_columns and "delivery_attempts" not in notification_columns:
            connection.execute(
                text(
                    "ALTER TABLE notifications ADD COLUMN delivery_attempts "
                    "INTEGER DEFAULT 0 NOT NULL"
                )
            )
            logger.info("Added SQLite compatibility column notifications.delivery_attempts")
        if notification_columns and "delivery_last_error" not in notification_columns:
            connection.execute(text("ALTER TABLE notifications ADD COLUMN delivery_last_error TEXT"))
            logger.info("Added SQLite compatibility column notifications.delivery_last_error")
        if notification_columns and "delivery_last_attempt_at" not in notification_columns:
            connection.execute(
                text("ALTER TABLE notifications ADD COLUMN delivery_last_attempt_at DATETIME")
            )
            logger.info("Added SQLite compatibility column notifications.delivery_last_attempt_at")
        if notification_columns and "delivery_completed_at" not in notification_columns:
            connection.execute(
                text("ALTER TABLE notifications ADD COLUMN delivery_completed_at DATETIME")
            )
            logger.info("Added SQLite compatibility column notifications.delivery_completed_at")

        chat_message_columns = _table_columns(connection, "chat_messages")
        if chat_message_columns and "visible_at" not in chat_message_columns:
            connection.execute(text("ALTER TABLE chat_messages ADD COLUMN visible_at DATETIME"))
            logger.info("Added SQLite compatibility column chat_messages.visible_at")
            connection.execute(text("UPDATE chat_messages SET visible_at = created_at WHERE visible_at IS NULL"))
            chat_message_columns = _table_columns(connection, "chat_messages")
        if chat_message_columns and "released_at" not in chat_message_columns:
            connection.execute(text("ALTER TABLE chat_messages ADD COLUMN released_at DATETIME"))
            logger.info("Added SQLite compatibility column chat_messages.released_at")
            connection.execute(text("UPDATE chat_messages SET released_at = created_at WHERE released_at IS NULL"))

        setting_columns = _table_columns(connection, "site_settings")
        if setting_columns and "timeline_path" not in setting_columns:
            connection.execute(
                text(
                    "ALTER TABLE site_settings ADD COLUMN timeline_path "
                    "VARCHAR(255) DEFAULT 'uploads/timeline' NOT NULL"
                )
            )
            logger.info("Added SQLite compatibility column site_settings.timeline_path")

        if setting_columns and "videos_path" not in setting_columns:
            connection.execute(
                text("ALTER TABLE site_settings ADD COLUMN videos_path VARCHAR(255) DEFAULT 'uploads/videos' NOT NULL")
            )
            logger.info("Added SQLite compatibility column site_settings.videos_path")

        if setting_columns and "allow_registration" not in setting_columns:
            connection.execute(
                text("ALTER TABLE site_settings ADD COLUMN allow_registration BOOLEAN DEFAULT 0 NOT NULL")
            )
            logger.info("Added SQLite compatibility column site_settings.allow_registration")

        if setting_columns and "max_image_kb" not in setting_columns:
            connection.execute(text("ALTER TABLE site_settings ADD COLUMN max_image_kb INTEGER DEFAULT 1024 NOT NULL"))
            logger.info("Added SQLite compatibility column site_settings.max_image_kb")

        if setting_columns and "thumb_width" not in setting_columns:
            connection.execute(text("ALTER TABLE site_settings ADD COLUMN thumb_width INTEGER DEFAULT 400 NOT NULL"))
            logger.info("Added SQLite compatibility column site_settings.thumb_width")

        if setting_columns and "compress_quality" not in setting_columns:
            connection.execute(
                text("ALTER TABLE site_settings ADD COLUMN compress_quality INTEGER DEFAULT 82 NOT NULL")
            )
            logger.info("Added SQLite compatibility column site_settings.compress_quality")

        if setting_columns and "strip_exif" not in setting_columns:
            connection.execute(text("ALTER TABLE site_settings ADD COLUMN strip_exif BOOLEAN DEFAULT 1 NOT NULL"))
            logger.info("Added SQLite compatibility column site_settings.strip_exif")

        if setting_columns and "allowed_image_types" not in setting_columns:
            connection.execute(
                text(
                    "ALTER TABLE site_settings ADD COLUMN allowed_image_types VARCHAR(512) "
                    "DEFAULT 'image/jpeg,image/png,image/webp,image/gif' NOT NULL"
                )
            )
            logger.info("Added SQLite compatibility column site_settings.allowed_image_types")

        if setting_columns and "partner_a_avatar" not in setting_columns:
            connection.execute(text("ALTER TABLE site_settings ADD COLUMN partner_a_avatar VARCHAR(255)"))
            logger.info("Added SQLite compatibility column site_settings.partner_a_avatar")

        if setting_columns and "partner_b_avatar" not in setting_columns:
            connection.execute(text("ALTER TABLE site_settings ADD COLUMN partner_b_avatar VARCHAR(255)"))
            logger.info("Added SQLite compatibility column site_settings.partner_b_avatar")

        for table_name in ("articles", "albums", "events", "moments", "messages"):
            table_columns = _table_columns(connection, table_name)
            if table_columns and "tags" not in table_columns:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN tags JSON DEFAULT '[]' NOT NULL"))
                logger.info("Added SQLite compatibility column %s.tags", table_name)

        for table_name in ("articles", "events", "messages"):
            table_columns = _table_columns(connection, table_name)
            if table_columns and "version" not in table_columns:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN version INTEGER DEFAULT 1 NOT NULL"))
                logger.info("Added SQLite compatibility column %s.version", table_name)

        # Idempotency-Key columns + unique indexes (added in 2026-07 batch).
        # The unique indexes are NOT enforced retroactively on existing SQLite
        # tables when adding a column, but they will guard every fresh insert;
        # the route layer also catches IntegrityError and re-fetches the row.
        idempotency_tables = (
            ("chat_messages", "sender_id", "uq_chat_message_sender_idempotency"),
            ("moments", "author_id", "uq_moment_author_idempotency"),
            ("checkins", "author_id", "uq_checkin_author_idempotency"),
            ("wishes", "author_id", "uq_wish_author_idempotency"),
            ("messages", "author_id", "uq_message_author_idempotency"),
        )
        for table_name, owner_column, index_name in idempotency_tables:
            table_columns = _table_columns(connection, table_name)
            if table_columns and "client_idempotency_key" not in table_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} ADD COLUMN client_idempotency_key VARCHAR(128)"
                    )
                )
                logger.info(
                    "Added SQLite compatibility column %s.client_idempotency_key",
                    table_name,
                )
                connection.execute(
                    text(
                        f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
                        f"ON {table_name}({owner_column}, client_idempotency_key) "
                        f"WHERE client_idempotency_key IS NOT NULL"
                    )
                )

        # Watch progress fields (added 2026-07).
        watch_columns = _table_columns(connection, "watch_sources")
        if watch_columns and "last_position_ms" not in watch_columns:
            connection.execute(text("ALTER TABLE watch_sources ADD COLUMN last_position_ms BIGINT DEFAULT 0 NOT NULL"))
            connection.execute(text("ALTER TABLE watch_sources ADD COLUMN last_viewed_at DATETIME"))
            connection.execute(text("ALTER TABLE watch_sources ADD COLUMN bookmarks_json TEXT DEFAULT '[]' NOT NULL"))
            logger.info(
                "Added SQLite compatibility columns watch_sources.{last_position_ms,last_viewed_at,bookmarks_json}")

        # E2EE chat fields (added 2026-07).
        chat_msg_columns = _table_columns(connection, "chat_messages")
        if chat_msg_columns and "is_encrypted" not in chat_msg_columns:
            connection.execute(
                text("ALTER TABLE chat_messages ADD COLUMN is_encrypted BOOLEAN DEFAULT 0 NOT NULL")
            )
            connection.execute(text("ALTER TABLE chat_messages ADD COLUMN iv VARCHAR(64)"))
            connection.execute(text("ALTER TABLE chat_messages ADD COLUMN ciphertext TEXT"))
            connection.execute(text("ALTER TABLE chat_messages ADD COLUMN algo VARCHAR(16)"))
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_chat_messages_is_encrypted ON chat_messages(is_encrypted)")
            )
            logger.info("Added SQLite compatibility columns chat_messages.{is_encrypted,iv,ciphertext,algo}")

        # chat_keys table for per-user E2E KDF metadata.
        chat_keys_cols = _table_columns(connection, "chat_keys")
        if not chat_keys_cols:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS chat_keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL UNIQUE,
                        salt VARCHAR(128) NOT NULL,
                        kdf VARCHAR(32) NOT NULL DEFAULT 'PBKDF2',
                        kdf_hash VARCHAR(32) NOT NULL DEFAULT 'SHA-256',
                        iterations INTEGER NOT NULL DEFAULT 210000,
                        algo VARCHAR(32) NOT NULL DEFAULT 'AES-GCM',
                        verifier_iv VARCHAR(64) NOT NULL,
                        verifier_cipher VARCHAR(512) NOT NULL,
                        verifier_hash VARCHAR(128) NOT NULL,
                        needs_re_encrypt BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    )
                    """
                )
            )
            connection.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_keys_user ON chat_keys(user_id)")
            )
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_keys_id ON chat_keys(id)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chat_keys_user_id ON chat_keys(user_id)"))


def _seed_partners() -> None:
    db = SessionLocal()
    try:
        partner_a = db.query(User).filter(User.role == UserRole.partner_a, User.deleted_at.is_(None)).first()
        if partner_a is None:
            partner_a = User(
                username="admin",
                nickname="Admin",
                role=UserRole.partner_a,
                password_hash=get_password_hash("admin"),
            )
            db.add(partner_a)
            logger.warning(
                "Seeded INSECURE default Partner A (admin/admin) for development. "
                "Never expose this environment publicly; change the password immediately."
            )

        partner_b = db.query(User).filter(User.role == UserRole.partner_b, User.deleted_at.is_(None)).first()
        if partner_b is None:
            partner_b = User(
                username="partner",
                nickname="Partner",
                role=UserRole.partner_b,
                password_hash=get_password_hash("partner"),
            )
            db.add(partner_b)
            logger.warning(
                "Seeded INSECURE default Partner B (partner/partner) for development. "
                "Never expose this environment publicly; change the password immediately."
            )

        db.commit()
    finally:
        db.close()


def _should_seed_default_partners() -> bool:
    # Single source of truth: never seed insecure default accounts in a
    # production-like environment (R-sev-3).
    return not settings.is_production_like


def _has_default_credential_partner() -> bool:
    """True if any partner account still uses a seeded default password.

    Guards against a dev seed (admin/admin, partner/partner) lingering in a
    production-like deployment, which would be a trivial account takeover.
    """
    from app.core.security import verify_password

    db = SessionLocal()
    try:
        for username, password in (("admin", "admin"), ("partner", "partner")):
            user = (
                db.query(User)
                .filter(User.username == username, User.deleted_at.is_(None))
                .first()
            )
            if user is not None and verify_password(password, user.password_hash):
                return True
        return False
    finally:
        db.close()


def _startup_self_check() -> None:
    db = SessionLocal()
    try:
        partner_count = (
            db.query(User)
            .filter(User.role.in_([UserRole.partner_a, UserRole.partner_b]), User.deleted_at.is_(None))
            .count()
        )
    finally:
        db.close()

    validate_startup_configuration(
        app_env=settings.app_env,
        partner_count=partner_count,
        bootstrap_setup_token=settings.bootstrap_setup_token,
        jwt_secret_key=settings.jwt_secret_key,
        cookie_vault_key=settings.cookie_vault_key,
    )

    if settings.web_push_enabled:
        if not settings.web_push_configured:
            raise RuntimeError(
                "Startup self-check failed: WEB_PUSH_ENABLED is true but VAPID keys or "
                "WEB_PUSH_SUBJECT are missing. Set WEB_PUSH_VAPID_PUBLIC_KEY, "
                "WEB_PUSH_VAPID_PRIVATE_KEY, and WEB_PUSH_SUBJECT."
            )
        if not web_push_runtime_ready():
            raise RuntimeError(
                "Startup self-check failed: Web Push is enabled but runtime support is "
                "not ready. Ensure pywebpush is installed and configuration is valid."
            )

    if settings.fcm_push_enabled:
        if not settings.fcm_configured:
            raise RuntimeError(
                "Startup self-check failed: FCM_PUSH_ENABLED is true but FCM service "
                "account configuration is missing. Set FCM_SERVICE_ACCOUNT_FILE or "
                "FCM_SERVICE_ACCOUNT_JSON."
            )
        if not fcm_runtime_ready():
            raise RuntimeError(
                "Startup self-check failed: FCM Push is enabled but runtime support is "
                "not ready. Ensure firebase-admin is installed and credentials are valid."
            )

    if settings.is_production_like and _has_default_credential_partner():
        raise RuntimeError(
            "Startup self-check failed: a default-credential account (admin/admin or "
            "partner/partner) exists in a production-like environment. Change its password "
            "or remove it before serving."
        )

    validate_schema_contracts()


def _seed_settings() -> None:
    db = SessionLocal()
    try:
        setting = db.query(SiteSetting).filter(SiteSetting.id == 1).first()
        if setting is None:
            setting = SiteSetting(id=1, site_name="恋爱记")
            db.add(setting)
            db.commit()
            logger.info("Seeded default SiteSettings.")
    finally:
        db.close()


def _ensure_upload_dirs() -> None:
    for path in (
        UPLOADS_ROOT,
        ALBUMS_UPLOAD_ROOT,
        ARTICLES_UPLOAD_ROOT,
        AVATARS_UPLOAD_ROOT,
        TIMELINE_UPLOAD_ROOT,
        VIDEOS_UPLOAD_ROOT,
    ):
        path.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    _run_migrations()
    # Safety net for dev/SQLite or pre-migration DBs; Alembic 20260620_1100
    # is the canonical creator on PostgreSQL.
    from sqlalchemy import inspect as sa_inspect

    if "upload_references" not in sa_inspect(engine).get_table_names():
        if str(engine.url).startswith("sqlite"):
            Base.metadata.create_all(bind=engine, tables=[UploadReference.__table__])
        else:
            raise RuntimeError(
                "Required upload_references table is missing after Alembic migrations"
            )
    _ensure_sqlite_compatibility()
    if _should_seed_default_partners():
        _seed_partners()
    else:
        logger.info("Skipping default partner seed in non-development environment.")
    _seed_settings()
    db = SessionLocal()
    try:
        rebuild_upload_references(db)
        db.commit()
    finally:
        db.close()
    _startup_self_check()

    # Capture the running loop so synchronous REST handlers can push frames
    # to cottage WebSocket clients (chat / presence / poke) cross-thread.
    from app.services.cottage_realtime import set_event_loop
    from app.services.health_monitor import health_monitor_loop
    from app.services.listen_together.auto_pause import auto_pause_loop
    from app.services.notification_scheduler import notification_scheduler_loop

    set_event_loop(asyncio.get_running_loop())

    async def auto_backup_loop() -> None:
        while True:
            try:
                from app.api.v1.export import run_scheduled_backup_if_due

                db = SessionLocal()
                try:
                    run_scheduled_backup_if_due(db)
                finally:
                    db.close()
            except Exception:
                logger.exception("Auto backup scheduler tick failed.")
            await asyncio.sleep(300)

    async def memory_push_loop() -> None:
        # "回到那一天"回忆推送：每天生成一次（date_key 幂等），失败仅记录不影响其他任务。
        while True:
            try:
                from datetime import date as _date

                from app.services.memories import run_memory_push_tick

                db = SessionLocal()
                try:
                    created = await asyncio.to_thread(
                        run_memory_push_tick, db, today=_date.today()
                    )
                    if created:
                        logger.info("Memory push created %d notification(s).", created)
                finally:
                    db.close()
            except Exception:
                logger.exception("Memory push scheduler tick failed.")
            # 每 6 小时检查一次；date_key 去重保证每天只发一次。
            await asyncio.sleep(6 * 3600)

    background_tasks = [
        asyncio.create_task(auto_backup_loop(), name="auto-backup-scheduler"),
        asyncio.create_task(
            notification_scheduler_loop(
                interval_seconds=settings.notification_scheduler_interval_seconds,
                days_ahead=settings.notification_scheduler_days_ahead,
            ),
            name="notification-scheduler",
        ),
        asyncio.create_task(memory_push_loop(), name="memory-push-scheduler"),
        asyncio.create_task(auto_pause_loop(), name="listen-auto-pause"),
        asyncio.create_task(health_monitor_loop(), name="health-monitor"),
    ]
    logger.info(
        "Started notification scheduler (interval=%ss, days_ahead=%s)",
        settings.notification_scheduler_interval_seconds,
        settings.notification_scheduler_days_ahead,
    )
    logger.info("Started listen-together auto-pause background task")
    logger.info("Started health monitor background task")

    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)


def create_app() -> FastAPI:
    # Hide the interactive API schema (Swagger / ReDoc / openapi.json) in
    # production so the full API surface isn't published to anonymous callers.
    docs_enabled = not settings.is_production_like
    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=_app_lifespan,
    )

    # Configure rate limiter: one shared instance drives both the global
    # SlowAPIMiddleware (default per-IP cap on every route) and the explicit
    # @limiter.limit decorators on sensitive routes.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    _ensure_upload_dirs()

    @app.get("/uploads/{file_path:path}")
    @limiter.exempt
    def serve_upload(request: Request, file_path: str, db: Session = Depends(get_db)):
        # Security: Enhanced path traversal protection
        # 1. Normalize path and strip leading slashes
        file_path = file_path.replace('\\', '/').strip('/')

        # 2. Check for path traversal attempts
        if '..' in file_path or file_path.startswith('/'):
            raise HTTPException(status_code=403, detail="Invalid path")

        # 3. Resolve the target path
        try:
            target_path = (UPLOADS_ROOT / file_path).resolve()
            # 4. Ensure resolved path is still under UPLOADS_ROOT
            target_path.relative_to(UPLOADS_ROOT)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Invalid path") from exc

        # 5. Ensure target is a file, not a directory
        if not target_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]

        user = None
        if token:
            try:
                payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
                uid = payload.get("sub")
                token_type = payload.get("type")
                if not uid or token_type != "access":
                    raise HTTPException(status_code=401, detail="Invalid token")

                user = db.query(User).filter(User.uid == uid, User.deleted_at.is_(None)).first()
                if not user:
                    raise HTTPException(status_code=401, detail="User not found")
                if user.role == UserRole.visitor and (
                    user.is_banned or user.permission_status == "banned"
                ):
                    raise HTTPException(status_code=401, detail="Account is banned")

                token_session_version = payload.get("session_version")
                if not check_session_version(user, token_session_version):
                    raise HTTPException(status_code=401, detail="Session revoked")
            except JWTError as exc:
                raise HTTPException(status_code=401, detail="Invalid token") from exc

        refs = (
            db.query(UploadReference)
            .filter(UploadReference.file_path == f"/uploads/{file_path.lstrip('/')}")
            .all()
        )
        authorized = False
        for ref in refs:
            content_access_granted = False
            capsule_open = None
            if ref.content_kind == "article":
                article = db.query(Article).filter(Article.id == ref.content_id).first()
                if article is not None:
                    content_access_granted = has_content_access(
                        request,
                        content_kind="article",
                        content_id=article.id,
                        password_hash=article.password_hash,
                    )
            elif ref.content_kind == "album":
                album = db.query(Album).filter(Album.id == ref.content_id).first()
                if album is not None:
                    content_access_granted = has_content_access(
                        request,
                        content_kind="album",
                        content_id=album.id,
                        password_hash=album.password_hash,
                    )
            elif ref.content_kind == "capsule":
                capsule = db.query(Capsule).filter(
                    Capsule.id == ref.content_id,
                    Capsule.deleted_at.is_(None),
                ).first()
                if capsule is not None:
                    open_at = capsule.open_at
                    if open_at.tzinfo is None:
                        open_at = open_at.replace(tzinfo=timezone.utc)
                    capsule_open = open_at <= datetime.now(timezone.utc)

            if can_access_upload_reference(
                ref,
                user,
                content_access_granted=content_access_granted,
                capsule_open=capsule_open,
            ):
                authorized = True
                break

        if not refs or not authorized:
            if user is None:
                raise HTTPException(status_code=401, detail="Authentication required to access media")
            raise HTTPException(status_code=403, detail="No permission to access media")

        return FileResponse(path=target_path)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security: Add security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS only in production with HTTPS
        if settings.is_production_like:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # unsafe-eval needed for Vue dev
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            # 'self' covers uploaded videos under /uploads; https: + blob: allow
            # the cottage 一起看 feature to play external direct links (.mp4 /
            # .m3u8) and future MSE/HLS blob sources.
            "media-src 'self' https: blob:",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response

    # Security: Global exception handler for production
    if settings.is_production_like:
        @app.exception_handler(Exception)
        async def generic_exception_handler(request: Request, exc: Exception):
            # Log the full error for debugging
            logger.error(f"Unhandled exception: {exc}", exc_info=True)
            # Return generic error to client
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )

    app.include_router(api_router)
    return app


app = create_app()
