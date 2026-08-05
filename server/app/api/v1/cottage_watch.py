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

"""REST endpoints for cottage 一起看 (watch-together).

Everything except the WebSocket. Manages the shared source library (片库),
returns the live room state, and fires an invite notification. All endpoints
are partner-only.

Endpoints under ``/v1/cottage/watch``:

- ``GET    /v1/cottage/watch/state``            — live room + partner presence
- ``GET    /v1/cottage/watch/sources``          — list the shared library
- ``POST   /v1/cottage/watch/sources``          — add a direct-URL source
- ``POST   /v1/cottage/watch/sources/upload``   — upload a video file source
- ``DELETE /v1/cottage/watch/sources/{wsid}``   — remove a source
- ``POST   /v1/cottage/watch/invite``           — notify partner to come watch
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.api.v1.cottage_watch_ws import manager as ws_manager
from app.core.i18n import get_message
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.watch import WatchSource
from app.schemas.watch import (
    WatchBookmark,
    WatchCurrent,
    WatchPartnerState,
    WatchSourceCreateRequest,
    WatchSourceListResponse,
    WatchSourcePatchRequest,
    WatchSourceResponse,
    WatchStateResponse,
)
from app.services import cottage_realtime
from app.services.notifications import notify_partners
from app.services.upload_references import (
    delete_upload_references_for,
    sync_watch_source_upload_references,
)
from app.services.watch_together import presence, room

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/watch", tags=["cottage-watch"])

BACKEND_ROOT = Path(__file__).resolve().parents[3]
UPLOADS_ROOT = (BACKEND_ROOT / "uploads").resolve()
VIDEOS_DIR = UPLOADS_ROOT / "videos"

# 2 GB ceiling per uploaded video — enough for a long episode / movie while
# keeping a private deployment's disk usage bounded. Streamed to disk so the
# whole file never sits in memory at once.
MAX_WATCH_VIDEO_BYTES = 2 * 1024 * 1024 * 1024
_UPLOAD_CHUNK = 1024 * 1024  # 1 MiB

VIDEO_CONTENT_TYPE_MAP = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/x-matroska": ".mkv",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _to_response(source: WatchSource) -> WatchSourceResponse:
    return WatchSourceResponse(
        wsid=source.wsid,
        title=source.title,
        kind=source.kind,
        url=source.url,
        poster_url=source.poster_url,
        size_bytes=source.size_bytes,
        author_uid=source.author.uid if source.author else "",
        author_nickname=source.author.nickname if source.author else "",
        created_at=source.created_at,
        last_position_ms=int(source.last_position_ms or 0),
        last_viewed_at=source.last_viewed_at,
        bookmarks=_decode_bookmarks(source.bookmarks_json),
    )


def _decode_bookmarks(raw: str | None) -> list[WatchBookmark]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    items: list[WatchBookmark] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            items.append(
                WatchBookmark(
                    bid=str(entry.get("bid") or uuid4().hex),
                    position_ms=int(entry.get("position_ms") or 0),
                    label=str(entry.get("label") or ""),
                    created_at=_parse_dt(entry.get("created_at")) or datetime.now(timezone.utc),
                    created_by_uid=str(entry.get("created_by_uid") or ""),
                )
            )
        except (TypeError, ValueError):
            continue
    return items


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # ISO 8601 — accept the trailing 'Z' shorthand by swapping it out.
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_source(db: Session, wsid: str) -> WatchSource:
    source = (
        db.query(WatchSource)
        .options(joinedload(WatchSource.author))
        .filter(WatchSource.wsid == wsid, WatchSource.deleted_at.is_(None))
        .first()
    )
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=get_message("error.watch_source_not_found"))
    return source


def _build_upload_url(stored_file: Path) -> str:
    relative = stored_file.resolve().relative_to(UPLOADS_ROOT).as_posix()
    return f"/uploads/{relative}"


def _broadcast(event_type: str, payload: dict[str, Any], origin_uid: str) -> None:
    """Schedule a system event onto the WS bus (best-effort)."""
    import asyncio

    event = {
        "type": event_type,
        "payload": payload,
        "event_seq": None,
        "origin_uid": origin_uid,
        "server_ts_ms": _now_ms(),
    }
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(ws_manager.broadcast(event))
    except Exception:
        logger.warning("[cottage-watch] failed to schedule broadcast: %s", event_type)


# ---------------------------------------------------------------------------
# Room state
# ---------------------------------------------------------------------------

@router.get("/state", response_model=WatchStateResponse)
def get_room_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> WatchStateResponse:
    ensure_partner(current_user)
    state = room.get_state(redis_client)
    cur = state["current"]

    partners = (
        db.query(User)
        .filter(
            User.role.in_([UserRole.partner_a, UserRole.partner_b]),
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .all()
    )
    partner_states = [
        WatchPartnerState(
            user_uid=p.uid,
            nickname=p.nickname,
            online=presence.is_online(redis_client, p.uid),
        )
        for p in partners
    ]

    return WatchStateResponse(
        current=WatchCurrent(
            source_wsid=cur.get("source_wsid"),
            source_url=cur.get("source_url"),
            source_title=cur.get("source_title"),
            source_kind=cur.get("source_kind"),
            paused=bool(cur.get("paused", True)),
            position_ms=int(cur.get("position_ms") or 0),
            rate=float(cur.get("rate") or 1.0),
            started_by=cur.get("started_by"),
            event_seq=int(cur.get("event_seq") or state["event_seq"]),
            server_ts_ms=int(cur.get("server_ts_ms") or _now_ms()),
        ),
        partners=partner_states,
    )


# ---------------------------------------------------------------------------
# Source library (片库)
# ---------------------------------------------------------------------------

@router.get("/sources", response_model=WatchSourceListResponse)
def list_sources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchSourceListResponse:
    ensure_partner(current_user)
    sources = (
        db.query(WatchSource)
        .options(joinedload(WatchSource.author))
        .filter(WatchSource.deleted_at.is_(None))
        .order_by(WatchSource.created_at.desc())
        .all()
    )
    return WatchSourceListResponse(
        items=[_to_response(s) for s in sources],
        total=len(sources),
    )


@router.post("/sources", response_model=WatchSourceResponse, status_code=status.HTTP_201_CREATED)
def add_url_source(
    payload: WatchSourceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchSourceResponse:
    ensure_partner(current_user)
    is_upload = payload.url.startswith("/uploads/")
    source = WatchSource(
        author_id=current_user.id,
        title=payload.title,
        kind="upload" if is_upload else "url",
        url=payload.url,
        poster_url=payload.poster_url,
    )
    db.add(source)
    db.flush()
    # Grant partner-only access to the file when it's one of ours.
    sync_watch_source_upload_references(db, source)
    db.commit()
    return _to_response(_load_source(db, source.wsid))


@router.post(
    "/sources/upload",
    response_model=WatchSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_source(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchSourceResponse:
    ensure_partner(current_user)

    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.no_file_selected"))
    content_type = (file.content_type or "").lower().strip()
    if content_type not in VIDEO_CONTENT_TYPE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_message("error.unsupported_video_type", types=', '.join(VIDEO_CONTENT_TYPE_MAP.values())),
        )

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = VIDEO_CONTENT_TYPE_MAP[content_type]
    stored_file = VIDEOS_DIR / f"{uuid4().hex}{suffix}"

    # Stream to disk in chunks with a hard size ceiling — never load the whole
    # video into memory, and abort + clean up if it exceeds the cap.
    size = 0
    try:
        with stored_file.open("wb") as out:
            while True:
                chunk = await file.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_WATCH_VIDEO_BYTES:
                    out.close()
                    stored_file.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=get_message("error.video_file_too_large"),
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        stored_file.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=get_message("error.save_video_failed"),
        ) from exc
    finally:
        await file.close()

    if size == 0:
        stored_file.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.file_empty"))

    title = Path(file.filename).stem[:200] or "未命名视频"
    source = WatchSource(
        author_id=current_user.id,
        title=title,
        kind="upload",
        url=_build_upload_url(stored_file),
        size_bytes=size,
    )
    db.add(source)
    db.flush()
    sync_watch_source_upload_references(db, source)
    db.commit()
    return _to_response(_load_source(db, source.wsid))


@router.patch("/sources/{wsid}", response_model=WatchSourceResponse)
def patch_source(
    wsid: str,
    payload: WatchSourcePatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchSourceResponse:
    """Update resume position, bookmarks, and/or library metadata.

    All fields are optional; clients can call this with just
    ``last_position_ms`` (the most common case - the player calls it every
    5 s and on pause), just ``bookmarks`` (when the user pins / unpins a
    spot), or ``title`` / ``poster_url`` to fix library metadata without
    re-adding the source. Empty body is a no-op.
    """
    ensure_partner(current_user)
    source = _load_source(db, wsid)

    if payload.last_position_ms is not None:
        source.last_position_ms = payload.last_position_ms
        source.last_viewed_at = datetime.now(timezone.utc)

    if payload.bookmarks is not None:
        # Bounded so a malicious client cannot dump a 10MB JSON blob.
        if len(payload.bookmarks) > 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=get_message("error.bookmark_limit_exceeded"),
            )
        source.bookmarks_json = json.dumps(
            [
                {
                    "bid": item.bid,
                    "position_ms": int(item.position_ms),
                    "label": item.label[:80],
                    "created_at": item.created_at.isoformat(),
                    # Always stamp the authenticated user — never trust the
                    # client-supplied created_by_uid, otherwise a partner
                    # could forge bookmarks "created by" the other side.
                    "created_by_uid": current_user.uid,
                }
                for item in payload.bookmarks
            ],
            ensure_ascii=False,
        )

    if payload.title is not None:
        source.title = payload.title

    if payload.poster_url is not None:
        source.poster_url = payload.poster_url or None

    source.version += 1
    db.commit()
    return _to_response(_load_source(db, wsid))


@router.delete("/sources/{wsid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    wsid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> Response:
    ensure_partner(current_user)
    source = _load_source(db, wsid)
    source.deleted_at = datetime.now(timezone.utc)
    delete_upload_references_for(db, "watch", source.id)
    db.commit()

    # If the room is currently showing this source, clear it so the player on
    # the other side doesn't keep pointing at a now-inaccessible file.
    try:
        state = room.get_state(redis_client)
        if state["current"].get("source_wsid") == wsid:
            room.clear_room(redis_client)
            _broadcast("ROOM_CLEARED", {"wsid": wsid}, origin_uid=current_user.uid)
    except Exception:
        logger.warning("[cottage-watch] failed to clear room after source delete")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Invite
# ---------------------------------------------------------------------------

@router.post("/invite", status_code=status.HTTP_204_NO_CONTENT)
async def invite_partner(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    ensure_partner(current_user)
    notify_partners(
        db,
        type="watch.invite",
        title=f"{current_user.nickname} 邀请你一起看",
        body="快进入小屋的「一起看」陪 Ta 一起追剧吧",
        link="/cottage/watch",
        source_type="watch",
        source_id=current_user.uid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    # Push the invite over the shared cottage realtime channel so the partner
    # sees it anywhere in the cottage, not only on the watch page. The persisted
    # notification above remains the reliable offline fallback.
    cottage_realtime.schedule_broadcast(
        {
            "type": "INVITE",
            "payload": {
                "from_uid": current_user.uid,
                "from_nickname": current_user.nickname,
                "kind": "watch",
                "title": "一起看",
                "link": "/cottage/watch",
            },
            "server_ts_ms": _now_ms(),
        },
        exclude_uid=current_user.uid,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
