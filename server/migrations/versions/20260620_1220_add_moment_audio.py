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

"""add voice-diary audio columns to moments

Revision ID: 20260620_1220
Revises: 20260620_1210
Create Date: 2026-06-20 13:00:00.000000

Note: renumbered from the original ``20260620_1300`` so it chains cleanly after
the renumbered capsule-media migration (``20260620_1210``).
"""
from alembic import op
import sqlalchemy as sa


revision = "20260620_1220"
down_revision = "20260620_1210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("moments")}

    if "audio_url" not in cols:
        op.add_column("moments", sa.Column("audio_url", sa.String(length=512), nullable=True))
    if "audio_duration_sec" not in cols:
        op.add_column("moments", sa.Column("audio_duration_sec", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("moments", "audio_duration_sec")
    op.drop_column("moments", "audio_url")
