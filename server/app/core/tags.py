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

MAX_TAGS = 12
MAX_TAG_LENGTH = 32


def normalize_tags(values: list[str] | tuple[str, ...] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw in values or []:
        tag = str(raw).strip().lstrip("#").strip()
        tag = " ".join(tag.split())
        if not tag:
            continue
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(f"Tag cannot exceed {MAX_TAG_LENGTH} characters")

        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(tag)

        if len(normalized) > MAX_TAGS:
            raise ValueError(f"At most {MAX_TAGS} tags are allowed")

    return normalized


def parse_tag_query(raw: str | None) -> list[str]:
    if raw is None:
        return []
    return normalize_tags([item for item in raw.split(",")])
