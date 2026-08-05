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

"""Best-effort external delivery for in-app notifications."""
from __future__ import annotations

import json
import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

from app.core.config import settings
from app.models.fcm_device_token import FcmDeviceToken
from app.models.push_subscription import PushSubscription
from app.models.notification import Notification
from app.models.user import User, UserRole

try:
    from pywebpush import WebPushException, webpush
except ImportError:  # pragma: no cover - covered indirectly once dependency is installed
    WebPushException = Exception
    webpush = None

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except ImportError:  # pragma: no cover - optional deployment dependency
    firebase_admin = None
    credentials = None
    messaging = None


logger = logging.getLogger(__name__)

_SCHEDULED_TYPES = frozenset(
    {
        "event.reminder",
        "cottage_reminder.due",
        "capsule.open",
    }
)
_PENDING_NOTIFICATION_OBJECTS_KEY = "pending_notification_objects"
_PENDING_NOTIFICATION_PAYLOADS_KEY = "pending_notification_payloads"
_PENDING_NOTIFICATION_PREPARED_KEY = "pending_notification_prepared"
DELIVERY_STATUS_NOT_QUEUED = "not_queued"
DELIVERY_STATUS_PENDING = "pending"
DELIVERY_STATUS_DELIVERED = "delivered"
DELIVERY_STATUS_FAILED = "failed"
_RETRYABLE_DELIVERY_STATUSES = frozenset({DELIVERY_STATUS_PENDING, DELIVERY_STATUS_FAILED})
_MAX_DELIVERY_ERROR_LENGTH = 500
_FCM_APP_NAME = "love-node-fcm"
_FCM_APP = None


@dataclass(slots=True)
class NotificationDeliveryPayload:
    nid: str | None
    recipient_id: int
    type: str
    title: str
    body: str | None
    link: str | None
    source_type: str | None
    source_id: str | None

    def to_push_data(self) -> dict[str, str | None]:
        return {
            "nid": self.nid,
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "link": self.link,
            "source_type": self.source_type,
            "source_id": self.source_id,
        }


def queue_notification_delivery(db: Session, notification: Notification) -> None:
    notification.delivery_status = DELIVERY_STATUS_PENDING
    notification.delivery_last_error = None
    notification.delivery_completed_at = None
    pending: list[Notification] = db.info.setdefault(_PENDING_NOTIFICATION_OBJECTS_KEY, [])
    if notification not in pending:
        pending.append(notification)


def _snapshot_notification(notification: Notification) -> NotificationDeliveryPayload:
    return NotificationDeliveryPayload(
        nid=notification.nid,
        recipient_id=notification.recipient_id,
        type=notification.type,
        title=notification.title,
        body=notification.body,
        link=notification.link,
        source_type=notification.source_type,
        source_id=notification.source_id,
    )


def _clear_session_delivery_state(session: Session) -> None:
    session.info.pop(_PENDING_NOTIFICATION_OBJECTS_KEY, None)
    session.info.pop(_PENDING_NOTIFICATION_PAYLOADS_KEY, None)
    session.info.pop(_PENDING_NOTIFICATION_PREPARED_KEY, None)


def _normalized_delivery_error(error_message: str | None) -> str | None:
    if error_message is None:
        return None
    normalized = error_message.strip()
    if not normalized:
        return None
    return normalized[:_MAX_DELIVERY_ERROR_LENGTH]


def _mark_delivery_outcome(
    notification: Notification,
    *,
    succeeded: bool,
    error_message: str | None = None,
) -> None:
    attempt_time = datetime.now(timezone.utc)
    notification.delivery_attempts += 1
    notification.delivery_last_attempt_at = attempt_time
    if succeeded:
        notification.delivery_status = DELIVERY_STATUS_DELIVERED
        notification.delivery_last_error = None
        notification.delivery_completed_at = attempt_time
        return

    notification.delivery_status = DELIVERY_STATUS_FAILED
    notification.delivery_last_error = _normalized_delivery_error(error_message)
    notification.delivery_completed_at = None


def _persist_delivery_outcome(
    db: Session,
    payload: NotificationDeliveryPayload,
    *,
    succeeded: bool,
    error_message: str | None = None,
) -> None:
    if not payload.nid:
        return

    try:
        notification = db.query(Notification).filter(Notification.nid == payload.nid).first()
        if notification is None:
            return
        _mark_delivery_outcome(
            notification,
            succeeded=succeeded,
            error_message=error_message,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to persist delivery outcome for notification %s",
            payload.nid,
        )


def _retryable_delivery_payloads(*, limit: int = 100) -> list[NotificationDeliveryPayload]:
    db = SessionLocal()
    try:
        notifications = (
            db.query(Notification)
            .filter(Notification.delivery_status.in_(_RETRYABLE_DELIVERY_STATUSES))
            .order_by(Notification.created_at.asc(), Notification.id.asc())
            .limit(limit)
            .all()
        )
        return [_snapshot_notification(notification) for notification in notifications]
    finally:
        db.close()


def retry_pending_notification_deliveries(*, limit: int = 100) -> int:
    payloads = _retryable_delivery_payloads(limit=limit)
    if not payloads:
        return 0
    deliver_notification_payloads(payloads)
    return len(payloads)


@event.listens_for(Session, "after_flush_postexec")
def _prepare_pending_notification_payloads(session: Session, _flush_context) -> None:
    pending: list[Notification] = session.info.get(_PENDING_NOTIFICATION_OBJECTS_KEY, [])
    if not pending:
        return

    payloads: list[NotificationDeliveryPayload] = session.info.setdefault(
        _PENDING_NOTIFICATION_PAYLOADS_KEY,
        [],
    )
    prepared: set[str] = session.info.setdefault(_PENDING_NOTIFICATION_PREPARED_KEY, set())
    remaining: list[Notification] = []
    for notification in pending:
        if not notification.nid:
            remaining.append(notification)
            continue
        if notification.nid in prepared:
            continue
        payloads.append(_snapshot_notification(notification))
        prepared.add(notification.nid)

    if remaining:
        session.info[_PENDING_NOTIFICATION_OBJECTS_KEY] = remaining
    else:
        session.info.pop(_PENDING_NOTIFICATION_OBJECTS_KEY, None)


@event.listens_for(Session, "after_commit")
def _deliver_pending_notifications_after_commit(session: Session) -> None:
    payloads: list[NotificationDeliveryPayload] = list(
        session.info.get(_PENDING_NOTIFICATION_PAYLOADS_KEY, [])
    )
    _clear_session_delivery_state(session)
    if not payloads:
        return
    try:
        deliver_notification_payloads(payloads)
    except Exception:
        logger.exception("Failed to deliver committed notifications")


@event.listens_for(Session, "after_rollback")
def _clear_pending_notifications_after_rollback(session: Session) -> None:
    _clear_session_delivery_state(session)


def _recipient_email(recipient: User) -> str | None:
    if recipient.role == UserRole.partner_a:
        return settings.notification_push_email_partner_a or None
    if recipient.role == UserRole.partner_b:
        return settings.notification_push_email_partner_b or None
    return None


def _send_email(*, to_addr: str, subject: str, body: str) -> None:
    if not settings.notification_smtp_host:
        logger.warning("Email push skipped: NOTIFICATION_SMTP_HOST is not configured.")
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.notification_smtp_from or settings.notification_smtp_user or "noreply@love-node"
    message["To"] = to_addr
    message.set_content(body)

    with smtplib.SMTP(settings.notification_smtp_host, settings.notification_smtp_port, timeout=30) as smtp:
        if settings.notification_smtp_use_tls:
            smtp.starttls()
        if settings.notification_smtp_user:
            smtp.login(settings.notification_smtp_user, settings.notification_smtp_password)
        smtp.send_message(message)


def _deliver_email(recipient: User, payload: NotificationDeliveryPayload) -> None:
    if payload.type not in _SCHEDULED_TYPES:
        return
    if not settings.notification_push_email_enabled:
        return

    to_addr = _recipient_email(recipient)
    if not to_addr:
        return

    subject = payload.title
    lines = [payload.title]
    if payload.body:
        lines.append("")
        lines.append(payload.body)
    if payload.link:
        lines.extend(["", f"打开：{payload.link}"])
    _send_email(to_addr=to_addr, subject=subject, body="\n".join(lines))


def _push_subscription_info(item: PushSubscription) -> dict[str, object]:
    return {
        "endpoint": item.endpoint,
        "keys": {
            "p256dh": item.p256dh,
            "auth": item.auth,
        },
    }


def _web_push_enabled() -> bool:
    return settings.web_push_enabled and settings.web_push_configured and webpush is not None


def web_push_runtime_ready() -> bool:
    return _web_push_enabled()


def _fcm_enabled() -> bool:
    return settings.fcm_push_enabled and settings.fcm_configured and firebase_admin is not None


def fcm_runtime_ready() -> bool:
    return _fcm_app() is not None and messaging is not None


def _fcm_app():
    global _FCM_APP
    if not _fcm_enabled():
        return None
    if _FCM_APP is not None:
        return _FCM_APP

    try:
        _FCM_APP = firebase_admin.get_app(_FCM_APP_NAME)
        return _FCM_APP
    except ValueError:
        pass

    try:
        cred_payload = settings.fcm_service_account_json.strip()
        if cred_payload:
            cred = credentials.Certificate(json.loads(cred_payload))
        else:
            cred = credentials.Certificate(settings.fcm_service_account_file.strip())
        _FCM_APP = firebase_admin.initialize_app(cred, name=_FCM_APP_NAME)
        return _FCM_APP
    except Exception:
        logger.exception("FCM push initialization failed")
        return None


def _mark_push_failure(item: PushSubscription, *, deactivate: bool) -> None:
    item.fail_count += 1
    if deactivate:
        item.is_active = False


def _mark_fcm_failure(item: FcmDeviceToken, *, deactivate: bool) -> None:
    item.fail_count += 1
    if deactivate:
        item.is_active = False


def _deliver_web_push(
    db: Session,
    recipient: User,
    payload: NotificationDeliveryPayload,
) -> None:
    if not _web_push_enabled():
        return

    subscriptions = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_id == recipient.id,
            PushSubscription.is_active.is_(True),
        )
        .all()
    )
    if not subscriptions:
        return

    vapid_claims = {"sub": settings.web_push_subject}
    data = json.dumps(payload.to_push_data(), ensure_ascii=False)
    needs_commit = False
    failed_sids: list[str] = []
    for item in subscriptions:
        try:
            webpush(
                subscription_info=_push_subscription_info(item),
                data=data,
                vapid_private_key=settings.web_push_vapid_private_key,
                vapid_claims=vapid_claims,
            )
            item.fail_count = 0
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            _mark_push_failure(item, deactivate=status_code in {404, 410})
            needs_commit = True
            failed_sids.append(item.sid)
            logger.warning(
                "Web push delivery failed for subscription %s with status %s",
                item.sid,
                status_code,
            )
        except Exception:
            _mark_push_failure(item, deactivate=False)
            needs_commit = True
            failed_sids.append(item.sid)
            logger.exception("Web push delivery crashed for subscription %s", item.sid)

    if needs_commit:
        db.commit()
    if failed_sids:
        raise RuntimeError(f"web push failed for {len(failed_sids)} subscription(s)")


def _fcm_data(payload: NotificationDeliveryPayload) -> dict[str, str]:
    return {
        key: "" if value is None else str(value)
        for key, value in payload.to_push_data().items()
    }


def _deliver_fcm_push(
    db: Session,
    recipient: User,
    payload: NotificationDeliveryPayload,
) -> None:
    app = _fcm_app()
    if app is None or messaging is None:
        return

    tokens = (
        db.query(FcmDeviceToken)
        .filter(
            FcmDeviceToken.user_id == recipient.id,
            FcmDeviceToken.is_active.is_(True),
        )
        .all()
    )
    if not tokens:
        return

    needs_commit = False
    failed_tids: list[str] = []
    data = _fcm_data(payload)
    android = messaging.AndroidConfig(priority="high")
    for item in tokens:
        try:
            message = messaging.Message(
                token=item.token,
                data=data,
                android=android,
            )
            messaging.send(message, app=app)
            item.fail_count = 0
        except Exception as exc:
            deactivate = exc.__class__.__name__ in {
                "UnregisteredError",
                "SenderIdMismatchError",
                "InvalidArgumentError",
            }
            _mark_fcm_failure(item, deactivate=deactivate)
            needs_commit = True
            failed_tids.append(item.tid)
            logger.warning(
                "FCM delivery failed for token %s: %s",
                item.tid,
                exc.__class__.__name__,
            )

    if needs_commit:
        db.commit()
    if failed_tids:
        raise RuntimeError(f"FCM push failed for {len(failed_tids)} device(s)")


def deliver_notification_payload(
    db: Session,
    payload: NotificationDeliveryPayload,
) -> None:
    recipient = db.query(User).filter(User.id == payload.recipient_id).first()
    if recipient is None:
        return

    _deliver_email(recipient, payload)
    _deliver_web_push(db, recipient, payload)
    _deliver_fcm_push(db, recipient, payload)


def deliver_notification_payloads(payloads: list[NotificationDeliveryPayload]) -> None:
    if not payloads:
        return

    db = SessionLocal()
    try:
        for payload in payloads:
            try:
                deliver_notification_payload(db, payload)
            except Exception as exc:
                db.rollback()
                _persist_delivery_outcome(
                    db,
                    payload,
                    succeeded=False,
                    error_message=str(exc) or exc.__class__.__name__,
                )
                logger.exception(
                    "Failed to deliver notification %s to external channels",
                    payload.nid,
                )
            else:
                _persist_delivery_outcome(db, payload, succeeded=True)
    finally:
        db.close()


def deliver_scheduled_notification(db: Session, notification: Notification) -> None:
    deliver_notification_payload(db, _snapshot_notification(notification))


def deliver_scheduled_notifications(db: Session, notifications: list[Notification]) -> None:
    for notification in notifications:
        deliver_scheduled_notification(db, notification)
