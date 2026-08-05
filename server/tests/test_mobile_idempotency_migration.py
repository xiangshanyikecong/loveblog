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

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings


class MobileIdempotencyMigrationTests(unittest.TestCase):
    def test_sqlite_upgrade_and_downgrade_from_previous_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "migration.db"
            database_url = f"sqlite:///{db_path.as_posix()}"
            engine = create_engine(database_url)
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
                connection.execute(text("CREATE TABLE mood_checkins (id INTEGER PRIMARY KEY)"))
                connection.execute(
                    text(
                        "CREATE TABLE messages ("
                        "id INTEGER PRIMARY KEY, author_id INTEGER NULL, content TEXT NOT NULL, "
                        "FOREIGN KEY(author_id) REFERENCES users(id))"
                    )
                )
                for table_name, author_column in (
                    ("chat_messages", "sender_id"),
                    ("moments", "author_id"),
                    ("checkins", "author_id"),
                    ("wishes", "author_id"),
                ):
                    connection.execute(
                        text(
                            f"CREATE TABLE {table_name} ("
                            f"id INTEGER PRIMARY KEY, {author_column} INTEGER NULL)"
                        )
                    )
                connection.execute(text("CREATE TABLE watch_sources (id INTEGER PRIMARY KEY)"))
                connection.execute(
                    text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)")
                )
                connection.execute(
                    text("INSERT INTO alembic_version(version_num) VALUES ('20260705_1000')")
                )
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            old_database_url = settings.database_url
            settings.database_url = database_url
            try:
                command.upgrade(config, "20260718_1200")

                inspector = inspect(engine)
                self.assertIn("client_idempotency_key", {
                    column["name"] for column in inspector.get_columns("messages")
                })
                self.assertIn("mood_idempotency_records", inspector.get_table_names())
                self.assertIn(
                    "uq_message_author_idempotency",
                    {constraint["name"] for constraint in inspector.get_unique_constraints("messages")},
                )
                for table_name in ("chat_messages", "moments", "checkins", "wishes"):
                    self.assertIn(
                        "client_idempotency_key",
                        {column["name"] for column in inspector.get_columns(table_name)},
                    )
                self.assertTrue(
                    {"last_position_ms", "last_viewed_at", "bookmarks_json"}.issubset(
                        {column["name"] for column in inspector.get_columns("watch_sources")}
                    )
                )

                command.downgrade(config, "20260705_1000")
                inspector = inspect(engine)
                self.assertNotIn("client_idempotency_key", {
                    column["name"] for column in inspector.get_columns("messages")
                })
                self.assertNotIn("mood_idempotency_records", inspector.get_table_names())
                for table_name in ("chat_messages", "moments", "checkins", "wishes"):
                    self.assertNotIn(
                        "client_idempotency_key",
                        {column["name"] for column in inspector.get_columns(table_name)},
                    )
                self.assertFalse(
                    {"last_position_ms", "last_viewed_at", "bookmarks_json"}
                    & {column["name"] for column in inspector.get_columns("watch_sources")}
                )
            finally:
                settings.database_url = old_database_url
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
