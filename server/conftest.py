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

"""Pytest-wide environment defaults.

``app.db.session`` builds a module-level engine at import time, which requires
a *parseable* DATABASE_URL even though the tests themselves run against their
own in-memory SQLite engines. Default to an in-memory SQLite URL so any test
module can be collected standalone (``pytest tests/test_auth_api.py``) without
host environment configuration. A DATABASE_URL set in the real environment
always wins.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
