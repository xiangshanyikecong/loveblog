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

"""add comment target type

Revision ID: 20260503_1000
Revises: 20260501_add_couple_avatars
Create Date: 2026-05-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '20260503_1000'
down_revision = '20260501_couple_avatars'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    # 检查 comments 表是否存在
    if "comments" not in inspector.get_table_names():
        return
    
    comment_columns = {column["name"] for column in inspector.get_columns("comments")}
    
    # 添加新字段
    if "target_type" not in comment_columns:
        # 创建枚举类型
        comment_target_type = sa.Enum('Moment', 'Article', 'Album', name='comment_target_type')
        comment_target_type.create(bind, checkfirst=True)
        
        # 添加 target_type 字段，默认为 'Moment'
        op.add_column('comments', sa.Column('target_type', comment_target_type, nullable=False, server_default='Moment'))
        op.create_index(op.f('ix_comments_target_type'), 'comments', ['target_type'], unique=False)
    
    if "target_id" not in comment_columns:
        # 添加 target_id 字段，先设为可空
        op.add_column('comments', sa.Column('target_id', sa.String(length=36), nullable=True))
        
        # 从现有的 moment_id 迁移数据到 target_id
        # 首先获取 moments 表中的 mid 对应关系
        op.execute("""
            UPDATE comments 
            SET target_id = (
                SELECT mid FROM moments WHERE moments.id = comments.moment_id
            )
            WHERE moment_id IS NOT NULL
        """)
        
        # SQLite 不支持 ALTER COLUMN，所以我们保持 target_id 可空
        # 在应用层确保新评论总是有 target_id
        op.create_index(op.f('ix_comments_target_id'), 'comments', ['target_id'], unique=False)
    
    # 将 moment_id 改为可空（保留以兼容旧数据）
    # SQLite 不支持直接修改列，所以跳过这一步
    # 在应用层处理兼容性


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    
    if "comments" not in inspector.get_table_names():
        return
    
    comment_columns = {column["name"] for column in inspector.get_columns("comments")}
    
    # 删除新字段
    if "target_id" in comment_columns:
        op.drop_index(op.f('ix_comments_target_id'), table_name='comments')
        op.drop_column('comments', 'target_id')
    
    if "target_type" in comment_columns:
        op.drop_index(op.f('ix_comments_target_type'), table_name='comments')
        op.drop_column('comments', 'target_type')
        
        # 删除枚举类型
        sa.Enum(name='comment_target_type').drop(bind, checkfirst=True)
    
    # 恢复 moment_id 为 NOT NULL
    if "moment_id" in comment_columns:
        op.alter_column('comments', 'moment_id', nullable=False)
