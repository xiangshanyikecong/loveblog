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

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PROMPT_MAX = 500
_ANSWER_MAX = 4000


class DailyQuestionCreateRequest(BaseModel):
    question_date: date | None = None
    prompt: str = Field(min_length=1, max_length=_PROMPT_MAX)

    @field_validator("prompt")
    @classmethod
    def _normalize_prompt(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("问题不能为空")
        return normalized


class DailyQuestionAnswerRequest(BaseModel):
    content: str = Field(min_length=1, max_length=_ANSWER_MAX)

    @field_validator("content")
    @classmethod
    def _normalize_content(cls, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ValueError("答案不能为空")
        return normalized


class DailyQuestionAnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    aid: str | None
    author_uid: str
    author_nickname: str
    is_self: bool
    answered: bool
    content_visible: bool
    content: str | None
    created_at: datetime | None
    updated_at: datetime | None


class DailyQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    qid: str
    question_date: date
    prompt: str
    author_uid: str
    author_nickname: str
    revealed: bool
    answered_count: int
    partner_count: int
    answers: list[DailyQuestionAnswerResponse]
    created_at: datetime
    updated_at: datetime


class DailyQuestionTodayResponse(BaseModel):
    item: DailyQuestionResponse | None


class DailyQuestionListResponse(BaseModel):
    items: list[DailyQuestionResponse]
    total: int
