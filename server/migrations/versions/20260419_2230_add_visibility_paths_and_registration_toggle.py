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

"""add visibility, upload paths and registration toggle

Revision ID: 20260419_2230
Revises: 20260419_2100
Create Date: 2026-04-19 22:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260419_2230"
down_revision: Union[str, None] = "20260419_2100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def _ensure_enum_type(bind, enum_name: str, values: list[str]) -> None:
    # PostgreSQL-only enum bootstrap. On SQLite/MySQL this is harmlessly skipped.
    if bind.dialect.name != "postgresql":
        return

    escaped = ", ".join([f"'{v}'" for v in values])
    op.execute(
        sa.text(
            f"DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') THEN "
            f"CREATE TYPE {enum_name} AS ENUM ({escaped}); "
            f"END IF; END $$;"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Ensure enum types for visibility fields (PostgreSQL)
    _ensure_enum_type(bind, "visibility", ["public", "partners_only", "encrypted"])
    _ensure_enum_type(bind, "moment_visibility", ["public", "partners_only", "encrypted"])

    # events.visibility
    if not _column_exists(inspector, "events", "visibility"):
        with op.batch_alter_table("events") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "visibility",
                    sa.Enum("public", "partners_only", "encrypted", name="visibility"),
                    nullable=False,
                    server_default="public",
                )
            )

    # moments.visibility
    inspector = inspect(bind)
    if not _column_exists(inspector, "moments", "visibility"):
        with op.batch_alter_table("moments") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "visibility",
                    sa.Enum("public", "partners_only", "encrypted", name="moment_visibility"),
                    nullable=False,
                    server_default="public",
                )
            )

    # site_settings.timeline_path / videos_path / allow_registration
    inspector = inspect(bind)
    with op.batch_alter_table("site_settings") as batch_op:
        if not _column_exists(inspector, "site_settings", "timeline_path"):
            batch_op.add_column(
                sa.Column("timeline_path", sa.String(length=255), nullable=False, server_default="uploads/timeline")
            )

        if not _column_exists(inspector, "site_settings", "videos_path"):
            batch_op.add_column(
                sa.Column("videos_path", sa.String(length=255), nullable=False, server_default="uploads/videos")
            )

        if not _column_exists(inspector, "site_settings", "allow_registration"):
            batch_op.add_column(
                sa.Column("allow_registration", sa.Boolean(), nullable=False, server_default=sa.text("false"))
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    with op.batch_alter_table("site_settings") as batch_op:
        if _column_exists(inspector, "site_settings", "allow_registration"):
            batch_op.drop_column("allow_registration")

        if _column_exists(inspector, "site_settings", "videos_path"):
            batch_op.drop_column("videos_path")

        if _column_exists(inspector, "site_settings", "timeline_path"):
            batch_op.drop_column("timeline_path")

    inspector = inspect(bind)
    if _column_exists(inspector, "moments", "visibility"):
        with op.batch_alter_table("moments") as batch_op:
            batch_op.drop_column("visibility")

    inspector = inspect(bind)
    if _column_exists(inspector, "events", "visibility"):
        with op.batch_alter_table("events") as batch_op:
            batch_op.drop_column("visibility")

    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TYPE IF EXISTS moment_visibility"))
        op.execute(sa.text("DROP TYPE IF EXISTS visibility"))
