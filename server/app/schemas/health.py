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

from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    app: str
    database: str
    redis: str


class SystemHealthCheck(BaseModel):
    """系统健康检查详细信息"""
    component: str
    status: str  # ok, warning, error
    message: str | None = None
    response_time_ms: float | None = None


class SystemHealthResponse(BaseModel):
    """系统健康检查响应"""
    overall_status: str  # healthy, degraded, unhealthy
    health_score: int  # 0-100
    checks: list[SystemHealthCheck]
    recommendations: list[str]
    uptime_seconds: float | None = None
    timestamp: str


class HealthSnapshotItem(BaseModel):
    """One historical health snapshot for the trend / history endpoint."""

    id: int
    overall_status: str
    health_score: int
    remediated: bool
    remediation_note: str
    created_at: datetime


class HealthHistoryResponse(BaseModel):
    """Historical health snapshots, oldest-first for easy charting."""

    items: list[HealthSnapshotItem]
    total: int


class HealthRemediationResponse(BaseModel):
    """Result of a manual (on-demand) remediation trigger."""

    remediated: bool
    note: str
    snapshot: SystemHealthResponse
