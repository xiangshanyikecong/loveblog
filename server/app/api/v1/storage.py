# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Storage usage statistics: disk volume, uploads tree, database size."""

import os
from pathlib import Path

import psutil
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.api.v1.uploads import DEFAULT_UPLOADS_ROOT
from app.db.session import get_db
from app.models.user import User
from app.schemas.storage import (
    CategoryUsage,
    DbInfo,
    DirInfo,
    DiskInfo,
    StorageUsageResponse,
)


router = APIRouter(prefix="/storage", tags=["storage"])

# Safety cap: stop walking after this many files so a runaway uploads tree can
# never stall the request (stats stay approximate, never blocking).
MAX_SCAN_FILES = 50000

# Category label for files stored directly in the uploads root (rare, e.g.
# marker files), so the breakdown still sums to the uploads total.
ROOT_CATEGORY = "root"


def _disk_info(uploads_root: Path) -> DiskInfo:
    """Usage of the volume hosting the uploads directory.

    Walks up to the nearest existing ancestor first because
    ``psutil.disk_usage`` fails on paths that do not exist yet (e.g. a fresh
    install without an uploads directory).
    """
    target = uploads_root
    while not target.exists() and target != target.parent:
        target = target.parent
    usage = psutil.disk_usage(str(target))
    return DiskInfo(
        total_bytes=int(usage.total),
        used_bytes=int(usage.used),
        free_bytes=int(usage.free),
        percent=float(usage.percent),
    )


def _sorted_breakdown(categories: dict[str, list[int]]) -> list[CategoryUsage]:
    """Turn {category: [bytes, files]} into a list sorted by size, desc."""
    return [
        CategoryUsage(category=name, bytes=bucket[0], file_count=bucket[1])
        for name, bucket in sorted(categories.items(), key=lambda item: item[1][0], reverse=True)
    ]


def _scan_uploads(uploads_root: Path) -> tuple[DirInfo, list[CategoryUsage]]:
    """Walk the uploads tree once, totalling bytes/files per first-level
    sub-directory. A missing directory simply yields zeros."""
    total_bytes = 0
    file_count = 0
    categories: dict[str, list[int]] = {}

    if uploads_root.exists():
        scanned = 0
        for dirpath, _dirnames, filenames in os.walk(uploads_root):
            rel_dir = os.path.relpath(dirpath, uploads_root)
            category = ROOT_CATEGORY if rel_dir == "." else rel_dir.split(os.sep)[0]
            for name in filenames:
                if scanned >= MAX_SCAN_FILES:
                    # Cap reached: report what we have and stop walking.
                    return (
                        DirInfo(total_bytes=total_bytes, file_count=file_count),
                        _sorted_breakdown(categories),
                    )
                scanned += 1
                try:
                    size = os.path.getsize(os.path.join(dirpath, name))
                except OSError:
                    continue  # file vanished between listing and stat
                total_bytes += size
                file_count += 1
                bucket = categories.setdefault(category, [0, 0])
                bucket[0] += size
                bucket[1] += 1

    return (
        DirInfo(total_bytes=total_bytes, file_count=file_count),
        _sorted_breakdown(categories),
    )


def _database_size(db: Session) -> DbInfo:
    """PostgreSQL database size; null when unavailable (e.g. non-PG backend)."""
    try:
        size = db.execute(text("SELECT pg_database_size(current_database())")).scalar()
        return DbInfo(size_bytes=int(size) if size is not None else None)
    except Exception:  # degrade to null instead of failing the whole panel
        return DbInfo(size_bytes=None)


@router.get("/usage", response_model=StorageUsageResponse)
def get_storage_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StorageUsageResponse:
    """Storage usage overview (disk / uploads / database) for the couple."""
    ensure_partner(current_user)

    uploads_root = Path(DEFAULT_UPLOADS_ROOT)
    disk = _disk_info(uploads_root)
    uploads, breakdown = _scan_uploads(uploads_root)
    database = _database_size(db)

    return StorageUsageResponse(disk=disk, uploads=uploads, database=database, breakdown=breakdown)
