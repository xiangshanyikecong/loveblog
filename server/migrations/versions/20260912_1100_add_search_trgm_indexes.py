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

"""add pg_trgm indexes for search ILIKE pre-filtering

Revision ID: 20260912_1100
Revises: 20260912_1000
"""
from alembic import op


revision = "20260912_1100"
down_revision = "20260912_1000"
branch_labels = None
depends_on = None

# Plain ILIKE '%…%' patterns cannot use btree indexes; pg_trgm GIN indexes
# keep the SQL-level search pre-filter fast on the large text columns.
# SQLite (used by the test suite) has no pg_trgm, so everything is skipped.
_TRGM_INDEXES = (
    ("ix_articles_title_trgm", "articles", "title"),
    ("ix_article_blocks_content_trgm", "article_blocks", "content"),
    ("ix_albums_title_trgm", "albums", "title"),
    ("ix_moments_content_trgm", "moments", "content"),
    ("ix_messages_content_trgm", "messages", "content"),
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgresql():
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table_name, column_name in _TRGM_INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} "
            f"USING gin ({column_name} gin_trgm_ops)"
        )


def downgrade() -> None:
    if not _is_postgresql():
        return
    for index_name, _table_name, _column_name in _TRGM_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
