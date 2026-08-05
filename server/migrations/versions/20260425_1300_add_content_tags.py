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

"""add content tags

Revision ID: 20260425_1300
Revises: 20260425_1200
Create Date: 2026-04-25 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260425_1300"
down_revision: Union[str, None] = "20260425_1200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONTENT_TABLES = ("articles", "albums", "events", "moments", "messages")


def upgrade() -> None:
    for table_name in CONTENT_TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
            )
    
    # SQLite doesn't support DROP DEFAULT via ALTER COLUMN easily. 
    # For SQLite we just leave the server_default or rely on batch mode if supported.
    # Here we skip the explicit drop if it's sqlite to avoid the error.
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        for table_name in CONTENT_TABLES:
            op.alter_column(table_name, "tags", server_default=None)



def downgrade() -> None:
    for table_name in reversed(CONTENT_TABLES):
        op.drop_column(table_name, "tags")
