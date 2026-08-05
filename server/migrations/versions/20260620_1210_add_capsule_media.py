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

"""add voice/video media columns to capsules

Revision ID: 20260620_1210
Revises: 20260620_1200
Create Date: 2026-06-20 12:10:00.000000

Note: this revision was renumbered from the original ``20260620_1200`` because
that id collided with ``20260620_1200_add_coupons_ledger_period`` (two
migrations sharing a revision id breaks Alembic's history graph). It now chains
linearly after the coupons/ledger/period migration.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260620_1210"
down_revision = "20260620_1200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("capsules")}

    if "media_url" not in cols:
        op.add_column("capsules", sa.Column("media_url", sa.String(length=512), nullable=True))
    if "media_type" not in cols:
        op.add_column("capsules", sa.Column("media_type", sa.String(length=16), nullable=True))
    if "media_duration_sec" not in cols:
        op.add_column("capsules", sa.Column("media_duration_sec", sa.Integer(), nullable=True))

    # Allow pure voice / video capsules with no text body.
    op.alter_column("capsules", "content", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("capsules", "content", existing_type=sa.Text(), nullable=False)
    op.drop_column("capsules", "media_duration_sec")
    op.drop_column("capsules", "media_type")
    op.drop_column("capsules", "media_url")
