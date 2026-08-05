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
Export / Backup / Restore API
==============================
Endpoints
---------
GET  /v1/export/all              – create + stream a full backup ZIP
GET  /v1/export/history          – list of past backup downloads
GET  /v1/export/preflight        – preview current data counts (no file created)
POST /v1/export/restore          – upload a backup ZIP, preflight-check, then restore
"""

import json
import logging
import os
import secrets
import shutil
import tempfile
import threading
import time
import uuid as _uuid_mod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session, joinedload
from starlette.background import BackgroundTask

from app.api.deps import ensure_partner, get_current_user
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.album import Album, AlbumMedia, MediaType
from app.models.article import Article, ArticleBlock, ArticleBlockType, ArticleStatus
from app.models.capsule import Capsule
from app.models.chat_key import ChatKey
from app.models.chat_message import ChatMessage
from app.models.chat_message_meta import ChatMessageFavorite, ChatPinnedQuote
from app.models.checkin import CheckIn
from app.models.comment import Comment, CommentTargetType
from app.models.content_version import ContentVersion
from app.models.content_visibility import ContentVisibility
from app.models.cottage_plan import CottagePlan
from app.models.cottage_reminder import CottageReminder
from app.models.daily_question import DailyQuestion, DailyQuestionAnswer
from app.models.event import Event, EventType
from app.models.event import Visibility as EventVisibility
from app.models.game_match import GameMatch
from app.models.coupon import Coupon
from app.models.fcm_device_token import FcmDeviceToken
from app.models.ledger_entry import LedgerEntry
from app.models.listen_history import ListenHistoryEntry
from app.models.listen_local_track import ListenLocalTrack
from app.models.message import Message
from app.models.moment import Moment
from app.models.moment import Visibility as MomentVisibility
from app.models.mood import MoodCheckin
from app.models.mood_idempotency import MoodIdempotencyRecord
from app.models.notification import Notification
from app.models.period_cycle import PeriodCycle
from app.models.push_subscription import PushSubscription
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole
from app.models.vault import VaultEntry, VaultMeta
from app.models.watch import WatchSource
from app.models.wish import Wish
from app.schemas.backup import AutoBackupRunResponse, BackupScheduleResponse, BackupScheduleUpdateRequest
from app.services.audit import write_audit_log
from app.services.notifications import notify_partners, partner_recipients
from app.services.upload_references import rebuild_upload_references

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[3]
UPLOADS_ROOT = BACKEND_ROOT / "uploads"
DEFAULT_BACKUP_DIR = "backups"

# Backup history is stored as a single JSON file on the server side.
# It is never included in the downloaded ZIP itself.
BACKUP_HISTORY_FILE = BACKEND_ROOT / DEFAULT_BACKUP_DIR / "backup_history.json"
BACKUP_SCHEDULE_FILE = BACKEND_ROOT / DEFAULT_BACKUP_DIR / "backup_schedule.json"
LEGACY_BACKUP_HISTORY_FILE = BACKEND_ROOT / "backup_history.json"
LEGACY_BACKUP_SCHEDULE_FILE = BACKEND_ROOT / "backup_schedule.json"

# Current schema version embedded in every backup manifest.
# v6 preserves E2EE chat envelopes and the shared public KDF metadata required
# to derive the chat key after a restore. Passphrases and derived keys remain
# excluded. Restores use public business keys/UIDs rather than database row IDs.
BACKUP_SCHEMA_VERSION = "v6"

# Maximum number of history entries to keep.
MAX_HISTORY_ENTRIES = 100

_HISTORY_THREAD_LOCK = threading.RLock()
_SCHEDULE_THREAD_LOCK = threading.RLock()
_BACKUP_RUN_THREAD_LOCK = threading.RLock()


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------

def _iso(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _safe_file_name(name: str) -> str:
    invalid = '<>:"/\\|?*\n\r\t'
    cleaned = "".join("_" if ch in invalid else ch for ch in (name or ""))
    cleaned = cleaned.strip(" .")
    return cleaned or "untitled"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def _interprocess_file_lock(lock_file: Path, thread_lock) -> Iterator[None]:
    """Serialize state mutations across request threads and worker processes."""
    with thread_lock:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        with lock_file.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()

            if os.name == "nt":
                import msvcrt

                while True:
                    try:
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        time.sleep(0.05)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

            try:
                yield
            finally:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _history_state_lock() -> Iterator[None]:
    lock_file = BACKUP_HISTORY_FILE.with_name(f".{BACKUP_HISTORY_FILE.name}.lock")
    with _interprocess_file_lock(lock_file, _HISTORY_THREAD_LOCK):
        yield


@contextmanager
def _schedule_state_lock() -> Iterator[None]:
    lock_file = BACKUP_SCHEDULE_FILE.with_name(f".{BACKUP_SCHEDULE_FILE.name}.lock")
    with _interprocess_file_lock(lock_file, _SCHEDULE_THREAD_LOCK):
        yield


@contextmanager
def _persistent_backup_run_lock() -> Iterator[None]:
    lock_file = BACKUP_SCHEDULE_FILE.with_name(".backup-run.lock")
    with _interprocess_file_lock(lock_file, _BACKUP_RUN_THREAD_LOCK):
        yield


def _atomic_write_json(path: Path, value: Any) -> None:
    """Replace a JSON state file atomically so readers never see a partial write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Backup history helpers
# ---------------------------------------------------------------------------

def _runtime_state_file(primary: Path, legacy: Path) -> Path:
    """Prefer persisted backup storage and import an older root-level file."""
    if primary.is_file():
        return primary
    if legacy.is_file():
        try:
            primary.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, primary)
            return primary
        except OSError:
            logger.warning("Failed to migrate legacy backup state file %s", legacy, exc_info=True)
            return legacy
    return primary


def _load_history_unlocked() -> list[dict]:
    history_file = _runtime_state_file(BACKUP_HISTORY_FILE, LEGACY_BACKUP_HISTORY_FILE)
    if not history_file.is_file():
        return []
    try:
        records = json.loads(history_file.read_text(encoding="utf-8"))
        return records if isinstance(records, list) else []
    except Exception:
        return []


def _load_history() -> list[dict]:
    with _history_state_lock():
        return _load_history_unlocked()


def _save_history_unlocked(records: list[dict]) -> None:
    _atomic_write_json(BACKUP_HISTORY_FILE, records[-MAX_HISTORY_ENTRIES:])


def _save_history(records: list[dict]) -> None:
    with _history_state_lock():
        _save_history_unlocked(records)


def _append_history(record: dict) -> None:
    with _history_state_lock():
        records = _load_history_unlocked()
        records.append(record)
        _save_history_unlocked(records)


def _default_schedule() -> dict:
    now = _now_utc()
    return {
        "enabled": False,
        "interval_hours": 24,
        "keep_last": 7,
        "backup_dir": DEFAULT_BACKUP_DIR,
        "last_run_at": None,
        "next_run_at": None,
        "last_status": None,
        "last_error": None,
        "updated_at": now.isoformat(),
    }


def _load_schedule_unlocked() -> dict:
    config = _default_schedule()
    schedule_file = _runtime_state_file(BACKUP_SCHEDULE_FILE, LEGACY_BACKUP_SCHEDULE_FILE)
    if schedule_file.is_file():
        try:
            raw = json.loads(schedule_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                config.update(raw)
        except Exception:
            logger.warning("Failed to read backup schedule config", exc_info=True)
    if config.get("enabled") and not config.get("next_run_at"):
        config["next_run_at"] = (_now_utc() + timedelta(hours=int(config["interval_hours"]))).isoformat()
    return config


def _load_schedule() -> dict:
    with _schedule_state_lock():
        return _load_schedule_unlocked()


def _save_schedule_unlocked(config: dict) -> dict:
    config = dict(config)
    config["updated_at"] = _now_utc().isoformat()
    _atomic_write_json(BACKUP_SCHEDULE_FILE, config)
    return config


def _save_schedule(config: dict) -> dict:
    with _schedule_state_lock():
        return _save_schedule_unlocked(config)


def _update_schedule(mutator: Callable[[dict], None]) -> dict:
    """Apply a read-modify-write while preserving concurrent config changes."""
    with _schedule_state_lock():
        config = _load_schedule_unlocked()
        mutator(config)
        return _save_schedule_unlocked(config)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _backup_dir_from_config(config: dict) -> Path:
    raw = str(config.get("backup_dir") or DEFAULT_BACKUP_DIR).replace("\\", "/").strip("/")
    if not raw or ".." in raw.split("/"):
        raw = DEFAULT_BACKUP_DIR
    return (BACKEND_ROOT / raw).resolve()


def _schedule_to_response(config: dict) -> BackupScheduleResponse:
    return BackupScheduleResponse(
        enabled=bool(config.get("enabled", False)),
        interval_hours=int(config.get("interval_hours", 24)),
        keep_last=int(config.get("keep_last", 7)),
        backup_dir=str(config.get("backup_dir") or DEFAULT_BACKUP_DIR),
        last_run_at=_parse_dt(config.get("last_run_at")),
        next_run_at=_parse_dt(config.get("next_run_at")),
        last_status=config.get("last_status"),
        last_error=config.get("last_error"),
        updated_at=_parse_dt(config.get("updated_at")),
    )


def _prune_auto_backups(config: dict) -> None:
    keep_last = int(config.get("keep_last") or 7)
    backup_dir = _backup_dir_from_config(config)
    if not backup_dir.exists():
        return
    files = sorted(
        backup_dir.glob("love-auto-backup-*.zip"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for stale in files[keep_last:]:
        try:
            stale.unlink()
        except Exception:
            logger.warning("Failed to prune stale auto backup %s", stale, exc_info=True)


def _find_auto_backup_operator(db: Session) -> User | None:
    partners = partner_recipients(db)
    return partners[0] if partners else None


# ---------------------------------------------------------------------------
# Data-gathering helpers
# ---------------------------------------------------------------------------

def _load_all_data(db: Session) -> dict[str, Any]:
    setting = db.query(SiteSetting).filter(SiteSetting.id == 1).first()
    users = db.query(User).all()
    articles = (
        db.query(Article)
        .options(
            joinedload(Article.author),
            joinedload(Article.blocks).joinedload(ArticleBlock.author),
        )
        .all()
    )
    albums = (
        db.query(Album)
        .options(joinedload(Album.author), joinedload(Album.media_items))
        .all()
    )
    events = db.query(Event).options(joinedload(Event.creator)).all()
    moments = (
        db.query(Moment)
        .options(
            joinedload(Moment.author),
            joinedload(Moment.comments).joinedload(Comment.author),
            joinedload(Moment.comments).joinedload(Comment.parent),
        )
        .all()
    )
    messages = db.query(Message).options(joinedload(Message.author)).all()
    capsules = db.query(Capsule).options(joinedload(Capsule.author)).all()
    versions = db.query(ContentVersion).options(joinedload(ContentVersion.actor)).all()
    notifications = db.query(Notification).all()
    checkins = db.query(CheckIn).options(joinedload(CheckIn.author)).all()
    wishes = (
        db.query(Wish)
        .options(joinedload(Wish.author), joinedload(Wish.completed_by))
        .all()
    )
    chat_messages = db.query(ChatMessage).options(joinedload(ChatMessage.sender)).all()
    chat_key = db.query(ChatKey).options(joinedload(ChatKey.user)).order_by(ChatKey.id.asc()).first()
    chat_favorites = (
        db.query(ChatMessageFavorite)
        .options(joinedload(ChatMessageFavorite.user), joinedload(ChatMessageFavorite.message))
        .all()
    )
    chat_pinned_quotes = (
        db.query(ChatPinnedQuote)
        .options(joinedload(ChatPinnedQuote.user), joinedload(ChatPinnedQuote.message))
        .all()
    )
    mood_checkins = db.query(MoodCheckin).options(joinedload(MoodCheckin.author)).all()
    mood_idempotency_records = (
        db.query(MoodIdempotencyRecord)
        .options(joinedload(MoodIdempotencyRecord.user), joinedload(MoodIdempotencyRecord.mood))
        .all()
    )
    watch_sources = db.query(WatchSource).options(joinedload(WatchSource.author)).all()
    daily_questions = (
        db.query(DailyQuestion)
        .options(
            joinedload(DailyQuestion.author),
            joinedload(DailyQuestion.answers).joinedload(DailyQuestionAnswer.author),
        )
        .all()
    )
    cottage_plans = (
        db.query(CottagePlan)
        .options(joinedload(CottagePlan.author), joinedload(CottagePlan.completed_by))
        .all()
    )
    cottage_reminders = (
        db.query(CottageReminder)
        .options(joinedload(CottageReminder.author), joinedload(CottageReminder.done_by))
        .all()
    )
    game_matches = (
        db.query(GameMatch)
        .options(
            joinedload(GameMatch.black),
            joinedload(GameMatch.white),
            joinedload(GameMatch.winner),
        )
        .all()
    )
    listen_history = db.query(ListenHistoryEntry).all()
    coupons = db.query(Coupon).options(joinedload(Coupon.author), joinedload(Coupon.redeemed_by)).all()
    ledger_entries = (
        db.query(LedgerEntry)
        .options(joinedload(LedgerEntry.author), joinedload(LedgerEntry.payer))
        .all()
    )
    period_cycles = db.query(PeriodCycle).options(joinedload(PeriodCycle.author)).all()
    listen_local_tracks = db.query(ListenLocalTrack).all()
    push_subscriptions = db.query(PushSubscription).options(joinedload(PushSubscription.user)).all()
    fcm_device_tokens = db.query(FcmDeviceToken).options(joinedload(FcmDeviceToken.user)).all()
    # E2EE vault: opaque ciphertext only (no plaintext is ever stored), but it
    # must be backed up or a lost DB means the couple's encrypted notes are gone
    # forever. The passphrase is never part of the backup.
    vault_meta = db.query(VaultMeta).filter(VaultMeta.id == 1).first()
    vault_entries = (
        db.query(VaultEntry)
        .options(joinedload(VaultEntry.author))
        .filter(VaultEntry.deleted_at.is_(None))
        .all()
    )

    return dict(
        setting=setting,
        users=users,
        articles=articles,
        albums=albums,
        events=events,
        moments=moments,
        messages=messages,
        capsules=capsules,
        versions=versions,
        notifications=notifications,
        checkins=checkins,
        wishes=wishes,
        chat_messages=chat_messages,
        chat_key=chat_key,
        chat_favorites=chat_favorites,
        chat_pinned_quotes=chat_pinned_quotes,
        mood_checkins=mood_checkins,
        mood_idempotency_records=mood_idempotency_records,
        watch_sources=watch_sources,
        daily_questions=daily_questions,
        cottage_plans=cottage_plans,
        cottage_reminders=cottage_reminders,
        game_matches=game_matches,
        listen_history=listen_history,
        coupons=coupons,
        ledger_entries=ledger_entries,
        period_cycles=period_cycles,
        listen_local_tracks=listen_local_tracks,
        push_subscriptions=push_subscriptions,
        fcm_device_tokens=fcm_device_tokens,
        vault_meta=vault_meta,
        vault_entries=vault_entries,
    )


def _count_summary(data: dict) -> dict[str, int]:
    return {
        "users": sum(1 for u in data["users"] if u.deleted_at is None),
        "articles": sum(1 for a in data["articles"] if a.deleted_at is None),
        "albums": sum(1 for a in data["albums"] if a.deleted_at is None),
        "events": sum(1 for e in data["events"] if e.deleted_at is None),
        "moments": sum(1 for m in data["moments"] if m.deleted_at is None),
        "messages": sum(1 for m in data["messages"] if not m.is_deleted),
        "capsules": sum(1 for c in data["capsules"] if c.deleted_at is None),
        "versions": len(data.get("versions", [])),
        "notifications": len(data.get("notifications", [])),
        "checkins": sum(1 for c in data.get("checkins", []) if c.deleted_at is None),
        "wishes": sum(1 for w in data.get("wishes", []) if w.deleted_at is None),
        "chat_messages": sum(1 for m in data.get("chat_messages", []) if m.deleted_at is None),
        "chat_key": 1 if data.get("chat_key") is not None else 0,
        "mood_checkins": len(data.get("mood_checkins", [])),
        "mood_idempotency_records": len(data.get("mood_idempotency_records", [])),
        "watch_sources": sum(1 for w in data.get("watch_sources", []) if w.deleted_at is None),
        "daily_questions": sum(1 for q in data.get("daily_questions", []) if q.deleted_at is None),
        "cottage_plans": sum(1 for p in data.get("cottage_plans", []) if p.deleted_at is None),
        "cottage_reminders": sum(1 for r in data.get("cottage_reminders", []) if r.deleted_at is None),
        "game_matches": len(data.get("game_matches", [])),
        "listen_history": len(data.get("listen_history", [])),
        "coupons": sum(1 for item in data.get("coupons", []) if item.deleted_at is None),
        "ledger_entries": sum(1 for item in data.get("ledger_entries", []) if item.deleted_at is None),
        "period_cycles": sum(1 for item in data.get("period_cycles", []) if item.deleted_at is None),
        "listen_local_tracks": sum(1 for item in data.get("listen_local_tracks", []) if item.deleted_at is None),
        "push_subscriptions": len(data.get("push_subscriptions", [])),
        "fcm_device_tokens": len(data.get("fcm_device_tokens", [])),
        "chat_favorites": len(data.get("chat_favorites", [])),
        "chat_pinned_quotes": len(data.get("chat_pinned_quotes", [])),
        "vault_entries": sum(1 for e in data.get("vault_entries", []) if e.deleted_at is None),
    }


# ---------------------------------------------------------------------------
# Manifest builder
# ---------------------------------------------------------------------------

def _build_manifest(data: dict, backup_id: str, operator_uid: str) -> dict:
    counts = _count_summary(data)
    upload_size_bytes: int = 0
    if UPLOADS_ROOT.exists():
        upload_size_bytes = sum(
            f.stat().st_size for f in UPLOADS_ROOT.rglob("*") if f.is_file()
        )

    return {
        "backup_id": backup_id,
        "schema_version": BACKUP_SCHEMA_VERSION,
        "created_at": _now_utc().isoformat(),
        "operator_uid": operator_uid,
        "site_name": data["setting"].site_name if data["setting"] else None,
        "counts": counts,
        "uploads_size_bytes": upload_size_bytes,
    }


# ---------------------------------------------------------------------------
# JSON payload builder (full data dump)
# ---------------------------------------------------------------------------

def _build_json_payload(data: dict, manifest: dict) -> dict:
    setting = data["setting"]
    users = data["users"]
    articles = data["articles"]
    albums = data["albums"]
    events = data["events"]
    moments = data["moments"]
    messages = data["messages"]
    capsules = data["capsules"]
    versions = data.get("versions", [])
    notifications = data.get("notifications", [])
    checkins = data.get("checkins", [])
    wishes = data.get("wishes", [])
    chat_messages = data.get("chat_messages", [])
    chat_key = data.get("chat_key")
    chat_favorites = data.get("chat_favorites", [])
    chat_pinned_quotes = data.get("chat_pinned_quotes", [])
    mood_checkins = data.get("mood_checkins", [])
    mood_idempotency_records = data.get("mood_idempotency_records", [])
    watch_sources = data.get("watch_sources", [])
    daily_questions = data.get("daily_questions", [])
    cottage_plans = data.get("cottage_plans", [])
    cottage_reminders = data.get("cottage_reminders", [])
    game_matches = data.get("game_matches", [])
    listen_history = data.get("listen_history", [])
    coupons = data.get("coupons", [])
    ledger_entries = data.get("ledger_entries", [])
    period_cycles = data.get("period_cycles", [])
    listen_local_tracks = data.get("listen_local_tracks", [])
    push_subscriptions = data.get("push_subscriptions", [])
    fcm_device_tokens = data.get("fcm_device_tokens", [])
    vault_meta = data.get("vault_meta")
    vault_entries = data.get("vault_entries", [])

    return {
        "meta": {
            "exported_at": manifest["created_at"],
            "backup_id": manifest["backup_id"],
            "schema_version": manifest["schema_version"],
            "counts": manifest["counts"],
        },
        "setting": {
            "site_name": setting.site_name if setting else None,
            "love_start_date": _iso(setting.love_start_date) if setting else None,
            "uploads_root": setting.uploads_root if setting else None,
            "articles_path": setting.articles_path if setting else None,
            "albums_path": setting.albums_path if setting else None,
            "avatar_path": setting.avatar_path if setting else None,
            "timeline_path": setting.timeline_path if setting else None,
            "videos_path": setting.videos_path if setting else None,
        },
        "users": [
            {
                "uid": u.uid,
                "username": u.username,
                "nickname": u.nickname,
                "avatar": u.avatar,
                "role": u.role.value,
                "created_at": _iso(u.created_at),
            }
            for u in users
            if u.deleted_at is None
        ],
        "articles": [
            {
                "aid": a.aid,
                "title": a.title,
                "excerpt": a.excerpt,
                "status": a.status.value,
                "visibility": a.visibility.value if a.visibility else None,
                "password_hash": a.password_hash,
                "is_encrypted": a.is_encrypted,
                "is_co_created": a.is_co_created,
                "partner_can_edit": a.partner_can_edit,
                "tags": a.tags or [],
                "cover_url": a.cover_url,
                "author_uid": a.author.uid,
                "published_at": _iso(a.published_at),
                "created_at": _iso(a.created_at),
                "blocks": [
                    {
                        "bid": b.bid,
                        "block_type": b.block_type.value,
                        "content": b.content,
                        "sort_order": b.sort_order,
                        "author_uid": b.author.uid,
                    }
                    for b in sorted(a.blocks, key=lambda item: item.sort_order)
                ],
            }
            for a in articles
            if a.deleted_at is None
        ],
        "albums": [
            {
                "alb_id": a.alb_id,
                "title": a.title,
                "description": a.description,
                "cover_url": a.cover_url,
                "visibility": a.visibility.value if a.visibility else None,
                "password_hash": a.password_hash,
                "is_encrypted": a.is_encrypted,
                "is_public": a.is_public,
                "tags": a.tags or [],
                "author_uid": a.author.uid,
                "created_at": _iso(a.created_at),
                "media_items": [
                    {
                        "media_id": m.media_id,
                        "media_type": m.media_type.value,
                        "file_url": m.file_url,
                        "thumbnail_url": m.thumbnail_url,
                        "file_size": m.file_size,
                        "mime_type": m.mime_type,
                        "is_encrypted": m.is_encrypted,
                        "created_at": _iso(m.created_at),
                    }
                    for m in a.media_items
                ],
            }
            for a in albums
            if a.deleted_at is None
        ],
        "events": [
            {
                "eid": e.eid,
                "title": e.title,
                "date": _iso(e.date),
                "type": e.type.value,
                "is_important": e.is_important,
                "is_yearly_repeat": e.is_yearly_repeat,
                "visibility": e.visibility.value,
                "tags": e.tags or [],
                "creator_uid": e.creator.uid,
                "created_at": _iso(e.created_at),
            }
            for e in events
            if e.deleted_at is None
        ],
        "moments": [
            {
                "mid": m.mid,
                "author_uid": m.author.uid,
                "content": m.content,
                "media_urls": m.media_urls,
                "audio_url": m.audio_url,
                "audio_duration_sec": m.audio_duration_sec,
                "location": m.location,
                "visibility": m.visibility.value,
                "tags": m.tags or [],
                "timestamp": _iso(m.timestamp),
                "comments": [
                    {
                        "cid": c.cid,
                        "parent_cid": c.parent.cid if c.parent else None,
                        "author_uid": c.author.uid,
                        "content": c.content,
                        "mention_uids": c.mention_uids,
                        "created_at": _iso(c.created_at),
                    }
                    for c in m.comments
                    if c.deleted_at is None
                ],
            }
            for m in moments
            if m.deleted_at is None
        ],
        "messages": [
            {
                "msg_id": m.msg_id,
                "author_uid": m.author.uid if m.author else None,
                "visitor_name": m.visitor_name,
                "client_idempotency_key": m.client_idempotency_key,
                "content": m.content,
                "is_public": m.is_public,
                "tags": m.tags or [],
                "created_at": _iso(m.created_at),
            }
            for m in messages
            if not m.is_deleted
        ],
        "capsules": [
            {
                "uuid": c.uuid,
                "author_uid": c.author.uid,
                "content": c.content,
                "media_url": c.media_url,
                "media_type": c.media_type,
                "media_duration_sec": c.media_duration_sec,
                "open_at": _iso(c.open_at),
                "created_at": _iso(c.created_at),
            }
            for c in capsules
            if c.deleted_at is None
        ],
        "versions": [
            {
                "vid": v.vid,
                "content_type": v.content_type,
                "content_id": v.content_id,
                "version": v.version,
                "title": v.title,
                "snapshot": v.snapshot,
                "note": v.note,
                "actor_uid": v.actor.uid if v.actor else None,
                "created_at": _iso(v.created_at),
            }
            for v in versions
        ],
        "notifications": [
            {
                "nid": n.nid,
                "recipient_uid": n.recipient.uid if n.recipient else None,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "link": n.link,
                "source_type": n.source_type,
                "source_id": n.source_id,
                "is_read": n.is_read,
                "delivery_status": n.delivery_status,
                "delivery_attempts": n.delivery_attempts,
                "delivery_last_error": n.delivery_last_error,
                "delivery_last_attempt_at": _iso(n.delivery_last_attempt_at),
                "delivery_completed_at": _iso(n.delivery_completed_at),
                "created_at": _iso(n.created_at),
                "read_at": _iso(n.read_at),
            }
            for n in notifications
        ],
        "checkins": [
            {
                "cid": c.cid,
                "author_uid": c.author.uid,
                "content": c.content,
                "media_urls": c.media_urls or [],
                "location_text": c.location_text,
                "location_status": c.location_status,
                "location_provider": c.location_provider,
                "created_at": _iso(c.created_at),
                "updated_at": _iso(c.updated_at),
            }
            for c in checkins
            if c.deleted_at is None
        ],
        "wishes": [
            {
                "wid": w.wid,
                "author_uid": w.author.uid,
                "title": w.title,
                "description": w.description,
                "category": w.category,
                "status": w.status,
                "priority": w.priority,
                "target_date": _iso(w.target_date),
                "completed_at": _iso(w.completed_at),
                "completed_by_uid": w.completed_by.uid if w.completed_by else None,
                "created_at": _iso(w.created_at),
                "updated_at": _iso(w.updated_at),
            }
            for w in wishes
            if w.deleted_at is None
        ],
        "chat_messages": [
            {
                "mid": m.mid,
                "sender_uid": m.sender.uid,
                "type": m.type,
                # Fail closed: a row marked as E2EE must never leak stale
                # plaintext columns into an otherwise ciphertext-only backup.
                "content": None if m.is_encrypted else m.content,
                "media_url": None if m.is_encrypted else m.media_url,
                "is_encrypted": m.is_encrypted,
                "iv": m.iv,
                "ciphertext": m.ciphertext,
                "algo": m.algo,
                "audio_duration_sec": m.audio_duration_sec,
                "reply_to_mid": m.reply_to.mid if m.reply_to else None,
                "read_at": _iso(m.read_at),
                "visible_at": _iso(m.visible_at),
                "released_at": _iso(m.released_at),
                "recalled_at": _iso(m.recalled_at),
                "created_at": _iso(m.created_at),
            }
            for m in chat_messages
            if m.deleted_at is None
        ],
        # Shared E2EE chat KDF metadata. This is sufficient for clients to
        # re-derive the key after restore but never contains a passphrase or key.
        "chat_key": (
            {
                "creator_uid": chat_key.user.uid if chat_key.user else None,
                "salt": chat_key.salt,
                "kdf": chat_key.kdf,
                "kdf_hash": chat_key.kdf_hash,
                "iterations": chat_key.iterations,
                "algo": chat_key.algo,
                "verifier_iv": chat_key.verifier_iv,
                "verifier_cipher": chat_key.verifier_cipher,
                "verifier_hash": chat_key.verifier_hash,
                "needs_re_encrypt": chat_key.needs_re_encrypt,
                "created_at": _iso(chat_key.created_at),
                "updated_at": _iso(chat_key.updated_at),
            }
            if chat_key
            else None
        ),
        "chat_favorites": [
            {
                "user_uid": item.user.uid,
                "message_mid": item.message.mid,
                "created_at": _iso(item.created_at),
            }
            for item in chat_favorites
            if item.user and item.message and item.message.deleted_at is None
        ],
        "chat_pinned_quotes": [
            {
                "user_uid": item.user.uid,
                "message_mid": item.message.mid,
                "created_at": _iso(item.created_at),
            }
            for item in chat_pinned_quotes
            if item.user and item.message and item.message.deleted_at is None
        ],
        "mood_checkins": [
            {
                "mid": m.mid,
                "author_uid": m.author.uid,
                "mood_date": _iso(m.mood_date),
                "mood": m.mood,
                "emoji": m.emoji,
                "note": m.note,
                "created_at": _iso(m.created_at),
                "updated_at": _iso(m.updated_at),
            }
            for m in mood_checkins
        ],
        "mood_idempotency_records": [
            {
                "user_uid": item.user.uid,
                "idempotency_key": item.idempotency_key,
                "payload_hash": item.payload_hash,
                "mood_mid": item.mood.mid,
                "created_at": _iso(item.created_at),
            }
            for item in mood_idempotency_records
            if item.user and item.mood
        ],
        "watch_sources": [
            {
                "wsid": w.wsid,
                "author_uid": w.author.uid,
                "title": w.title,
                "kind": w.kind,
                "url": w.url,
                "poster_url": w.poster_url,
                "size_bytes": w.size_bytes,
                "created_at": _iso(w.created_at),
                "updated_at": _iso(w.updated_at),
            }
            for w in watch_sources
            if w.deleted_at is None
        ],
        "daily_questions": [
            {
                "qid": q.qid,
                "author_uid": q.author.uid,
                "question_date": _iso(q.question_date),
                "prompt": q.prompt,
                "created_at": _iso(q.created_at),
                "updated_at": _iso(q.updated_at),
                "answers": [
                    {
                        "dqa_id": a.aid,
                        "author_uid": a.author.uid,
                        "content": a.content,
                        "created_at": _iso(a.created_at),
                        "updated_at": _iso(a.updated_at),
                    }
                    for a in q.answers
                ],
            }
            for q in daily_questions
            if q.deleted_at is None
        ],
        "cottage_plans": [
            {
                "pid": p.pid,
                "author_uid": p.author.uid,
                "title": p.title,
                "description": p.description,
                "location": p.location,
                "plan_date": _iso(p.plan_date),
                "status": p.status,
                "priority": p.priority,
                "checklist": p.checklist or [],
                "completed_at": _iso(p.completed_at),
                "completed_by_uid": p.completed_by.uid if p.completed_by else None,
                "created_at": _iso(p.created_at),
                "updated_at": _iso(p.updated_at),
            }
            for p in cottage_plans
            if p.deleted_at is None
        ],
        "cottage_reminders": [
            {
                "rid": r.rid,
                "author_uid": r.author.uid,
                "title": r.title,
                "note": r.note,
                "remind_at": _iso(r.remind_at),
                "audience": r.audience,
                "is_done": r.is_done,
                "done_at": _iso(r.done_at),
                "done_by_uid": r.done_by.uid if r.done_by else None,
                "last_notified_at": _iso(r.last_notified_at),
                "created_at": _iso(r.created_at),
                "updated_at": _iso(r.updated_at),
            }
            for r in cottage_reminders
            if r.deleted_at is None
        ],
        "game_matches": [
            {
                "gmid": m.gmid,
                "game_key": m.game_key,
                "black_uid": m.black.uid if m.black else None,
                "white_uid": m.white.uid if m.white else None,
                "winner_uid": m.winner.uid if m.winner else None,
                "is_draw": m.is_draw,
                "end_reason": m.end_reason,
                "move_count": m.move_count,
                "created_at": _iso(m.created_at),
            }
            for m in game_matches
        ],
        "listen_history": [
            {
                "hid": h.hid,
                "song_id": h.song_id,
                "name": h.name,
                "artists": h.artists,
                "album": h.album,
                "duration_ms": h.duration_ms,
                "cover_url": h.cover_url,
                "started_by_uid": h.started_by_uid,
                "played_at": _iso(h.played_at),
            }
            for h in listen_history
        ],
        "coupons": [
            {
                "cpid": item.cpid,
                "author_uid": item.author.uid,
                "title": item.title,
                "description": item.description,
                "icon": item.icon,
                "status": item.status,
                "redeemed_at": _iso(item.redeemed_at),
                "redeemed_by_uid": item.redeemed_by.uid if item.redeemed_by else None,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
                "version": item.version,
            }
            for item in coupons
            if item.deleted_at is None
        ],
        "ledger_entries": [
            {
                "leid": item.leid,
                "author_uid": item.author.uid,
                "payer_uid": item.payer.uid,
                "title": item.title,
                "note": item.note,
                "amount_cents": item.amount_cents,
                "category": item.category,
                "split_type": item.split_type,
                "spent_on": _iso(item.spent_on),
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
                "version": item.version,
            }
            for item in ledger_entries
            if item.deleted_at is None
        ],
        "period_cycles": [
            {
                "pcid": item.pcid,
                "author_uid": item.author.uid,
                "start_date": _iso(item.start_date),
                "end_date": _iso(item.end_date),
                "note": item.note,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
                "version": item.version,
            }
            for item in period_cycles
            if item.deleted_at is None
        ],
        "listen_local_tracks": [
            {
                "tid": item.tid,
                "name": item.name,
                "artists": item.artists,
                "album": item.album,
                "duration_ms": item.duration_ms,
                "cover_url": item.cover_url,
                "audio_url": item.audio_url,
                "uploaded_by_uid": item.uploaded_by_uid,
                "created_at": _iso(item.created_at),
            }
            for item in listen_local_tracks
            if item.deleted_at is None
        ],
        "push_subscriptions": [
            {
                "sid": item.sid,
                "user_uid": item.user.uid,
                "endpoint": item.endpoint,
                "p256dh": item.p256dh,
                "auth": item.auth,
                "expiration_time": item.expiration_time,
                "user_agent": item.user_agent,
                "is_active": item.is_active,
                "fail_count": item.fail_count,
                "last_seen_at": _iso(item.last_seen_at),
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in push_subscriptions
            if item.user
        ],
        "fcm_device_tokens": [
            {
                "tid": item.tid,
                "user_uid": item.user.uid,
                "token": item.token,
                "platform": item.platform,
                "device_name": item.device_name,
                "app_version": item.app_version,
                "is_active": item.is_active,
                "fail_count": item.fail_count,
                "last_seen_at": _iso(item.last_seen_at),
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in fcm_device_tokens
            if item.user
        ],
        # E2EE vault — opaque ciphertext + KDF params only (no passphrase/key).
        "vault_meta": (
            {
                "salt": vault_meta.salt,
                "kdf": vault_meta.kdf,
                "kdf_hash": vault_meta.kdf_hash,
                "iterations": vault_meta.iterations,
                "algo": vault_meta.algo,
                "verifier_iv": vault_meta.verifier_iv,
                "verifier_cipher": vault_meta.verifier_cipher,
                "created_at": _iso(vault_meta.created_at),
            }
            if vault_meta
            else None
        ),
        "vault_entries": [
            {
                "vid": e.vid,
                "author_uid": e.author.uid if e.author else None,
                "iv": e.iv,
                "ciphertext": e.ciphertext,
                "created_at": _iso(e.created_at),
                "updated_at": _iso(e.updated_at),
            }
            for e in vault_entries
            if e.deleted_at is None
        ],
    }


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def _append_comment_lines(
    lines: list[str],
    comment: Comment,
    comments_by_parent: dict,
    depth: int = 0,
) -> None:
    indent = "  " * depth
    lines.append(f"{indent}- {comment.author.nickname}: {comment.content}")
    for child in comments_by_parent.get(comment.id, []):
        _append_comment_lines(lines, child, comments_by_parent, depth + 1)


def _write_markdown_exports(
    target_dir: Path,
    articles: list[Article],
    moments: list[Moment],
) -> None:
    md_root = target_dir / "markdown"
    articles_dir = md_root / "articles"
    timeline_dir = md_root / "timeline"
    articles_dir.mkdir(parents=True, exist_ok=True)
    timeline_dir.mkdir(parents=True, exist_ok=True)

    for article in articles:
        file_name = f"{_safe_file_name(article.title)}_{article.aid}.md"
        lines = [
            f"# {article.title}",
            "",
            f"- aid: {article.aid}",
            f"- status: {article.status.value}",
            f"- author: {article.author.nickname} ({article.author.uid})",
            f"- tags: {', '.join(article.tags or [])}",
            f"- created_at: {_iso(article.created_at)}",
            f"- published_at: {_iso(article.published_at)}",
            "",
        ]
        if article.excerpt:
            lines.extend(["## 摘要", "", article.excerpt, ""])
        lines.extend(["## 正文", ""])
        for block in sorted(article.blocks, key=lambda b: b.sort_order):
            lines.append(f"### {block.block_type.value} #{block.sort_order}")
            lines.append("")
            lines.append(block.content)
            lines.append("")
        (articles_dir / file_name).write_text("\n".join(lines), encoding="utf-8")

    for moment in moments:
        file_name = f"{moment.mid}.md"
        lines = [
            f"# 时间线记录 {moment.mid}",
            "",
            f"- author: {moment.author.nickname} ({moment.author.uid})",
            f"- timestamp: {_iso(moment.timestamp)}",
            f"- location: {moment.location or ''}",
            f"- tags: {', '.join(moment.tags or [])}",
            "",
            "## 内容",
            "",
            moment.content,
            "",
        ]
        if moment.media_urls:
            lines.extend(["## 媒体", ""])
            lines.extend([f"- {url}" for url in moment.media_urls])
            lines.append("")
        active_comments = [c for c in moment.comments if c.deleted_at is None]
        by_parent: dict = {}
        for c in active_comments:
            by_parent.setdefault(c.parent_id, []).append(c)
        for siblings in by_parent.values():
            siblings.sort(key=lambda item: item.created_at)
        root_comments = by_parent.get(None, [])
        if root_comments:
            lines.extend(["## 评论", ""])
            for c in root_comments:
                _append_comment_lines(lines, c, by_parent)
            lines.append("")
        (timeline_dir / file_name).write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Archive builder
# ---------------------------------------------------------------------------

def _build_archive(export_dir: Path, data: dict, manifest: dict) -> Path:
    """Write all backup artefacts into export_dir and return the .zip path."""
    # 1. Manifest
    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 2. Full JSON dump
    payload = _build_json_payload(data, manifest)
    json_path = export_dir / "data.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 3. Markdown
    _write_markdown_exports(export_dir, data["articles"], data["moments"])

    # 4. Uploads tree
    if UPLOADS_ROOT.exists():
        shutil.copytree(UPLOADS_ROOT, export_dir / "uploads", dirs_exist_ok=True)

    # 5. Compress
    archive_path = export_dir / "backup.zip"
    with ZipFile(archive_path, mode="w", compression=ZIP_DEFLATED) as zf:
        for file in export_dir.rglob("*"):
            if file == archive_path or file.is_dir():
                continue
            zf.write(file, file.relative_to(export_dir))

    return archive_path


def _auto_backup_file_name(backup_id: str, created_at: datetime | None = None) -> str:
    created_at = created_at or _now_utc()
    timestamp = created_at.strftime("%Y%m%d-%H%M%S-%f")
    return f"love-auto-backup-{timestamp}-{backup_id}.zip"


def _update_backup_schedule_result(status: str, error: str | None) -> dict:
    completed_at = _now_utc()

    def mutate(config: dict) -> None:
        config["last_run_at"] = completed_at.isoformat()
        config["last_status"] = status
        config["last_error"] = error
        if config.get("enabled"):
            interval = int(config.get("interval_hours") or 24)
            config["next_run_at"] = (completed_at + timedelta(hours=interval)).isoformat()
        else:
            config["next_run_at"] = None

    return _update_schedule(mutate)


def _create_persistent_auto_backup(db: Session, operator: User, *, reason: str = "manual") -> dict:
    with _persistent_backup_run_lock():
        return _create_persistent_auto_backup_locked(db, operator, reason=reason)


def _create_persistent_auto_backup_locked(
    db: Session,
    operator: User,
    *,
    reason: str,
) -> dict:
    config = _load_schedule()
    backup_dir = _backup_dir_from_config(config)
    try:
        backup_dir.relative_to(BACKEND_ROOT)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Backup directory must stay inside the backend folder.") from exc

    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_id = str(_uuid_mod.uuid4())
    data = _load_all_data(db)
    manifest = _build_manifest(data, backup_id, operator.uid)

    export_dir = Path(tempfile.mkdtemp(prefix="love_auto_backup_"))
    try:
        archive_path = _build_archive(export_dir, data, manifest)
        archive_size = archive_path.stat().st_size
        file_name = _auto_backup_file_name(backup_id)
        target_path = backup_dir / file_name
        shutil.move(str(archive_path), target_path)

        record = {
            "backup_id": backup_id,
            "action": "auto_backup",
            "reason": reason,
            "file_name": file_name,
            "file_path": str(target_path),
            "schema_version": BACKUP_SCHEMA_VERSION,
            "created_at": manifest["created_at"],
            "operator_uid": operator.uid,
            "operator_nickname": operator.nickname,
            "counts": manifest["counts"],
            "archive_size_bytes": archive_size,
            "status": "success",
        }
        _append_history(record)
        _prune_auto_backups(config)

        _update_backup_schedule_result("success", None)
    except Exception as exc:
        # A failed flush/commit leaves SQLAlchemy sessions unusable until
        # rollback. Cleanup and failure reporting must never hide the original
        # archive/state error with PendingRollbackError.
        try:
            db.rollback()
        except Exception:
            logger.warning("Failed to roll back backup database session", exc_info=True)
        try:
            _update_backup_schedule_result("failed", str(exc))
        except Exception:
            logger.warning("Failed to persist backup failure state", exc_info=True)
        try:
            notify_partners(
                db,
                type="backup.failed",
                title="自动备份失败",
                body=str(exc),
                link="/admin/export",
                source_type="backup",
                source_id=f"failed:{_now_utc().isoformat()}",
            )
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            logger.warning("Failed to send backup failure notification", exc_info=True)
        raise
    finally:
        shutil.rmtree(export_dir, ignore_errors=True)

    # Audit rows and user notifications are secondary to the already-created
    # archive. Their transaction may fail without rewriting a successful
    # backup/history/schedule result as failed.
    try:
        write_audit_log(
            db,
            action="backup.auto",
            actor=operator,
            resource_type="backup",
            resource_id=backup_id,
            resource_name=file_name,
            detail={
                "reason": reason,
                "archive_size_bytes": archive_size,
                "counts": manifest["counts"],
            },
        )
        notify_partners(
            db,
            type="backup.success",
            title="自动备份已完成",
            body=f"{file_name}，大小 {archive_size} bytes",
            link="/admin/export",
            source_type="backup",
            source_id=backup_id,
            dedupe=True,
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning(
            "Backup archive succeeded but audit/notification persistence failed",
            exc_info=True,
        )
    return record


def run_scheduled_backup_if_due(db: Session) -> dict | None:
    # Re-check due state only after obtaining the cross-process run lease. Two
    # scheduler workers can wake together, but only the first may create the
    # backup; the second observes the newly advanced next_run_at.
    with _persistent_backup_run_lock():
        config = _load_schedule()
        if not config.get("enabled"):
            return None

        now = _now_utc()
        next_run_at = _parse_dt(config.get("next_run_at"))
        if next_run_at and next_run_at > now:
            return None

        operator = _find_auto_backup_operator(db)
        if operator is None:
            _update_backup_schedule_result(
                "failed", "No partner account is available to run scheduled backups."
            )
            return None

        return _create_persistent_auto_backup_locked(db, operator, reason="schedule")


# ---------------------------------------------------------------------------
# Restore helpers
# ---------------------------------------------------------------------------

# Every schema version this codebase can read back during restore. Historical
# versions are listed explicitly and this set must only ever grow; the current
# export version is unioned in via BACKUP_SCHEMA_VERSION so bumping the format
# can never again leave the restore allow-list behind — the regression where the
# server refused to restore the very backups it had just written.
SUPPORTED_VERSIONS = {"v1", "v2", "v3", "v4", "v5"} | {BACKUP_SCHEMA_VERSION}


def _preflight_check_zip(zip_path: Path) -> dict:
    """
    Open the uploaded ZIP and return a preflight report.

    Returns a dict with:
      - ok: bool
      - errors: list[str]      — fatal problems that prevent restore
      - warnings: list[str]    — non-fatal notices
      - manifest: dict | None  — parsed manifest.json if present
      - has_data_json: bool
      - has_uploads: bool
    """
    errors: list[str] = []
    warnings: list[str] = []
    manifest: dict | None = None
    has_data_json = False
    has_uploads = False

    try:
        with ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())

            # Must have data.json
            if "data.json" not in names:
                errors.append("备份包中缺少 data.json，无法恢复。")
            else:
                has_data_json = True
                try:
                    with zf.open("data.json") as f:
                        data_bytes = f.read(50 * 1024 * 1024)  # 50MB limit
                        if f.read(1):
                            raise ValueError("data.json exceeds 50MB limit")
                        raw = json.loads(data_bytes.decode("utf-8"))
                    meta = raw.get("meta", {})
                    schema_ver = meta.get("schema_version", "v1")
                    if schema_ver not in SUPPORTED_VERSIONS:
                        errors.append(
                            f"不支持的备份版本 {schema_ver!r}，"
                            f"当前支持：{', '.join(sorted(SUPPORTED_VERSIONS))}。"
                        )
                except Exception as exc:
                    errors.append(f"data.json 解析失败：{exc}")

            # manifest.json (optional but preferred)
            if "manifest.json" in names:
                try:
                    with zf.open("manifest.json") as f:
                        manifest_bytes = f.read(5 * 1024 * 1024)  # 5MB limit
                        if f.read(1):
                            raise ValueError("manifest.json exceeds 5MB limit")
                        manifest = json.loads(manifest_bytes.decode("utf-8"))
                    ver = manifest.get("schema_version", "")
                    if ver not in SUPPORTED_VERSIONS:
                        warnings.append(
                            f"manifest.json 中 schema_version={ver!r} 未被当前版本识别，"
                            "将尝试继续恢复。"
                        )
                except Exception as exc:
                    warnings.append(f"manifest.json 解析失败（非致命）：{exc}")
            else:
                warnings.append("备份包中没有 manifest.json，部分元信息不可用。")

            # Uploads presence
            has_uploads = any(n.startswith("uploads/") for n in names)
            if not has_uploads:
                warnings.append("备份包中没有 uploads/ 目录，媒体文件将不会恢复。")

    except BadZipFile:
        errors.append("上传的文件不是有效的 ZIP 格式。")
    except Exception as exc:
        errors.append(f"读取 ZIP 失败：{exc}")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "manifest": manifest,
        "has_data_json": has_data_json,
        "has_uploads": has_uploads,
    }


# ---------------------------------------------------------------------------
# Restore: database import (data.json → DB rows)
# ---------------------------------------------------------------------------
#
# Semantics: NON-DESTRUCTIVE, idempotent "additive" restore. Each record is
# matched by its public business key (uid / aid / alb_id / eid / mid / msg_id /
# capsule uuid). Existing rows are left untouched (counted as "skipped");
# missing rows are recreated with their original key, timestamps, authorship and
# privacy settings. This recovers data lost from the DB (the disaster-recovery
# case) without ever clobbering data that is currently present — so uploading
# the wrong backup file can't destroy live content.
#
# Not imported: ``notifications`` (reference volatile internal ids and are
# ephemeral) and content ``versions`` (history). These are reported as skipped
# sections so the operator knows.


def _parse_iso_dt(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_iso_date(value: Any) -> date | None:
    dt = _parse_iso_dt(value)
    if dt is not None:
        return dt.date()
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _safe_enum(enum_cls, value: Any, default):
    """Parse an enum from its stored ``.value`` (or name); fall back to default."""
    if value is None:
        return default
    try:
        return enum_cls(value)
    except (ValueError, KeyError):
        try:
            return enum_cls[value]
        except (KeyError, TypeError):
            return default


def _restore_users(db: Session, users_data: list[dict], index: dict[str, User]) -> dict[str, int]:
    """Match backup users to existing rows (by uid then username) or create a
    placeholder so authored content has a valid FK target.

    Backups intentionally omit ``password_hash`` (a privacy/security choice), so
    a freshly-created placeholder gets a random, unusable hash: the account
    exists for authorship/display but cannot be logged into until a partner
    resets its password from the admin panel.
    """
    created = 0
    matched = 0
    for u in users_data:
        uid = u.get("uid")
        if not uid:
            continue
        existing = db.query(User).filter(User.uid == uid).first()
        if existing is None and u.get("username"):
            existing = db.query(User).filter(User.username == u["username"]).first()
        if existing is not None:
            index[uid] = existing
            matched += 1
            continue

        username = (u.get("username") or f"user_{uid[:8]}").strip() or f"user_{uid[:8]}"
        if db.query(User).filter(User.username == username).first() is not None:
            # Username taken by a different account — suffix to stay unique.
            username = f"{username}_{uid[:6]}"
        user = User(
            uid=uid,
            username=username,
            nickname=u.get("nickname") or username,
            avatar=u.get("avatar"),
            role=_safe_enum(UserRole, u.get("role"), UserRole.partner_a),
            password_hash=get_password_hash(secrets.token_urlsafe(32)),
        )
        created_at = _parse_iso_dt(u.get("created_at"))
        if created_at:
            user.created_at = created_at
        db.add(user)
        db.flush()
        index[uid] = user
        created += 1
    return {"created": created, "matched": matched}


def _resolve_author(db: Session, index: dict[str, User], uid: Any, fallback: User | None) -> User | None:
    if not uid:
        return fallback
    cached = index.get(uid)
    if cached is not None:
        return cached
    user = db.query(User).filter(User.uid == uid).first()
    if user is not None:
        index[uid] = user
        return user
    return fallback


def _import_data_json(db: Session, data_json: dict) -> dict:
    """Re-create missing DB rows from a backup's ``data.json``. Idempotent."""
    index: dict[str, User] = {}
    result: dict[str, Any] = {
        "users": _restore_users(db, data_json.get("users") or [], index),
        "skipped_sections": ["versions"],
    }

    fallback_user = (
        db.query(User)
        .filter(
            User.role.in_([UserRole.partner_a, UserRole.partner_b]),
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .first()
    )

    # ── Shared E2EE chat KDF metadata ────────────────────────────────────
    chat_key_data = data_json.get("chat_key") or {}
    chat_key_restored = False
    if chat_key_data and db.query(ChatKey).first() is None:
        creator = _resolve_author(db, index, chat_key_data.get("creator_uid"), fallback_user)
        required = (
            chat_key_data.get("salt"),
            chat_key_data.get("verifier_iv"),
            chat_key_data.get("verifier_cipher"),
            chat_key_data.get("verifier_hash"),
        )
        if creator is not None and all(required):
            restored_key = ChatKey(
                user_id=creator.id,
                salt=chat_key_data["salt"],
                kdf=chat_key_data.get("kdf") or "PBKDF2",
                kdf_hash=chat_key_data.get("kdf_hash") or "SHA-256",
                iterations=int(chat_key_data.get("iterations") or 210000),
                algo=chat_key_data.get("algo") or "AES-GCM",
                verifier_iv=chat_key_data["verifier_iv"],
                verifier_cipher=chat_key_data["verifier_cipher"],
                verifier_hash=chat_key_data["verifier_hash"],
                needs_re_encrypt=bool(chat_key_data.get("needs_re_encrypt", False)),
            )
            created_at = _parse_iso_dt(chat_key_data.get("created_at"))
            updated_at = _parse_iso_dt(chat_key_data.get("updated_at"))
            if created_at:
                restored_key.created_at = created_at
            if updated_at:
                restored_key.updated_at = updated_at
            db.add(restored_key)
            db.flush()
            chat_key_restored = True
    result["chat_key"] = {"restored": chat_key_restored}

    # ── Site setting (config singleton, id=1) ─────────────────────────────
    setting_data = data_json.get("setting") or {}
    if setting_data:
        setting = db.query(SiteSetting).filter(SiteSetting.id == 1).first()
        if setting is None:
            setting = SiteSetting(id=1)
            db.add(setting)
        if setting_data.get("site_name"):
            setting.site_name = setting_data["site_name"]
        love_start = _parse_iso_dt(setting_data.get("love_start_date"))
        if love_start:
            setting.love_start_date = love_start
        for field in ("uploads_root", "articles_path", "albums_path", "avatar_path", "timeline_path", "videos_path"):
            if setting_data.get(field):
                setattr(setting, field, setting_data[field])
        db.flush()
        result["site_setting"] = {"updated": True}

    # ── Articles (+ blocks) ───────────────────────────────────────────────
    a_created = a_skipped = 0
    for a in data_json.get("articles") or []:
        aid = a.get("aid")
        if aid and db.query(Article).filter(Article.aid == aid).first():
            a_skipped += 1
            continue
        author = _resolve_author(db, index, a.get("author_uid"), fallback_user)
        if author is None:
            a_skipped += 1
            continue
        article = Article(
            author_id=author.id,
            title=a.get("title") or "",
            excerpt=a.get("excerpt"),
            is_encrypted=bool(a.get("is_encrypted")),
            is_co_created=bool(a.get("is_co_created")),
            partner_can_edit=bool(a.get("partner_can_edit")),
            tags=a.get("tags") or [],
            status=_safe_enum(ArticleStatus, a.get("status"), ArticleStatus.draft),
            visibility=_safe_enum(ContentVisibility, a.get("visibility"), ContentVisibility.public),
            password_hash=a.get("password_hash"),
            cover_url=a.get("cover_url"),
        )
        if aid:
            article.aid = aid
        published_at = _parse_iso_dt(a.get("published_at"))
        if published_at:
            article.published_at = published_at
        created_at = _parse_iso_dt(a.get("created_at"))
        if created_at:
            article.created_at = created_at
        db.add(article)
        db.flush()
        for b in a.get("blocks") or []:
            b_author = _resolve_author(db, index, b.get("author_uid"), author)
            block = ArticleBlock(
                article_id=article.id,
                author_id=(b_author or author).id,
                block_type=_safe_enum(ArticleBlockType, b.get("block_type"), ArticleBlockType.paragraph),
                content=b.get("content") or "",
                sort_order=int(b.get("sort_order") or 0),
            )
            if b.get("bid"):
                block.bid = b["bid"]
            db.add(block)
        db.flush()
        a_created += 1
    result["articles"] = {"created": a_created, "skipped": a_skipped}

    # ── Albums (+ media) ──────────────────────────────────────────────────
    al_created = al_skipped = 0
    for al in data_json.get("albums") or []:
        alb_id = al.get("alb_id")
        if alb_id and db.query(Album).filter(Album.alb_id == alb_id).first():
            al_skipped += 1
            continue
        author = _resolve_author(db, index, al.get("author_uid"), fallback_user)
        if author is None:
            al_skipped += 1
            continue
        album = Album(
            author_id=author.id,
            title=al.get("title") or "",
            description=al.get("description"),
            cover_url=al.get("cover_url"),
            is_encrypted=bool(al.get("is_encrypted")),
            is_public=bool(al.get("is_public", True)),
            tags=al.get("tags") or [],
            visibility=_safe_enum(ContentVisibility, al.get("visibility"), ContentVisibility.public),
            password_hash=al.get("password_hash"),
        )
        if alb_id:
            album.alb_id = alb_id
        created_at = _parse_iso_dt(al.get("created_at"))
        if created_at:
            album.created_at = created_at
        db.add(album)
        db.flush()
        for mi in al.get("media_items") or []:
            media = AlbumMedia(
                album_id=album.id,
                media_type=_safe_enum(MediaType, mi.get("media_type"), MediaType.image),
                file_url=mi.get("file_url") or "",
                thumbnail_url=mi.get("thumbnail_url"),
                file_size=mi.get("file_size"),
                mime_type=mi.get("mime_type"),
                is_encrypted=bool(mi.get("is_encrypted")),
            )
            if mi.get("media_id"):
                media.media_id = mi["media_id"]
            media_created = _parse_iso_dt(mi.get("created_at"))
            if media_created:
                media.created_at = media_created
            db.add(media)
        db.flush()
        al_created += 1
    result["albums"] = {"created": al_created, "skipped": al_skipped}

    # ── Events ────────────────────────────────────────────────────────────
    e_created = e_skipped = 0
    for e in data_json.get("events") or []:
        eid = e.get("eid")
        if eid and db.query(Event).filter(Event.eid == eid).first():
            e_skipped += 1
            continue
        creator = _resolve_author(db, index, e.get("creator_uid"), fallback_user)
        if creator is None:
            e_skipped += 1
            continue
        event = Event(
            creator_id=creator.id,
            title=e.get("title") or "",
            date=_parse_iso_date(e.get("date")) or _now_utc().date(),
            type=_safe_enum(EventType, e.get("type"), EventType.countdown),
            is_important=bool(e.get("is_important")),
            is_yearly_repeat=bool(e.get("is_yearly_repeat")),
            visibility=_safe_enum(EventVisibility, e.get("visibility"), EventVisibility.public),
            tags=e.get("tags") or [],
        )
        if eid:
            event.eid = eid
        created_at = _parse_iso_dt(e.get("created_at"))
        if created_at:
            event.created_at = created_at
        db.add(event)
        db.flush()
        e_created += 1
    result["events"] = {"created": e_created, "skipped": e_skipped}

    # ── Moments (+ comments) ──────────────────────────────────────────────
    m_created = m_skipped = 0
    c_created = 0
    for m in data_json.get("moments") or []:
        mid = m.get("mid")
        if mid and db.query(Moment).filter(Moment.mid == mid).first():
            m_skipped += 1
            continue
        author = _resolve_author(db, index, m.get("author_uid"), fallback_user)
        if author is None:
            m_skipped += 1
            continue
        moment = Moment(
            author_id=author.id,
            content=m.get("content") or "",
            media_urls=m.get("media_urls") or [],
            audio_url=m.get("audio_url"),
            audio_duration_sec=m.get("audio_duration_sec"),
            location=m.get("location"),
            visibility=_safe_enum(MomentVisibility, m.get("visibility"), MomentVisibility.public),
            tags=m.get("tags") or [],
        )
        if mid:
            moment.mid = mid
        ts = _parse_iso_dt(m.get("timestamp"))
        if ts:
            moment.timestamp = ts
            moment.created_at = ts
        db.add(moment)
        db.flush()

        comments_data = m.get("comments") or []
        cid_map: dict[str, Comment] = {}
        for c in comments_data:
            c_author = _resolve_author(db, index, c.get("author_uid"), fallback_user)
            if c_author is None:
                continue
            comment = Comment(
                target_type=CommentTargetType.moment,
                target_id=moment.mid,
                moment_id=moment.id,
                author_id=c_author.id,
                content=c.get("content") or "",
            )
            if c.get("cid"):
                comment.cid = c["cid"]
            c_created_at = _parse_iso_dt(c.get("created_at"))
            if c_created_at:
                comment.created_at = c_created_at
            mentions = c.get("mention_uids") or []
            if mentions:
                comment.set_mention_uids(mentions)
            db.add(comment)
            db.flush()
            if c.get("cid"):
                cid_map[c["cid"]] = comment
            c_created += 1
        # Second pass: resolve threaded replies now that all cids exist.
        for c in comments_data:
            parent_cid = c.get("parent_cid")
            child_cid = c.get("cid")
            if parent_cid and child_cid and parent_cid in cid_map and child_cid in cid_map:
                cid_map[child_cid].parent_id = cid_map[parent_cid].id
        db.flush()
        m_created += 1
    result["moments"] = {"created": m_created, "skipped": m_skipped}
    result["comments"] = {"created": c_created}

    # ── Messages ──────────────────────────────────────────────────────────
    msg_created = msg_skipped = 0
    for m in data_json.get("messages") or []:
        msg_id = m.get("msg_id")
        if msg_id and db.query(Message).filter(Message.msg_id == msg_id).first():
            msg_skipped += 1
            continue
        author = _resolve_author(db, index, m.get("author_uid"), None)
        idempotency_key = m.get("client_idempotency_key")
        if idempotency_key and author and db.query(Message).filter(
            Message.author_id == author.id,
            Message.client_idempotency_key == idempotency_key,
        ).first():
            msg_skipped += 1
            continue
        message = Message(
            author_id=author.id if author else None,
            visitor_name=None if author else m.get("visitor_name"),
            client_idempotency_key=idempotency_key,
            content=m.get("content") or "",
            is_public=bool(m.get("is_public", True)),
            tags=m.get("tags") or [],
        )
        if msg_id:
            message.msg_id = msg_id
        created_at = _parse_iso_dt(m.get("created_at"))
        if created_at:
            message.created_at = created_at
        db.add(message)
        db.flush()
        msg_created += 1
    result["messages"] = {"created": msg_created, "skipped": msg_skipped}

    # ── Capsules ──────────────────────────────────────────────────────────
    cap_created = cap_skipped = 0
    for c in data_json.get("capsules") or []:
        cap_uuid = c.get("uuid")
        if cap_uuid and db.query(Capsule).filter(Capsule.uuid == cap_uuid).first():
            cap_skipped += 1
            continue
        author = _resolve_author(db, index, c.get("author_uid"), fallback_user)
        if author is None:
            cap_skipped += 1
            continue
        capsule = Capsule(
            author_id=author.id,
            content=c.get("content"),
            media_url=c.get("media_url"),
            media_type=c.get("media_type"),
            media_duration_sec=c.get("media_duration_sec"),
            open_at=_parse_iso_dt(c.get("open_at")) or _now_utc(),
        )
        if cap_uuid:
            capsule.uuid = cap_uuid
        created_at = _parse_iso_dt(c.get("created_at"))
        if created_at:
            capsule.created_at = created_at
        db.add(capsule)
        db.flush()
        cap_created += 1
    result["capsules"] = {"created": cap_created, "skipped": cap_skipped}

    # ── Cottage: check-ins ────────────────────────────────────────────────
    ci_created = ci_skipped = 0
    for c in data_json.get("checkins") or []:
        cid = c.get("cid")
        if cid and db.query(CheckIn).filter(CheckIn.cid == cid).first():
            ci_skipped += 1
            continue
        author = _resolve_author(db, index, c.get("author_uid"), fallback_user)
        if author is None:
            ci_skipped += 1
            continue
        checkin = CheckIn(
            author_id=author.id,
            content=c.get("content"),
            media_urls=c.get("media_urls") or [],
            location_text=c.get("location_text"),
            location_status=str(c.get("location_status") or "omitted"),
            location_provider=c.get("location_provider"),
        )
        if cid:
            checkin.cid = cid
        created_at = _parse_iso_dt(c.get("created_at"))
        if created_at:
            checkin.created_at = created_at
        updated_at = _parse_iso_dt(c.get("updated_at"))
        if updated_at:
            checkin.updated_at = updated_at
        db.add(checkin)
        db.flush()
        ci_created += 1
    result["checkins"] = {"created": ci_created, "skipped": ci_skipped}

    # ── Cottage: wishes ───────────────────────────────────────────────────
    w_created = w_skipped = 0
    for w in data_json.get("wishes") or []:
        wid = w.get("wid")
        if wid and db.query(Wish).filter(Wish.wid == wid).first():
            w_skipped += 1
            continue
        author = _resolve_author(db, index, w.get("author_uid"), fallback_user)
        if author is None:
            w_skipped += 1
            continue
        completed_by = _resolve_author(db, index, w.get("completed_by_uid"), None)
        wish = Wish(
            author_id=author.id,
            title=w.get("title") or "",
            description=w.get("description"),
            category=w.get("category"),
            status=str(w.get("status") or "pending"),
            priority=int(w.get("priority") or 0),
            target_date=_parse_iso_date(w.get("target_date")),
            completed_at=_parse_iso_dt(w.get("completed_at")),
            completed_by_id=completed_by.id if completed_by else None,
        )
        if wid:
            wish.wid = wid
        created_at = _parse_iso_dt(w.get("created_at"))
        if created_at:
            wish.created_at = created_at
        updated_at = _parse_iso_dt(w.get("updated_at"))
        if updated_at:
            wish.updated_at = updated_at
        db.add(wish)
        db.flush()
        w_created += 1
    result["wishes"] = {"created": w_created, "skipped": w_skipped}

    # ── Cottage: chat messages ────────────────────────────────────────────
    cm_created = cm_skipped = 0
    chat_by_mid = {
        item.mid: item
        for item in db.query(ChatMessage).filter(ChatMessage.deleted_at.is_(None)).all()
    }
    for m in data_json.get("chat_messages") or []:
        mid = m.get("mid")
        if mid and mid in chat_by_mid:
            cm_skipped += 1
            continue
        sender = _resolve_author(db, index, m.get("sender_uid"), fallback_user)
        if sender is None:
            cm_skipped += 1
            continue
        chat_msg = ChatMessage(
            sender_id=sender.id,
            type=str(m.get("type") or "text"),
            content=m.get("content"),
            media_url=m.get("media_url"),
            is_encrypted=bool(m.get("is_encrypted", False)),
            iv=m.get("iv"),
            ciphertext=m.get("ciphertext"),
            algo=m.get("algo"),
            audio_duration_sec=m.get("audio_duration_sec"),
            read_at=_parse_iso_dt(m.get("read_at")),
            visible_at=(
                _parse_iso_dt(m.get("visible_at"))
                or _parse_iso_dt(m.get("created_at"))
                or _now_utc()
            ),
            released_at=_parse_iso_dt(m.get("released_at")),
            recalled_at=_parse_iso_dt(m.get("recalled_at")),
        )
        if mid:
            chat_msg.mid = mid
        created_at = _parse_iso_dt(m.get("created_at"))
        if created_at:
            chat_msg.created_at = created_at
        db.add(chat_msg)
        db.flush()
        if mid:
            chat_by_mid[mid] = chat_msg
        cm_created += 1

    # Replies use internal integer FKs, so resolve them only after every public
    # message MID has been recreated in the destination database.
    for m in data_json.get("chat_messages") or []:
        item = chat_by_mid.get(m.get("mid"))
        reply = chat_by_mid.get(m.get("reply_to_mid"))
        if item is not None and reply is not None and item.reply_to_message_id is None:
            item.reply_to_message_id = reply.id
    db.flush()
    result["chat_messages"] = {"created": cm_created, "skipped": cm_skipped}

    favorite_created = favorite_skipped = 0
    for item in data_json.get("chat_favorites") or []:
        user = _resolve_author(db, index, item.get("user_uid"), None)
        message = chat_by_mid.get(item.get("message_mid"))
        if user is None or message is None:
            favorite_skipped += 1
            continue
        existing = db.query(ChatMessageFavorite).filter(
            ChatMessageFavorite.user_id == user.id,
            ChatMessageFavorite.message_id == message.id,
        ).first()
        if existing is not None:
            favorite_skipped += 1
            continue
        favorite = ChatMessageFavorite(user_id=user.id, message_id=message.id)
        created_at = _parse_iso_dt(item.get("created_at"))
        if created_at:
            favorite.created_at = created_at
        db.add(favorite)
        db.flush()
        favorite_created += 1
    result["chat_favorites"] = {"created": favorite_created, "skipped": favorite_skipped}

    pin_created = pin_skipped = 0
    for item in data_json.get("chat_pinned_quotes") or []:
        user = _resolve_author(db, index, item.get("user_uid"), None)
        message = chat_by_mid.get(item.get("message_mid"))
        if user is None or message is None:
            pin_skipped += 1
            continue
        existing = db.query(ChatPinnedQuote).filter(ChatPinnedQuote.user_id == user.id).first()
        if existing is not None:
            pin_skipped += 1
            continue
        pin = ChatPinnedQuote(user_id=user.id, message_id=message.id)
        created_at = _parse_iso_dt(item.get("created_at"))
        if created_at:
            pin.created_at = created_at
        db.add(pin)
        db.flush()
        pin_created += 1
    result["chat_pinned_quotes"] = {"created": pin_created, "skipped": pin_skipped}

    # ── Cottage: mood check-ins ───────────────────────────────────────────
    mood_created = mood_skipped = 0
    for m in data_json.get("mood_checkins") or []:
        mid = m.get("mid")
        if mid and db.query(MoodCheckin).filter(MoodCheckin.mid == mid).first():
            mood_skipped += 1
            continue
        author = _resolve_author(db, index, m.get("author_uid"), fallback_user)
        mood_date = _parse_iso_date(m.get("mood_date"))
        if author is None or mood_date is None:
            mood_skipped += 1
            continue
        existing = (
            db.query(MoodCheckin)
            .filter(MoodCheckin.author_id == author.id, MoodCheckin.mood_date == mood_date)
            .first()
        )
        if existing is not None:
            mood_skipped += 1
            continue
        mood = MoodCheckin(
            author_id=author.id,
            mood_date=mood_date,
            mood=str(m.get("mood") or "happy"),
            emoji=m.get("emoji"),
            note=m.get("note"),
        )
        if mid:
            mood.mid = mid
        created_at = _parse_iso_dt(m.get("created_at"))
        if created_at:
            mood.created_at = created_at
        updated_at = _parse_iso_dt(m.get("updated_at"))
        if updated_at:
            mood.updated_at = updated_at
        db.add(mood)
        db.flush()
        mood_created += 1
    result["mood_checkins"] = {"created": mood_created, "skipped": mood_skipped}

    mood_operation_created = mood_operation_skipped = 0
    moods_by_mid = {item.mid: item for item in db.query(MoodCheckin).all()}
    for item in data_json.get("mood_idempotency_records") or []:
        user = _resolve_author(db, index, item.get("user_uid"), None)
        mood = moods_by_mid.get(item.get("mood_mid"))
        key = item.get("idempotency_key")
        payload_hash = item.get("payload_hash")
        if user is None or mood is None or not key or not payload_hash:
            mood_operation_skipped += 1
            continue
        if db.query(MoodIdempotencyRecord).filter(
            MoodIdempotencyRecord.user_id == user.id,
            MoodIdempotencyRecord.idempotency_key == key,
        ).first():
            mood_operation_skipped += 1
            continue
        record = MoodIdempotencyRecord(
            user_id=user.id,
            idempotency_key=str(key),
            payload_hash=str(payload_hash),
            mood_id=mood.id,
        )
        created_at = _parse_iso_dt(item.get("created_at"))
        if created_at:
            record.created_at = created_at
        db.add(record)
        db.flush()
        mood_operation_created += 1
    result["mood_idempotency_records"] = {
        "created": mood_operation_created,
        "skipped": mood_operation_skipped,
    }

    # ── Cottage: watch sources ────────────────────────────────────────────
    ws_created = ws_skipped = 0
    for w in data_json.get("watch_sources") or []:
        wsid = w.get("wsid")
        if wsid and db.query(WatchSource).filter(WatchSource.wsid == wsid).first():
            ws_skipped += 1
            continue
        author = _resolve_author(db, index, w.get("author_uid"), fallback_user)
        if author is None:
            ws_skipped += 1
            continue
        source = WatchSource(
            author_id=author.id,
            title=w.get("title") or "",
            kind=str(w.get("kind") or "url"),
            url=w.get("url") or "",
            poster_url=w.get("poster_url"),
            size_bytes=w.get("size_bytes"),
        )
        if wsid:
            source.wsid = wsid
        created_at = _parse_iso_dt(w.get("created_at"))
        if created_at:
            source.created_at = created_at
        updated_at = _parse_iso_dt(w.get("updated_at"))
        if updated_at:
            source.updated_at = updated_at
        db.add(source)
        db.flush()
        ws_created += 1
    result["watch_sources"] = {"created": ws_created, "skipped": ws_skipped}

    # ── Cottage: daily questions (+ answers) ──────────────────────────────
    dq_created = dq_skipped = 0
    dqa_created = 0
    for q in data_json.get("daily_questions") or []:
        qid = q.get("qid")
        if qid and db.query(DailyQuestion).filter(DailyQuestion.qid == qid).first():
            dq_skipped += 1
            continue
        author = _resolve_author(db, index, q.get("author_uid"), fallback_user)
        question_date = _parse_iso_date(q.get("question_date"))
        if author is None or question_date is None:
            dq_skipped += 1
            continue
        if db.query(DailyQuestion).filter(DailyQuestion.question_date == question_date).first():
            dq_skipped += 1
            continue
        question = DailyQuestion(
            author_id=author.id,
            question_date=question_date,
            prompt=q.get("prompt") or "",
        )
        if qid:
            question.qid = qid
        created_at = _parse_iso_dt(q.get("created_at"))
        if created_at:
            question.created_at = created_at
        updated_at = _parse_iso_dt(q.get("updated_at"))
        if updated_at:
            question.updated_at = updated_at
        db.add(question)
        db.flush()
        for a in q.get("answers") or []:
            dqa_id = a.get("dqa_id")
            if dqa_id and db.query(DailyQuestionAnswer).filter(DailyQuestionAnswer.aid == dqa_id).first():
                continue
            a_author = _resolve_author(db, index, a.get("author_uid"), fallback_user)
            if a_author is None:
                continue
            if (
                db.query(DailyQuestionAnswer)
                .filter(
                    DailyQuestionAnswer.question_id == question.id,
                    DailyQuestionAnswer.author_id == a_author.id,
                )
                .first()
            ):
                continue
            answer = DailyQuestionAnswer(
                question_id=question.id,
                author_id=a_author.id,
                content=a.get("content") or "",
            )
            if dqa_id:
                answer.aid = dqa_id
            a_created_at = _parse_iso_dt(a.get("created_at"))
            if a_created_at:
                answer.created_at = a_created_at
            a_updated_at = _parse_iso_dt(a.get("updated_at"))
            if a_updated_at:
                answer.updated_at = a_updated_at
            db.add(answer)
            db.flush()
            dqa_created += 1
        dq_created += 1
    result["daily_questions"] = {"created": dq_created, "skipped": dq_skipped}
    result["daily_question_answers"] = {"created": dqa_created}

    # ── Cottage: plans ────────────────────────────────────────────────────
    cp_created = cp_skipped = 0
    for p in data_json.get("cottage_plans") or []:
        pid = p.get("pid")
        if pid and db.query(CottagePlan).filter(CottagePlan.pid == pid).first():
            cp_skipped += 1
            continue
        author = _resolve_author(db, index, p.get("author_uid"), fallback_user)
        if author is None:
            cp_skipped += 1
            continue
        completed_by = _resolve_author(db, index, p.get("completed_by_uid"), None)
        plan = CottagePlan(
            author_id=author.id,
            title=p.get("title") or "",
            description=p.get("description"),
            location=p.get("location"),
            plan_date=_parse_iso_date(p.get("plan_date")),
            status=str(p.get("status") or "planned"),
            priority=int(p.get("priority") or 0),
            checklist=p.get("checklist") or [],
            completed_at=_parse_iso_dt(p.get("completed_at")),
            completed_by_id=completed_by.id if completed_by else None,
        )
        if pid:
            plan.pid = pid
        created_at = _parse_iso_dt(p.get("created_at"))
        if created_at:
            plan.created_at = created_at
        updated_at = _parse_iso_dt(p.get("updated_at"))
        if updated_at:
            plan.updated_at = updated_at
        db.add(plan)
        db.flush()
        cp_created += 1
    result["cottage_plans"] = {"created": cp_created, "skipped": cp_skipped}

    # ── Cottage: reminders ────────────────────────────────────────────────
    cr_created = cr_skipped = 0
    for r in data_json.get("cottage_reminders") or []:
        rid = r.get("rid")
        if rid and db.query(CottageReminder).filter(CottageReminder.rid == rid).first():
            cr_skipped += 1
            continue
        author = _resolve_author(db, index, r.get("author_uid"), fallback_user)
        remind_at = _parse_iso_dt(r.get("remind_at"))
        if author is None or remind_at is None:
            cr_skipped += 1
            continue
        done_by = _resolve_author(db, index, r.get("done_by_uid"), None)
        reminder = CottageReminder(
            author_id=author.id,
            title=r.get("title") or "",
            note=r.get("note"),
            remind_at=remind_at,
            audience=str(r.get("audience") or "both"),
            is_done=bool(r.get("is_done")),
            done_at=_parse_iso_dt(r.get("done_at")),
            done_by_id=done_by.id if done_by else None,
            last_notified_at=_parse_iso_dt(r.get("last_notified_at")),
        )
        if rid:
            reminder.rid = rid
        created_at = _parse_iso_dt(r.get("created_at"))
        if created_at:
            reminder.created_at = created_at
        updated_at = _parse_iso_dt(r.get("updated_at"))
        if updated_at:
            reminder.updated_at = updated_at
        db.add(reminder)
        db.flush()
        cr_created += 1
    result["cottage_reminders"] = {"created": cr_created, "skipped": cr_skipped}

    # ── Cottage: game matches ─────────────────────────────────────────────
    gm_created = gm_skipped = 0
    for m in data_json.get("game_matches") or []:
        gmid = m.get("gmid")
        if gmid and db.query(GameMatch).filter(GameMatch.gmid == gmid).first():
            gm_skipped += 1
            continue
        black = _resolve_author(db, index, m.get("black_uid"), fallback_user)
        white = _resolve_author(db, index, m.get("white_uid"), fallback_user)
        if black is None or white is None:
            gm_skipped += 1
            continue
        winner = _resolve_author(db, index, m.get("winner_uid"), None)
        match = GameMatch(
            game_key=str(m.get("game_key") or "gomoku"),
            black_id=black.id,
            white_id=white.id,
            winner_id=winner.id if winner else None,
            is_draw=bool(m.get("is_draw")),
            end_reason=str(m.get("end_reason") or "five"),
            move_count=int(m.get("move_count") or 0),
        )
        if gmid:
            match.gmid = gmid
        created_at = _parse_iso_dt(m.get("created_at"))
        if created_at:
            match.created_at = created_at
        db.add(match)
        db.flush()
        gm_created += 1
    result["game_matches"] = {"created": gm_created, "skipped": gm_skipped}

    # ── Cottage: listen history ───────────────────────────────────────────
    lh_created = lh_skipped = 0
    for h in data_json.get("listen_history") or []:
        hid = h.get("hid")
        if hid and db.query(ListenHistoryEntry).filter(ListenHistoryEntry.hid == hid).first():
            lh_skipped += 1
            continue
        artists = h.get("artists") or []
        if not isinstance(artists, list):
            artists = []
        entry = ListenHistoryEntry(
            song_id=str(h.get("song_id") or ""),
            name=str(h.get("name") or ""),
            artists_json=json.dumps([str(a) for a in artists if a], ensure_ascii=False),
            album=h.get("album"),
            duration_ms=h.get("duration_ms"),
            cover_url=h.get("cover_url"),
            started_by_uid=str(h.get("started_by_uid") or ""),
            played_at=_parse_iso_dt(h.get("played_at")) or _now_utc(),
        )
        if hid:
            entry.hid = hid
        db.add(entry)
        db.flush()
        lh_created += 1
    result["listen_history"] = {"created": lh_created, "skipped": lh_skipped}

    # ── Cottage: coupons ──────────────────────────────────────────────────
    coupon_created = coupon_skipped = 0
    for item in data_json.get("coupons") or []:
        cpid = item.get("cpid")
        if cpid and db.query(Coupon).filter(Coupon.cpid == cpid).first():
            coupon_skipped += 1
            continue
        author = _resolve_author(db, index, item.get("author_uid"), fallback_user)
        if author is None:
            coupon_skipped += 1
            continue
        redeemed_by = _resolve_author(db, index, item.get("redeemed_by_uid"), None)
        coupon = Coupon(
            author_id=author.id,
            title=str(item.get("title") or ""),
            description=item.get("description"),
            icon=item.get("icon"),
            status=str(item.get("status") or "active"),
            redeemed_at=_parse_iso_dt(item.get("redeemed_at")),
            redeemed_by_id=redeemed_by.id if redeemed_by else None,
            version=max(1, int(item.get("version") or 1)),
        )
        if cpid:
            coupon.cpid = cpid
        for field in ("created_at", "updated_at"):
            value = _parse_iso_dt(item.get(field))
            if value:
                setattr(coupon, field, value)
        db.add(coupon)
        db.flush()
        coupon_created += 1
    result["coupons"] = {"created": coupon_created, "skipped": coupon_skipped}

    # ── Cottage: ledger entries ───────────────────────────────────────────
    ledger_created = ledger_skipped = 0
    for item in data_json.get("ledger_entries") or []:
        leid = item.get("leid")
        if leid and db.query(LedgerEntry).filter(LedgerEntry.leid == leid).first():
            ledger_skipped += 1
            continue
        author = _resolve_author(db, index, item.get("author_uid"), fallback_user)
        payer = _resolve_author(db, index, item.get("payer_uid"), fallback_user)
        spent_on = _parse_iso_date(item.get("spent_on"))
        if author is None or payer is None or spent_on is None:
            ledger_skipped += 1
            continue
        entry = LedgerEntry(
            author_id=author.id,
            payer_id=payer.id,
            title=str(item.get("title") or ""),
            note=item.get("note"),
            amount_cents=max(0, int(item.get("amount_cents") or 0)),
            category=item.get("category"),
            split_type=str(item.get("split_type") or "aa"),
            spent_on=spent_on,
            version=max(1, int(item.get("version") or 1)),
        )
        if leid:
            entry.leid = leid
        for field in ("created_at", "updated_at"):
            value = _parse_iso_dt(item.get(field))
            if value:
                setattr(entry, field, value)
        db.add(entry)
        db.flush()
        ledger_created += 1
    result["ledger_entries"] = {"created": ledger_created, "skipped": ledger_skipped}

    # ── Cottage: period cycles ────────────────────────────────────────────
    period_created = period_skipped = 0
    for item in data_json.get("period_cycles") or []:
        pcid = item.get("pcid")
        if pcid and db.query(PeriodCycle).filter(PeriodCycle.pcid == pcid).first():
            period_skipped += 1
            continue
        author = _resolve_author(db, index, item.get("author_uid"), fallback_user)
        start_date = _parse_iso_date(item.get("start_date"))
        if author is None or start_date is None:
            period_skipped += 1
            continue
        if db.query(PeriodCycle).filter(
            PeriodCycle.author_id == author.id,
            PeriodCycle.start_date == start_date,
        ).first():
            period_skipped += 1
            continue
        cycle = PeriodCycle(
            author_id=author.id,
            start_date=start_date,
            end_date=_parse_iso_date(item.get("end_date")),
            note=item.get("note"),
            version=max(1, int(item.get("version") or 1)),
        )
        if pcid:
            cycle.pcid = pcid
        for field in ("created_at", "updated_at"):
            value = _parse_iso_dt(item.get(field))
            if value:
                setattr(cycle, field, value)
        db.add(cycle)
        db.flush()
        period_created += 1
    result["period_cycles"] = {"created": period_created, "skipped": period_skipped}

    # ── Cottage: uploaded local tracks ────────────────────────────────────
    local_created = local_skipped = 0
    for item in data_json.get("listen_local_tracks") or []:
        tid = item.get("tid")
        if tid and db.query(ListenLocalTrack).filter(ListenLocalTrack.tid == tid).first():
            local_skipped += 1
            continue
        uploader = _resolve_author(db, index, item.get("uploaded_by_uid"), fallback_user)
        audio_url = item.get("audio_url")
        if uploader is None or not audio_url:
            local_skipped += 1
            continue
        artists = item.get("artists") or []
        if not isinstance(artists, list):
            artists = []
        track = ListenLocalTrack(
            name=str(item.get("name") or ""),
            artists_json=json.dumps([str(value) for value in artists if value], ensure_ascii=False),
            album=item.get("album"),
            duration_ms=item.get("duration_ms"),
            cover_url=item.get("cover_url"),
            audio_url=str(audio_url),
            uploaded_by_uid=uploader.uid,
        )
        if tid:
            track.tid = tid
        created_at = _parse_iso_dt(item.get("created_at"))
        if created_at:
            track.created_at = created_at
        db.add(track)
        db.flush()
        local_created += 1
    result["listen_local_tracks"] = {"created": local_created, "skipped": local_skipped}

    # ── Push device registrations ─────────────────────────────────────────
    push_created = push_skipped = 0
    for item in data_json.get("push_subscriptions") or []:
        user = _resolve_author(db, index, item.get("user_uid"), None)
        sid = item.get("sid")
        endpoint = item.get("endpoint")
        if user is None or not endpoint or db.query(PushSubscription).filter(
            (PushSubscription.sid == sid) | (PushSubscription.endpoint == endpoint)
        ).first():
            push_skipped += 1
            continue
        subscription = PushSubscription(
            user_id=user.id,
            endpoint=str(endpoint),
            p256dh=str(item.get("p256dh") or ""),
            auth=str(item.get("auth") or ""),
            expiration_time=item.get("expiration_time"),
            user_agent=item.get("user_agent"),
            is_active=bool(item.get("is_active", True)),
            fail_count=max(0, int(item.get("fail_count") or 0)),
        )
        if sid:
            subscription.sid = sid
        for field in ("last_seen_at", "created_at", "updated_at"):
            value = _parse_iso_dt(item.get(field))
            if value:
                setattr(subscription, field, value)
        db.add(subscription)
        db.flush()
        push_created += 1
    result["push_subscriptions"] = {"created": push_created, "skipped": push_skipped}

    fcm_created = fcm_skipped = 0
    for item in data_json.get("fcm_device_tokens") or []:
        user = _resolve_author(db, index, item.get("user_uid"), None)
        tid = item.get("tid")
        token = item.get("token")
        if user is None or not token or db.query(FcmDeviceToken).filter(
            (FcmDeviceToken.tid == tid) | (FcmDeviceToken.token == token)
        ).first():
            fcm_skipped += 1
            continue
        device = FcmDeviceToken(
            user_id=user.id,
            token=str(token),
            platform=str(item.get("platform") or "android"),
            device_name=item.get("device_name"),
            app_version=item.get("app_version"),
            is_active=bool(item.get("is_active", True)),
            fail_count=max(0, int(item.get("fail_count") or 0)),
        )
        if tid:
            device.tid = tid
        for field in ("last_seen_at", "created_at", "updated_at"):
            value = _parse_iso_dt(item.get(field))
            if value:
                setattr(device, field, value)
        db.add(device)
        db.flush()
        fcm_created += 1
    result["fcm_device_tokens"] = {"created": fcm_created, "skipped": fcm_skipped}

    # Notifications are user-facing history, not merely transient rows. Keep
    # their original delivery state so a restore does not resend old alerts.
    notification_created = notification_skipped = 0
    for item in data_json.get("notifications") or []:
        nid = item.get("nid")
        if nid and db.query(Notification).filter(Notification.nid == nid).first():
            notification_skipped += 1
            continue
        recipient = _resolve_author(db, index, item.get("recipient_uid"), None)
        if recipient is None:
            notification_skipped += 1
            continue
        notification = Notification(
            recipient_id=recipient.id,
            type=str(item.get("type") or "restored"),
            title=str(item.get("title") or ""),
            body=item.get("body"),
            link=item.get("link"),
            source_type=item.get("source_type"),
            source_id=item.get("source_id"),
            is_read=bool(item.get("is_read")),
            delivery_status=str(item.get("delivery_status") or "not_queued"),
            delivery_attempts=max(0, int(item.get("delivery_attempts") or 0)),
            delivery_last_error=item.get("delivery_last_error"),
            delivery_last_attempt_at=_parse_iso_dt(item.get("delivery_last_attempt_at")),
            delivery_completed_at=_parse_iso_dt(item.get("delivery_completed_at")),
            read_at=_parse_iso_dt(item.get("read_at")),
        )
        if nid:
            notification.nid = nid
        created_at = _parse_iso_dt(item.get("created_at"))
        if created_at:
            notification.created_at = created_at
        db.add(notification)
        db.flush()
        notification_created += 1
    result["notifications"] = {"created": notification_created, "skipped": notification_skipped}

    # ── Cottage: E2EE vault (meta singleton + ciphertext entries) ─────────
    # The meta row is a singleton (id=1); only restore it when absent so we
    # never clobber a vault the couple is actively using with a different key.
    vault_meta_data = data_json.get("vault_meta")
    vault_meta_restored = False
    if vault_meta_data and db.query(VaultMeta).filter(VaultMeta.id == 1).first() is None:
        salt = vault_meta_data.get("salt")
        verifier_iv = vault_meta_data.get("verifier_iv")
        verifier_cipher = vault_meta_data.get("verifier_cipher")
        # Only restore a structurally complete meta row — a partial one would
        # leave the vault unusable (no way to derive/verify the key).
        if salt and verifier_iv and verifier_cipher:
            meta = VaultMeta(
                id=1,
                salt=salt,
                kdf=vault_meta_data.get("kdf") or "PBKDF2",
                kdf_hash=vault_meta_data.get("kdf_hash") or "SHA-256",
                iterations=int(vault_meta_data.get("iterations") or 210000),
                algo=vault_meta_data.get("algo") or "AES-GCM",
                verifier_iv=verifier_iv,
                verifier_cipher=verifier_cipher,
            )
            db.add(meta)
            db.flush()
            vault_meta_restored = True
    result["vault_meta"] = {"restored": vault_meta_restored}

    ve_created = ve_skipped = 0
    for e in data_json.get("vault_entries") or []:
        vid = e.get("vid")
        if vid and db.query(VaultEntry).filter(VaultEntry.vid == vid).first():
            ve_skipped += 1
            continue
        author = _resolve_author(db, index, e.get("author_uid"), fallback_user)
        iv = e.get("iv")
        ciphertext = e.get("ciphertext")
        if author is None or not iv or not ciphertext:
            ve_skipped += 1
            continue
        entry = VaultEntry(author_id=author.id, iv=iv, ciphertext=ciphertext)
        if vid:
            entry.vid = vid
        created_at = _parse_iso_dt(e.get("created_at"))
        if created_at:
            entry.created_at = created_at
        updated_at = _parse_iso_dt(e.get("updated_at"))
        if updated_at:
            entry.updated_at = updated_at
        db.add(entry)
        db.flush()
        ve_created += 1
    result["vault_entries"] = {"created": ve_created, "skipped": ve_skipped}

    # Rebuild per-file media access-control rows so restored uploads are
    # actually viewable (the /uploads guard checks UploadReference).
    rebuild_upload_references(db)
    db.flush()
    return result


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@router.get("/preflight")
def get_preflight(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a preview of what a backup would contain right now."""
    ensure_partner(current_user)
    data = _load_all_data(db)
    counts = _count_summary(data)

    upload_size_bytes = 0
    upload_file_count = 0
    if UPLOADS_ROOT.exists():
        files = [f for f in UPLOADS_ROOT.rglob("*") if f.is_file()]
        upload_file_count = len(files)
        upload_size_bytes = sum(f.stat().st_size for f in files)

    return {
        "schema_version": BACKUP_SCHEMA_VERSION,
        "counts": counts,
        "uploads": {
            "file_count": upload_file_count,
            "size_bytes": upload_size_bytes,
        },
        "checked_at": _now_utc().isoformat(),
    }


@router.get("/schedule", response_model=BackupScheduleResponse)
def get_backup_schedule(
    current_user: User = Depends(get_current_user),
) -> BackupScheduleResponse:
    ensure_partner(current_user)
    return _schedule_to_response(_load_schedule())


@router.put("/schedule", response_model=BackupScheduleResponse)
def update_backup_schedule(
    payload: BackupScheduleUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> BackupScheduleResponse:
    ensure_partner(current_user)

    def mutate(config: dict) -> None:
        config.update(payload.model_dump())
        if payload.enabled:
            config["next_run_at"] = (
                _now_utc() + timedelta(hours=payload.interval_hours)
            ).isoformat()
            config["last_error"] = None
        else:
            config["next_run_at"] = None

    return _schedule_to_response(_update_schedule(mutate))


@router.post("/auto/run", response_model=AutoBackupRunResponse)
def run_auto_backup_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AutoBackupRunResponse:
    ensure_partner(current_user)
    record = _create_persistent_auto_backup(db, current_user, reason="manual")
    return AutoBackupRunResponse(ok=True, message="自动备份已完成", record=record)


@router.get("/history")
def get_backup_history(
    current_user: User = Depends(get_current_user),
):
    """Return the list of past backup downloads (most recent first)."""
    ensure_partner(current_user)
    history = _load_history()
    return {"items": list(reversed(history))}


@router.get("/all")
def export_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create and stream a full backup ZIP."""
    ensure_partner(current_user)

    backup_id = str(_uuid_mod.uuid4())
    data = _load_all_data(db)
    manifest = _build_manifest(data, backup_id, current_user.uid)

    export_dir = Path(tempfile.mkdtemp(prefix="love_backup_"))
    archive_path = _build_archive(export_dir, data, manifest)

    if not archive_path.exists():
        shutil.rmtree(export_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="备份文件生成失败")

    archive_size = archive_path.stat().st_size
    timestamp_str = _now_utc().strftime("%Y%m%d-%H%M%S")
    file_name = f"love-backup-{timestamp_str}.zip"

    # Persist to history
    history_record = {
        "backup_id": backup_id,
        "file_name": file_name,
        "schema_version": BACKUP_SCHEMA_VERSION,
        "created_at": manifest["created_at"],
        "operator_uid": current_user.uid,
        "operator_nickname": current_user.nickname,
        "counts": manifest["counts"],
        "archive_size_bytes": archive_size,
    }
    try:
        _append_history(history_record)
    except Exception:
        logger.warning("Failed to write backup history record", exc_info=True)

    write_audit_log(
        db,
        action="backup.export",
        actor=current_user,
        resource_type="backup",
        resource_id=backup_id,
        resource_name=file_name,
        detail={
            "schema_version": BACKUP_SCHEMA_VERSION,
            "archive_size_bytes": archive_size,
            "counts": manifest["counts"],
        },
    )

    return FileResponse(
        path=archive_path,
        filename=file_name,
        media_type="application/zip",
        background=BackgroundTask(shutil.rmtree, export_dir, ignore_errors=True),
    )


async def _save_upload_chunked(file: UploadFile, target_path: Path, max_size: int = 1024 * 1024 * 1024) -> None:
    total_size = 0
    with target_path.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > max_size:
                raise HTTPException(status_code=413, detail="Upload file is too large.")
            f.write(chunk)


def _safe_extract(
    zip_path: Path,
    extract_dir: Path,
    max_uncompressed_size: int = 5 * 1024 * 1024 * 1024,
    max_files: int = 100000,
) -> None:
    extract_dir.mkdir(parents=True, exist_ok=True)
    total_extracted_size = 0
    extracted_files = 0

    with ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue

            if ".." in info.filename or info.filename.startswith("/") or info.filename.startswith("\\"):
                raise HTTPException(status_code=400, detail="Invalid path in ZIP archive.")

            extracted_files += 1
            if extracted_files > max_files:
                raise HTTPException(status_code=413, detail="Too many files in ZIP archive.")

            target_path = (extract_dir / info.filename).resolve()
            try:
                target_path.relative_to(extract_dir.resolve())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid path traversal in ZIP archive.") from exc

            target_path.parent.mkdir(parents=True, exist_ok=True)

            with zf.open(info) as src, target_path.open("wb") as dst:
                while True:
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    total_extracted_size += len(chunk)
                    if total_extracted_size > max_uncompressed_size:
                        raise HTTPException(status_code=413, detail="Uncompressed size exceeds limit.")
                    dst.write(chunk)


@router.post("/restore/preflight")
async def restore_preflight(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Accept a backup ZIP upload, run preflight checks, and return a report
    WITHOUT actually modifying any data.
    """
    ensure_partner(current_user)

    # Stream to a temp file
    tmp_dir = Path(tempfile.mkdtemp(prefix="love_restore_pre_"))
    tmp_zip = tmp_dir / "uploaded.zip"
    try:
        await _save_upload_chunked(file, tmp_zip)
        report = _preflight_check_zip(tmp_zip)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    status_code = 200 if report["ok"] else 422
    return JSONResponse(content=report, status_code=status_code)


@router.post("/restore")
async def restore_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a backup ZIP. After preflight checks pass, restore the uploads/ tree
    from the archive and then re-import the database additively & idempotently
    from data.json (rows matched by business key are skipped; only missing rows
    are recreated). The DB import runs in its own transaction: on any error it is
    rolled back and reported, leaving the just-copied uploads in place.
    """
    ensure_partner(current_user)

    tmp_dir = Path(tempfile.mkdtemp(prefix="love_restore_"))
    tmp_zip = tmp_dir / "uploaded.zip"

    try:
        await _save_upload_chunked(file, tmp_zip)

        # ── Preflight ─────────────────────────────────────────────────────
        report = _preflight_check_zip(tmp_zip)
        if not report["ok"]:
            raise HTTPException(
                status_code=422,
                detail={"message": "备份预检失败，恢复中止。", "errors": report["errors"]},
            )

        # ── Extract ───────────────────────────────────────────────────────
        extract_dir = tmp_dir / "extracted"
        _safe_extract(tmp_zip, extract_dir)

        # Read manifest + data
        manifest: dict = {}
        manifest_path = extract_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        data_path = extract_dir / "data.json"
        data_json: dict = json.loads(data_path.read_text(encoding="utf-8"))

        # ── Restore uploads ───────────────────────────────────────────────
        restored_uploads = False
        src_uploads = extract_dir / "uploads"
        if src_uploads.exists():
            if UPLOADS_ROOT.exists():
                # Back-up current uploads before overwriting
                bk_path = UPLOADS_ROOT.parent / f"uploads_bk_{_now_utc().strftime('%Y%m%d%H%M%S')}"
                shutil.copytree(UPLOADS_ROOT, bk_path)
            shutil.copytree(src_uploads, UPLOADS_ROOT, dirs_exist_ok=True)
            restored_uploads = True

        # ── Restore database (additive, idempotent) ───────────────────────
        # Recreate missing rows from data.json. Wrapped in its own try so a
        # failure here rolls back the DB transaction (leaving the just-copied
        # uploads in place) and is surfaced to the operator instead of being
        # silently swallowed.
        database_import: dict | None = None
        database_error: str | None = None
        try:
            database_import = _import_data_json(db, data_json)
            db.commit()
        except Exception as exc:  # noqa: BLE001 — report, don't crash mid-restore
            db.rollback()
            database_error = str(exc)
            logger.exception("Database restore import failed")

        # Audit logging commits on its own session; do it only after the import
        # is durably committed so a logging hiccup can't roll back the restore.
        if database_error is None and database_import is not None:
            write_audit_log(
                db,
                action="backup.restore",
                actor=current_user,
                resource_type="backup",
                resource_id=manifest.get("backup_id", "unknown"),
                resource_name=file.filename or "unknown.zip",
                detail={
                    "schema_version": manifest.get("schema_version", "unknown"),
                    "restored_uploads": restored_uploads,
                    "database_import": database_import,
                },
            )

        # ── Record restore event in history ───────────────────────────────
        restore_record = {
            "backup_id": manifest.get("backup_id", "unknown"),
            "action": "restore",
            "file_name": file.filename or "unknown.zip",
            "schema_version": manifest.get("schema_version", "unknown"),
            "original_created_at": manifest.get("created_at"),
            "restored_at": _now_utc().isoformat(),
            "operator_uid": current_user.uid,
            "operator_nickname": current_user.nickname,
            "counts": manifest.get("counts"),
            "restored_uploads": restored_uploads,
            "database_import": database_import,
            "database_error": database_error,
            "warnings": report["warnings"],
        }
        try:
            _append_history(restore_record)
        except Exception:
            logger.warning("Failed to write restore history record", exc_info=True)

        if database_error is not None:
            message = (
                "媒体文件已恢复，但数据库导入失败，数据库未改动（已回滚）。"
                f"错误：{database_error}"
            )
        elif database_import is not None:
            message = "备份恢复完成：媒体文件已更新，数据库内容已按业务键补齐（已存在的条目自动跳过）。"
        else:
            message = "备份恢复完成：媒体文件已更新（备份中无数据库内容）。"

        return {
            "ok": database_error is None,
            "message": message,
            "restored_uploads": restored_uploads,
            "database_import": database_import,
            "database_error": database_error,
            "warnings": report["warnings"],
            "manifest": manifest,
            "data_summary": data_json.get("meta", {}),
        }

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
