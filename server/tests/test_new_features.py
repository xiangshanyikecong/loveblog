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

"""Tests for the 2026-09 feature batch:

- Listen library: liked tracks ("我喜欢") + couple custom playlists
- Security: TOTP 2FA service + API, login-device management
- Memories: "on this day" collection + daily push idempotency
- Annual report aggregation

The endpoint handlers are plain functions whose FastAPI ``Depends`` defaults
can be overridden by passing ``db`` / ``current_user`` directly, so business
logic runs against an in-memory SQLite database.
"""
import json
import time
import unittest
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.db.base import Base
from app.models import (
    Album,
    AlbumMedia,
    Article,
    Capsule,
    ListenHistoryEntry,
    Notification,
    Wish,
)
from app.models.login_device import LoginDevice
from app.models.memory_push_log import MemoryPushLog
from app.models.wish import WishStatus
from app.models.listen_playlist import ListenPlaylist, ListenPlaylistTrack
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole
from app.api.v1.auth import _verify_second_factor
from app.api.v1.devices import list_login_devices, revoke_all_login_devices, revoke_login_device
from app.api.v1.listen_library import (
    add_playlist_track,
    create_playlist,
    delete_liked_track,
    delete_playlist,
    get_liked_status,
    get_playlist,
    list_liked_tracks,
    list_playlists,
    remove_playlist_track,
    toggle_liked_track,
    update_playlist,
)
from app.api.v1.memories import on_this_day
from app.api.v1.totp import disable_totp, enable_totp, setup_totp, totp_status
from app.api.v1.annual_report import annual_report
from app.schemas.devices import LoginDeviceResponse
from app.schemas.listen_library import (
    LikedToggleRequest,
    PlaylistCreateRequest,
    PlaylistTrackAddRequest,
    PlaylistUpdateRequest,
)
from app.schemas.totp import TotpDisableRequest, TotpEnableRequest
from app.services.memories import collect_on_this_day, run_memory_push_tick
from app.services.totp import (
    generate_recovery_codes,
    generate_secret,
    hash_recovery_code,
    provisioning_uri,
    totp_at,
    verify_totp,
)

PASSWORD = "Passw0rd123"


def _dt(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


class NewFeaturesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.a = self._partner("alice", UserRole.partner_a)
        self.b = self._partner("bob", UserRole.partner_b)
        self.today = date(2026, 9, 12)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _partner(self, username: str, role: UserRole) -> User:
        user = User(
            username=username,
            nickname=username,
            role=role,
            password_hash=get_password_hash(PASSWORD),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _article(self, created_at: datetime, title: str = "日记") -> Article:
        article = Article(author_id=self.a.id, title=title, excerpt=f"{title} 摘要")
        article.created_at = created_at
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)
        return article

    # ── liked tracks ────────────────────────────────────────────────────────
    def test_liked_toggle_list_status_delete(self) -> None:
        song = {
            "song_id": "186016",
            "name": "稻香",
            "artists": ["周杰伦"],
            "album": "魔杰座",
            "duration_ms": 223000,
            "cover_url": None,
        }
        # User isolation: a's list starts empty even though nothing liked yet.
        self.assertEqual(list_liked_tracks(db=self.db, current_user=self.a).total, 0)

        toggled = toggle_liked_track(LikedToggleRequest(**song), db=self.db, current_user=self.a)
        self.assertTrue(toggled.liked)
        self.assertEqual(toggled.total, 1)

        # Partner B does not see A's like.
        self.assertEqual(get_liked_status("186016", db=self.db, current_user=self.b).song_ids, [])
        self.assertEqual(
            get_liked_status("186016,999", db=self.db, current_user=self.a).song_ids, ["186016"]
        )

        items = list_liked_tracks(db=self.db, current_user=self.a).items
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].song_id, "186016")
        self.assertEqual(items[0].artists, ["周杰伦"])

        # Toggle again removes it.
        toggled = toggle_liked_track(LikedToggleRequest(**song), db=self.db, current_user=self.a)
        self.assertFalse(toggled.liked)
        self.assertEqual(toggled.total, 0)

        # Idempotent delete of a missing row.
        self.assertTrue(delete_liked_track("186016", db=self.db, current_user=self.a)["ok"])

    def test_liked_rejects_visitor(self) -> None:
        visitor = self._partner("carol", UserRole.visitor)
        with self.assertRaises(HTTPException) as ctx:
            list_liked_tracks(db=self.db, current_user=visitor)
        self.assertEqual(ctx.exception.status_code, 403)

    # ── couple playlists ───────────────────────────────────────────────────
    def test_playlist_crud_and_collaboration(self) -> None:
        created = create_playlist(
            PlaylistCreateRequest(name="我们的歌单", description="一起听"),
            db=self.db,
            current_user=self.a,
        )
        self.assertEqual(created.track_count, 0)

        # Partner B sees it too (couple-shared) and can edit it.
        self.assertEqual(len(list_playlists(db=self.db, current_user=self.b)), 1)

        t1 = add_playlist_track(
            created.pid,
            PlaylistTrackAddRequest(song_id="1", name="A", artists=["X"], duration_ms=1000),
            db=self.db,
            current_user=self.b,
        )
        t2 = add_playlist_track(
            created.pid,
            PlaylistTrackAddRequest(song_id="2", name="B", artists=["Y"]),
            db=self.db,
            current_user=self.a,
        )
        self.assertEqual((t1.position, t2.position), (1, 2))
        self.assertEqual(t1.added_by_uid, self.b.uid)  # collaboration proven

        # Duplicate song is rejected.
        with self.assertRaises(HTTPException) as ctx:
            add_playlist_track(
                created.pid,
                PlaylistTrackAddRequest(song_id="1", name="A"),
                db=self.db,
                current_user=self.a,
            )
        self.assertEqual(ctx.exception.status_code, 409)

        detail = get_playlist(created.pid, db=self.db, current_user=self.b)
        self.assertEqual([t.song_id for t in detail.tracks], ["1", "2"])

        # Remove first track; remaining order preserved.
        remove_playlist_track(created.pid, "1", db=self.db, current_user=self.a)
        detail = get_playlist(created.pid, db=self.db, current_user=self.b)
        self.assertEqual([t.song_id for t in detail.tracks], ["2"])

        # Metadata update by the other partner.
        updated = update_playlist(
            created.pid,
            PlaylistUpdateRequest(name="改名了"),
            db=self.db,
            current_user=self.b,
        )
        self.assertEqual(updated.name, "改名了")
        self.assertEqual(updated.track_count, 1)

        # Delete cascades tracks.
        self.assertTrue(delete_playlist(created.pid, db=self.db, current_user=self.a)["ok"])
        self.assertEqual(list_playlists(db=self.db, current_user=self.b), [])
        self.assertEqual(
            self.db.query(ListenPlaylistTrack).filter_by(playlist_id=created.pid).count(), 0
        )

        # 404 for unknown playlist.
        with self.assertRaises(HTTPException) as ctx:
            get_playlist("nope", db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 404)

    # ── TOTP service ───────────────────────────────────────────────────────
    def test_totp_service_verify_and_recovery(self) -> None:
        secret = generate_secret()
        code = totp_at(secret, int(time.time()))
        self.assertTrue(verify_totp(secret, code))
        self.assertFalse(verify_totp(secret, "000000" if code != "000000" else "111111"))
        self.assertFalse(verify_totp(secret, "abc"))
        self.assertIn("otpauth://totp/", provisioning_uri(secret, "alice"))

        codes = generate_recovery_codes()
        self.assertEqual(len(codes), 8)
        digest = hash_recovery_code(codes[0])
        self.assertEqual(digest, hash_recovery_code(codes[0].upper()))

    def test_totp_api_lifecycle(self) -> None:
        # Setup stores a secret but keeps 2FA disabled.
        setup = setup_totp(db=self.db, current_user=self.a)
        self.db.refresh(self.a)
        self.assertEqual(self.a.totp_secret, setup.secret)
        self.assertFalse(self.a.totp_enabled)
        self.assertEqual(totp_status(current_user=self.a).enabled, False)

        # Setup again while disabled is allowed (re-issue).
        setup2 = setup_totp(db=self.db, current_user=self.a)
        self.a.totp_secret = setup2.secret
        self.db.commit()

        # Wrong code cannot enable.
        with self.assertRaises(HTTPException) as ctx:
            enable_totp(TotpEnableRequest(code="000000"), db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 400)

        # Valid code enables 2FA and issues recovery codes (hashed, once).
        code = totp_at(setup2.secret, int(time.time()))
        enabled = enable_totp(TotpEnableRequest(code=code), db=self.db, current_user=self.a)
        self.db.refresh(self.a)
        self.assertTrue(self.a.totp_enabled)
        self.assertEqual(len(enabled.recovery_codes), 8)
        stored = json.loads(self.a.totp_recovery_codes or "[]")
        self.assertEqual(stored, [hash_recovery_code(c) for c in enabled.recovery_codes])
        self.assertEqual(totp_status(current_user=self.a).recovery_codes_remaining, 8)

        # Setup is refused while 2FA is live.
        with self.assertRaises(HTTPException) as ctx:
            setup_totp(db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 400)

        # Disable requires the account password first.
        with self.assertRaises(HTTPException) as ctx:
            disable_totp(
                TotpDisableRequest(code=enabled.recovery_codes[0], password="wrong"),
                db=self.db,
                current_user=self.a,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.db.refresh(self.a)
        self.assertTrue(self.a.totp_enabled)  # recovery code not burned

        # Password + recovery code disables and clears everything.
        disabled = disable_totp(
            TotpDisableRequest(code=enabled.recovery_codes[0], password=PASSWORD),
            db=self.db,
            current_user=self.a,
        )
        self.db.refresh(self.a)
        self.assertFalse(disabled.enabled)
        self.assertFalse(self.a.totp_enabled)
        self.assertIsNone(self.a.totp_secret)
        self.assertIsNone(self.a.totp_recovery_codes)

    def test_login_second_factor_burns_recovery_code(self) -> None:
        secret = generate_secret()
        codes = generate_recovery_codes(2)
        self.a.totp_secret = secret
        self.a.totp_enabled = True
        self.a.totp_recovery_codes = json.dumps([hash_recovery_code(c) for c in codes])
        self.db.commit()

        # TOTP code verifies without touching recovery codes.
        self.assertTrue(_verify_second_factor(self.db, self.a, totp_at(secret, int(time.time()))))
        self.db.refresh(self.a)
        self.assertEqual(len(json.loads(self.a.totp_recovery_codes)), 2)

        # A recovery code verifies once and is burned.
        self.assertTrue(_verify_second_factor(self.db, self.a, codes[1]))
        self.db.refresh(self.a)
        remaining = json.loads(self.a.totp_recovery_codes)
        self.assertNotIn(hash_recovery_code(codes[1]), remaining)

        # Reuse of the same code fails.
        self.assertFalse(_verify_second_factor(self.db, self.a, codes[1]))

    # ── login devices ──────────────────────────────────────────────────────
    def test_login_devices_list_and_revoke(self) -> None:
        device_a = LoginDevice(
            user_id=self.a.id, device_hash="ha", device_name="Chrome · Windows", ip="1.2.3.4"
        )
        device_b = LoginDevice(
            user_id=self.b.id, device_hash="hb", device_name="Safari · iOS", ip="5.6.7.8"
        )
        self.db.add_all([device_a, device_b])
        self.db.commit()
        self.db.refresh(device_a)

        mine = list_login_devices(db=self.db, current_user=self.a)
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0].device_name, "Chrome · Windows")
        self.assertIsInstance(mine[0], LoginDeviceResponse)

        old_version = self.a.session_version

        # Cannot revoke someone else's device.
        with self.assertRaises(HTTPException) as ctx:
            revoke_login_device(device_b.did, db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 404)

        # Own revoke bumps session version (forces re-login everywhere).
        result = revoke_login_device(device_a.did, db=self.db, current_user=self.a)
        self.assertTrue(result.revoked)
        self.assertEqual(result.new_session_version, old_version + 1)
        self.assertEqual(
            self.db.query(LoginDevice).filter_by(user_id=self.a.id).count(), 0
        )

        # Revoke-all path.
        self.db.add(LoginDevice(user_id=self.b.id, device_hash="hb2", device_name="Edge"))
        self.db.commit()
        cleared = revoke_all_login_devices(db=self.db, current_user=self.b)
        self.assertEqual(cleared.revoked, 2)
        self.assertEqual(
            self.db.query(LoginDevice).filter_by(user_id=self.b.id).count(), 0
        )

    # ── memories: on this day + daily push ─────────────────────────────────
    def test_on_this_day_collection_and_push(self) -> None:
        self._article(_dt(2024, 9, 12, 8, 0), title="去年前")
        self._article(_dt(2025, 9, 12, 9, 0), title="去年")
        self._article(_dt(2025, 9, 13, 9, 0), title="不该出现")
        self._article(_dt(2026, 9, 12, 9, 0), title="今年不算")
        album = Album(author_id=self.a.id, title="旧相册")
        album.created_at = _dt(2025, 9, 12, 10, 0)
        self.db.add(album)
        self.db.commit()
        self.db.refresh(album)
        self.db.add(
            ListenHistoryEntry(
                song_id="1", name="歌一", artists_json='["A"]', started_by_uid=self.a.uid,
                played_at=_dt(2025, 9, 12, 11, 0),
            )
        )
        self.db.add(
            ListenHistoryEntry(
                song_id="2", name="歌二", artists_json="[]", started_by_uid=self.a.uid,
                played_at=_dt(2025, 9, 12, 12, 0),
            )
        )
        self.db.commit()

        result = collect_on_this_day(self.db, today=self.today)
        self.assertEqual([g.year for g in result.years], [2025, 2024])
        self.assertEqual(result.totals.articles, 2)
        self.assertEqual(result.totals.albums, 1)
        self.assertEqual(result.totals.songs, 2)

        api_view = on_this_day("2026-09-12", db=self.db, current_user=self.a)
        self.assertEqual(api_view.date, "2026-09-12")

        with self.assertRaises(HTTPException) as ctx:
            on_this_day("not-a-date", db=self.db, current_user=self.a)
        self.assertEqual(ctx.exception.status_code, 422)

        # Daily push: one notification per partner, idempotent per day.
        created = run_memory_push_tick(self.db, today=self.today)
        self.assertEqual(created, 2)
        notes = (
            self.db.query(Notification)
            .filter(Notification.type == "memory.on_this_day")
            .all()
        )
        self.assertEqual({n.recipient_id for n in notes}, {self.a.id, self.b.id})
        self.assertEqual(run_memory_push_tick(self.db, today=self.today), 0)  # dedup
        self.assertIsNotNone(
            self.db.query(MemoryPushLog).filter_by(date_key=self.today.isoformat()).first()
        )

        # A day without history still logs the key (avoids rescanning) and pushes nothing.
        self.assertEqual(run_memory_push_tick(self.db, today=date(2026, 1, 1)), 0)
        self.assertIsNotNone(
            self.db.query(MemoryPushLog).filter_by(date_key="2026-01-01").first()
        )

    # ── annual report ──────────────────────────────────────────────────────
    def test_annual_report_aggregation(self) -> None:
        self.db.add(SiteSetting(id=1, site_name="demo", love_start_date=_dt(2024, 1, 1)))
        self._article(_dt(2025, 3, 10), title="三月")
        self._article(_dt(2025, 9, 12), title="九月")
        self._article(_dt(2024, 5, 5), title="去年不算")

        album = Album(author_id=self.a.id, title="2025相册")
        album.created_at = _dt(2025, 8, 1)
        self.db.add(album)
        self.db.commit()
        self.db.refresh(album)
        media1 = AlbumMedia(album_id=album.id, file_url="uploads/a.jpg")
        media1.created_at = _dt(2025, 8, 2)
        media2 = AlbumMedia(album_id=album.id, file_url="uploads/b.jpg")
        media2.created_at = _dt(2025, 8, 3)
        self.db.add_all([media1, media2])
        for song_id, name, at in [
            ("1", "热歌", _dt(2025, 9, 12, 8, 0)),
            ("1", "热歌", _dt(2025, 9, 12, 9, 0)),
            ("2", "冷门", _dt(2025, 5, 5, 9, 0)),
        ]:
            self.db.add(
                ListenHistoryEntry(
                    song_id=song_id,
                    name=name,
                    artists_json="[]",
                    duration_ms=240000 if song_id == "1" else 60000,
                    started_by_uid=self.a.uid,
                    played_at=at,
                )
            )
        capsule = Capsule(author_id=self.a.id, open_at=_dt(2027, 1, 1))
        capsule.created_at = _dt(2025, 7, 7)
        self.db.add(capsule)
        self.db.add(
            Wish(
                author_id=self.a.id,
                title="一起去看海",
                status=WishStatus.completed.value,
                completed_at=_dt(2025, 10, 1),
            )
        )
        self.db.commit()

        report = annual_report(2025, db=self.db, current_user=self.b)
        self.assertEqual(report.year, 2025)
        self.assertIsNotNone(report.couple_since)
        self.assertGreater(report.stats.articles, 0)
        self.assertEqual(report.stats.articles, 2)
        self.assertEqual(report.stats.albums, 1)
        self.assertEqual(report.stats.photos, 2)
        self.assertEqual(report.stats.songs_played, 3)
        self.assertEqual(report.stats.songs_minutes, 9)  # (240k*2 + 60k) / 60000
        self.assertEqual(report.stats.capsules_created, 1)
        self.assertEqual(report.stats.wishes_completed, 1)
        self.assertEqual(len(report.monthly), 12)
        self.assertEqual(report.monthly[8].articles, 1)  # September 2025
        self.assertEqual(report.monthly[8].songs, 2)
        top = report.top_songs
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0].song_id, "1")
        self.assertEqual(top[0].play_count, 2)
        self.assertTrue(report.highlights)
        self.assertGreater(report.days_together, 365)

        # Empty year is all zeros with no highlights crash.
        empty = annual_report(1999, db=self.db, current_user=self.a)
        self.assertEqual(empty.stats.articles, 0)
        self.assertEqual(empty.top_songs, [])


if __name__ == "__main__":
    unittest.main()
