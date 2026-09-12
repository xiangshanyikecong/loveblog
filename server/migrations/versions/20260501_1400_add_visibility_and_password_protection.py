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

"""add visibility and password protection

Revision ID: add_visibility_pwd
Revises: 20260426_1000_add_versions_notifications_auto_backup
Create Date: 2026-05-01 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_visibility_pwd'
down_revision = 'add_versions_notifications'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create visibility enum type
    visibility_enum = sa.Enum(
        'private', 'partners_only', 'guest_viewable', 'public', 'password_protected',
        name='content_visibility'
    )
    visibility_enum.create(op.get_bind(), checkfirst=True)
    
    # Add visibility column to articles table
    op.add_column('articles', sa.Column(
        'visibility',
        sa.Enum('private', 'partners_only', 'guest_viewable', 'public', 'password_protected', name='content_visibility'),
        nullable=True
    ))
    
    # Add password_hash column to articles table
    op.add_column('articles', sa.Column('password_hash', sa.String(255), nullable=True))
    
    # Migrate existing articles data
    # - If is_encrypted=True -> partners_only
    # - If status=published and is_encrypted=False -> public
    # - If status=draft -> private
    op.execute("""
        UPDATE articles
        SET visibility = CASE
            WHEN is_encrypted = TRUE THEN 'partners_only'::content_visibility
            WHEN status = 'published' AND is_encrypted = FALSE THEN 'public'::content_visibility
            ELSE 'private'::content_visibility
        END
        WHERE visibility IS NULL
    """)
    
    # Make visibility NOT NULL after migration
    op.alter_column('articles', 'visibility', nullable=False)
    
    # Add visibility column to albums table
    op.add_column('albums', sa.Column(
        'visibility',
        sa.Enum('private', 'partners_only', 'guest_viewable', 'public', 'password_protected', name='content_visibility'),
        nullable=True
    ))
    
    # Add password_hash column to albums table
    op.add_column('albums', sa.Column('password_hash', sa.String(255), nullable=True))
    
    # Migrate existing albums data
    # - If is_encrypted=True -> partners_only
    # - If is_public=True and is_encrypted=False -> public
    # - If is_public=False -> private
    op.execute("""
        UPDATE albums
        SET visibility = CASE
            WHEN is_encrypted = TRUE THEN 'partners_only'::content_visibility
            WHEN is_public = TRUE AND is_encrypted = FALSE THEN 'public'::content_visibility
            ELSE 'private'::content_visibility
        END
        WHERE visibility IS NULL
    """)
    
    # Make visibility NOT NULL after migration
    op.alter_column('albums', 'visibility', nullable=False)


def downgrade() -> None:
    # Remove columns from albums
    op.drop_column('albums', 'password_hash')
    op.drop_column('albums', 'visibility')
    
    # Remove columns from articles
    op.drop_column('articles', 'password_hash')
    op.drop_column('articles', 'visibility')
    
    # Drop enum type
    sa.Enum(name='content_visibility').drop(op.get_bind(), checkfirst=True)
