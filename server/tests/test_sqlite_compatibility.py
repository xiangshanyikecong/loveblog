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

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app import main as main_module


class SqliteCompatibilityTests(unittest.TestCase):
    def test_legacy_chat_table_uses_sender_id_and_creates_chat_keys(self) -> None:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
                connection.execute(
                    text(
                        "CREATE TABLE chat_messages ("
                        "id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL, "
                        "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                    )
                )

            with patch.object(main_module, "engine", engine):
                main_module._ensure_sqlite_compatibility()

            inspector = inspect(engine)
            self.assertIn("chat_keys", inspector.get_table_names())
            self.assertIn(
                "client_idempotency_key",
                {column["name"] for column in inspector.get_columns("chat_messages")},
            )
            self.assertIn(
                "uq_chat_message_sender_idempotency",
                {index["name"] for index in inspector.get_indexes("chat_messages")},
            )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
