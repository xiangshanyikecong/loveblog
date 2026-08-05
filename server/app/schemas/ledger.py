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

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_TITLE_MAX = 160
_NOTE_MAX = 2000
_CATEGORY_MAX = 32
# 1 亿元 in cents — a sane upper bound that still fits a 32-bit int.
_AMOUNT_MAX = 10_000_000_00


class LedgerCreateRequest(BaseModel):
    """Request body for ``POST /v1/cottage/ledger``.

    ``amount_cents`` is the amount in **cents** (分). ``payer`` says who paid,
    relative to the caller. ``split_type`` drives the net balance.
    """

    title: str = Field(min_length=1, max_length=_TITLE_MAX)
    amount_cents: int = Field(ge=1, le=_AMOUNT_MAX)
    note: str | None = Field(default=None, max_length=_NOTE_MAX)
    category: str | None = Field(default=None, max_length=_CATEGORY_MAX)
    payer: Literal["me", "partner"] = "me"
    split_type: Literal["aa", "treat", "owed_full"] = "aa"
    spent_on: date

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("账目标题不能为空")
        return normalized

    @field_validator("note", "category")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LedgerUpdateRequest(BaseModel):
    """Partial update for a ledger entry."""

    title: str | None = Field(default=None, max_length=_TITLE_MAX)
    amount_cents: int | None = Field(default=None, ge=1, le=_AMOUNT_MAX)
    note: str | None = Field(default=None, max_length=_NOTE_MAX)
    category: str | None = Field(default=None, max_length=_CATEGORY_MAX)
    payer: Literal["me", "partner"] | None = None
    split_type: Literal["aa", "treat", "owed_full"] | None = None
    spent_on: date | None = None

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("账目标题不能为空")
        return normalized

    @field_validator("note", "category")
    @classmethod
    def _normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LedgerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    leid: str
    title: str
    note: str | None
    amount_cents: int
    category: str | None
    split_type: str
    spent_on: date
    payer_uid: str
    payer_nickname: str
    author_uid: str
    author_nickname: str
    created_at: datetime


class LedgerListResponse(BaseModel):
    items: list[LedgerResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class LedgerPayerStat(BaseModel):
    uid: str
    nickname: str
    paid_cents: int


class LedgerCategoryStat(BaseModel):
    category: str
    amount_cents: int


class LedgerBalance(BaseModel):
    """Net "who owes whom" after applying every entry's split rule."""

    settled: bool
    debtor_uid: str | None = None
    debtor_nickname: str | None = None
    creditor_uid: str | None = None
    creditor_nickname: str | None = None
    amount_cents: int = 0


class LedgerSummaryResponse(BaseModel):
    month: str | None
    total_spent_cents: int
    entry_count: int
    by_payer: list[LedgerPayerStat]
    by_category: list[LedgerCategoryStat]
    balance: LedgerBalance
