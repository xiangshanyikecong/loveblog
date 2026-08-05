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

from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from app.api.v1 import (
    cottage_chat_ws,
    cottage_games_ws,
    cottage_listen_ws,
    cottage_watch_ws,
)
from app.models.user import UserRole


class WebSocketSessionSecurityTests(unittest.TestCase):
    modules = (
        cottage_chat_ws,
        cottage_games_ws,
        cottage_listen_ws,
        cottage_watch_ws,
    )

    def _resolve(self, module, user):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = user
        payload = {"sub": "uid-a", "type": "access", "session_version": 1}
        with (
            patch.object(module, "SessionLocal", return_value=db),
            patch.object(module.jwt, "decode", return_value=payload),
        ):
            return module._resolve_user("token")

    def test_partner_demotion_invalidates_every_websocket_resolver(self) -> None:
        visitor = SimpleNamespace(
            uid="uid-a",
            role=UserRole.visitor,
            is_banned=False,
            permission_status="active",
            session_version=1,
        )
        for module in self.modules:
            with self.subTest(module=module.__name__):
                self.assertIsNone(self._resolve(module, visitor))

    def test_banned_partner_invalidates_every_websocket_resolver(self) -> None:
        banned_partner = SimpleNamespace(
            uid="uid-a",
            role=UserRole.partner_a,
            is_banned=True,
            permission_status="banned",
            session_version=1,
        )
        for module in self.modules:
            with self.subTest(module=module.__name__):
                self.assertIsNone(self._resolve(module, banned_partner))


if __name__ == "__main__":
    unittest.main()
