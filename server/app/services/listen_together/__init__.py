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

"""cottage-listen-together backend services.

Submodules:

- crypto: Fernet derivation + encrypt / decrypt helpers for NetEase cookies.
- cookie_vault: Redis-backed encrypted storage of partner NetEase cookies.
- netease_client: HTTP client wrapping NeteaseCloudMusicApi endpoints.
- room: Redis-backed room state (current song / queue / event_seq).
"""
