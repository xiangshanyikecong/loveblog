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

"""add notification list + dedupe indexes

Revision ID: 20260912_1000
Revises: 20260911_1000
"""
from alembic import op


revision = "20260912_1000"
down_revision = "20260911_1000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ORDER BY created_at DESC on GET /notifications (per-recipient lists).
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    # Four-column equality dedupe lookup in services/notifications.py.
    op.create_index(
        "ix_notifications_dedupe",
        "notifications",
        ["recipient_id", "type", "source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_dedupe", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
