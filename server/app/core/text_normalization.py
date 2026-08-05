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

from typing import Any


def _contains_cjk(value: str) -> bool:
    return any(
        ("\u4e00" <= ch <= "\u9fff") or ("\u3040" <= ch <= "\u30ff") or ("\uac00" <= ch <= "\ud7af")
        for ch in value
    )


def _looks_like_utf8_mojibake(value: str) -> bool:
    # Typical marks when UTF-8 bytes are decoded as latin-1/cp1252.
    markers = ("Ã", "Â", "â", "å", "æ", "ç", "¤", "ï¿½")
    return any(marker in value for marker in markers)


def normalize_maybe_mojibake_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not value:
        return value
    if _contains_cjk(value):
        return value
    if not _looks_like_utf8_mojibake(value):
        return value

    for source_encoding in ("latin-1", "cp1252"):
        try:
            repaired = value.encode(source_encoding).decode("utf-8")
        except UnicodeError:
            continue
        if _contains_cjk(repaired):
            return repaired
    return value


def normalize_nested_text_values(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_maybe_mojibake_text(value)
    if isinstance(value, list):
        return [normalize_nested_text_values(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_nested_text_values(item) for key, item in value.items()}
    return value
