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

"""HTTP client wrapping NeteaseCloudMusicApi.

NeteaseCloudMusicApi (Binaryify) is a community-maintained reverse-engineered
proxy in front of NetEase Cloud Music. We only ever talk to NeteaseCloudMusicApi
over the docker-compose internal network — never directly to music.163.com.

All transport / parse / NetEase-business failures are normalized into a
:class:`NeteaseError` with a ``kind`` field; the route layer catches and
maps those kinds to HTTP responses (R10.1 / R10.2). Routes never see a
raw httpx exception escape this module.

Privacy: cookies are passed in as plain string arguments (already decrypted
by the caller for the duration of a single request) and forwarded as the
``Cookie`` header on the upstream call. We do NOT keep cookies in any
module-level cache, do NOT log cookies (just an opaque "Cookie: <hidden>"
on debug logs), and do NOT echo the upstream ``Set-Cookie`` back to our
own clients.
"""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


_NETEASE_LOGIN_REQUIRED_CODE = 301  # NetEase's "not logged in" code
# NetEase's "no copyright" or "song unplayable" code returned by /song/url/v1
_NETEASE_NO_COPYRIGHT_CODE = -110  # heuristic; varies by upstream version


class NeteaseError(Exception):
    """Wrap a single failed NetEase upstream call.

    ``kind`` is the route-layer-friendly classification:

    - ``timeout`` — httpx timeout
    - ``http_error`` — non-2xx or transport error
    - ``parse_error`` — JSON parse / missing field
    - ``login_required`` — upstream returned the 'not logged in' code
    - ``unsupported`` — programmer error / endpoint disabled
    """

    def __init__(self, kind: str, message: str = "") -> None:
        super().__init__(f"[netease/{kind}] {message}")
        self.kind = kind
        self.message = message


_client = httpx.Client(base_url=settings.netease_api_base_url, timeout=5.0)


# NetEase risk-control judges "异地/异常登录" mainly by source IP. We forward a
# stable mainland-China IP on every call (NeteaseCloudMusicApi turns the
# ``realIP`` query param into X-Real-IP / X-Forwarded-For, which NetEase's
# gateway trusts). Pinned ONCE at import for the process lifetime: a single
# fixed identity is far less suspicious than the server's real IP — and than a
# per-request random IP, which makes one account look like it's "jumping around"
# and is itself a risk signal.
def _pick_stable_real_ip() -> str:
    configured = (settings.netease_real_ip or "").strip()
    if configured:
        return configured
    # Mirror the prefix ranges NeteaseCloudMusicApi itself uses for spoofing.
    import random

    prefix = random.choice(
        ["116.25", "116.76", "116.77", "116.78", "116.79", "116.80",
         "116.81", "116.82", "116.83", "116.84", "116.85", "116.86",
         "116.87", "116.88", "116.89", "116.90", "116.91", "116.92",
         "116.93", "116.94"]
    )
    return f"{prefix}.{random.randint(1, 254)}.{random.randint(1, 254)}"


_REAL_IP = _pick_stable_real_ip()


def _params(real_ip: str | None = None, **extra: Any) -> dict[str, Any]:
    """Common query params for every upstream call: fresh timestamp (cache
    bust) + the spoofed realIP (risk-control). ``real_ip`` is the per-request
    IP the route layer wants NetEase to see (the partner's real login IP);
    when absent we fall back to the process-wide stable IP. Caller-supplied
    params are merged on top."""
    base: dict[str, Any] = {"timestamp": _ts_param(), "realIP": real_ip or _REAL_IP}
    base.update(extra)
    return base


def _safe_call(func: Callable[..., dict]) -> Callable[..., dict]:
    """Decorator: convert all expected upstream failure modes into NeteaseError."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            payload = func(*args, **kwargs)
        except httpx.TimeoutException as exc:
            raise NeteaseError("timeout", str(exc)) from exc
        except httpx.HTTPError as exc:
            raise NeteaseError("http_error", str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise NeteaseError("parse_error", str(exc)) from exc

        # NeteaseCloudMusicApi convention: top-level "code" field. 200 = OK,
        # 301 = login required. We don't fail on every non-200 — some
        # endpoints (e.g. /song/url/v1 for unplayable songs) carry their
        # signal in nested fields rather than the top-level code.
        code = payload.get("code") if isinstance(payload, dict) else None
        if code == _NETEASE_LOGIN_REQUIRED_CODE:
            raise NeteaseError("login_required", "upstream reports not logged in")
        return payload

    return wrapper


def _cookie_header(cookie: str | None) -> dict[str, str]:
    return {"Cookie": cookie} if cookie else {}


@_safe_call
def qr_key(real_ip: str | None = None) -> dict:
    """Step 1 of QR-code login. Returns a unikey to feed into qr_create."""
    r = _client.get("/login/qr/key", params=_params(real_ip))
    r.raise_for_status()
    return r.json()


@_safe_call
def qr_create(unikey: str, real_ip: str | None = None) -> dict:
    """Step 2: turn the unikey into a base64 PNG data URL the frontend can
    drop straight into ``<img src=...>`` (response field ``qrimg``).
    """
    r = _client.get(
        "/login/qr/create",
        params=_params(real_ip, key=unikey, qrimg="true"),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def qr_check(unikey: str, real_ip: str | None = None) -> dict:
    """Step 3: poll for scan / confirm. ``code`` semantics:
    800=expired, 801=waiting, 802=scanned, 803=confirmed (cookie present).
    On 803 the response includes a ``cookie`` field with the full cookie
    string the caller should immediately encrypt and store.
    """
    r = _client.get(
        "/login/qr/check",
        params=_params(real_ip, key=unikey),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def login_status(cookie: str, real_ip: str | None = None) -> dict:
    r = _client.post(
        "/login/status",
        headers=_cookie_header(cookie),
        params=_params(real_ip),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def search(cookie: str | None, kw: str, page: int, page_size: int, real_ip: str | None = None) -> dict:
    """Cloudsearch — returns the modern song list (``result.songs``)."""
    offset = max(0, (page - 1) * page_size)
    r = _client.get(
        "/cloudsearch",
        params=_params(
            real_ip,
            keywords=kw,
            limit=page_size,
            offset=offset,
            type=1,
        ),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def playlists(cookie: str, uid: int, real_ip: str | None = None) -> dict:
    """User's playlists. We pass the cookie *and* the upstream uid because
    NeteaseCloudMusicApi requires both for /user/playlist.
    """
    r = _client.get(
        "/user/playlist",
        params=_params(real_ip, uid=uid, limit=200),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def playlist_tracks(cookie: str, playlist_id: str, page: int, page_size: int, real_ip: str | None = None) -> dict:
    """Tracks inside a single playlist. Endpoint: /playlist/track/all."""
    offset = max(0, (page - 1) * page_size)
    r = _client.get(
        "/playlist/track/all",
        params=_params(
            real_ip,
            id=playlist_id,
            limit=page_size,
            offset=offset,
        ),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def song_url(cookie: str, song_id: str, real_ip: str | None = None) -> dict:
    """Resolve a temporary signed mp3 URL. The response top-level ``data[0]``
    contains ``url`` (None or string), ``code`` (200 OK, otherwise
    unplayable for various reasons), and ``time`` (TTL ms).
    """
    r = _client.get(
        "/song/url/v1",
        params=_params(real_ip, id=song_id, level="standard"),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def song_detail(cookie: str, song_ids: str, real_ip: str | None = None) -> dict:
    """Get song details by IDs. More accurate than search for known song_ids.

    Args:
        cookie: NetEase cookie
        song_ids: Comma-separated song IDs (e.g., "186016,347230")
        real_ip: Spoofed source IP to forward to NetEase (cookie owner's login IP)

    Returns:
        Response with songs array containing full metadata
    """
    r = _client.get(
        "/song/detail",
        params=_params(real_ip, ids=song_ids),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def recommend_songs(cookie: str, real_ip: str | None = None) -> dict:
    """Daily recommended songs for the logged-in user."""
    r = _client.get(
        "/recommend/songs",
        params=_params(real_ip),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def personalized_playlists(cookie: str, limit: int = 12, real_ip: str | None = None) -> dict:
    """Personalized playlist recommendations (homepage-style discovery)."""
    r = _client.get(
        "/personalized",
        params=_params(real_ip, limit=max(1, min(limit, 30))),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def toplist(cookie: str | None = None, real_ip: str | None = None) -> dict:
    """All official music charts / rankings."""
    r = _client.get(
        "/toplist",
        params=_params(real_ip),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def playlist_detail(cookie: str | None, playlist_id: str, real_ip: str | None = None) -> dict:
    """Playlist metadata (used for chart drill-down)."""
    r = _client.get(
        "/playlist/detail",
        params=_params(real_ip, id=playlist_id),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


@_safe_call
def lyric(cookie: str | None, song_id: str, real_ip: str | None = None) -> dict:
    """Fetch a song's LRC lyric. Public endpoint, so ``cookie`` is optional.

    The original (timestamped) lyric lives under ``lrc.lyric`` and the
    optional Chinese translation under ``tlyric.lyric``. Pure-music tracks
    come back with ``nolyric: true``; not-yet-transcribed ones with
    ``uncollected: true``.
    """
    r = _client.get(
        "/lyric",
        params=_params(real_ip, id=song_id),
        headers=_cookie_header(cookie),
    )
    r.raise_for_status()
    return r.json()


def _ts_param() -> int:
    """NetEase mirrors require a fresh timestamp to bypass upstream caches."""
    import time

    return int(time.time() * 1000)
