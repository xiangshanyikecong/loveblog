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

"""Background health monitor: periodic snapshots + degradation alerts +
auto-remediation of orphaned temp files.

The live ``GET /health/system`` endpoint stays stateless and on-demand. This
module is the *only* writer of ``HealthSnapshot`` rows. It runs on a fixed
interval so the history endpoint has a continuous timeline and so a partner
gets a notification the moment a component degrades - without anyone having
to open the admin page.
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.health_snapshot import HealthSnapshot
from app.models.user import User, UserRole
from app.services.notifications import create_notification

logger = logging.getLogger(__name__)

# Interval between background snapshots. 5 minutes is granular enough to
# catch a degradation promptly without hammering the DB / Redis.
MONITOR_INTERVAL_SECONDS = 300

# Only auto-remediate when disk usage is at/above this threshold so we never
# touch the filesystem when the system is healthy.
DISK_REMEDIATE_THRESHOLD_PERCENT = 80

# Temp files / dirs younger than this are left alone so an in-flight backup
# or upload isn't yanked out from under the writer.
TEMP_AGE_SECONDS = 3600  # 1 hour

# System temp-dir prefixes this app creates (see app/api/v1/export.py).
_TEMP_PREFIXES = ("love_auto_backup_", "love_backup_", "love_restore_")

# Max snapshots to keep. Older rows are pruned each tick so the table stays
# bounded - 288 rows = 24h at 5-minute cadence.
MAX_SNAPSHOTS = 288


def _run_all_checks(db: Session) -> list[dict[str, Any]]:
    """Run every component check and return plain-dict results.

    Reuses the same check functions as the live endpoint so the persisted
    snapshots are identical to what an admin would see on demand.
    """
    from app.api.v1.health import _available_component_checks

    checks: list[dict[str, Any]] = []
    for component, factory in _available_component_checks(db).items():
        result = factory()
        checks.append(
            {
                "component": result.component,
                "status": result.status,
                "message": result.message,
                "response_time_ms": result.response_time_ms,
            }
        )
    return checks


def _overall_status(checks: list[dict[str, Any]]) -> str:
    has_error = any(c.get("status") == "error" for c in checks)
    has_warning = any(c.get("status") == "warning" for c in checks)
    if has_error:
        return "unhealthy"
    if has_warning:
        return "degraded"
    return "healthy"


def _score(checks: list[dict[str, Any]]) -> int:
    from app.api.v1.health import _calculate_health_score, _generate_recommendations  # noqa: F401

    # Reuse the canonical scoring so the persisted score matches the live one.
    from app.schemas.health import SystemHealthCheck

    typed = [SystemHealthCheck(**c) for c in checks]
    return _calculate_health_score(typed)


def auto_remediate(checks: list[dict[str, Any]]) -> str:
    """Clean known-safe orphaned temp files when disk is high.

    Returns a short human-readable note describing what was cleaned (or "" when
    no action was taken). Designed to be conservative: only files/dirs this app
    itself creates, only when disk usage is at/above the threshold, and only
    artifacts older than ``TEMP_AGE_SECONDS`` so in-flight work is untouched.
    """
    disk_check = next((c for c in checks if c.get("component") == "disk_space"), None)
    if not disk_check:
        return ""
    status = disk_check.get("status")
    if status not in ("warning", "error"):
        return ""

    backend_root = Path(__file__).resolve().parents[2]
    uploads_dir = backend_root / "uploads"
    now = time.time()
    removed_files = 0
    removed_bytes = 0

    # 1. Orphaned .tmp files under uploads/ (e.g. interrupted backup writes).
    if uploads_dir.exists():
        for tmp_file in uploads_dir.rglob("*.tmp"):
            try:
                if now - tmp_file.stat().st_mtime < TEMP_AGE_SECONDS:
                    continue
                size = tmp_file.stat().st_size
                tmp_file.unlink(missing_ok=True)
                removed_files += 1
                removed_bytes += size
            except OSError:
                # Permission / busy file - skip rather than crash the monitor.
                continue

        # 2. The health-check probe file itself, if it somehow lingers.
        probe = uploads_dir / ".health_check"
        if probe.exists():
            try:
                if now - probe.stat().st_mtime < TEMP_AGE_SECONDS:
                    pass
                else:
                    probe.unlink(missing_ok=True)
                    removed_files += 1
            except OSError:
                pass

    # 3. Orphaned temp dirs this app creates in the system temp folder.
    sys_tmp = Path(tempfile.gettempdir())
    if sys_tmp.exists():
        for entry in sys_tmp.iterdir():
            if not entry.is_dir():
                continue
            if not any(entry.name.startswith(p) for p in _TEMP_PREFIXES):
                continue
            try:
                if now - entry.stat().st_mtime < TEMP_AGE_SECONDS:
                    continue
                # Best-effort recursive size count before removal.
                dir_bytes = 0
                for f in entry.rglob("*"):
                    try:
                        if f.is_file():
                            dir_bytes += f.stat().st_size
                    except OSError:
                        pass
                import shutil

                shutil.rmtree(entry, ignore_errors=True)
                removed_files += 1
                removed_bytes += dir_bytes
            except OSError:
                continue

    if not removed_files:
        return ""

    mb = removed_bytes / (1024 * 1024)
    if mb >= 1024:
        size_text = f"{mb / 1024:.1f}GB"
    else:
        size_text = f"{mb:.0f}MB"
    return f"自动清理了 {removed_files} 个临时文件/目录，释放 {size_text}"


def _maybe_alert(db: Session, prev: HealthSnapshot | None, curr: HealthSnapshot) -> None:
    """Notify both partners when overall status degrades.

    A healthy -> degraded/unhealthy or degraded -> unhealthy transition fires
    one notification per partner. Recovery is deliberately not alerted so the
    couple isn't pinged for transient blips that the monitor already cleaned up.
    """
    if prev is None:
        return
    severity = {"healthy": 0, "degraded": 1, "unhealthy": 2}
    prev_sev = severity.get(prev.overall_status, 0)
    curr_sev = severity.get(curr.overall_status, 0)
    if curr_sev <= prev_sev:
        return

    # Find the worst component to mention in the body.
    worst = ""
    for c in curr.checks:
        if c.get("status") == "error":
            worst = c.get("message") or c.get("component") or ""
            break
    if not worst:
        for c in curr.checks:
            if c.get("status") == "warning":
                worst = c.get("message") or c.get("component") or ""
                break

    title = "系统健康度下降"
    body = f"当前状态：{curr.overall_status}（评分 {curr.health_score}）"
    if worst:
        body += f"\n{worst}"
    if curr.remediated and curr.remediation_note:
        body += f"\n{curr.remediation_note}"

    partners = (
        db.query(User)
        .filter(User.role.in_([UserRole.partner_a, UserRole.partner_b]), User.deleted_at.is_(None))
        .all()
    )
    # Dedupe by source so a flapping status doesn't spam - one alert per
    # degrade event until it recovers and degrades again (source_id rotates).
    for p in partners:
        create_notification(
            db,
            recipient=p,
            type="system.health_alert",
            title=title,
            body=body,
            link="/admin",
            source_type="health_alert",
            source_id=str(curr.id),
            dedupe=True,
            queue_delivery=True,
        )


def _prune_old_snapshots(db: Session) -> None:
    """Keep only the most recent ``MAX_SNAPSHOTS`` rows."""
    total = db.query(HealthSnapshot).count()
    if total <= MAX_SNAPSHOTS:
        return
    cutoff_row = (
        db.query(HealthSnapshot)
        .order_by(HealthSnapshot.created_at.desc())
        .offset(MAX_SNAPSHOTS)
        .first()
    )
    if cutoff_row is None:
        return
    db.query(HealthSnapshot).filter(
        HealthSnapshot.created_at < cutoff_row.created_at
    ).delete(synchronize_session=False)


def record_health_snapshot(db: Session) -> HealthSnapshot:
    """Run all checks, persist a snapshot, alert + auto-remediate as needed.

    Returns the freshly persisted snapshot. This is the single writer entry
    point used by both the background loop and the manual trigger endpoint.
    """
    checks = _run_all_checks(db)
    status = _overall_status(checks)
    score_val = _score(checks)

    # Auto-remediate BEFORE persisting so the snapshot records what we did.
    note = auto_remediate(checks)
    remediated = bool(note)

    snapshot = HealthSnapshot(
        overall_status=status,
        health_score=score_val,
        checks_json=json.dumps(checks, ensure_ascii=False),
        remediated=remediated,
        remediation_note=note,
    )
    db.add(snapshot)
    db.flush()  # populate snapshot.id for the alert's source_id

    prev = (
        db.query(HealthSnapshot)
        .filter(HealthSnapshot.id < snapshot.id)
        .order_by(HealthSnapshot.id.desc())
        .first()
    )
    _maybe_alert(db, prev, snapshot)

    _prune_old_snapshots(db)
    db.commit()
    return snapshot


async def health_monitor_loop() -> None:
    """Background coroutine: record a snapshot every ``MONITOR_INTERVAL_SECONDS``.

    Failures are logged and swallowed so a transient error in one tick never
    kills the monitor permanently.
    """
    logger.info("Started health monitor background task (interval=%ss)", MONITOR_INTERVAL_SECONDS)
    while True:
        try:
            db = SessionLocal()
            try:
                record_health_snapshot(db)
            finally:
                db.close()
        except Exception:
            logger.exception("Health monitor tick failed.")
        await asyncio.sleep(MONITOR_INTERVAL_SECONDS)
