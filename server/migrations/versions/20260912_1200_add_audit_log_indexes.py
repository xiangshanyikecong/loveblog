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

"""add audit log sort and trgm search indexes

Revision ID: 20260912_1200
Revises: 20260912_1100
"""
from alembic import op


revision = "20260912_1200"
down_revision = "20260912_1100"
branch_labels = None
depends_on = None

# Covers the admin list ordering (created_at DESC, id DESC) so deep
# OFFSET pages scan an index instead of the heap.
_SORT_INDEX = ("ix_audit_logs_created_id", "audit_logs", ["created_at", "id"])

# ILIKE '%…%' keyword search over the free-text columns; pg_trgm GIN
# indexes keep those scans fast. PostgreSQL only (tests run on SQLite).
_TRGM_INDEXES = (
    ("ix_audit_logs_actor_username_trgm", "audit_logs", "actor_username"),
    ("ix_audit_logs_actor_nickname_trgm", "audit_logs", "actor_nickname"),
    ("ix_audit_logs_resource_name_trgm", "audit_logs", "resource_name"),
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_index(_SORT_INDEX[0], _SORT_INDEX[1], _SORT_INDEX[2])
    if not _is_postgresql():
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, table_name, column_name in _TRGM_INDEXES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} "
            f"USING gin ({column_name} gin_trgm_ops)"
        )


def downgrade() -> None:
    if _is_postgresql():
        for index_name, _table_name, _column_name in _TRGM_INDEXES:
            op.execute(f"DROP INDEX IF EXISTS {index_name}")
    op.drop_index(_SORT_INDEX[0], table_name=_SORT_INDEX[1])
