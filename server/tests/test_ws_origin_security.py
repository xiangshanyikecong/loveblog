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
from types import SimpleNamespace
from unittest.mock import patch

from app.api.v1.ws_security import allowed_websocket_origins, websocket_origin_allowed


class WebSocketOriginSecurityTests(unittest.TestCase):
    def test_allowed_websocket_origins_normalizes_configured_values(self) -> None:
        with patch("app.api.v1.ws_security.settings.cors_origins", "https://example.com/, http://localhost:5173"):
            self.assertEqual(
                allowed_websocket_origins(),
                {"https://example.com", "http://localhost:5173"},
            )

    def test_websocket_origin_allowed_accepts_whitelisted_origin(self) -> None:
        ws = SimpleNamespace(headers={"origin": "https://example.com"})

        with patch("app.api.v1.ws_security.settings.cors_origins", "https://example.com"):
            self.assertTrue(websocket_origin_allowed(ws))

    def test_websocket_origin_allowed_allows_missing_origin_for_native_clients(self) -> None:
        # Native (non-browser) clients such as the Android app send no Origin
        # header. This is allowed: the socket is still gated by JWT +
        # session-version auth, and a browser-driven cross-origin attempt always
        # carries an Origin (rejected by the allowlist branch below).
        missing_origin_ws = SimpleNamespace(headers={})
        with patch("app.api.v1.ws_security.settings.cors_origins", "https://example.com"):
            self.assertTrue(websocket_origin_allowed(missing_origin_ws))

    def test_websocket_origin_allowed_rejects_unlisted_browser_origin(self) -> None:
        evil_origin_ws = SimpleNamespace(headers={"origin": "https://evil.example"})
        with patch("app.api.v1.ws_security.settings.cors_origins", "https://example.com"):
            self.assertFalse(websocket_origin_allowed(evil_origin_ws))


if __name__ == "__main__":
    unittest.main()
