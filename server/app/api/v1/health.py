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

import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psutil
import redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import ensure_partner, get_current_user

from app.core.config import settings
from app.db.session import get_db
from app.models.health_snapshot import HealthSnapshot
from app.models.user import User
from app.schemas.health import (
    HealthHistoryResponse,
    HealthRemediationResponse,
    HealthResponse,
    HealthSnapshotItem,
    SystemHealthCheck,
    SystemHealthResponse,
)


router = APIRouter(tags=["health"])

# 记录启动时间
START_TIME = time.time()
HealthCheckFactory = Callable[[], SystemHealthCheck]


def _check_database(db: Session) -> SystemHealthCheck:
    """检查数据库连接"""
    start = time.time()
    try:
        db.execute(text("SELECT 1"))
        response_time = (time.time() - start) * 1000

        if response_time > 1000:
            return SystemHealthCheck(
                component="database",
                status="warning",
                message=f"数据库响应较慢 ({response_time:.0f}ms)",
                response_time_ms=response_time
            )

        return SystemHealthCheck(
            component="database",
            status="ok",
            message="数据库连接正常",
            response_time_ms=response_time
        )
    except Exception as e:
        return SystemHealthCheck(
            component="database",
            status="error",
            message=f"数据库连接失败: {str(e)}",
            response_time_ms=(time.time() - start) * 1000
        )


def _check_redis() -> SystemHealthCheck:
    """检查 Redis 连接"""
    start = time.time()
    try:
        client = redis.Redis.from_url(settings.resolved_redis_url, socket_timeout=2)
        client.ping()
        response_time = (time.time() - start) * 1000

        if response_time > 500:
            return SystemHealthCheck(
                component="redis",
                status="warning",
                message=f"Redis 响应较慢 ({response_time:.0f}ms)",
                response_time_ms=response_time
            )

        return SystemHealthCheck(
            component="redis",
            status="ok",
            message="Redis 连接正常",
            response_time_ms=response_time
        )
    except Exception as e:
        return SystemHealthCheck(
            component="redis",
            status="error",
            message=f"Redis 连接失败: {str(e)}",
            response_time_ms=(time.time() - start) * 1000
        )


def _check_disk_space() -> SystemHealthCheck:
    """检查磁盘空间"""
    try:
        disk = psutil.disk_usage('/')
        percent_used = disk.percent

        if percent_used > 90:
            return SystemHealthCheck(
                component="disk_space",
                status="error",
                message=f"磁盘空间严重不足 ({percent_used:.1f}% 已使用)"
            )
        elif percent_used > 80:
            return SystemHealthCheck(
                component="disk_space",
                status="warning",
                message=f"磁盘空间不足 ({percent_used:.1f}% 已使用)"
            )

        return SystemHealthCheck(
            component="disk_space",
            status="ok",
            message=f"磁盘空间充足 ({percent_used:.1f}% 已使用)"
        )
    except Exception as e:
        return SystemHealthCheck(
            component="disk_space",
            status="warning",
            message=f"无法检查磁盘空间: {str(e)}"
        )


def _check_memory() -> SystemHealthCheck:
    """检查内存使用"""
    try:
        memory = psutil.virtual_memory()
        percent_used = memory.percent

        if percent_used > 90:
            return SystemHealthCheck(
                component="memory",
                status="error",
                message=f"内存使用过高 ({percent_used:.1f}% 已使用)"
            )
        elif percent_used > 80:
            return SystemHealthCheck(
                component="memory",
                status="warning",
                message=f"内存使用较高 ({percent_used:.1f}% 已使用)"
            )

        return SystemHealthCheck(
            component="memory",
            status="ok",
            message=f"内存使用正常 ({percent_used:.1f}% 已使用)"
        )
    except Exception as e:
        return SystemHealthCheck(
            component="memory",
            status="warning",
            message=f"无法检查内存: {str(e)}"
        )


def _check_cpu() -> SystemHealthCheck:
    """检查 CPU 使用"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)

        if cpu_percent > 90:
            return SystemHealthCheck(
                component="cpu",
                status="error",
                message=f"CPU 使用过高 ({cpu_percent:.1f}%)"
            )
        elif cpu_percent > 80:
            return SystemHealthCheck(
                component="cpu",
                status="warning",
                message=f"CPU 使用较高 ({cpu_percent:.1f}%)"
            )

        return SystemHealthCheck(
            component="cpu",
            status="ok",
            message=f"CPU 使用正常 ({cpu_percent:.1f}%)"
        )
    except Exception as e:
        return SystemHealthCheck(
            component="cpu",
            status="warning",
            message=f"无法检查 CPU: {str(e)}"
        )


def _check_uploads_directory() -> SystemHealthCheck:
    """检查上传目录"""
    try:
        backend_root = Path(__file__).resolve().parents[3]
        uploads_dir = backend_root / "uploads"

        if not uploads_dir.exists():
            return SystemHealthCheck(
                component="uploads_directory",
                status="warning",
                message="上传目录不存在，将在首次上传时创建"
            )

        # 检查是否可写
        test_file = uploads_dir / ".health_check"
        try:
            test_file.touch()
            test_file.unlink()
            return SystemHealthCheck(
                component="uploads_directory",
                status="ok",
                message="上传目录可写"
            )
        except Exception:
            return SystemHealthCheck(
                component="uploads_directory",
                status="error",
                message="上传目录不可写，请检查权限"
            )
    except Exception as e:
        return SystemHealthCheck(
            component="uploads_directory",
            status="error",
            message=f"无法检查上传目录: {str(e)}"
        )


def _calculate_health_score(checks: list[SystemHealthCheck]) -> int:
    """计算健康评分 (0-100)"""
    if not checks:
        return 0

    total_score = 0
    weights = {
        "database": 25,
        "redis": 20,
        "disk_space": 15,
        "memory": 15,
        "cpu": 15,
        "uploads_directory": 10,
    }

    for check in checks:
        weight = weights.get(check.component, 10)

        if check.status == "ok":
            total_score += weight
        elif check.status == "warning":
            total_score += weight * 0.5
        # error 状态不加分

    return int(total_score)


def _generate_recommendations(checks: list[SystemHealthCheck]) -> list[str]:
    """生成优化建议"""
    recommendations = []

    for check in checks:
        if check.status == "error":
            if check.component == "database":
                recommendations.append("🔴 数据库连接失败，请检查数据库服务是否运行")
            elif check.component == "redis":
                recommendations.append("🔴 Redis 连接失败，请检查 Redis 服务是否运行")
            elif check.component == "disk_space":
                recommendations.append("🔴 磁盘空间严重不足，请清理不必要的文件")
            elif check.component == "memory":
                recommendations.append("🔴 内存使用过高，考虑重启服务或增加内存")
            elif check.component == "cpu":
                recommendations.append("🔴 CPU 使用过高，检查是否有异常进程")
            elif check.component == "uploads_directory":
                recommendations.append("🔴 上传目录不可写，请检查文件权限")

        elif check.status == "warning":
            if check.component == "database":
                recommendations.append("🟡 数据库响应较慢，考虑优化查询或增加资源")
            elif check.component == "redis":
                recommendations.append("🟡 Redis 响应较慢，检查网络或 Redis 配置")
            elif check.component == "disk_space":
                recommendations.append("🟡 磁盘空间不足，建议清理旧备份和日志文件")
            elif check.component == "memory":
                recommendations.append("🟡 内存使用较高，考虑优化应用或增加内存")
            elif check.component == "cpu":
                recommendations.append("🟡 CPU 使用较高，检查后台任务")

    if not recommendations:
        recommendations.append("✅ 系统运行良好，无需优化")

    return recommendations


def _determine_overall_status(checks: list[SystemHealthCheck]) -> str:
    """确定整体状态"""
    has_error = any(check.status == "error" for check in checks)
    has_warning = any(check.status == "warning" for check in checks)

    if has_error:
        return "unhealthy"
    elif has_warning:
        return "degraded"
    else:
        return "healthy"


def _available_component_checks(db: Session) -> dict[str, HealthCheckFactory]:
    return {
        "database": lambda: _check_database(db),
        "redis": _check_redis,
        "disk_space": _check_disk_space,
        "memory": _check_memory,
        "cpu": _check_cpu,
        "uploads_directory": _check_uploads_directory,
    }


def _parse_requested_components(
    components: str | None,
    *,
    available_components: dict[str, HealthCheckFactory],
) -> list[str]:
    if components is None:
        return list(available_components)

    requested_components: list[str] = []
    invalid_components: list[str] = []
    seen_components: set[str] = set()

    for raw_component in components.split(","):
        component = raw_component.strip()
        if not component or component in seen_components:
            continue
        seen_components.add(component)
        if component in available_components:
            requested_components.append(component)
        else:
            invalid_components.append(component)

    if invalid_components:
        supported = ", ".join(available_components)
        invalid = ", ".join(invalid_components)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported components: {invalid}. Supported values: {supported}",
        )

    if not requested_components:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one valid component must be provided.",
        )

    return requested_components


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """简单健康检查（用于容器健康检查）"""
    db_state = "ok"
    redis_state = "ok"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_state = "error"

    try:
        client = redis.Redis.from_url(settings.resolved_redis_url, socket_timeout=1)
        client.ping()
    except Exception:
        redis_state = "error"

    return HealthResponse(app="ok", database=db_state, redis=redis_state)


@router.get("/health/system", response_model=SystemHealthResponse)
def system_health_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    components: str | None = None,
    include_recommendations: bool = True,
    detailed: bool = True
) -> SystemHealthResponse:
    """
    详细的系统健康检查

    参数:
    - components: 指定要检查的组件，逗号分隔。可选值: database,redis,disk_space,memory,cpu,uploads_directory
                  例如: "database,redis" 只检查数据库和Redis
                  不指定则检查所有组件
    - include_recommendations: 是否包含优化建议，默认 True
    - detailed: 是否返回详细信息（响应时间等），默认 True
    """
    ensure_partner(current_user)

    available_components = _available_component_checks(db)
    requested_components = _parse_requested_components(
        components,
        available_components=available_components,
    )
    checks = [available_components[component]() for component in requested_components]

    # 如果不需要详细信息，清除响应时间
    if not detailed:
        for check in checks:
            check.response_time_ms = None

    health_score = _calculate_health_score(checks)
    overall_status = _determine_overall_status(checks)
    recommendations = _generate_recommendations(checks) if include_recommendations else []
    uptime = time.time() - START_TIME

    return SystemHealthResponse(
        overall_status=overall_status,
        health_score=health_score,
        checks=checks,
        recommendations=recommendations,
        uptime_seconds=uptime,
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@router.get("/health/system/history", response_model=HealthHistoryResponse)
def health_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    hours: int = Query(24, ge=1, le=168, description="回溯时长（小时），最长 7 天"),
    limit: int = Query(48, ge=1, le=288, description="最多返回的快照条数"),
) -> HealthHistoryResponse:
    """历史健康快照（由后台监控任务定期写入）。

    返回最近 ``hours`` 小时内的快照，按时间升序排列（便于直接绘制趋势图）。
    """
    ensure_partner(current_user)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        db.query(HealthSnapshot)
        .filter(HealthSnapshot.created_at >= since)
        .order_by(HealthSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()  # oldest-first for charting
    items = [
        HealthSnapshotItem(
            id=r.id,
            overall_status=r.overall_status,
            health_score=r.health_score,
            remediated=bool(r.remediated),
            remediation_note=r.remediation_note or "",
            created_at=r.created_at,
        )
        for r in rows
    ]
    return HealthHistoryResponse(items=items, total=len(items))


@router.post("/health/system/remediate", response_model=HealthRemediationResponse)
def remediate_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HealthRemediationResponse:
    """手动触发一次自动修复并立即记录快照。

    会运行所有组件检查，按需清理临时文件，并持久化一条快照（含清理说明）。
    用于管理员想立刻释放磁盘 / 确认系统状态时。
    """
    ensure_partner(current_user)
    from app.services.health_monitor import record_health_snapshot

    snapshot = record_health_snapshot(db)

    # Re-run a fresh live check for the response so the caller sees the
    # post-cleanup state immediately (the snapshot's own checks were captured
    # before/during cleanup).
    available_components = _available_component_checks(db)
    checks = [factory() for factory in available_components.values()]
    health_score = _calculate_health_score(checks)
    overall_status = _determine_overall_status(checks)
    recommendations = _generate_recommendations(checks)
    uptime = time.time() - START_TIME
    live = SystemHealthResponse(
        overall_status=overall_status,
        health_score=health_score,
        checks=checks,
        recommendations=recommendations,
        uptime_seconds=uptime,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    return HealthRemediationResponse(
        remediated=bool(snapshot.remediated),
        note=snapshot.remediation_note or "",
        snapshot=live,
    )
