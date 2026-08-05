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

"""add couple avatars to site settings

Revision ID: 20260501_couple_avatars
Revises: 20260419_0300
Create Date: 2026-05-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260501_couple_avatars"
down_revision: Union[str, None] = "add_visibility_pwd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # Check if site_settings table exists
    tables = set(inspector.get_table_names())
    if "site_settings" not in tables:
        return
    
    # Check if columns already exist
    columns = {col["name"] for col in inspector.get_columns("site_settings")}
    
    if "partner_a_avatar" not in columns:
        op.add_column("site_settings", sa.Column("partner_a_avatar", sa.String(length=255), nullable=True))
    
    if "partner_b_avatar" not in columns:
        op.add_column("site_settings", sa.Column("partner_b_avatar", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    tables = set(inspector.get_table_names())
    if "site_settings" not in tables:
        return
    
    columns = {col["name"] for col in inspector.get_columns("site_settings")}
    
    if "partner_b_avatar" in columns:
        op.drop_column("site_settings", "partner_b_avatar")
    
    if "partner_a_avatar" in columns:
        op.drop_column("site_settings", "partner_a_avatar")
