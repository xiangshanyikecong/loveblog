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

import logging
from pathlib import Path, PurePosixPath
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.core.media import (
    ALL_IMAGE_TYPES,
    MediaPolicy,
    compute_storage_stats,
    process_image,
    validate_mime_type,
)
from app.db.session import get_db
from app.models.album import Album
from app.models.article import Article, ArticleBlock
from app.models.capsule import Capsule
from app.models.listen_local_track import ListenLocalTrack
from app.models.moment import Moment
from app.models.site_setting import SiteSetting
from app.models.user import User
from app.models.watch import WatchSource
from app.schemas.upload import QQAvatarRequest, UploadCleanupResponse, UploadResponse
from app.services.upload_references import register_pending_upload


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_UPLOADS_ROOT = (BACKEND_ROOT / "uploads").resolve()

# Hard-coded maximums enforced before policy processing.
MAX_IMAGE_SIZE_BYTES = 30 * 1024 * 1024   # 30 MB raw upload limit
MAX_VIDEO_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024   # 25 MB (voice notes are small)

VIDEO_CONTENT_TYPE_MAP = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}

# Browser MediaRecorder emits webm/opus on Chromium and mp4/aac on Safari; we
# store the recording verbatim (no transcoding) so playback uses the same codec
# the browser already supports.
AUDIO_CONTENT_TYPE_MAP = {
    "audio/webm": ".weba",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/x-m4a": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}

# QQ exposes public avatars on a fixed host. Only the (validated, numeric) QQ
# number is interpolated into the query string and the host is hard-coded, so
# there is no SSRF surface here.
QQ_AVATAR_ENDPOINT = "https://q1.qlogo.cn/g"


# ---------------------------------------------------------------------------
# DB / path helpers
# ---------------------------------------------------------------------------

def _get_or_create_setting(db: Session) -> SiteSetting:
    setting = db.query(SiteSetting).filter(SiteSetting.id == 1).first()
    if setting is not None:
        return setting
    setting = SiteSetting(id=1)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def _resolve_storage_dir(relative_path: str) -> Path:
    DEFAULT_UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    normalized = relative_path.strip().replace("\\", "/").lstrip("/") or "uploads/albums"
    candidate = (BACKEND_ROOT / normalized).resolve()
    if candidate != DEFAULT_UPLOADS_ROOT and DEFAULT_UPLOADS_ROOT not in candidate.parents:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid upload directory configuration",
        )
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _build_relative_upload_url(stored_file: Path) -> str:
    """Return a server-relative URL of the form ``/uploads/<...>`` for a stored
    file.

    The value depends only on ``stored_file``'s location under
    ``DEFAULT_UPLOADS_ROOT`` and is therefore independent of any request-derived
    header (Host, scheme, X-Forwarded-*). The frontend's ``resolveAssetUrl``
    helper resolves this against the viewer's current origin, so the asset
    works regardless of how the page was reached.

    Anchoring at ``DEFAULT_UPLOADS_ROOT`` (rather than the project root) makes
    it structurally impossible to return a path outside ``/uploads/...``.
    """
    relative = stored_file.resolve().relative_to(DEFAULT_UPLOADS_ROOT).as_posix()
    return f"/uploads/{relative}"


def _to_abs_path_from_url(url: str) -> Path | None:
    if not url:
        return None
    raw = str(url).strip()
    if not raw:
        return None
    marker = "/uploads/"
    idx = raw.find(marker)
    if idx < 0:
        return None
    rel = raw[idx + 1:].replace("\\", "/")
    candidate = (BACKEND_ROOT / rel).resolve()
    try:
        candidate.relative_to(DEFAULT_UPLOADS_ROOT)
    except ValueError:
        return None
    return candidate


# ---------------------------------------------------------------------------
# Referenced-path collector (for orphan cleanup)
# ---------------------------------------------------------------------------

def _extract_urls_from_article_blocks(blocks: list[ArticleBlock]) -> set[str]:
    urls: set[str] = set()
    for block in blocks:
        value = str(block.content or "").strip()
        if value and "/uploads/" in value:
            urls.add(value)
    return urls


def _collect_referenced_upload_paths(db: Session) -> set[Path]:
    refs: set[Path] = set()

    users = db.query(User).filter(User.deleted_at.is_(None)).all()
    for user in users:
        path = _to_abs_path_from_url(str(user.avatar or ""))
        if path:
            refs.add(path)

    articles = (
        db.query(Article)
        .options(joinedload(Article.blocks))
        .filter(Article.deleted_at.is_(None))
        .all()
    )
    for article in articles:
        cover = _to_abs_path_from_url(str(article.cover_url or ""))
        if cover:
            refs.add(cover)
        for url in _extract_urls_from_article_blocks(list(article.blocks or [])):
            path = _to_abs_path_from_url(url)
            if path:
                refs.add(path)

    albums = (
        db.query(Album)
        .options(joinedload(Album.media_items))
        .filter(Album.deleted_at.is_(None))
        .all()
    )
    for album in albums:
        cover = _to_abs_path_from_url(str(album.cover_url or ""))
        if cover:
            refs.add(cover)
        for item in list(album.media_items or []):
            for u in (item.file_url, item.thumbnail_url):
                p = _to_abs_path_from_url(str(u or ""))
                if p:
                    refs.add(p)

    moments = db.query(Moment).filter(Moment.deleted_at.is_(None)).all()
    for moment in moments:
        for url in list(moment.media_urls or []):
            path = _to_abs_path_from_url(url)
            if path:
                refs.add(path)
        audio_path = _to_abs_path_from_url(str(moment.audio_url or ""))
        if audio_path:
            refs.add(audio_path)

    from app.models.checkin import CheckIn
    from app.models.chat_message import ChatMessage

    checkins = db.query(CheckIn).filter(CheckIn.deleted_at.is_(None)).all()
    for checkin in checkins:
        for url in checkin.media_urls or []:
            path = _to_abs_path_from_url(str(url or ""))
            if path:
                refs.add(path)

    chat_messages = db.query(ChatMessage).filter(ChatMessage.deleted_at.is_(None)).all()
    for message in chat_messages:
        path = _to_abs_path_from_url(str(message.media_url or ""))
        if path:
            refs.add(path)

    settings = db.query(SiteSetting).all()
    for setting in settings:
        for url in (setting.partner_a_avatar, setting.partner_b_avatar):
            path = _to_abs_path_from_url(str(url or ""))
            if path:
                refs.add(path)

    # Watch-together uploaded videos live under /uploads/videos but aren't
    # referenced by any other content — without this they'd be flagged as
    # orphans and deleted by cleanup.
    watch_sources = db.query(WatchSource).filter(WatchSource.deleted_at.is_(None)).all()
    for source in watch_sources:
        path = _to_abs_path_from_url(str(source.url or ""))
        if path:
            refs.add(path)

    # Time-capsule voice / video recordings live under /uploads/capsule and are
    # likewise not referenced elsewhere; protect them from orphan cleanup.
    capsules = db.query(Capsule).filter(Capsule.deleted_at.is_(None)).all()
    for capsule in capsules:
        path = _to_abs_path_from_url(str(capsule.media_url or ""))
        if path:
            refs.add(path)

    # Listen-together uploaded audio lives under /uploads/listen and isn't
    # referenced elsewhere; protect it from orphan cleanup.
    local_tracks = (
        db.query(ListenLocalTrack).filter(ListenLocalTrack.deleted_at.is_(None)).all()
    )
    for track in local_tracks:
        path = _to_abs_path_from_url(str(track.audio_url or ""))
        if path:
            refs.add(path)

    # A newly uploaded file may not yet be attached to its final content row.
    # Keep fresh uploader-owned leases; stale leases are intentionally ignored
    # so cleanup can reclaim abandoned uploads after 24 hours.
    from datetime import datetime, timedelta, timezone
    from app.models.upload_reference import UploadReference

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    pending_refs = db.query(UploadReference).filter(
        UploadReference.content_kind == "pending",
        UploadReference.created_at >= cutoff,
    ).all()
    for pending in pending_refs:
        path = _to_abs_path_from_url(pending.file_path)
        if path:
            refs.add(path)

    return refs


def _cleanup_orphan_upload_files(db: Session, dry_run: bool) -> UploadCleanupResponse:
    if not DEFAULT_UPLOADS_ROOT.exists():
        return UploadCleanupResponse(
            dry_run=dry_run, scanned=0, referenced=0,
            orphaned=0, deleted=0, deleted_files=[],
        )

    referenced = _collect_referenced_upload_paths(db)
    scanned_files = [p for p in DEFAULT_UPLOADS_ROOT.rglob("*") if p.is_file()]
    orphaned_files = [p for p in scanned_files if p.resolve() not in referenced]

    deleted_files: list[str] = []
    deleted_count = 0
    for path in orphaned_files:
        rel = path.resolve().relative_to(BACKEND_ROOT).as_posix()
        deleted_files.append(rel)
        if not dry_run:
            try:
                path.unlink(missing_ok=True)
                deleted_count += 1
            except OSError:
                continue

    return UploadCleanupResponse(
        dry_run=dry_run,
        scanned=len(scanned_files),
        referenced=len(referenced),
        orphaned=len(orphaned_files),
        deleted=deleted_count if not dry_run else 0,
        deleted_files=deleted_files,
    )


# ---------------------------------------------------------------------------
# Core upload processor (images)
# ---------------------------------------------------------------------------

def _persist_image_bytes(
    raw_bytes: bytes,
    content_type: str,
    original_name: str,
    db: Session,
    path_attr: str,
) -> UploadResponse:
    """Run raw image bytes through the media pipeline and persist them.

    Shared by direct file uploads and server-side fetches (e.g. QQ avatars),
    so both paths get the same whitelist / size guard / EXIF strip / thumbnail
    treatment and the same storage layout.
    """
    content_type = (content_type or "").lower().strip()
    setting = _get_or_create_setting(db)
    policy = MediaPolicy.from_setting(setting)

    # 1. Whitelist check (uses per-setting allowed types)
    try:
        validate_mime_type(content_type, policy)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # 2. Guard hard upload ceiling
    if not raw_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if len(raw_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File is too large")

    # 3. Process: compress + EXIF strip + thumbnail
    try:
        result = process_image(raw_bytes, content_type, policy)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Pillow not installed — fall back to raw save
        result = None  # handled below
        _pillow_missing = str(exc)
    else:
        _pillow_missing = None

    configured_path = getattr(setting, path_attr, "uploads/media")
    storage_dir = _resolve_storage_dir(configured_path)
    stem = uuid4().hex

    if result is not None:
        extension = result.extension
        stored_file = storage_dir / f"{stem}{extension}"
        stored_file.write_bytes(result.data)

        # Save thumbnail alongside original with _thumb suffix
        if result.thumbnail:
            thumb_file = storage_dir / f"{stem}_thumb{extension}"
            thumb_file.write_bytes(result.thumbnail)
    else:
        # Pillow unavailable: raw save with original extension
        logger.warning(_pillow_missing)
        suffix = PurePosixPath(original_name or "file").suffix.lower() or ".jpg"
        stored_file = storage_dir / f"{stem}{suffix}"
        stored_file.write_bytes(raw_bytes)

    return UploadResponse(
        url=_build_relative_upload_url(stored_file),
        file_name=original_name or stored_file.name,
        content_type=content_type,
        size=stored_file.stat().st_size,
    )


async def _process_image_upload(
    file: UploadFile,
    db: Session,
    path_attr: str,
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected")

    content_type = (file.content_type or "").lower().strip()
    raw_bytes = await file.read()
    await file.close()

    return _persist_image_bytes(raw_bytes, content_type, file.filename, db, path_attr)


async def _process_video_upload(
    file: UploadFile,
    db: Session,
    path_attr: str,
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected")

    content_type = (file.content_type or "").lower()
    if content_type not in VIDEO_CONTENT_TYPE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video type. Allowed: {', '.join(VIDEO_CONTENT_TYPE_MAP.values())}",
        )

    file_bytes = await file.read()
    await file.close()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if len(file_bytes) > MAX_VIDEO_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File is too large")

    setting = _get_or_create_setting(db)
    suffix = VIDEO_CONTENT_TYPE_MAP[content_type]
    storage_dir = _resolve_storage_dir(getattr(setting, path_attr, "uploads/videos"))
    stored_file = storage_dir / f"{uuid4().hex}{suffix}"
    stored_file.write_bytes(file_bytes)

    return UploadResponse(
        url=_build_relative_upload_url(stored_file),
        file_name=file.filename,
        content_type=file.content_type,
        size=len(file_bytes),
    )


async def process_audio_upload(
    file: UploadFile,
    storage_subdir: str,
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected")

    # Strip any codec suffix, e.g. "audio/webm;codecs=opus".
    content_type = (file.content_type or "").split(";")[0].lower().strip()
    if content_type not in AUDIO_CONTENT_TYPE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的音频类型 {content_type!r}",
        )

    file_bytes = await file.read()
    await file.close()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if len(file_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File is too large")

    suffix = AUDIO_CONTENT_TYPE_MAP[content_type]
    storage_dir = _resolve_storage_dir(storage_subdir)
    stored_file = storage_dir / f"{uuid4().hex}{suffix}"
    stored_file.write_bytes(file_bytes)

    return UploadResponse(
        url=_build_relative_upload_url(stored_file),
        file_name=file.filename,
        content_type=content_type,
        size=len(file_bytes),
    )


async def _process_video_upload_to(
    file: UploadFile,
    storage_subdir: str,
) -> UploadResponse:
    """Store a video upload under an explicit subdir (no SiteSetting attr)."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected")

    content_type = (file.content_type or "").split(";")[0].lower().strip()
    if content_type not in VIDEO_CONTENT_TYPE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported video type. Allowed: {', '.join(VIDEO_CONTENT_TYPE_MAP.values())}",
        )

    file_bytes = await file.read()
    await file.close()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if len(file_bytes) > MAX_VIDEO_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File is too large")

    suffix = VIDEO_CONTENT_TYPE_MAP[content_type]
    storage_dir = _resolve_storage_dir(storage_subdir)
    stored_file = storage_dir / f"{uuid4().hex}{suffix}"
    stored_file.write_bytes(file_bytes)

    return UploadResponse(
        url=_build_relative_upload_url(stored_file),
        file_name=file.filename,
        content_type=content_type,
        size=len(file_bytes),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/albums", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_album_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    ensure_partner(current_user)
    result = await _process_image_upload(file, db, "albums_path")
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/articles", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_article_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    ensure_partner(current_user)
    result = await _process_image_upload(file, db, "articles_path")
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/avatars", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_avatar_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    ensure_partner(current_user)
    result = await _process_image_upload(file, db, "avatar_path")
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/avatars/from-qq", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def fetch_avatar_from_qq(
    payload: QQAvatarRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    """Fetch a QQ account's public avatar and store it as a local upload.

    Downloading and re-hosting (rather than linking ``q1.qlogo.cn`` directly)
    keeps avatars working offline, dodges hotlink/CORS surprises, and runs the
    image through the same processing pipeline as a normal upload.
    """
    ensure_partner(current_user)

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(
                QQ_AVATAR_ENDPOINT,
                params={"b": "qq", "nk": payload.qq, "s": "640"},
            )
    except httpx.HTTPError as exc:
        logger.warning("QQ avatar fetch failed for %s: %s", payload.qq, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="获取 QQ 头像失败，请稍后重试",
        ) from exc

    if response.status_code != 200 or not response.content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="获取 QQ 头像失败，请确认 QQ 号是否正确",
        )

    content_type = (response.headers.get("content-type") or "image/jpeg").split(";")[0].strip().lower()
    if content_type not in ALL_IMAGE_TYPES:
        content_type = "image/jpeg"

    result = _persist_image_bytes(response.content, content_type, f"qq-{payload.qq}.jpg", db, "avatar_path")
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/timeline", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_timeline_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    ensure_partner(current_user)
    result = await _process_image_upload(file, db, "timeline_path")
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/checkin", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_checkin_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    """Upload an image attached to a cottage check-in.

    Reuses the same processing pipeline (MIME whitelist / EXIF strip /
    thumbnail) and the existing ``timeline_path`` storage location, so we
    don't fragment the on-disk layout. The returned URL is a server-relative
    ``/uploads/<...>`` path the frontend will pass back as one of the
    ``media_urls`` entries on the subsequent ``POST /v1/checkins``.
    """
    ensure_partner(current_user)
    result = await _process_image_upload(file, db, "timeline_path")
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/chat-audio", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_chat_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    """Upload a voice note for cottage chat."""
    ensure_partner(current_user)
    result = await process_audio_upload(file, "uploads/chat")
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/chat-encrypted-media", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_chat_encrypted_media(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    """Store an opaque encrypted blob for E2E cottage chat media.

    No MIME whitelist / image processing: the content is client-side
    AES-GCM ciphertext (random bytes). The server cannot decrypt it.
    Stored with a ``.enc`` suffix so the file-serving endpoint and media
    panel treat it as opaque binary.
    """
    ensure_partner(current_user)
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected")

    file_bytes = await file.read()
    await file.close()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    # Same ceiling as audio (25 MB) – encrypted images/voice are small.
    if len(file_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File is too large")

    storage_dir = _resolve_storage_dir("uploads/chat")
    stored_file = storage_dir / f"{uuid4().hex}.enc"
    stored_file.write_bytes(file_bytes)

    result = UploadResponse(
        url=_build_relative_upload_url(stored_file),
        file_name=file.filename,
        content_type="application/octet-stream",
        size=len(file_bytes),
    )
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/videos", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    ensure_partner(current_user)
    result = await _process_video_upload(file, db, "videos_path")
    register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
    return result


@router.post("/capsule", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_capsule_media(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    """Upload a voice note or short video for a time capsule / voice diary.

    Accepts both audio and video; the file is stored under ``uploads/capsule``
    and the returned ``/uploads/...`` URL is later attached to the capsule (or
    moment), which registers a partner-only :class:`UploadReference`. The URL is
    itself kept sealed by the capsules API until ``open_at``.
    """
    ensure_partner(current_user)
    content_type = (file.content_type or "").split(";")[0].lower().strip()
    if content_type in AUDIO_CONTENT_TYPE_MAP:
        result = await process_audio_upload(file, "uploads/capsule")
        register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
        return result
    if content_type in VIDEO_CONTENT_TYPE_MAP:
        result = await _process_video_upload_to(file, "uploads/capsule")
        register_pending_upload(db, file_url=result.url, owner_user_id=current_user.id)
        return result
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="仅支持语音或短视频文件",
    )


@router.get("/storage-stats")
def get_storage_stats(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return per-directory and total upload storage usage."""
    ensure_partner(current_user)
    return compute_storage_stats(DEFAULT_UPLOADS_ROOT)


@router.post("/cleanup", response_model=UploadCleanupResponse)
def cleanup_orphan_uploads(
    dry_run: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadCleanupResponse:
    ensure_partner(current_user)
    return _cleanup_orphan_upload_files(db, dry_run=dry_run)
