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

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Album,
    Article,
    Capsule,
    ChatMessage,
    CheckIn,
    Moment,
    SiteSetting,
    UploadReference,
    WatchSource,
)
from app.models.article import ArticleStatus
from app.models.content_visibility import ContentVisibility
from app.models.moment import Visibility as MomentVisibility
from app.models.user import User
from app.models.listen_local_track import ListenLocalTrack
from app.services.visibility_policy import VisibilityPolicy


def extract_upload_suffix(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    raw = str(raw_url).strip()
    marker = "/uploads/"
    idx = raw.find(marker)
    if idx < 0:
        return None
    return raw[idx:]


def _album_ref_rows(album: Album) -> list[UploadReference]:
    rows: list[UploadReference] = []
    cover_path = extract_upload_suffix(album.cover_url)
    if cover_path:
        rows.append(
            UploadReference(
                file_path=cover_path,
                content_kind="album",
                content_id=album.id,
                slot="cover",
                owner_user_id=album.author_id,
                visibility=album.visibility.value if album.visibility else None,
                is_public=bool(album.is_public),
                content_is_encrypted=bool(album.is_encrypted),
                ref_is_encrypted=bool(album.is_encrypted),
            )
        )

    for media in album.media_items or []:
        file_path = extract_upload_suffix(media.file_url)
        if file_path:
            rows.append(
                UploadReference(
                    file_path=file_path,
                    content_kind="album",
                    content_id=album.id,
                    slot="media_file",
                    owner_user_id=album.author_id,
                    visibility=album.visibility.value if album.visibility else None,
                    is_public=bool(album.is_public),
                    content_is_encrypted=bool(album.is_encrypted),
                    ref_is_encrypted=bool(media.is_encrypted),
                )
            )

        thumb_path = extract_upload_suffix(media.thumbnail_url)
        if thumb_path:
            rows.append(
                UploadReference(
                    file_path=thumb_path,
                    content_kind="album",
                    content_id=album.id,
                    slot="media_thumbnail",
                    owner_user_id=album.author_id,
                    visibility=album.visibility.value if album.visibility else None,
                    is_public=bool(album.is_public),
                    content_is_encrypted=bool(album.is_encrypted),
                    ref_is_encrypted=bool(media.is_encrypted),
                )
            )
    return rows


def _article_ref_rows(article: Article) -> list[UploadReference]:
    rows: list[UploadReference] = []
    cover_path = extract_upload_suffix(article.cover_url)
    if cover_path:
        rows.append(
            UploadReference(
                file_path=cover_path,
                content_kind="article",
                content_id=article.id,
                slot="cover",
                owner_user_id=article.author_id,
                visibility=article.visibility.value if article.visibility else None,
                status=article.status.value if article.status else None,
                content_is_encrypted=bool(article.is_encrypted),
                ref_is_encrypted=bool(article.is_encrypted),
                partner_can_edit=bool(article.partner_can_edit),
            )
        )

    for block in article.blocks or []:
        block_path = extract_upload_suffix(block.content)
        if block_path:
            rows.append(
                UploadReference(
                    file_path=block_path,
                    content_kind="article",
                    content_id=article.id,
                    slot="block",
                    owner_user_id=article.author_id,
                    visibility=article.visibility.value if article.visibility else None,
                    status=article.status.value if article.status else None,
                    content_is_encrypted=bool(article.is_encrypted),
                    ref_is_encrypted=bool(article.is_encrypted),
                    partner_can_edit=bool(article.partner_can_edit),
                )
            )
    return rows


def _moment_ref_rows(moment: Moment) -> list[UploadReference]:
    rows: list[UploadReference] = []
    for media_url in moment.media_urls or []:
        media_path = extract_upload_suffix(media_url)
        if media_path:
            rows.append(
                UploadReference(
                    file_path=media_path,
                    content_kind="moment",
                    content_id=moment.id,
                    slot="media",
                    owner_user_id=moment.author_id,
                    visibility=moment.visibility.value if moment.visibility else None,
                )
            )
    audio_path = extract_upload_suffix(getattr(moment, "audio_url", None))
    if audio_path:
        rows.append(
            UploadReference(
                file_path=audio_path,
                content_kind="moment",
                content_id=moment.id,
                slot="audio",
                owner_user_id=moment.author_id,
                visibility=moment.visibility.value if moment.visibility else None,
            )
        )
    return rows


def _checkin_ref_rows(checkin: CheckIn) -> list[UploadReference]:
    """Build UploadReference rows for a CheckIn's media files.

    Cottage check-ins are partner-only (both PartnerA and PartnerB can view).
    No cover slot — only ``media`` slot for each photo. ``visibility`` is
    left None because access control collapses to "is the viewer a Partner?"
    via :func:`can_access_upload_reference`.
    """
    rows: list[UploadReference] = []
    for media_url in checkin.media_urls or []:
        media_path = extract_upload_suffix(media_url)
        if media_path:
            rows.append(
                UploadReference(
                    file_path=media_path,
                    content_kind="checkin",
                    content_id=checkin.id,
                    slot="media",
                    owner_user_id=checkin.author_id,
                )
            )
    return rows


def _chat_message_ref_rows(message: ChatMessage) -> list[UploadReference]:
    """Build UploadReference rows for a chat message's image / sticker file.

    Cottage chat is a private 1:1 partner channel, so access collapses to
    "is the viewer a Partner?" — mirroring check-ins / watch sources.
    """
    file_path = extract_upload_suffix(message.media_url)
    if not file_path:
        return []
    return [
        UploadReference(
            file_path=file_path,
            content_kind="chat",
            content_id=message.id,
            slot="media",
            owner_user_id=message.sender_id,
        )
    ]


def _capsule_ref_rows(capsule: Capsule) -> list[UploadReference]:
    """Build UploadReference rows for a time-capsule's voice / video file.

    Time capsules are a private 1:1 partner artefact, so access collapses to
    "is the viewer a Partner?" — mirroring check-ins / chat / watch. The
    *temporal* lock (sealed until ``open_at``) is enforced at the API layer by
    masking ``media_url``; this gate only governs raw file fetches once the URL
    is known.
    """
    file_path = extract_upload_suffix(capsule.media_url)
    if not file_path:
        return []
    return [
        UploadReference(
            file_path=file_path,
            content_kind="capsule",
            content_id=capsule.id,
            slot="media",
            owner_user_id=capsule.author_id,
            status=capsule.open_at.isoformat(),
        )
    ]


def _listen_local_track_ref_rows(track: ListenLocalTrack) -> list[UploadReference]:
    file_path = extract_upload_suffix(track.audio_url)
    if not file_path:
        return []
    # uploaded_by_uid is deliberately a public UID rather than an FK. The
    # reference's owner is filled during rebuild below when the user exists.
    return [
        UploadReference(
            file_path=file_path,
            content_kind="listen",
            content_id=track.id,
            slot="audio",
            owner_user_id=None,
        )
    ]


def register_pending_upload(db: Session, *, file_url: str, owner_user_id: int) -> None:
    """Grant the uploader temporary access until the URL is attached to content."""
    file_path = extract_upload_suffix(file_url)
    if not file_path:
        return
    db.query(UploadReference).filter(
        UploadReference.file_path == file_path,
        UploadReference.content_kind == "pending",
        UploadReference.owner_user_id == owner_user_id,
    ).delete(synchronize_session=False)
    db.add(
        UploadReference(
            file_path=file_path,
            content_kind="pending",
            content_id=owner_user_id,
            slot="upload",
            owner_user_id=owner_user_id,
        )
    )
    db.commit()


def _consume_pending_uploads(db: Session, rows: Iterable[UploadReference]) -> None:
    paths = {row.file_path for row in rows if row.file_path}
    if not paths:
        return
    db.query(UploadReference).filter(
        UploadReference.content_kind == "pending",
        UploadReference.file_path.in_(paths),
    ).delete(synchronize_session=False)


def _site_setting_ref_rows(setting: SiteSetting) -> list[UploadReference]:
    rows: list[UploadReference] = []
    for slot, raw_path in (
        ("partner_a_avatar", setting.partner_a_avatar),
        ("partner_b_avatar", setting.partner_b_avatar),
    ):
        avatar_path = extract_upload_suffix(raw_path)
        if avatar_path:
            rows.append(
                UploadReference(
                    file_path=avatar_path,
                    content_kind="site_setting",
                    content_id=setting.id,
                    slot=slot,
                )
            )
    return rows


def _watch_source_ref_rows(source: WatchSource) -> list[UploadReference]:
    """Build UploadReference rows for an uploaded watch source's video file.

    Only ``kind="upload"`` sources (whose ``url`` is a ``/uploads/...`` path)
    get a row — external direct links are fetched by the browser and never
    touch our media-serving route. Access is partner-only, mirroring check-ins,
    so ``visibility`` is left None and the gate collapses to "is a Partner?".
    """
    file_path = extract_upload_suffix(source.url)
    if not file_path:
        return []
    return [
        UploadReference(
            file_path=file_path,
            content_kind="watch",
            content_id=source.id,
            slot="media",
            owner_user_id=source.author_id,
        )
    ]


def sync_album_upload_references(db: Session, album: Album) -> None:
    db.query(UploadReference).filter(
        UploadReference.content_kind == "album",
        UploadReference.content_id == album.id,
    ).delete(synchronize_session=False)
    rows = _album_ref_rows(album)
    _consume_pending_uploads(db, rows)
    if rows:
        db.add_all(rows)


def sync_article_upload_references(db: Session, article: Article) -> None:
    db.query(UploadReference).filter(
        UploadReference.content_kind == "article",
        UploadReference.content_id == article.id,
    ).delete(synchronize_session=False)
    rows = _article_ref_rows(article)
    _consume_pending_uploads(db, rows)
    if rows:
        db.add_all(rows)


def sync_moment_upload_references(db: Session, moment: Moment) -> None:
    db.query(UploadReference).filter(
        UploadReference.content_kind == "moment",
        UploadReference.content_id == moment.id,
    ).delete(synchronize_session=False)
    rows = _moment_ref_rows(moment)
    _consume_pending_uploads(db, rows)
    if rows:
        db.add_all(rows)


def sync_checkin_upload_references(db: Session, checkin: CheckIn) -> None:
    """Replace UploadReference rows for the given CheckIn.

    Mirrors :func:`sync_moment_upload_references`. Called after creating a
    new CheckIn to grant Partner-only access to the freshly-uploaded photos.
    """
    db.query(UploadReference).filter(
        UploadReference.content_kind == "checkin",
        UploadReference.content_id == checkin.id,
    ).delete(synchronize_session=False)
    rows = _checkin_ref_rows(checkin)
    _consume_pending_uploads(db, rows)
    if rows:
        db.add_all(rows)


def sync_chat_message_upload_references(db: Session, message: ChatMessage) -> None:
    """Replace UploadReference rows for the given chat message.

    Grants Partner-only access to a freshly-uploaded chat image / sticker so
    the counterpart can actually load it through the guarded ``/uploads`` route.
    """
    db.query(UploadReference).filter(
        UploadReference.content_kind == "chat",
        UploadReference.content_id == message.id,
    ).delete(synchronize_session=False)
    rows = _chat_message_ref_rows(message)
    _consume_pending_uploads(db, rows)
    if rows:
        db.add_all(rows)


def sync_capsule_upload_references(db: Session, capsule: Capsule) -> None:
    """Replace UploadReference rows for the given time capsule's media file."""
    db.query(UploadReference).filter(
        UploadReference.content_kind == "capsule",
        UploadReference.content_id == capsule.id,
    ).delete(synchronize_session=False)
    rows = _capsule_ref_rows(capsule)
    _consume_pending_uploads(db, rows)
    if rows:
        db.add_all(rows)


def sync_site_setting_upload_references(db: Session, setting: SiteSetting) -> None:
    db.query(UploadReference).filter(
        UploadReference.content_kind == "site_setting",
        UploadReference.content_id == setting.id,
    ).delete(synchronize_session=False)
    rows = _site_setting_ref_rows(setting)
    _consume_pending_uploads(db, rows)
    if rows:
        db.add_all(rows)


def sync_watch_source_upload_references(db: Session, source: WatchSource) -> None:
    db.query(UploadReference).filter(
        UploadReference.content_kind == "watch",
        UploadReference.content_id == source.id,
    ).delete(synchronize_session=False)
    rows = _watch_source_ref_rows(source)
    _consume_pending_uploads(db, rows)
    if rows:
        db.add_all(rows)


def delete_upload_references_for(db: Session, content_kind: str, content_id: int) -> None:
    db.query(UploadReference).filter(
        UploadReference.content_kind == content_kind,
        UploadReference.content_id == content_id,
    ).delete(synchronize_session=False)


def rebuild_upload_references(db: Session) -> None:
    # Preserve fresh pending-upload leases across process restarts. They are
    # reclaimed by orphan cleanup after their 24-hour grace period.
    db.query(UploadReference).filter(
        UploadReference.content_kind != "pending"
    ).delete(synchronize_session="fetch")

    albums = (
        db.query(Album)
        .options(joinedload(Album.media_items))
        .filter(Album.deleted_at.is_(None))
        .all()
    )
    for album in albums:
        rows = _album_ref_rows(album)
        if rows:
            db.add_all(rows)

    articles = (
        db.query(Article)
        .options(joinedload(Article.blocks))
        .filter(Article.deleted_at.is_(None))
        .all()
    )
    for article in articles:
        rows = _article_ref_rows(article)
        if rows:
            db.add_all(rows)

    moments = db.query(Moment).filter(Moment.deleted_at.is_(None)).all()
    for moment in moments:
        rows = _moment_ref_rows(moment)
        if rows:
            db.add_all(rows)

    checkins = db.query(CheckIn).filter(CheckIn.deleted_at.is_(None)).all()
    for checkin in checkins:
        rows = _checkin_ref_rows(checkin)
        if rows:
            db.add_all(rows)

    chat_messages = db.query(ChatMessage).filter(ChatMessage.deleted_at.is_(None)).all()
    for message in chat_messages:
        rows = _chat_message_ref_rows(message)
        if rows:
            db.add_all(rows)

    settings = db.query(SiteSetting).all()
    for setting in settings:
        rows = _site_setting_ref_rows(setting)
        if rows:
            db.add_all(rows)

    watch_sources = db.query(WatchSource).filter(WatchSource.deleted_at.is_(None)).all()
    for source in watch_sources:
        rows = _watch_source_ref_rows(source)
        if rows:
            db.add_all(rows)

    capsules = db.query(Capsule).filter(Capsule.deleted_at.is_(None)).all()
    for capsule in capsules:
        rows = _capsule_ref_rows(capsule)
        if rows:
            db.add_all(rows)

    local_tracks = db.query(ListenLocalTrack).filter(ListenLocalTrack.deleted_at.is_(None)).all()
    users_by_uid = {user.uid: user.id for user in db.query(User).all()}
    for track in local_tracks:
        rows = _listen_local_track_ref_rows(track)
        for row in rows:
            row.owner_user_id = users_by_uid.get(track.uploaded_by_uid)
        if rows:
            db.add_all(rows)

    db.flush()
    attached_paths = {
        value
        for (value,) in db.query(UploadReference.file_path).filter(
            UploadReference.content_kind != "pending"
        ).all()
    }
    if attached_paths:
        db.query(UploadReference).filter(
            UploadReference.content_kind == "pending",
            UploadReference.file_path.in_(attached_paths),
        ).delete(synchronize_session=False)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    db.query(UploadReference).filter(
        UploadReference.content_kind == "pending",
        UploadReference.created_at < stale_cutoff,
    ).delete(synchronize_session=False)

    db.flush()


def can_access_upload_reference(
    ref: UploadReference,
    user: User | None,
    *,
    content_access_granted: bool = False,
    capsule_open: bool | None = None,
) -> bool:
    if ref.content_kind == "pending":
        created_at = ref.created_at
        if created_at is None:
            return False
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        is_fresh = (datetime.now(timezone.utc) - created_at).total_seconds() <= 24 * 60 * 60
        return is_fresh and VisibilityPolicy.is_owner(user, owner_id=ref.owner_user_id)

    if ref.content_kind == "album":
        if ref.content_is_encrypted or ref.ref_is_encrypted:
            return VisibilityPolicy.can_reveal_encrypted(user)
        visibility = ref.visibility or ContentVisibility.public.value
        if visibility == ContentVisibility.password_protected.value:
            return (
                content_access_granted
                or VisibilityPolicy.is_partner(user)
                or VisibilityPolicy.is_owner(user, owner_id=ref.owner_user_id)
            )
        if not ref.is_public:
            return VisibilityPolicy.is_owner(user, owner_id=ref.owner_user_id)
        return VisibilityPolicy.can_view_by_visibility(
            ContentVisibility(visibility),
            user,
            owner_id=ref.owner_user_id,
        )

    if ref.content_kind == "article":
        status = ref.status or ArticleStatus.published.value
        if status != ArticleStatus.published.value:
            return VisibilityPolicy.is_owner(user, owner_id=ref.owner_user_id) or (
                ref.partner_can_edit and VisibilityPolicy.is_partner(user)
            )
        if ref.content_is_encrypted or ref.ref_is_encrypted:
            return VisibilityPolicy.can_reveal_encrypted(user)
        visibility = ref.visibility or ContentVisibility.public.value
        if visibility == ContentVisibility.password_protected.value:
            return (
                content_access_granted
                or VisibilityPolicy.is_partner(user)
                or VisibilityPolicy.is_owner(user, owner_id=ref.owner_user_id)
            )
        return VisibilityPolicy.can_view_by_visibility(
            ContentVisibility(visibility),
            user,
            owner_id=ref.owner_user_id,
        )

    if ref.content_kind == "moment":
        visibility = ref.visibility or MomentVisibility.public.value
        return VisibilityPolicy.can_view_level(
            visibility,
            user,
            owner_id=ref.owner_user_id,
        )

    if ref.content_kind == "checkin":
        # Check-in photos are partner-only (both PartnerA and PartnerB).
        return VisibilityPolicy.is_partner(user)

    if ref.content_kind == "chat":
        # Cottage chat images are partner-only (both PartnerA and PartnerB).
        return VisibilityPolicy.is_partner(user)

    if ref.content_kind == "site_setting":
        # Couple avatars (partner_a_avatar / partner_b_avatar) are rendered on
        # the public homepage hero for every viewer, including anonymous
        # visitors, so the media-serving gate must allow public access.
        return True

    if ref.content_kind == "watch":
        # Watch-together videos are partner-only (both PartnerA and PartnerB).
        return VisibilityPolicy.is_partner(user)

    if ref.content_kind == "capsule":
        if capsule_open is None:
            try:
                open_at = datetime.fromisoformat(ref.status or "")
                if open_at.tzinfo is None:
                    open_at = open_at.replace(tzinfo=timezone.utc)
                capsule_open = open_at <= datetime.now(timezone.utc)
            except ValueError:
                capsule_open = False
        return bool(capsule_open) and VisibilityPolicy.is_partner(user)

    if ref.content_kind == "listen":
        # Listen-together uploaded audio is partner-only (both PartnerA and PartnerB).
        return VisibilityPolicy.is_partner(user)

    return False
