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

"""add daily blind questions

Revision ID: 20260619_0900
Revises: 20260614_0000
Create Date: 2026-06-19 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260619_0900"
down_revision = "20260614_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qid", sa.String(length=36), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("question_date", sa.Date(), nullable=False),
        sa.Column("prompt", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_daily_questions_id"), "daily_questions", ["id"], unique=False)
    op.create_index(op.f("ix_daily_questions_qid"), "daily_questions", ["qid"], unique=True)
    op.create_index(op.f("ix_daily_questions_author_id"), "daily_questions", ["author_id"], unique=False)
    op.create_index(op.f("ix_daily_questions_question_date"), "daily_questions", ["question_date"], unique=True)

    op.create_table(
        "daily_question_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aid", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["question_id"], ["daily_questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_id", "author_id", name="uq_daily_question_answer_author"),
    )
    op.create_index(op.f("ix_daily_question_answers_id"), "daily_question_answers", ["id"], unique=False)
    op.create_index(op.f("ix_daily_question_answers_aid"), "daily_question_answers", ["aid"], unique=True)
    op.create_index(
        op.f("ix_daily_question_answers_question_id"),
        "daily_question_answers",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_question_answers_author_id"),
        "daily_question_answers",
        ["author_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_question_answers_author_id"), table_name="daily_question_answers")
    op.drop_index(op.f("ix_daily_question_answers_question_id"), table_name="daily_question_answers")
    op.drop_index(op.f("ix_daily_question_answers_aid"), table_name="daily_question_answers")
    op.drop_index(op.f("ix_daily_question_answers_id"), table_name="daily_question_answers")
    op.drop_table("daily_question_answers")

    op.drop_index(op.f("ix_daily_questions_question_date"), table_name="daily_questions")
    op.drop_index(op.f("ix_daily_questions_author_id"), table_name="daily_questions")
    op.drop_index(op.f("ix_daily_questions_qid"), table_name="daily_questions")
    op.drop_index(op.f("ix_daily_questions_id"), table_name="daily_questions")
    op.drop_table("daily_questions")
