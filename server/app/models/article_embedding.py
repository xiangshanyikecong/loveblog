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

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ArticleEmbedding(Base):
    """Cached embedding vector for one article (AI 语义搜索).

    Vectors are stored as JSON text (not pgvector) so the feature works on
    both SQLite and vanilla PostgreSQL — the couple-scale corpus (hundreds of
    articles) is comfortably scored with an in-process cosine similarity.
    ``content_hash`` invalidates the cache when the article text changes;
    ``model`` guards against mixing vectors from different embedding models
    after an operator swaps the configured LLM.
    """

    __tablename__ = "article_embeddings"
    __table_args__ = (
        UniqueConstraint("article_id", "model", name="uq_article_embedding_article_model"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    # sha256 hex of the exact text that was embedded.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # JSON array of floats.
    vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    article = relationship("Article")
