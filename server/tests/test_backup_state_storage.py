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

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.api.v1 import export


class BackupStateStorageTests(unittest.TestCase):
    def _state_paths(self, root: Path) -> tuple[Path, Path, Path, Path]:
        backups = root / "backups"
        return (
            backups / "backup_history.json",
            backups / "backup_schedule.json",
            root / "backup_history.json",
            root / "backup_schedule.json",
        )

    def test_legacy_runtime_files_are_copied_into_persisted_backup_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backups = root / "backups"
            legacy_history = root / "backup_history.json"
            legacy_schedule = root / "backup_schedule.json"
            history_file = backups / "backup_history.json"
            schedule_file = backups / "backup_schedule.json"
            legacy_history.write_text('[{"status":"ok"}]', encoding="utf-8")
            legacy_schedule.write_text(
                json.dumps({"enabled": True, "interval_hours": 12}),
                encoding="utf-8",
            )

            with (
                patch.object(export, "BACKUP_HISTORY_FILE", history_file),
                patch.object(export, "BACKUP_SCHEDULE_FILE", schedule_file),
                patch.object(export, "LEGACY_BACKUP_HISTORY_FILE", legacy_history),
                patch.object(export, "LEGACY_BACKUP_SCHEDULE_FILE", legacy_schedule),
            ):
                self.assertEqual(export._load_history(), [{"status": "ok"}])
                self.assertTrue(history_file.is_file())
                self.assertTrue(export._load_schedule()["enabled"])
                self.assertTrue(schedule_file.is_file())

                export._save_history([{"status": "new"}])
                export._save_schedule(export._default_schedule())

            self.assertEqual(json.loads(history_file.read_text(encoding="utf-8")), [{"status": "new"}])
            self.assertFalse(json.loads(schedule_file.read_text(encoding="utf-8"))["enabled"])

    def test_concurrent_history_appends_do_not_drop_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_file, schedule_file, legacy_history, legacy_schedule = self._state_paths(root)
            with (
                patch.object(export, "BACKUP_HISTORY_FILE", history_file),
                patch.object(export, "BACKUP_SCHEDULE_FILE", schedule_file),
                patch.object(export, "LEGACY_BACKUP_HISTORY_FILE", legacy_history),
                patch.object(export, "LEGACY_BACKUP_SCHEDULE_FILE", legacy_schedule),
                ThreadPoolExecutor(max_workers=8) as executor,
            ):
                list(executor.map(lambda index: export._append_history({"index": index}), range(80)))
                records = export._load_history()

            self.assertEqual(len(records), 80)
            self.assertEqual({record["index"] for record in records}, set(range(80)))

    def test_concurrent_schedule_updates_preserve_unrelated_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_file, schedule_file, legacy_history, legacy_schedule = self._state_paths(root)

            def update(index: int) -> None:
                export._update_schedule(
                    lambda config: config.__setitem__(f"worker_{index}", True)
                )

            with (
                patch.object(export, "BACKUP_HISTORY_FILE", history_file),
                patch.object(export, "BACKUP_SCHEDULE_FILE", schedule_file),
                patch.object(export, "LEGACY_BACKUP_HISTORY_FILE", legacy_history),
                patch.object(export, "LEGACY_BACKUP_SCHEDULE_FILE", legacy_schedule),
                ThreadPoolExecutor(max_workers=8) as executor,
            ):
                list(executor.map(update, range(40)))
                config = export._load_schedule()

            for index in range(40):
                self.assertTrue(config[f"worker_{index}"])

    def test_auto_backup_names_are_unique_even_at_the_same_instant(self) -> None:
        created_at = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
        first = export._auto_backup_file_name("11111111-1111-1111-1111-111111111111", created_at)
        second = export._auto_backup_file_name("22222222-2222-2222-2222-222222222222", created_at)

        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith("-11111111-1111-1111-1111-111111111111.zip"))
        self.assertTrue(second.endswith("-22222222-2222-2222-2222-222222222222.zip"))

    def test_notification_failure_does_not_reclassify_created_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database = MagicMock()
            operator = SimpleNamespace(uid="partner-a", nickname="Partner A")

            def build_archive(export_dir: Path, _data: dict, _manifest: dict) -> Path:
                archive = export_dir / "backup.zip"
                archive.write_bytes(b"backup")
                return archive

            with (
                patch.object(export, "BACKEND_ROOT", root),
                patch.object(export, "_load_schedule", return_value=export._default_schedule()),
                patch.object(export, "_load_all_data", return_value={}),
                patch.object(
                    export,
                    "_build_manifest",
                    return_value={"created_at": "2026-07-17T12:00:00+00:00", "counts": {}},
                ),
                patch.object(export, "_build_archive", side_effect=build_archive),
                patch.object(export, "_append_history"),
                patch.object(export, "_prune_auto_backups"),
                patch.object(export, "_update_backup_schedule_result") as update_result,
                patch.object(export, "write_audit_log"),
                patch.object(export, "notify_partners", side_effect=RuntimeError("notification db failed")),
            ):
                record = export._create_persistent_auto_backup_locked(
                    database, operator, reason="manual"
                )

            self.assertEqual(record["status"], "success")
            self.assertTrue(Path(record["file_path"]).is_file())
            update_result.assert_called_once_with("success", None)
            database.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
