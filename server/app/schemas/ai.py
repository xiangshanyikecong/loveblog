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

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AIAvailabilityResponse(BaseModel):
    enabled: bool
    chat_model: str | None = None
    embedding_model: str | None = None
    features: list[str] = Field(
        description="Activated AI capability keys, e.g. article_polish / semantic_search."
    )


class AIPolishRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    mode: Literal["polish", "continue", "proofread"] = "polish"


class AIPolishResponse(BaseModel):
    text: str


class AISemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    top_k: int = Field(default=5, ge=1, le=10)


class AISemanticSearchResult(BaseModel):
    aid: str
    title: str
    snippet: str
    score: float
    updated_at: datetime | None = None


class AISemanticSearchResponse(BaseModel):
    query: str
    results: list[AISemanticSearchResult]
    indexed_count: int


class AIMonthlyReportRequest(BaseModel):
    year: int = Field(ge=1970, le=2100)
    month: int = Field(ge=1, le=12)


class AIMonthlyReportResponse(BaseModel):
    year: int
    month: int
    text: str


class AIQuestionsRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=10)


class AIQuestionsResponse(BaseModel):
    questions: list[str]
