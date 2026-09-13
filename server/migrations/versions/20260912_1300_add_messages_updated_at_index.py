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
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""add messages updated_at index for incremental sync

Revision ID: 20260912_1300
Revises: 20260912_1200
"""
from alembic import op


revision = "20260912_1300"
down_revision = "20260912_1200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Incremental message sync filters on updated_at > cursor and orders by
    # (updated_at, id); the composite index lets PostgreSQL walk that range
    # without a sort step.
    op.create_index("ix_messages_updated_at_id", "messages", ["updated_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_messages_updated_at_id", table_name="messages")
