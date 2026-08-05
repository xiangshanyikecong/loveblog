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

"""Shared primitives for the cottage 一起玩 game engines.

Keeping :class:`IllegalMove` here (instead of inside a single engine) lets the
generic Redis room layer and every per-game engine raise/catch the *same*
exception type, so the WebSocket handler can stay game-agnostic.
"""
from __future__ import annotations


class IllegalMove(Exception):
    """Raised when a move violates a game's rules (occupied cell, wrong turn…)."""
