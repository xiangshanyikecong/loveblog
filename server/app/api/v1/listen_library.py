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

"""REST endpoints for the cottage-listen music library.

Two couple-shared collections on top of listen-together:

- Liked songs ("我喜欢") — per-partner favorites keyed by (user_id, song_id).
- Couple playlists ("我们的歌单") — free-form playlists both partners edit.
  Playlists are couple-global by design: the product has exactly two partner
  accounts, so ``ensure_partner`` is the only authorization needed.

``song_id`` values are either NetEase numeric ids or ``local:<tid>`` refs to
partner-uploaded audio. Both flavors fit the String(64) columns and enqueue
into the room queue identically — the room stores id + metadata; the provider
is only resolved later, when the player asks for a playable URL.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.api.v1.cottage_listen_ws import manager as ws_manager
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.listen_liked_track import ListenLikedTrack
from app.models.listen_playlist import ListenPlaylist, ListenPlaylistTrack
from app.models.user import User
from app.schemas.listen_library import (
    LikedStatusResponse,
    LikedToggleRequest,
    LikedToggleResponse,
    LikedTrackItem,
    LikedTracksResponse,
    PlaylistCreateRequest,
    PlaylistDetail,
    PlaylistSummary,
    PlaylistTrackAddRequest,
    PlaylistTrackItem,
    PlaylistUpdateRequest,
)
from app.services.listen_together import room

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/listen", tags=["cottage-listen"])

# GET /liked/status accepts at most this many comma-separated song ids.
_LIKED_STATUS_MAX_IDS = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_artists(artists: list[str]) -> str:
    return json.dumps([str(a) for a in (artists or []) if a], ensure_ascii=False)


def _liked_total(db: Session, user_id: int) -> int:
    return int(
        db.query(func.count(ListenLikedTrack.id))
        .filter(ListenLikedTrack.user_id == user_id)
        .scalar()
        or 0
    )


def _liked_item(row: ListenLikedTrack) -> LikedTrackItem:
    return LikedTrackItem(
        song_id=row.song_id,
        name=row.name,
        artists=row.artists,
        album=row.album,
        duration_ms=row.duration_ms,
        cover_url=row.cover_url,
        liked_at=row.created_at.isoformat() if row.created_at else "",
    )


def _get_playlist_or_404(db: Session, pid: str) -> ListenPlaylist:
    playlist = db.query(ListenPlaylist).filter(ListenPlaylist.pid == pid).first()
    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )
    return playlist


def _playlist_track_count(db: Session, playlist_id: int) -> int:
    return int(
        db.query(func.count(ListenPlaylistTrack.id))
        .filter(ListenPlaylistTrack.playlist_id == playlist_id)
        .scalar()
        or 0
    )


def _playlist_summary(playlist: ListenPlaylist, track_count: int) -> PlaylistSummary:
    return PlaylistSummary(
        pid=playlist.pid,
        name=playlist.name,
        description=playlist.description,
        cover_url=playlist.cover_url,
        created_by_uid=playlist.created_by_uid,
        track_count=track_count,
        created_at=playlist.created_at.isoformat() if playlist.created_at else "",
        updated_at=playlist.updated_at.isoformat() if playlist.updated_at else "",
    )


def _playlist_track_item(row: ListenPlaylistTrack) -> PlaylistTrackItem:
    return PlaylistTrackItem(
        song_id=row.song_id,
        name=row.name,
        artists=row.artists,
        album=row.album,
        duration_ms=row.duration_ms,
        cover_url=row.cover_url,
        added_by_uid=row.added_by_uid,
        position=row.position,
        added_at=row.added_at.isoformat() if row.added_at else "",
    )


def _playlist_tracks(db: Session, playlist_id: int) -> list[ListenPlaylistTrack]:
    return (
        db.query(ListenPlaylistTrack)
        .filter(ListenPlaylistTrack.playlist_id == playlist_id)
        .order_by(ListenPlaylistTrack.position.asc(), ListenPlaylistTrack.id.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Liked songs ("我喜欢")
# ---------------------------------------------------------------------------

@router.get("/liked", response_model=LikedTracksResponse)
def list_liked_tracks(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LikedTracksResponse:
    """The current partner's liked songs, newest first."""
    ensure_partner(current_user)
    rows = (
        db.query(ListenLikedTrack)
        .filter(ListenLikedTrack.user_id == current_user.id)
        .order_by(ListenLikedTrack.created_at.desc(), ListenLikedTrack.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return LikedTracksResponse(
        items=[_liked_item(row) for row in rows],
        total=_liked_total(db, current_user.id),
    )


@router.get("/liked/status", response_model=LikedStatusResponse)
def get_liked_status(
    song_ids: Annotated[
        str, Query(description="Comma-separated song ids (at most 50).")
    ] = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LikedStatusResponse:
    """Which of the given song ids the current partner has already liked."""
    ensure_partner(current_user)
    ids = [part.strip() for part in (song_ids or "").split(",") if part.strip()]
    if len(ids) > _LIKED_STATUS_MAX_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {_LIKED_STATUS_MAX_IDS} song_ids allowed",
        )
    liked: list[str] = []
    if ids:
        rows = (
            db.query(ListenLikedTrack.song_id)
            .filter(
                ListenLikedTrack.user_id == current_user.id,
                ListenLikedTrack.song_id.in_(ids),
            )
            .all()
        )
        liked = [str(row[0]) for row in rows]
    return LikedStatusResponse(
        song_ids=liked, total=_liked_total(db, current_user.id)
    )


@router.put("/liked/toggle", response_model=LikedToggleResponse)
def toggle_liked_track(
    payload: LikedToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LikedToggleResponse:
    """Like the song if it isn't liked yet, otherwise un-like it."""
    ensure_partner(current_user)
    existing = (
        db.query(ListenLikedTrack)
        .filter(
            ListenLikedTrack.user_id == current_user.id,
            ListenLikedTrack.song_id == payload.song_id,
        )
        .first()
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
        return LikedToggleResponse(
            liked=False, total=_liked_total(db, current_user.id)
        )

    track = ListenLikedTrack(
        user_id=current_user.id,
        song_id=payload.song_id,
        name=payload.name or "",
        artists_json=_serialize_artists(payload.artists),
        album=payload.album,
        duration_ms=payload.duration_ms,
        cover_url=payload.cover_url,
    )
    db.add(track)
    try:
        db.commit()
    except IntegrityError:
        # Another tab of the same partner won the (user_id, song_id) unique
        # race between our SELECT and COMMIT. Roll back, re-check, and report
        # the actual state instead of failing the request.
        db.rollback()
        winner = (
            db.query(ListenLikedTrack)
            .filter(
                ListenLikedTrack.user_id == current_user.id,
                ListenLikedTrack.song_id == payload.song_id,
            )
            .first()
        )
        return LikedToggleResponse(
            liked=winner is not None,
            total=_liked_total(db, current_user.id),
        )
    return LikedToggleResponse(liked=True, total=_liked_total(db, current_user.id))


@router.delete("/liked/{song_id}")
def delete_liked_track(
    song_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Remove one liked song. Idempotent: a missing row still returns ok."""
    ensure_partner(current_user)
    db.query(ListenLikedTrack).filter(
        ListenLikedTrack.user_id == current_user.id,
        ListenLikedTrack.song_id == song_id,
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Couple playlists ("我们的歌单")
# ---------------------------------------------------------------------------

@router.get("/playlists/mine", response_model=list[PlaylistSummary])
def list_playlists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlaylistSummary]:
    """All couple-built playlists, most recently updated first.

    Playlists are shared between the two partners ("mine" = the couple's), so
    there is no per-user filter — every partner sees every playlist.
    """
    ensure_partner(current_user)
    track_count_sq = (
        db.query(
            ListenPlaylistTrack.playlist_id.label("playlist_id"),
            func.count(ListenPlaylistTrack.id).label("track_count"),
        )
        .group_by(ListenPlaylistTrack.playlist_id)
        .subquery()
    )
    rows = (
        db.query(ListenPlaylist, track_count_sq.c.track_count)
        .outerjoin(track_count_sq, track_count_sq.c.playlist_id == ListenPlaylist.id)
        .order_by(ListenPlaylist.updated_at.desc(), ListenPlaylist.id.desc())
        .all()
    )
    return [_playlist_summary(playlist, int(count or 0)) for playlist, count in rows]


@router.post(
    "/playlists/mine",
    response_model=PlaylistSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_playlist(
    payload: PlaylistCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistSummary:
    """Create a new couple playlist (creator = the current partner)."""
    ensure_partner(current_user)
    playlist = ListenPlaylist(
        name=payload.name,
        description=payload.description,
        cover_url=payload.cover_url,
        created_by_uid=current_user.uid,
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    return _playlist_summary(playlist, 0)


@router.get("/playlists/mine/{pid}", response_model=PlaylistDetail)
def get_playlist(
    pid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistDetail:
    """One playlist with its full ordered track list."""
    ensure_partner(current_user)
    playlist = _get_playlist_or_404(db, pid)
    tracks = _playlist_tracks(db, playlist.id)
    summary = _playlist_summary(playlist, len(tracks))
    return PlaylistDetail(
        **summary.model_dump(),
        tracks=[_playlist_track_item(track) for track in tracks],
    )


@router.put("/playlists/mine/{pid}", response_model=PlaylistSummary)
def update_playlist(
    pid: str,
    payload: PlaylistUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistSummary:
    """Update playlist metadata. Only non-None fields are changed."""
    ensure_partner(current_user)
    playlist = _get_playlist_or_404(db, pid)
    if payload.name is not None:
        playlist.name = payload.name
    if payload.description is not None:
        playlist.description = payload.description
    if payload.cover_url is not None:
        playlist.cover_url = payload.cover_url
    # Explicit touch so updated_at bumps even when no field actually changed.
    playlist.updated_at = _utcnow()
    db.commit()
    db.refresh(playlist)
    return _playlist_summary(playlist, _playlist_track_count(db, playlist.id))


@router.delete("/playlists/mine/{pid}")
def delete_playlist(
    pid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete a playlist and every track in it (tracks first)."""
    ensure_partner(current_user)
    playlist = _get_playlist_or_404(db, pid)
    db.query(ListenPlaylistTrack).filter(
        ListenPlaylistTrack.playlist_id == playlist.id
    ).delete(synchronize_session=False)
    db.query(ListenPlaylist).filter(ListenPlaylist.id == playlist.id).delete(
        synchronize_session=False
    )
    db.commit()
    return {"ok": True}


@router.post(
    "/playlists/mine/{pid}/tracks",
    response_model=PlaylistTrackItem,
    status_code=status.HTTP_201_CREATED,
)
def add_playlist_track(
    pid: str,
    payload: PlaylistTrackAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlaylistTrackItem:
    """Append a song to the playlist (position = current max + 1)."""
    ensure_partner(current_user)
    playlist = _get_playlist_or_404(db, pid)
    max_position = (
        db.query(func.max(ListenPlaylistTrack.position))
        .filter(ListenPlaylistTrack.playlist_id == playlist.id)
        .scalar()
    )
    track = ListenPlaylistTrack(
        playlist_id=playlist.id,
        song_id=payload.song_id,
        name=payload.name or "",
        artists_json=_serialize_artists(payload.artists),
        album=payload.album,
        duration_ms=payload.duration_ms,
        cover_url=payload.cover_url,
        added_by_uid=current_user.uid,
        position=(max_position or 0) + 1,
    )
    db.add(track)
    # Content changed → bump the list ordering (lists sort by updated_at).
    playlist.updated_at = _utcnow()
    try:
        db.commit()
    except IntegrityError as exc:
        # unique(playlist_id, song_id): the song is already in this playlist.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Song already in playlist",
        ) from exc
    db.refresh(track)
    return _playlist_track_item(track)


@router.delete("/playlists/mine/{pid}/tracks/{song_id}")
def remove_playlist_track(
    pid: str,
    song_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Remove one song from the playlist. Idempotent for missing songs."""
    ensure_partner(current_user)
    playlist = _get_playlist_or_404(db, pid)
    deleted = (
        db.query(ListenPlaylistTrack)
        .filter(
            ListenPlaylistTrack.playlist_id == playlist.id,
            ListenPlaylistTrack.song_id == song_id,
        )
        .delete(synchronize_session=False)
    )
    if deleted:
        playlist.updated_at = _utcnow()
    db.commit()
    return {"ok": True}


@router.post("/playlists/mine/{pid}/play")
async def play_playlist(
    pid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> dict:
    """Queue every song of the playlist into the listen-together room.

    Uses the same ``QUEUE_APPEND`` path as the WS handler:
    ``room.apply_event`` stores the full song metadata alongside the id and
    returns the broadcast envelope, which we relay through the WS manager so
    both partners' players pick the new queue entries up live. NetEase ids
    and ``local:<tid>`` ids enqueue identically — the queue is
    provider-agnostic.

    Per-track failures (Redis hiccup, lock timeout, …) skip that song so one
    bad entry never blocks the rest; the response reports how many made it.
    """
    ensure_partner(current_user)
    playlist = _get_playlist_or_404(db, pid)
    tracks = _playlist_tracks(db, playlist.id)

    queued = 0
    for track in tracks:
        try:
            event = await asyncio.to_thread(
                room.apply_event,
                redis_client,
                "QUEUE_APPEND",
                {
                    "song_id": track.song_id,
                    "song_meta": {
                        "song_id": track.song_id,
                        "name": track.name,
                        "artists": track.artists,
                        "album": track.album,
                        "duration_ms": track.duration_ms,
                        "cover_url": track.cover_url,
                    },
                },
                current_user.uid,
            )
        except Exception:
            logger.warning(
                "[cottage-listen] failed to queue playlist track %s",
                track.song_id,
                exc_info=True,
            )
            continue
        if event is None:
            continue
        queued += 1
        try:
            await ws_manager.broadcast(event)
        except Exception:
            # The queue write already succeeded; a dead socket must not
            # misreport the queued count.
            logger.warning(
                "[cottage-listen] failed to broadcast QUEUE_APPEND", exc_info=True
            )
    return {"queued": queued}
