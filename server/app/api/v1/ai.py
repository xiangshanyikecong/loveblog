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

"""Optional AI assist endpoints, backed by a self-hosted LLM.

All endpoints are partner-only and degrade to 503 when the operator has not
configured ``AI_BASE_URL`` + models — the rest of the node keeps working,
mirroring how the Redis-dependent realtime modules fail closed.

Endpoints under ``/v1/ai``:

- ``GET  /v1/ai/status``            — feature availability probe (drives UI affordances)
- ``POST /v1/ai/article/polish``    — polish / continue / proofread diary text
- ``POST /v1/ai/article/search``    — semantic search across readable articles
- ``POST /v1/ai/report/monthly``    — LLM-written narrative for a month's stats
- ``POST /v1/ai/questions/generate``— daily-question candidates (not auto-inserted)
"""
from __future__ import annotations

import calendar
import hashlib
import json
import math
import re
from collections.abc import Callable
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.article import Article, ArticleBlockType
from app.models.article_embedding import ArticleEmbedding
from app.models.chat_message import ChatMessage
from app.models.checkin import CheckIn
from app.models.game_match import GameMatch
from app.models.listen_history import ListenHistoryEntry
from app.models.moment import Moment
from app.models.mood import MoodCheckin
from app.models.user import User
from app.models.wish import Wish, WishStatus
from app.schemas.ai import (
    AIMonthlyReportRequest,
    AIMonthlyReportResponse,
    AIPolishRequest,
    AIPolishResponse,
    AIQuestionsRequest,
    AIQuestionsResponse,
    AISemanticSearchRequest,
    AISemanticSearchResponse,
    AISemanticSearchResult,
    AIAvailabilityResponse,
)
from app.services import ai_client
from app.services.ai_client import AIServiceError

router = APIRouter(prefix="/ai", tags=["ai"])

# Cap the corpus scanned per search — couple scale is far below this; the cap
# bounds embedding fan-out if an instance is (ab)used as a general blog.
MAX_SEARCH_ARTICLES = 500

POLISH_PROMPTS = {
    "polish": (
        "你是一位温暖的中文写作助手。请润色下面的恋爱日记片段：保留作者的本意与语气，"
        "让文字更流畅动人；直接输出润色后的正文，不要任何解释、标题或前后缀。"
    ),
    "continue": (
        "你是一位温暖的中文写作助手。请顺着下面的恋爱日记内容自然续写一段"
        "（150 字以内），保持相同的叙述视角与语气；直接输出续写内容，不要复述原文。"
    ),
    "proofread": (
        "你是一位细心的中文校对助手。请只修正下面文字中的错别字、标点和语病，"
        "不改变用词风格与内容；直接输出修改后的全文，不要解释。"
    ),
}

QUESTION_PROMPT = (
    "你为一对情侣的「每日一问」出题。请生成 {count} 个适合情侣双方各自作答、"
    "然后互相揭晓的有趣问题：具体、轻松、能引发回忆或了解彼此，避免空泛或敏感。"
    "每行一个问题，不要编号、引号或其他格式。"
)

MONTHLY_PROMPT = (
    "你为一对情侣撰写 {year} 年 {month} 月的恋爱月报文案。请基于下面的真实统计数据，"
    "写一段 150-250 字的中文小结：先概括本月的相处亮点，再点出一两个最突出的数字，"
    "语气温暖亲密，像写给两个人的信；不要罗列全部数字，不要使用 Markdown。\n\n统计数据：\n{stats}"
)


def _map_ai_error(exc: AIServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status", response_model=AIAvailabilityResponse)
def ai_status(
    current_user: User = Depends(get_current_user),
) -> AIAvailabilityResponse:
    ensure_partner(current_user)
    features: list[str] = []
    if ai_client.is_chat_configured():
        features.extend(["article_polish", "monthly_report", "question_generate"])
    if ai_client.is_embedding_configured() and ai_client.is_chat_configured():
        # Semantic search needs chat too (graceful hint when embeddings missing).
        features.append("semantic_search")
    return AIAvailabilityResponse(
        enabled=ai_client.is_chat_configured(),
        chat_model=settings.ai_chat_model.strip() or None,
        embedding_model=settings.ai_embedding_model.strip() or None,
        features=features,
    )


# ---------------------------------------------------------------------------
# Article polish / continue / proofread
# ---------------------------------------------------------------------------

@router.post("/article/polish", response_model=AIPolishResponse)
@limiter.limit("10/minute")
def article_polish(
    request: Request,
    payload: AIPolishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIPolishResponse:
    ensure_partner(current_user)
    try:
        text = ai_client.chat_completion(
            [
                {"role": "system", "content": POLISH_PROMPTS[payload.mode]},
                {"role": "user", "content": payload.content},
            ],
            max_tokens=2048,
        )
    except AIServiceError as exc:
        raise _map_ai_error(exc) from exc
    return AIPolishResponse(text=text)


# ---------------------------------------------------------------------------
# Semantic article search
# ---------------------------------------------------------------------------

def _article_text(article: Article) -> str:
    parts = [article.title]
    for block in article.blocks:
        if block.block_type in (
            ArticleBlockType.paragraph.value,
            ArticleBlockType.heading.value,
            ArticleBlockType.quote.value,
        ):
            parts.append(block.content)
    text = "\n".join(part for part in parts if part)
    return text[:4000]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if norm == 0:
        return 0.0
    return dot / norm


def _ensure_embeddings(
    db: Session,
    articles: list[tuple[Article, str]],
    *,
    embed: Callable[[list[str]], list[list[float]]],
    model: str,
) -> dict[int, list[float]]:
    """Refresh stale/missing embeddings in one batch; returns id → vector."""
    by_article: dict[int, ArticleEmbedding] = {
        row.article_id: row
        for row in db.query(ArticleEmbedding).filter(
            ArticleEmbedding.model == model,
            ArticleEmbedding.article_id.in_([article.id for article, _text in articles]),
        ).all()
    }
    pending: list[tuple[Article, str]] = []
    for article, text in articles:
        content_hash = hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()
        row = by_article.get(article.id)
        if row is None or row.content_hash != content_hash:
            pending.append((article, text))

    if pending:
        vectors = embed([text for _article, text in pending])
        for (article, text), vector in zip(pending, vectors):
            content_hash = hashlib.sha256(f"{model}\n{text}".encode("utf-8")).hexdigest()
            row = by_article.get(article.id)
            if row is None:
                row = ArticleEmbedding(
                    article_id=article.id, model=model, content_hash=content_hash
                )
                db.add(row)
                by_article[article.id] = row
            row.content_hash = content_hash
            row.vector_json = json.dumps(vector)
        db.commit()

    result: dict[int, list[float]] = {}
    for article, _text in articles:
        row = by_article.get(article.id)
        if row is not None:
            try:
                result[article.id] = json.loads(row.vector_json)
            except ValueError:
                continue
    return result


@router.post("/article/search", response_model=AISemanticSearchResponse)
@limiter.limit("10/minute")
def semantic_search(
    request: Request,
    payload: AISemanticSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AISemanticSearchResponse:
    ensure_partner(current_user)
    try:
        ai_client.require_embedding()
        articles = (
            db.query(Article)
            .options(joinedload(Article.blocks))
            .filter(
                Article.deleted_at.is_(None),
                # Encrypted articles are server-opaque ciphertext; skip them.
                Article.is_encrypted.is_(False),
            )
            .order_by(Article.updated_at.desc())
            .limit(MAX_SEARCH_ARTICLES)
            .all()
        )
        texts = [(article, _article_text(article)) for article in articles]
        texts = [(article, text) for article, text in texts if text.strip()]
        if not texts:
            return AISemanticSearchResponse(
                query=payload.query, results=[], indexed_count=0
            )

        model = settings.ai_embedding_model.strip()
        vectors = _ensure_embeddings(db, texts, embed=ai_client.embed_texts, model=model)
        query_vector = ai_client.embed_texts([payload.query])[0]

        scored: list[tuple[float, Article, str]] = []
        for article, text in texts:
            vector = vectors.get(article.id)
            if vector is None:
                continue
            scored.append((_cosine(query_vector, vector), article, text))
        scored.sort(key=lambda item: item[0], reverse=True)

        results = [
            AISemanticSearchResult(
                aid=article.aid,
                title=article.title,
                snippet=text[:160],
                score=round(score, 4),
                updated_at=article.updated_at,
            )
            for score, article, text in scored[: payload.top_k]
        ]
        return AISemanticSearchResponse(
            query=payload.query, results=results, indexed_count=len(texts)
        )
    except AIServiceError as exc:
        raise _map_ai_error(exc) from exc


# ---------------------------------------------------------------------------
# AI monthly report narrative
# ---------------------------------------------------------------------------

def _month_stats(db: Session, year: int, month: int) -> dict[str, int]:
    last_day = calendar.monthrange(year, month)[1]
    start_day, end_day = date(year, month, 1), date(year, month, last_day)
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
    end_dt = (
        datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=timezone.utc)
    )

    def count(query) -> int:
        return int(query.scalar() or 0)

    return {
        "报备次数": count(
            db.query(func.count(CheckIn.id)).filter(
                CheckIn.deleted_at.is_(None),
                CheckIn.created_at >= start_dt,
                CheckIn.created_at < end_dt,
            )
        ),
        "心情打卡": count(
            db.query(func.count(MoodCheckin.id)).filter(
                MoodCheckin.mood_date >= start_day,
                MoodCheckin.mood_date <= end_day,
            )
        ),
        "悄悄话消息": count(
            db.query(func.count(ChatMessage.id)).filter(
                ChatMessage.deleted_at.is_(None),
                ChatMessage.created_at >= start_dt,
                ChatMessage.created_at < end_dt,
            )
        ),
        "完成心愿": count(
            db.query(func.count(Wish.id)).filter(
                Wish.deleted_at.is_(None),
                Wish.status == WishStatus.completed.value,
                Wish.completed_at >= start_dt,
                Wish.completed_at < end_dt,
            )
        ),
        "游戏对局": count(
            db.query(func.count(GameMatch.id)).filter(
                GameMatch.created_at >= start_dt,
                GameMatch.created_at < end_dt,
            )
        ),
        "一起听歌曲": count(
            db.query(func.count(ListenHistoryEntry.id)).filter(
                ListenHistoryEntry.played_at >= start_dt,
                ListenHistoryEntry.played_at < end_dt,
            )
        ),
        "碎碎念": count(
            db.query(func.count(Moment.id)).filter(
                Moment.deleted_at.is_(None),
                Moment.created_at >= start_dt,
                Moment.created_at < end_dt,
            )
        ),
    }


@router.post("/report/monthly", response_model=AIMonthlyReportResponse)
@limiter.limit("5/minute")
def monthly_report_narrative(
    request: Request,
    payload: AIMonthlyReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIMonthlyReportResponse:
    ensure_partner(current_user)
    stats = _month_stats(db, payload.year, payload.month)
    stats_text = "\n".join(f"- {name}: {value}" for name, value in stats.items())
    try:
        text = ai_client.chat_completion(
            [
                {
                    "role": "system",
                    "content": MONTHLY_PROMPT.format(
                        year=payload.year, month=payload.month, stats=stats_text
                    ),
                },
                {"role": "user", "content": "请生成本月月报文案。"},
            ],
            max_tokens=1024,
        )
    except AIServiceError as exc:
        raise _map_ai_error(exc) from exc
    return AIMonthlyReportResponse(year=payload.year, month=payload.month, text=text)


# ---------------------------------------------------------------------------
# Daily question candidates
# ---------------------------------------------------------------------------

_LINE_NOISE = re.compile(r"^[\s\d\.\、\-\*·•)．)]+")


@router.post("/questions/generate", response_model=AIQuestionsResponse)
@limiter.limit("5/minute")
def generate_questions(
    request: Request,
    payload: AIQuestionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AIQuestionsResponse:
    ensure_partner(current_user)
    try:
        raw = ai_client.chat_completion(
            [
                {
                    "role": "system",
                    "content": QUESTION_PROMPT.format(count=payload.count),
                },
                {"role": "user", "content": "请出题。"},
            ],
            max_tokens=1024,
        )
    except AIServiceError as exc:
        raise _map_ai_error(exc) from exc

    questions: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        cleaned = _LINE_NOISE.sub("", line.strip()).strip()
        if not cleaned or len(cleaned) < 4 or len(cleaned) > 120:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        questions.append(cleaned)
        if len(questions) >= payload.count:
            break
    if not questions:
        raise HTTPException(
            status_code=502, detail="AI upstream returned no usable questions"
        )
    return AIQuestionsResponse(questions=questions)
