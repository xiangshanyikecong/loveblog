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

"""Cottage 一起玩 (two-person games) backend.

This package is intentionally self-contained and additive: it owns its own
Redis namespace (``cottage_game:*``) and never touches the existing modules.
A bug here cannot affect articles / albums / listen / watch / chat — at worst
a single match's state is wrong and the players start a new one.

Each game exposes a pure rules engine (no I/O) plus a shared
:mod:`app.services.cottage_games.room` layer for Redis-backed, lock-guarded
room state. Supported games: gomoku, tictactoe, reversi, memory, linklink.
"""
