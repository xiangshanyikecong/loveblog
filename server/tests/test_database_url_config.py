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

from app.core.config import Settings


class DatabaseUrlConfigTests(unittest.TestCase):
    def test_discrete_postgres_fields_escape_reserved_password_characters(self) -> None:
        settings = Settings(
            _env_file=None,
            database_url="",
            postgres_user="love-user",
            postgres_password="p@ss:/#%word",
            postgres_db="love_node",
            postgres_host="postgres",
            postgres_port=5432,
        )

        self.assertEqual(
            settings.resolved_database_url,
            "postgresql+psycopg2://love-user:p%40ss%3A%2F%23%25word@postgres:5432/love_node",
        )

    def test_explicit_database_url_takes_precedence(self) -> None:
        settings = Settings(
            _env_file=None,
            database_url="sqlite:///explicit.db",
            postgres_password="ignored",
        )
        self.assertEqual(settings.resolved_database_url, "sqlite:///explicit.db")


class RedisUrlConfigTests(unittest.TestCase):
    def test_discrete_redis_fields_escape_reserved_password_characters(self) -> None:
        settings = Settings(
            _env_file=None,
            redis_url="",
            redis_password="p@ss:/#%word",
            redis_host="redis",
            redis_port=6379,
            redis_db=2,
        )

        self.assertEqual(
            settings.resolved_redis_url,
            "redis://:p%40ss%3A%2F%23%25word@redis:6379/2",
        )

    def test_explicit_redis_url_takes_precedence(self) -> None:
        settings = Settings(
            _env_file=None,
            redis_url="rediss://example.test:6380/4",
            redis_password="ignored",
        )
        self.assertEqual(settings.resolved_redis_url, "rediss://example.test:6380/4")


if __name__ == "__main__":
    unittest.main()
