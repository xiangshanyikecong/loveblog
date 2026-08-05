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

"""REST endpoints for cottage-listen-together (everything except the WS).

Privacy invariant: NetEase cookies are decrypted into local variables and
passed straight to ``netease_client``; they never enter a response body, a
log entry, or a long-lived module cache.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Annotated, Any, NoReturn

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.api.v1.cottage_listen_ws import manager as ws_manager
from app.api.v1.uploads import process_audio_upload
from app.core.config import settings
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.listen_local_track import ListenLocalTrack
from app.models.upload_reference import UploadReference
from app.models.user import User, UserRole
from app.schemas.cottage_listen import (
    ImportCookieRequest,
    ListenHistoryItem,
    ListenHistoryResponse,
    LocalTracksResponse,
    PartnerLoginState,
    PlaylistItem,
    PlaylistsResponse,
    PlaylistTracksResponse,
    QrKeyResponse,
    QrStatusResponse,
    RoomCurrent,
    RoomStateResponse,
    SongLyricResponse,
    LyricLine,
    SongMeta,
    SongSearchResponse,
    SongUrlResponse,
    ToplistItem,
    ToplistResponse,
)
from app.services.listen_together import cookie_vault, history as listen_history, netease_client, room

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/cottage/listen", tags=["cottage-listen"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _cookie_ttl_seconds() -> int:
    return settings.cottage_listen_cookie_ttl_days * 24 * 3600


def _extract_music_u(cookie: str) -> str | None:
    """Pull the ``MUSIC_U=...`` field out of a full NetEase cookie string.

    The upstream cookie string carries many fields (Max-Age, Expires, Path…)
    that confuse NeteaseCloudMusicApi; we only need MUSIC_U. Accepts a bare
    ``MUSIC_U=...`` too. Returns None if no MUSIC_U is present.
    """
    for part in (cookie or "").split(";"):
        part = part.strip()
        if part.startswith("MUSIC_U="):
            return part
    return None


def _request_is_https(request: Request) -> bool:
    """Whether the browser reached us over HTTPS.

    Behind nginx the app server always sees http on the socket, so we trust the
    ``X-Forwarded-Proto`` nginx sets to the original client scheme, falling back
    to the request's own scheme for direct/dev hits.
    """
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "")
    return proto.split(",")[0].strip().lower() == "https"


def _force_https(url: str | None) -> str | None:
    """Upgrade a NetEase direct-URL from http:// to https://.

    NetEase's /song/url often hands back an ``http://`` CDN link. On an HTTPS
    page that link is mixed-content-blocked by the browser — a big part of
    "部分环境无法播放". NetEase's audio CDN (``*.music.126.net`` /
    ``*.music.127.net``) serves the same object over HTTPS, so a straight scheme
    swap is safe. We only do it for HTTPS callers: an HTTP deployment can keep
    using the http link (no mixed-content there) and need not depend on the CDN
    answering on https.
    """
    if url and url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def _client_ip(request: Request) -> str | None:
    """Best-effort real public client IP of the partner making the request.

    nginx sets ``X-Real-IP`` to the TCP peer ($remote_addr), *overwriting* any
    client-supplied value, so it's the trustworthy source behind our edge; we
    fall back to the first ``X-Forwarded-For`` hop and finally the socket peer.
    Returns None for anything that isn't a public IPv4 address (private /
    loopback / CGNAT / IPv6) — NetEase's realIP spoofing expects a public
    mainland IPv4, and a non-routable value is worse than our stable fallback.
    """
    candidates: list[str] = []
    xri = request.headers.get("x-real-ip")
    if xri:
        candidates.append(xri.strip())
    xff = request.headers.get("x-forwarded-for")
    if xff:
        candidates.append(xff.split(",")[0].strip())
    if request.client:
        candidates.append(request.client.host)

    for raw in candidates:
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if ip.version == 4 and ip.is_global:
            return str(ip)
    return None


def _login_ip_for(redis_client, owner_uid: str) -> str | None:
    """The spoofed realIP to use when calling NetEase with ``owner_uid``'s
    cookie: the IP they scan-logged in from. None → client falls back to the
    process-wide stable IP."""
    return cookie_vault.get_login_ip(redis_client, owner_uid)


def _require_partner_cookie(redis_client, user_uid: str) -> str:
    """Decrypt and return the user's NetEase cookie, or raise 409.

    Used by every NetEase-backed endpoint except the QR-login flow itself.
    """
    cookie = cookie_vault.get_cookie(redis_client, user_uid)
    if not cookie:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "netease_login_required", "message": "请先登录网易云"},
        )
    return cookie


def _broadcast(event_type: str, payload: dict[str, Any], origin_uid: str) -> None:
    """Fire a system event into the WS bus.

    These REST handlers are synchronous, so FastAPI runs them in a worker thread
    that has NO running event loop — ``asyncio.get_event_loop()`` would raise
    there and the push would be silently dropped. We hand the coroutine to
    ``cottage_realtime``, which schedules it on the uvicorn loop captured at
    startup via ``run_coroutine_threadsafe``.
    """
    from app.services import cottage_realtime

    event = {
        "type": event_type,
        "payload": payload,
        "event_seq": None,  # system events: no seq from room.apply_event
        "origin_uid": origin_uid,
        "server_ts_ms": _now_ms(),
    }
    cottage_realtime.schedule_coroutine(ws_manager.broadcast(event))


def _handle_netease_error(exc: netease_client.NeteaseError, redis_client, user_uid: str) -> NoReturn:
    """Common mapping of upstream errors to HTTP responses.

    On ``login_required`` we eagerly delete the partner's stored cookie and
    broadcast a ``COOKIE_EXPIRED`` event so the frontend can show its UI
    affordance. On other kinds we return HTTP 502 with structured detail.
    """
    if exc.kind == "login_required":
        cookie_vault.delete_cookie(redis_client, user_uid)
        _broadcast("COOKIE_EXPIRED", {"user_uid": user_uid}, origin_uid=user_uid)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "netease_login_required", "message": "网易云登录已失效"},
        )
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": f"netease_{exc.kind}", "message": exc.message},
    )


def _song_from_cloudsearch(item: dict) -> SongMeta:
    artists = [a.get("name", "") for a in (item.get("ar") or item.get("artists") or [])]
    album = (item.get("al") or item.get("album") or {}).get("name")
    cover = (item.get("al") or item.get("album") or {}).get("picUrl")
    duration = item.get("dt") or item.get("duration")
    return SongMeta(
        song_id=str(item.get("id")),
        name=item.get("name", ""),
        artists=[a for a in artists if a],
        album=album,
        duration_ms=int(duration) if duration else None,
        cover_url=cover,
    )


# A single LRC timestamp: [mm:ss], [mm:ss.xx] or [mm:ss.xxx]. We accept ':' as
# the fraction separator too — some upstream lyrics use it. Metadata tags like
# [ti:...] / [ar:...] / [by:...] don't match (their "minutes" part isn't all
# digits / has no second field), so they're skipped naturally.
_LRC_TIME_RE = re.compile(r"\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def _parse_lrc(text: str | None) -> list[tuple[int, str]]:
    """Parse an LRC blob into ``(time_ms, text)`` pairs, sorted by time.

    Handles multiple timestamps on one line (``[00:01][00:05]词``), drops lines
    with no real text (pure metadata / empty), and normalizes the fractional
    part to milliseconds (2-digit = centiseconds, 3-digit = milliseconds).
    """
    out: list[tuple[int, str]] = []
    for raw in (text or "").splitlines():
        stamps = list(_LRC_TIME_RE.finditer(raw))
        if not stamps:
            continue
        body = _LRC_TIME_RE.sub("", raw).strip()
        if not body:
            continue
        for m in stamps:
            minutes, seconds = int(m.group(1)), int(m.group(2))
            millis = int((m.group(3) or "0").ljust(3, "0")[:3])
            out.append(((minutes * 60 + seconds) * 1000 + millis, body))
    out.sort(key=lambda pair: pair[0])
    return out


def _lyric_from_payload(song_id: str, payload: dict) -> SongLyricResponse:
    """Normalize an upstream /lyric response into our structured schema.

    Merges the Chinese translation (``tlyric``) onto each original line by
    exact timestamp match — NetEase emits translation lines on the very same
    timestamps as the originals.
    """
    if payload.get("nolyric"):
        return SongLyricResponse(song_id=song_id, lines=[], kind="instrumental")

    main = _parse_lrc((payload.get("lrc") or {}).get("lyric"))
    if not main:
        return SongLyricResponse(song_id=song_id, lines=[], kind="none")

    trans_by_time = dict(_parse_lrc((payload.get("tlyric") or {}).get("lyric")))
    lines = [
        LyricLine(time_ms=t, text=txt, trans=trans_by_time.get(t))
        for t, txt in main
    ]
    return SongLyricResponse(song_id=song_id, lines=lines, kind="lrc")


def _resolve_partners(db: Session, redis_client) -> list[PartnerLoginState]:
    partners = (
        db.query(User)
        .filter(
            User.role.in_([UserRole.partner_a, UserRole.partner_b]),
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .all()
    )
    return [
        PartnerLoginState(
            user_uid=p.uid,
            nickname=p.nickname,
            netease_logged_in=cookie_vault.has_cookie(redis_client, p.uid),
        )
        for p in partners
    ]


# ---------------------------------------------------------------------------
# Auth (QR-code login)
# ---------------------------------------------------------------------------

@router.get("/auth/qr-key", response_model=QrKeyResponse)
def get_qr_key(
    request: Request,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> QrKeyResponse:
    ensure_partner(current_user)
    # Use the partner's own real IP for the whole login handshake so NetEase
    # sees the QR being generated from where they actually are.
    client_ip = _client_ip(request)
    try:
        key_payload = netease_client.qr_key(real_ip=client_ip)
        unikey = key_payload.get("data", {}).get("unikey") or key_payload.get("unikey")
        if not unikey:
            raise netease_client.NeteaseError("parse_error", "missing unikey")
        create_payload = netease_client.qr_create(str(unikey), real_ip=client_ip)
        # qr_create returns either qrimg=data:image/png;base64,... or qrurl
        qrimg = create_payload.get("data", {}).get("qrimg") or create_payload.get("qrimg")
        if not qrimg:
            raise netease_client.NeteaseError("parse_error", "missing qrimg")
        # If upstream returns a url-only response, base64-encode the URL into
        # a passthrough so the frontend can still <img src=...>. In practice
        # NeteaseCloudMusicApi returns a data: URL when qrimg=true.
        if not qrimg.startswith("data:"):
            qrimg = f"data:text/plain;base64,{base64.b64encode(qrimg.encode()).decode()}"
        return QrKeyResponse(unikey=str(unikey), qr_image_data_url=qrimg)
    except netease_client.NeteaseError as exc:
        _handle_netease_error(exc, redis_client, current_user.uid)


@router.get("/auth/qr-status", response_model=QrStatusResponse)
def check_qr_status(
    request: Request,
    key: Annotated[str, Query(min_length=1)],
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> QrStatusResponse:
    ensure_partner(current_user)
    client_ip = _client_ip(request)
    try:
        result = netease_client.qr_check(key, real_ip=client_ip)
    except netease_client.NeteaseError as exc:
        return QrStatusResponse(status="error", message=exc.message)

    code = result.get("code")
    if code == 800:
        return QrStatusResponse(status="expired")
    if code == 801:
        return QrStatusResponse(status="waiting")
    if code == 802:
        return QrStatusResponse(status="scanned")
    if code == 803:
        cookie = result.get("cookie")
        if not cookie:
            return QrStatusResponse(status="error", message="upstream missing cookie")

        # Extract only MUSIC_U from the full cookie string (the rest — Max-Age,
        # Expires, Path… — can confuse the NetEase API). Fall back to the full
        # cookie if MUSIC_U isn't present for some reason.
        cookie_to_store = _extract_music_u(cookie) or cookie

        ttl = _cookie_ttl_seconds()
        cookie_vault.set_cookie(redis_client, current_user.uid, cookie_to_store, ttl)
        # Remember the IP this partner logged in from; every later call made
        # with this cookie will reuse it as the spoofed realIP so the account
        # keeps looking like it's logging in from the same place.
        if client_ip:
            cookie_vault.set_login_ip(redis_client, current_user.uid, client_ip, ttl)
        _broadcast("LOGIN_OK", {"user_uid": current_user.uid}, origin_uid=current_user.uid)
        return QrStatusResponse(status="confirmed", message="已登录网易云")
    return QrStatusResponse(status="error", message=f"unexpected code {code}")


@router.post("/auth/logout")
def logout_netease(
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> Response:
    ensure_partner(current_user)
    cookie_vault.delete_cookie(redis_client, current_user.uid)
    _broadcast("LOGOUT", {"user_uid": current_user.uid}, origin_uid=current_user.uid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/import-cookie", response_model=QrStatusResponse)
def import_cookie(
    request: Request,
    payload: ImportCookieRequest,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> QrStatusResponse:
    """Store a manually-pasted NetEase cookie (defeats 异地登录 risk-control).

    The server-side QR login fails 异地 risk-control because NetEase's *login*
    anti-fraud judges by the genuine TCP source — our server's IDC egress —
    not by the spoofable realIP header. So instead the partner logs into
    music.163.com from their OWN in-region network and pastes the cookie here.

    We validate it server-side via ``/login/status``: that's an *authenticated*
    call, not a login, so it doesn't trip risk-control — and a profile coming
    back proves the cookie works for every later server-side call too. On
    success we store the cookie + the partner's real client IP (their own, since
    they hit us directly) so song-url geo-unlock still forwards a sensible
    realIP.
    """
    ensure_partner(current_user)

    music_u = _extract_music_u(payload.cookie)
    if not music_u:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_cookie",
                "message": "未找到 MUSIC_U，请粘贴包含 MUSIC_U 的网易云 cookie",
            },
        )

    client_ip = _client_ip(request)
    try:
        status_payload = netease_client.login_status(music_u, real_ip=client_ip)
    except netease_client.NeteaseError as exc:
        # Don't delete anything here — there may be a previously-valid cookie.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": f"netease_{exc.kind}", "message": exc.message},
        ) from exc

    netease_uid = _extract_user_uid_from_login_status(status_payload)
    if not netease_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "netease_login_required", "message": "cookie 无效或已过期，请重新获取"},
        )

    ttl = _cookie_ttl_seconds()
    cookie_vault.set_cookie(redis_client, current_user.uid, music_u, ttl)
    if client_ip:
        cookie_vault.set_login_ip(redis_client, current_user.uid, client_ip, ttl)
    _broadcast("LOGIN_OK", {"user_uid": current_user.uid}, origin_uid=current_user.uid)
    return QrStatusResponse(status="confirmed", message="已导入网易云登录")


# ---------------------------------------------------------------------------
# Room state
# ---------------------------------------------------------------------------

@router.get("/state", response_model=RoomStateResponse)
def get_room_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> RoomStateResponse:
    ensure_partner(current_user)
    state = room.get_state(redis_client)
    cur = state["current"]

    # Best-effort song meta enrichment for current song. We don't fail the
    # whole endpoint when the cookie is missing or NetEase is down; callers
    # get song_meta=None and the frontend renders a placeholder.
    #
    # Priority order:
    # 1. Use song_meta from Redis (stored when PLAY event was sent)
    # 2. If not available, try to fetch using starter's cookie
    # 3. Fallback to current user's cookie
    current_song_meta: SongMeta | None = None

    # First, check if we have song_meta from Redis
    if cur.get("song_meta"):
        try:
            current_song_meta = SongMeta(**cur["song_meta"])
        except Exception:
            pass  # Invalid format, will try to fetch below

    # Fetch from NetEase when the stored meta is missing entirely OR is present
    # but has no duration_ms. duration drives the player's progress bar, and
    # PLAY events frequently carry a null duration (queue items / legacy
    # senders); without this backfill the bar can't scale, and the frontend's
    # decode-side fallback also fails when autoplay is blocked after a refresh.
    if cur.get("song_id") and (current_song_meta is None or not current_song_meta.duration_ms):
        # Try to use the starter's cookie first, fallback to current user's cookie
        started_by_uid = cur.get("started_by")
        cookie = None
        cookie_owner_uid = None
        if started_by_uid:
            cookie = cookie_vault.get_cookie(redis_client, started_by_uid)
            if cookie:
                cookie_owner_uid = started_by_uid
        if not cookie:
            # Fallback to current user's cookie if starter's cookie is unavailable
            cookie = cookie_vault.get_cookie(redis_client, current_user.uid)
            if cookie:
                cookie_owner_uid = current_user.uid

        if cookie:
            try:
                # Use song/detail endpoint for accurate metadata by ID, spoofing
                # the cookie owner's own login IP.
                payload = netease_client.song_detail(
                    cookie, cur["song_id"], real_ip=_login_ip_for(redis_client, cookie_owner_uid)
                )
                songs = payload.get("songs") or []
                if songs:
                    fetched = _song_from_cloudsearch(songs[0])
                    if current_song_meta is None:
                        current_song_meta = fetched
                    else:
                        # Keep the stored meta, fill only the blanks (esp. duration).
                        current_song_meta = SongMeta(
                            song_id=current_song_meta.song_id or fetched.song_id,
                            name=current_song_meta.name or fetched.name,
                            artists=current_song_meta.artists or fetched.artists,
                            album=current_song_meta.album or fetched.album,
                            duration_ms=current_song_meta.duration_ms or fetched.duration_ms,
                            cover_url=current_song_meta.cover_url or fetched.cover_url,
                        )
            except netease_client.NeteaseError:
                pass

    # Build queue metadata. NOTE: room.get_state() returns each queue entry as
    # a DICT ({"song_id", "name", "artists", ...}) — the frontend stores full
    # song_meta on QUEUE_APPEND — so we read those fields directly. Treating
    # the list as bare song_id strings (the previous code) raised a TypeError
    # (",".join(<dicts>) and dict-as-dict-key) and 500'd this whole endpoint
    # whenever the queue was non-empty, surfacing as "加载房间状态失败,请刷新重试".
    def _meta_from_queue_item(item: Any) -> SongMeta | None:
        if not isinstance(item, dict):
            item = {"song_id": str(item)}  # legacy/defensive: a bare id string
        sid = str(item.get("song_id") or "")
        if not sid:
            return None
        raw_artists = item.get("artists") or []
        artists = [str(a) for a in raw_artists] if isinstance(raw_artists, list) else []
        return SongMeta(
            song_id=sid,
            name=str(item.get("name") or ""),
            artists=artists,
            album=item.get("album"),
            duration_ms=item.get("duration_ms"),
            cover_url=item.get("cover_url"),
        )

    queue_metas: list[SongMeta] = [
        m for m in (_meta_from_queue_item(it) for it in state["queue"]) if m is not None
    ]

    # Best-effort: enrich entries still missing a name (e.g. legacy bare-id
    # items) with a single NetEase batch lookup. Never fail the endpoint over
    # this — a down / unauthenticated NetEase just leaves the placeholders.
    missing_ids = [m.song_id for m in queue_metas if not m.name]
    if missing_ids:
        cookie = cookie_vault.get_cookie(redis_client, current_user.uid)
        if cookie:
            try:
                payload = netease_client.song_detail(
                    cookie,
                    ",".join(missing_ids),
                    real_ip=_login_ip_for(redis_client, current_user.uid),
                )
                song_map = {
                    str(s.get("id")): _song_from_cloudsearch(s)
                    for s in (payload.get("songs") or [])
                    if s.get("id")
                }
                queue_metas = [song_map.get(m.song_id, m) for m in queue_metas]
            except netease_client.NeteaseError:
                pass

    return RoomStateResponse(
        event_seq=int(state["event_seq"]),
        current=RoomCurrent(
            song_id=cur.get("song_id"),
            song_meta=current_song_meta,
            paused=bool(cur.get("paused", True)),
            position_ms=int(cur.get("position_ms") or 0),
            started_by=cur.get("started_by"),
            event_seq=int(cur.get("event_seq") or state["event_seq"]),
            server_ts_ms=int(cur.get("server_ts_ms") or _now_ms()),
        ),
        queue=queue_metas,
        partners=_resolve_partners(db, redis_client),
    )


# ---------------------------------------------------------------------------
# Search & playlists
# ---------------------------------------------------------------------------

@router.get("/search", response_model=SongSearchResponse)
def search_songs(
    keyword: Annotated[str, Query(min_length=1)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> SongSearchResponse:
    ensure_partner(current_user)
    cookie = _require_partner_cookie(redis_client, current_user.uid)
    try:
        result = netease_client.search(
            cookie, keyword, page, page_size,
            real_ip=_login_ip_for(redis_client, current_user.uid),
        )
    except netease_client.NeteaseError as exc:
        _handle_netease_error(exc, redis_client, current_user.uid)
    songs_raw = (result.get("result") or {}).get("songs") or []
    items = [_song_from_cloudsearch(item) for item in songs_raw]
    total = (result.get("result") or {}).get("songCount", len(items))
    has_next = (page * page_size) < total
    return SongSearchResponse(items=items, page=page, page_size=page_size, has_next=has_next)


def _extract_user_uid_from_login_status(login_payload: dict) -> int | None:
    """Pull the upstream NetEase numeric uid from /login/status response."""
    profile = ((login_payload.get("data") or {}).get("profile") or {})
    uid = profile.get("userId") or profile.get("id")
    return int(uid) if uid else None


@router.get("/playlists", response_model=PlaylistsResponse)
def list_playlists(
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> PlaylistsResponse:
    ensure_partner(current_user)
    cookie = _require_partner_cookie(redis_client, current_user.uid)
    real_ip = _login_ip_for(redis_client, current_user.uid)

    try:
        login_payload = netease_client.login_status(cookie, real_ip=real_ip)
        netease_uid = _extract_user_uid_from_login_status(login_payload)
        if not netease_uid:
            raise netease_client.NeteaseError("login_required", "missing upstream uid")
        result = netease_client.playlists(cookie, netease_uid, real_ip=real_ip)
    except netease_client.NeteaseError as exc:
        _handle_netease_error(exc, redis_client, current_user.uid)

    raw_playlists = result.get("playlist") or []
    items: list[PlaylistItem] = []
    for p in raw_playlists:
        # Filter to playlists the user OWNS (not subscribed). Field convention:
        # subscribed=False on owned, True on subscribed.
        if p.get("subscribed"):
            continue
        items.append(
            PlaylistItem(
                playlist_id=str(p.get("id")),
                name=p.get("name", ""),
                cover_url=p.get("coverImgUrl"),
                track_count=int(p.get("trackCount") or 0),
            )
        )
    return PlaylistsResponse(items=items)


@router.get("/playlists/{playlist_id}/tracks", response_model=PlaylistTracksResponse)
def list_playlist_tracks(
    playlist_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> PlaylistTracksResponse:
    ensure_partner(current_user)
    cookie = _require_partner_cookie(redis_client, current_user.uid)
    real_ip = _login_ip_for(redis_client, current_user.uid)

    # R7.4: refuse if playlist_id is not in current_user's own playlists.
    try:
        login_payload = netease_client.login_status(cookie, real_ip=real_ip)
        netease_uid = _extract_user_uid_from_login_status(login_payload)
        if not netease_uid:
            raise netease_client.NeteaseError("login_required", "missing upstream uid")
        my_playlists = netease_client.playlists(cookie, netease_uid, real_ip=real_ip)
    except netease_client.NeteaseError as exc:
        _handle_netease_error(exc, redis_client, current_user.uid)

    own_ids = {
        str(p.get("id"))
        for p in (my_playlists.get("playlist") or [])
        if not p.get("subscribed")
    }
    if playlist_id not in own_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不是你的歌单")

    try:
        tracks = netease_client.playlist_tracks(
            cookie, playlist_id, page, page_size, real_ip=real_ip
        )
    except netease_client.NeteaseError as exc:
        _handle_netease_error(exc, redis_client, current_user.uid)

    songs = tracks.get("songs") or []
    items = [_song_from_cloudsearch(s) for s in songs]
    total = int(tracks.get("songCount") or len(items))
    has_next = (page * page_size) < total
    return PlaylistTracksResponse(items=items, page=page, page_size=page_size, has_next=has_next)


# ---------------------------------------------------------------------------
# Discover (recommend / homepage / charts)
# ---------------------------------------------------------------------------

def _songs_from_recommend_payload(payload: dict) -> list[SongMeta]:
    """Normalize daily recommend / chart track payloads."""
    data = payload.get("data") or {}
    songs_raw = data.get("dailySongs") or data.get("songs") or []
    if not songs_raw and isinstance(payload.get("result"), list):
        # /personalized/newsong style fallback
        songs_raw = payload.get("result") or []
    if not songs_raw and isinstance(payload.get("playlist"), dict):
        songs_raw = (payload.get("playlist") or {}).get("tracks") or []
    return [_song_from_cloudsearch(item) for item in songs_raw if item.get("id")]


@router.get("/discover/recommend-songs", response_model=SongSearchResponse)
def discover_recommend_songs(
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> SongSearchResponse:
    """Daily recommended songs (NetEase homepage-style feed)."""
    ensure_partner(current_user)
    cookie = _require_partner_cookie(redis_client, current_user.uid)
    try:
        result = netease_client.recommend_songs(
            cookie, real_ip=_login_ip_for(redis_client, current_user.uid)
        )
    except netease_client.NeteaseError as exc:
        _handle_netease_error(exc, redis_client, current_user.uid)
    items = _songs_from_recommend_payload(result)
    return SongSearchResponse(items=items, page=1, page_size=len(items), has_next=False)


@router.get("/discover/playlists", response_model=PlaylistsResponse)
def discover_playlists(
    limit: Annotated[int, Query(ge=1, le=30)] = 12,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> PlaylistsResponse:
    """Personalized playlist recommendations."""
    ensure_partner(current_user)
    cookie = _require_partner_cookie(redis_client, current_user.uid)
    try:
        result = netease_client.personalized_playlists(
            cookie, limit=limit, real_ip=_login_ip_for(redis_client, current_user.uid)
        )
    except netease_client.NeteaseError as exc:
        _handle_netease_error(exc, redis_client, current_user.uid)

    items: list[PlaylistItem] = []
    for p in result.get("result") or []:
        if not p.get("id"):
            continue
        items.append(
            PlaylistItem(
                playlist_id=str(p.get("id")),
                name=p.get("name", ""),
                cover_url=p.get("picUrl") or p.get("coverImgUrl"),
                track_count=int(p.get("songCount") or p.get("trackCount") or 0),
            )
        )
    return PlaylistsResponse(items=items)


@router.get("/discover/playlists/{playlist_id}/tracks", response_model=PlaylistTracksResponse)
def discover_playlist_tracks(
    playlist_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> PlaylistTracksResponse:
    """Tracks inside a personalized recommended playlist."""
    ensure_partner(current_user)
    cookie = _require_partner_cookie(redis_client, current_user.uid)
    real_ip = _login_ip_for(redis_client, current_user.uid)
    try:
        tracks = netease_client.playlist_tracks(
            cookie, playlist_id, page, page_size, real_ip=real_ip
        )
    except netease_client.NeteaseError as exc:
        _handle_netease_error(exc, redis_client, current_user.uid)

    songs = tracks.get("songs") or []
    items = [_song_from_cloudsearch(s) for s in songs]
    total = int(tracks.get("songCount") or len(items))
    has_next = (page * page_size) < total
    return PlaylistTracksResponse(items=items, page=page, page_size=page_size, has_next=has_next)


@router.get("/discover/toplist", response_model=ToplistResponse)
def discover_toplist(
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> ToplistResponse:
    """Official NetEase music charts."""
    ensure_partner(current_user)
    cookie = cookie_vault.get_cookie(redis_client, current_user.uid)
    try:
        result = netease_client.toplist(
            cookie, real_ip=_login_ip_for(redis_client, current_user.uid) if cookie else None
        )
    except netease_client.NeteaseError as exc:
        if cookie:
            _handle_netease_error(exc, redis_client, current_user.uid)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": f"netease_{exc.kind}", "message": exc.message},
        ) from exc

    items: list[ToplistItem] = []
    for chart in result.get("list") or []:
        if not chart.get("id"):
            continue
        items.append(
            ToplistItem(
                toplist_id=str(chart.get("id")),
                name=chart.get("name", ""),
                cover_url=chart.get("coverImgUrl"),
                update_frequency=chart.get("updateFrequency"),
                track_count=int(chart.get("trackCount") or 0),
            )
        )
    return ToplistResponse(items=items)


@router.get("/discover/toplist/{toplist_id}/tracks", response_model=PlaylistTracksResponse)
def discover_toplist_tracks(
    toplist_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> PlaylistTracksResponse:
    """Tracks inside an official chart (backed by NetEase playlist API)."""
    ensure_partner(current_user)
    cookie = cookie_vault.get_cookie(redis_client, current_user.uid)
    real_ip = _login_ip_for(redis_client, current_user.uid) if cookie else None
    try:
        tracks = netease_client.playlist_tracks(
            cookie or "", toplist_id, page, page_size, real_ip=real_ip
        )
    except netease_client.NeteaseError as exc:
        if cookie:
            _handle_netease_error(exc, redis_client, current_user.uid)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": f"netease_{exc.kind}", "message": exc.message},
        ) from exc

    songs = tracks.get("songs") or []
    items = [_song_from_cloudsearch(s) for s in songs]
    total = int(tracks.get("songCount") or len(items))
    has_next = (page * page_size) < total
    return PlaylistTracksResponse(items=items, page=page, page_size=page_size, has_next=has_next)


# ---------------------------------------------------------------------------
# Listen history
# ---------------------------------------------------------------------------

@router.get("/history", response_model=ListenHistoryResponse)
def list_listen_history(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ListenHistoryResponse:
    ensure_partner(current_user)
    raw_items = listen_history.list_history(db, limit=limit)
    items = [
        ListenHistoryItem(
            song_id=str(item.get("song_id")),
            name=str(item.get("name") or ""),
            artists=[str(a) for a in (item.get("artists") or []) if a],
            album=item.get("album"),
            duration_ms=item.get("duration_ms"),
            cover_url=item.get("cover_url"),
            played_at_ms=int(item.get("played_at_ms") or 0),
            started_by_uid=str(item.get("started_by_uid") or ""),
        )
        for item in raw_items
    ]
    return ListenHistoryResponse(items=items)


# ---------------------------------------------------------------------------
# Local (uploaded) tracks — play without a NetEase login
# ---------------------------------------------------------------------------

_LOCAL_PREFIX = "local:"


def _song_meta_from_local(track: ListenLocalTrack) -> SongMeta:
    return SongMeta(
        song_id=track.song_id,
        name=track.name,
        artists=track.artists,
        album=track.album,
        duration_ms=track.duration_ms,
        cover_url=track.cover_url,
    )


def _split_artists(raw: str) -> list[str]:
    return [a.strip() for a in re.split(r"[,，/、]", raw or "") if a.strip()]


@router.get("/local-tracks", response_model=LocalTracksResponse)
def list_local_tracks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LocalTracksResponse:
    """List partner-uploaded audio files, newest first.

    These play without a NetEase login (no QR scan), reusing the same
    play / queue / WS-sync machinery as NetEase songs.
    """
    ensure_partner(current_user)
    rows = (
        db.query(ListenLocalTrack)
        .filter(ListenLocalTrack.deleted_at.is_(None))
        .order_by(ListenLocalTrack.created_at.desc())
        .all()
    )
    return LocalTracksResponse(items=[_song_meta_from_local(t) for t in rows])


@router.post(
    "/local-tracks", response_model=SongMeta, status_code=status.HTTP_201_CREATED
)
async def upload_local_track(
    file: UploadFile = File(...),
    name: str = Form(""),
    artist: str = Form(""),
    album: str = Form(""),
    duration_ms: Annotated[int | None, Form()] = None,
    cover_url: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SongMeta:
    """Upload an audio file and register it as a playable local track."""
    ensure_partner(current_user)

    upload = await process_audio_upload(file, "uploads/listen")

    display_name = (name or "").strip() or (file.filename or "未命名歌曲")
    track = ListenLocalTrack(
        name=display_name[:256],
        artists_json=json.dumps(_split_artists(artist), ensure_ascii=False),
        album=((album or "").strip() or None),
        duration_ms=(duration_ms if isinstance(duration_ms, int) and duration_ms > 0 else None),
        cover_url=((cover_url or "").strip() or None),
        audio_url=upload.url,
        uploaded_by_uid=current_user.uid,
    )
    db.add(track)
    db.flush()

    # Register an UploadReference so the media-serving route (/uploads/...) will
    # serve the file to both partners. Without it the gate returns 403 and the
    # audio won't play. Partner-only access mirrors watch-together videos.
    db.add(
        UploadReference(
            file_path=upload.url,
            content_kind="listen",
            content_id=track.id,
            slot="media",
            owner_user_id=current_user.id,
        )
    )
    db.commit()
    db.refresh(track)
    return _song_meta_from_local(track)


@router.delete("/local-tracks/{tid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_local_track(
    tid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Soft-delete a local track. The on-disk file is reclaimed by the existing
    orphan-upload cleanup job."""
    ensure_partner(current_user)
    track = (
        db.query(ListenLocalTrack)
        .filter(ListenLocalTrack.tid == tid, ListenLocalTrack.deleted_at.is_(None))
        .first()
    )
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="曲目不存在")
    track.deleted_at = datetime.now(timezone.utc)
    db.query(UploadReference).filter(
        UploadReference.content_kind == "listen",
        UploadReference.content_id == track.id,
    ).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Direct URL (R8)
# ---------------------------------------------------------------------------

def _local_song_url(db: Session, song_id: str) -> SongUrlResponse:
    """Resolve a ``local:<tid>`` song to its stored upload URL — no cookie."""
    tid = song_id[len(_LOCAL_PREFIX):]
    track = (
        db.query(ListenLocalTrack)
        .filter(ListenLocalTrack.tid == tid, ListenLocalTrack.deleted_at.is_(None))
        .first()
    )
    if track is None or not track.audio_url:
        return SongUrlResponse(
            song_id=song_id, url=None, provider="local", error_kind="unavailable"
        )
    return SongUrlResponse(song_id=song_id, url=track.audio_url, provider="local")


@router.get("/songs/{song_id}/url", response_model=SongUrlResponse)
def get_song_url(
    song_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> SongUrlResponse:
    ensure_partner(current_user)

    # Locally-uploaded tracks resolve straight to their stored URL — they never
    # touch NetEase and so don't require a scan-login cookie.
    if song_id.startswith(_LOCAL_PREFIX):
        return _local_song_url(db, song_id)

    # R8.2: prefer the cookie of the partner who started the current song;
    # fall back to the requester's cookie. Whoever's cookie wins gets the
    # song to play.
    state = room.get_state(redis_client)
    started_by = state["current"].get("started_by")
    # (owner_uid, cookie) pairs — we keep the owner so each attempt forwards
    # that partner's own login IP as realIP (using A's cookie with B's IP would
    # itself look like an 异地 login for A's account).
    candidates: list[tuple[str, str]] = []
    if started_by and started_by != current_user.uid:
        cookie_started = cookie_vault.get_cookie(redis_client, started_by)
        if cookie_started:
            candidates.append((started_by, cookie_started))
    own_cookie = cookie_vault.get_cookie(redis_client, current_user.uid)
    if own_cookie:
        candidates.append((current_user.uid, own_cookie))

    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "netease_login_required", "message": "请先登录网易云"},
        )

    last_exc: netease_client.NeteaseError | None = None
    for owner_uid, cookie in candidates:
        try:
            payload = netease_client.song_url(
                cookie, song_id, real_ip=_login_ip_for(redis_client, owner_uid)
            )
        except netease_client.NeteaseError as exc:
            last_exc = exc
            continue

        data = (payload.get("data") or [None])[0] or {}
        url = data.get("url")
        if url and _request_is_https(request):
            url = _force_https(url)
        if url:
            ttl_ms = data.get("time")
            expires_at_ms = (
                _now_ms() + int(ttl_ms) if isinstance(ttl_ms, (int, float)) else None
            )
            return SongUrlResponse(
                song_id=song_id,
                url=url,
                expires_at_ms=expires_at_ms,
            )
        # url is None — song unplayable. Don't try the next cookie; copyright
        # is per-song not per-account.
        return SongUrlResponse(
            song_id=song_id,
            url=None,
            error_kind="unavailable",
        )

    # Both attempts hit upstream errors. Surface the last one.
    if last_exc is not None:
        _handle_netease_error(last_exc, redis_client, current_user.uid)
    return SongUrlResponse(song_id=song_id, url=None, error_kind="unknown")


# ---------------------------------------------------------------------------
# Lyric
# ---------------------------------------------------------------------------

@router.get("/songs/{song_id}/lyric", response_model=SongLyricResponse)
def get_song_lyric(
    song_id: str,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
) -> SongLyricResponse:
    ensure_partner(current_user)

    # Locally-uploaded tracks have no NetEase lyric source.
    if song_id.startswith(_LOCAL_PREFIX):
        return SongLyricResponse(song_id=song_id, lines=[], kind="none")

    # /lyric is a public endpoint, but we mirror get_song_url's cookie order
    # (prefer the partner who started the song, each forwarding their OWN login
    # IP as realIP) for consistency, then fall back to an anonymous call so the
    # lyric is reachable even when nobody is logged in.
    state = room.get_state(redis_client)
    started_by = state["current"].get("started_by")
    candidates: list[tuple[str | None, str | None]] = []
    if started_by and started_by != current_user.uid:
        cookie_started = cookie_vault.get_cookie(redis_client, started_by)
        if cookie_started:
            candidates.append((started_by, cookie_started))
    own_cookie = cookie_vault.get_cookie(redis_client, current_user.uid)
    if own_cookie:
        candidates.append((current_user.uid, own_cookie))
    if not candidates:
        candidates.append((None, None))  # anonymous fallback

    last_exc: netease_client.NeteaseError | None = None
    for owner_uid, cookie in candidates:
        real_ip = _login_ip_for(redis_client, owner_uid) if owner_uid else None
        try:
            payload = netease_client.lyric(cookie, song_id, real_ip=real_ip)
        except netease_client.NeteaseError as exc:
            last_exc = exc
            continue
        return _lyric_from_payload(song_id, payload)

    if last_exc is not None:
        _handle_netease_error(last_exc, redis_client, current_user.uid)
    return SongLyricResponse(song_id=song_id, lines=[], kind="none")
