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
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.exc import OperationalError

from app.core.config import settings


SERVER_ROOT = Path(__file__).resolve().parents[1]


class MigrationFailClosedTests(unittest.TestCase):
    def test_unreachable_postgres_never_falls_back_to_sqlite(self) -> None:
        config = Config(str(SERVER_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(SERVER_ROOT / "migrations"))

        old_database_url = settings.database_url
        old_postgres_password = settings.postgres_password
        settings.database_url = (
            "postgresql+psycopg2://invalid:invalid@127.0.0.1:1/invalid"
            "?connect_timeout=1"
        )
        settings.postgres_password = ""
        try:
            # Local Python 3.13+ intentionally lacks the production-only
            # psycopg2 wheel, while the Python 3.12 image reaches the socket
            # and raises OperationalError. Both are fail-closed outcomes.
            with self.assertRaises((OperationalError, ModuleNotFoundError)):
                command.upgrade(config, "head")
        finally:
            settings.database_url = old_database_url
            settings.postgres_password = old_postgres_password


if __name__ == "__main__":
    unittest.main()
