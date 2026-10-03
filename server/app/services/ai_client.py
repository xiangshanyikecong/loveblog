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

"""Minimal OpenAI-compatible client for the optional self-hosted LLM.

Speaks the de-facto standard ``/chat/completions`` + ``/embeddings`` surface
so ANY provider works without new dependencies: Ollama (``/v1``), vLLM,
LM Studio, llama.cpp server, or a gateway like one-api. The node owner
points ``AI_BASE_URL`` at their own deployment — nothing is sent to a
third-party SaaS, keeping the self-hosted privacy promise.

Failure model mirrors the Redis-dependent modules: when AI is not
configured the API layer degrades to a clean 503 instead of dragging other
features down; upstream errors surface as 502 with the provider message.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Raised when the AI backend is unavailable or misbehaves."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def is_chat_configured() -> bool:
    return bool(
        settings.ai_enabled
        and settings.ai_base_url.strip()
        and settings.ai_chat_model.strip()
    )


def is_embedding_configured() -> bool:
    return bool(
        settings.ai_enabled
        and settings.ai_base_url.strip()
        and settings.ai_embedding_model.strip()
    )


def require_chat() -> None:
    if not is_chat_configured():
        raise AIServiceError(503, "AI is not enabled on this node")


def require_embedding() -> None:
    if not is_embedding_configured():
        raise AIServiceError(503, "AI semantic search is not enabled on this node")


def _endpoint(path: str) -> str:
    return settings.ai_base_url.strip().rstrip("/") + path


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.ai_api_key.strip()}"
    return headers


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.post(
            _endpoint(path),
            json=payload,
            headers=_headers(),
            timeout=settings.ai_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        logger.warning("AI upstream unreachable: %s", exc)
        raise AIServiceError(502, "AI upstream is unreachable") from exc
    if response.status_code >= 400:
        # Never leak the full upstream body into responses; keep first 200 chars.
        raise AIServiceError(
            502, f"AI upstream error ({response.status_code}): {response.text[:200]}"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise AIServiceError(502, "AI upstream returned invalid JSON") from exc


def chat_completion(messages: list[dict[str, str]], *, max_tokens: int = 1024) -> str:
    """One-shot (non-streaming) chat completion; returns the text answer."""
    require_chat()
    data = _post(
        "/chat/completions",
        {
            "model": settings.ai_chat_model.strip(),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "stream": False,
        },
    )
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIServiceError(502, "AI upstream returned an unexpected completion") from exc
    if not isinstance(content, str) or not content.strip():
        raise AIServiceError(502, "AI upstream returned an empty completion")
    return content.strip()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts; returns vectors aligned with the input order."""
    require_embedding()
    data = _post(
        "/embeddings",
        {"model": settings.ai_embedding_model.strip(), "input": texts},
    )
    try:
        rows = sorted(data["data"], key=lambda item: item.get("index", 0))
        vectors = [[float(value) for value in row["embedding"]] for row in rows]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIServiceError(502, "AI upstream returned invalid embeddings") from exc
    if len(vectors) != len(texts):
        raise AIServiceError(502, "AI upstream returned a mismatched embedding batch")
    return vectors
