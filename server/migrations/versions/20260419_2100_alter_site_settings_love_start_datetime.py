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

"""alter love_start_date to datetime

Revision ID: 20260419_2100
Revises: 20260419_0300
Create Date: 2026-04-19 21:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260419_2100"
down_revision: Union[str, None] = "20260419_0300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_column_type(table_name: str, column_name: str):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for column in inspector.get_columns(table_name):
        if column.get("name") == column_name:
            return column.get("type")
    return None


def upgrade() -> None:
    column_type = _get_column_type("site_settings", "love_start_date")
    if column_type is None:
        return

    if isinstance(column_type, sa.DateTime):
        return

    with op.batch_alter_table("site_settings") as batch_op:
        batch_op.alter_column(
            "love_start_date",
            existing_type=sa.Date(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=True,
        )


def downgrade() -> None:
    column_type = _get_column_type("site_settings", "love_start_date")
    if column_type is None:
        return

    if isinstance(column_type, sa.Date) and not isinstance(column_type, sa.DateTime):
        return

    with op.batch_alter_table("site_settings") as batch_op:
        batch_op.alter_column(
            "love_start_date",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.Date(),
            existing_nullable=True,
        )
