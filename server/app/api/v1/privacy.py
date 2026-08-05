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

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.album import Album
from app.models.article import Article
from app.models.audit_log import AuditLog
from app.models.canvas_artwork import CanvasArtwork
from app.models.capsule import Capsule
from app.models.chat_key import ChatKey
from app.models.chat_message import ChatMessage
from app.models.checkin import CheckIn
from app.models.cottage_plan import CottagePlan
from app.models.cottage_reminder import CottageReminder
from app.models.coupon import Coupon
from app.models.daily_question import DailyQuestion, DailyQuestionAnswer
from app.models.event import Event
from app.models.game_match import GameMatch
from app.models.ledger_entry import LedgerEntry
from app.models.listen_history import ListenHistoryEntry
from app.models.listen_local_track import ListenLocalTrack
from app.models.message import Message
from app.models.moment import Moment
from app.models.mood import MoodCheckin
from app.models.period_cycle import PeriodCycle
from app.models.user import User
from app.models.vault import VaultEntry, VaultMeta
from app.models.watch import WatchSource
from app.models.wish import Wish
from app.schemas.privacy import (
    PrivacyAccessCounts,
    PrivacyAccountSnapshot,
    PrivacyActivityItem,
    PrivacyEncryptionStatus,
    PrivacyExportPolicy,
    PrivacyModuleSummary,
    PrivacyProtectionCounts,
    PrivacyRecoveryEventRequest,
    PrivacyRecoveryEventResponse,
    PrivacySummaryResponse,
)
from app.services.audit import write_audit_log
from app.services.visibility_policy import VisibilityLevel, VisibilityPolicy


router = APIRouter(prefix="/privacy", tags=["privacy"])


def _active_count(db: Session, model, deleted_column=None) -> int:
    query = db.query(model)
    if deleted_column is not None:
        query = query.filter(deleted_column.is_(None))
    return query.count()


def _access_bucket(level: VisibilityLevel) -> str:
    if level == VisibilityLevel.public:
        return "public"
    if level == VisibilityLevel.guest_viewable:
        return "signed_in"
    if level in {VisibilityLevel.partners_only, VisibilityLevel.encrypted}:
        return "partners"
    if level == VisibilityLevel.password_protected:
        return "password"
    return "author_only"


def _counts_from_levels(levels: list[VisibilityLevel]) -> PrivacyAccessCounts:
    counts = PrivacyAccessCounts()
    for level in levels:
        field = _access_bucket(level)
        setattr(counts, field, getattr(counts, field) + 1)
    return counts


def _protection(
    total: int,
    *,
    e2ee: int = 0,
    server_masked: int = 0,
) -> PrivacyProtectionCounts:
    return PrivacyProtectionCounts(
        end_to_end_encrypted=e2ee,
        server_readable=max(total - e2ee, 0),
        server_masked=server_masked,
    )


def _chat_message_is_e2ee(item: ChatMessage) -> bool:
    return bool(
        item.is_encrypted
        and item.iv
        and item.ciphertext
        and item.algo == "AES-GCM"
    )


def _module(
    *,
    key: str,
    label: str,
    levels: list[VisibilityLevel],
    manage_path: str,
    note: str,
    e2ee: int = 0,
    server_masked: int = 0,
) -> PrivacyModuleSummary:
    total = len(levels)
    return PrivacyModuleSummary(
        key=key,
        label=label,
        total=total,
        access=_counts_from_levels(levels),
        protection=_protection(total, e2ee=e2ee, server_masked=server_masked),
        manage_path=manage_path,
        note=note,
    )


def _private_cottage_count(db: Session) -> int:
    active_questions = db.query(DailyQuestion.id).filter(DailyQuestion.deleted_at.is_(None))
    answer_count = (
        db.query(DailyQuestionAnswer)
        .filter(DailyQuestionAnswer.question_id.in_(active_questions))
        .count()
    )
    return sum(
        (
            _active_count(db, CheckIn, CheckIn.deleted_at),
            _active_count(db, MoodCheckin),
            _active_count(db, DailyQuestion, DailyQuestion.deleted_at),
            answer_count,
            _active_count(db, CottagePlan, CottagePlan.deleted_at),
            _active_count(db, CottageReminder, CottageReminder.deleted_at),
            _active_count(db, Wish, Wish.deleted_at),
            _active_count(db, Coupon, Coupon.deleted_at),
            _active_count(db, LedgerEntry, LedgerEntry.deleted_at),
            _active_count(db, PeriodCycle, PeriodCycle.deleted_at),
            _active_count(db, WatchSource, WatchSource.deleted_at),
            _active_count(db, ListenHistoryEntry),
            _active_count(db, ListenLocalTrack, ListenLocalTrack.deleted_at),
            _active_count(db, GameMatch),
            _active_count(db, CanvasArtwork, CanvasArtwork.deleted_at),
        )
    )


def _recent_activity(db: Session) -> list[PrivacyActivityItem]:
    items = (
        db.query(AuditLog)
        .filter(
            or_(
                AuditLog.action.in_(("auth.login", "auth.logout", "content.access")),
                AuditLog.action.like("security.%"),
                AuditLog.action.like("backup.%"),
                AuditLog.action.like("privacy.%"),
            )
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(20)
        .all()
    )
    return [
        PrivacyActivityItem(
            log_id=item.log_id,
            action=item.action,
            result=item.result,
            actor=item.actor_nickname or item.actor_username,
            resource_type=item.resource_type,
            resource_name=item.resource_name or item.resource_id,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.get("/summary", response_model=PrivacySummaryResponse)
def get_privacy_summary(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PrivacySummaryResponse:
    ensure_partner(current_user)
    response.headers["Cache-Control"] = "no-store"

    articles = db.query(Article).filter(Article.deleted_at.is_(None)).all()
    albums = db.query(Album).filter(Album.deleted_at.is_(None)).all()
    events = db.query(Event).filter(Event.deleted_at.is_(None)).all()
    moments = db.query(Moment).filter(Moment.deleted_at.is_(None)).all()
    messages = db.query(Message).filter(Message.is_deleted.is_(False)).all()
    capsules = db.query(Capsule).filter(Capsule.deleted_at.is_(None)).all()
    chat_messages = db.query(ChatMessage).filter(ChatMessage.deleted_at.is_(None)).all()
    vault_entries = db.query(VaultEntry).filter(VaultEntry.deleted_at.is_(None)).all()
    cottage_count = _private_cottage_count(db)

    modules = [
        _module(
            key="articles",
            label="文章",
            levels=[VisibilityPolicy.article_visibility(item) for item in articles],
            manage_path="/admin/articles",
            note="草稿按协作权限归入仅作者或双方可见。",
            server_masked=sum(1 for item in articles if item.is_encrypted),
        ),
        _module(
            key="albums",
            label="相册",
            levels=[VisibilityPolicy.album_visibility(item) for item in albums],
            manage_path="/admin/albums",
            note="媒体文件继承相册访问范围，不重复计数。",
            server_masked=sum(1 for item in albums if item.is_encrypted),
        ),
        _module(
            key="moments",
            label="时间轴",
            levels=[VisibilityPolicy.moment_visibility(item) for item in moments],
            manage_path="/admin/timeline",
            note="评论继承所属内容的访问范围。",
            server_masked=sum(
                1
                for item in moments
                if VisibilityPolicy.moment_visibility(item) == VisibilityLevel.encrypted
            ),
        ),
        _module(
            key="events",
            label="纪念日",
            levels=[VisibilityPolicy.event_visibility(item) for item in events],
            manage_path="/events",
            note="加密标记代表仅双方可见，正文仍由服务器处理。",
            server_masked=sum(
                1
                for item in events
                if VisibilityPolicy.event_visibility(item) == VisibilityLevel.encrypted
            ),
        ),
        _module(
            key="messages",
            label="留言",
            levels=[
                VisibilityLevel.public if item.is_public else VisibilityLevel.partners_only
                for item in messages
            ],
            manage_path="/admin/messages",
            note="非公开留言仅登录伴侣和留言者本人可见。",
        ),
        _module(
            key="capsules",
            label="时光胶囊",
            levels=[VisibilityLevel.partners_only] * len(capsules),
            manage_path="/admin/capsules",
            note="开启时间限制读取时机，不提供端到端加密。",
        ),
        _module(
            key="chat",
            label="悄悄话",
            levels=[VisibilityLevel.partners_only] * len(chat_messages),
            manage_path="/cottage/chat",
            note="仅标记为端到端加密的消息对服务器保持不可读。",
            e2ee=sum(1 for item in chat_messages if _chat_message_is_e2ee(item)),
        ),
        _module(
            key="vault",
            label="加密保险箱",
            levels=[VisibilityLevel.partners_only] * len(vault_entries),
            manage_path="/cottage/vault",
            note="条目始终以 AES-GCM 密文保存，服务器不持有口令。",
            e2ee=len(vault_entries),
        ),
        _module(
            key="cottage",
            label="小屋私密数据",
            levels=[VisibilityLevel.partners_only] * cottage_count,
            manage_path="/cottage",
            note="含报备、心情、问答、计划、账本、健康记录与互动历史。",
        ),
    ]

    totals = PrivacyAccessCounts()
    protection = PrivacyProtectionCounts()
    for item in modules:
        for field in PrivacyAccessCounts.model_fields:
            setattr(totals, field, getattr(totals, field) + getattr(item.access, field))
        for field in PrivacyProtectionCounts.model_fields:
            setattr(
                protection,
                field,
                getattr(protection, field) + getattr(item.protection, field),
            )

    chat_key = db.query(ChatKey).order_by(ChatKey.id.asc()).first()
    vault_meta = db.query(VaultMeta).filter(VaultMeta.id == 1).first()
    encryption = [
        PrivacyEncryptionStatus(
            scope="chat",
            label="悄悄话",
            initialized=chat_key is not None,
            algorithm=chat_key.algo if chat_key else None,
            kdf=chat_key.kdf_hash if chat_key else None,
            iterations=chat_key.iterations if chat_key else None,
            item_count=len(chat_messages),
            encrypted_count=sum(1 for item in chat_messages if _chat_message_is_e2ee(item)),
            manage_path="/cottage/chat",
        ),
        PrivacyEncryptionStatus(
            scope="vault",
            label="加密保险箱",
            initialized=vault_meta is not None,
            algorithm=vault_meta.algo if vault_meta else None,
            kdf=vault_meta.kdf_hash if vault_meta else None,
            iterations=vault_meta.iterations if vault_meta else None,
            item_count=len(vault_entries),
            encrypted_count=len(vault_entries),
            manage_path="/cottage/vault",
        ),
    ]

    return PrivacySummaryResponse(
        generated_at=datetime.now(timezone.utc),
        totals=totals,
        protection=protection,
        modules=modules,
        encryption=encryption,
        export_policy=PrivacyExportPolicy(
            archive_encrypted=False,
            uploads_included=True,
            server_readable_content_plaintext=True,
            end_to_end_content_plaintext=False,
            account_password_hashes_included=False,
            encryption_passphrases_included=False,
            push_credentials_included=True,
        ),
        account=PrivacyAccountSnapshot(
            uid=current_user.uid,
            nickname=current_user.nickname,
            last_login_at=current_user.last_login_at,
            last_login_ip=current_user.last_login_ip,
            password_changed_at=current_user.password_changed_at,
            session_version=current_user.session_version,
        ),
        recent_activity=_recent_activity(db),
        activity_scope=(
            "记录登录、会话与密码操作、备份恢复、密钥变更、恢复包事件，"
            "以及访客通过内容密码完成的访问；普通页面浏览不记录。"
        ),
    )


@router.post("/recovery-events", response_model=PrivacyRecoveryEventResponse)
def record_recovery_event(
    payload: PrivacyRecoveryEventRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PrivacyRecoveryEventResponse:
    ensure_partner(current_user)
    response.headers["Cache-Control"] = "no-store"
    action = {
        "kit_created": "privacy.recovery_kit_created",
        "kit_recovered": "privacy.recovery_kit_recovered",
    }[payload.event]
    log = write_audit_log(
        db,
        action=action,
        actor=current_user,
        resource_type="encryption_key",
        resource_id=payload.scope,
        detail={"scope": payload.scope, "contains_secret": False},
    )
    return PrivacyRecoveryEventResponse(recorded=log is not None)
