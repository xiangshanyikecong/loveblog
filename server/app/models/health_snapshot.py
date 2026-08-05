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

"""Persisted health-check snapshots for trend / alert / auto-remediation.

Each row is a point-in-time roll-up of the 6 component checks. The live
``GET /health/system`` endpoint stays stateless; this table is only written
by the background ``health_monitor_loop`` and read by the history endpoint.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HealthSnapshot(Base):
    __tablename__ = "health_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # "healthy" | "degraded" | "unhealthy" - mirrors SystemHealthResponse.
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    health_score: Mapped[int] = mapped_column(Integer, nullable=False)
    # JSON-serialised list of SystemHealthCheck dicts. Kept as Text so the
    # table is portable across PostgreSQL / SQLite without JSON column drama.
    checks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # True when the auto-remediator took action on this snapshot (e.g. cleaned
    # temp files because disk_space was warning/error). Lets the UI show a
    # "已自动清理" badge and avoids double-cleaning on the next tick.
    remediated: Mapped[bool] = mapped_column(
        Integer, default=0, nullable=False
    )
    # Optional human-readable summary of what the remediator did (or "" when
    # no action was needed). Bounded so a runaway cleanup log can't blow up
    # the row.
    remediation_note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    @property
    def checks(self) -> list[dict[str, Any]]:
        if not self.checks_json:
            return []
        try:
            raw = json.loads(self.checks_json)
        except (TypeError, ValueError):
            return []
        return raw if isinstance(raw, list) else []
