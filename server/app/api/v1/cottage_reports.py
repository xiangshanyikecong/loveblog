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

"""Monthly cottage report endpoints."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.chat_message import ChatMessage
from app.models.checkin import CheckIn
from app.models.cottage_plan import CottagePlan, CottagePlanStatus
from app.models.cottage_reminder import CottageReminder
from app.models.daily_question import DailyQuestion, DailyQuestionAnswer
from app.models.mood import MoodCheckin
from app.models.user import User
from app.models.wish import Wish, WishStatus
from app.schemas.cottage_report import (
    CottageMonthlyReportResponse,
    CottageMoodStat,
    CottageReportHighlight,
)


router = APIRouter(prefix="/cottage/reports", tags=["cottage-reports"])


def _month_bounds(year: int, month: int) -> tuple[date, date, datetime, datetime]:
    start_day = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_day = date(year, month, last_day)
    start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_dt = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start_day, end_day, start_dt, end_dt


def _count(query) -> int:
    return int(query.scalar() or 0)


@router.get("/monthly", response_model=CottageMonthlyReportResponse)
def monthly_report(
    year: Annotated[int, Query(ge=1970, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottageMonthlyReportResponse:
    ensure_partner(current_user)
    start_day, end_day, start_dt, end_dt = _month_bounds(year, month)

    stats = {
        "checkins": _count(
            db.query(func.count(CheckIn.id)).filter(
                CheckIn.deleted_at.is_(None),
                CheckIn.created_at >= start_dt,
                CheckIn.created_at < end_dt,
            )
        ),
        "moods": _count(
            db.query(func.count(MoodCheckin.id)).filter(
                MoodCheckin.mood_date >= start_day,
                MoodCheckin.mood_date <= end_day,
            )
        ),
        "questions": _count(
            db.query(func.count(DailyQuestion.id)).filter(
                DailyQuestion.deleted_at.is_(None),
                DailyQuestion.question_date >= start_day,
                DailyQuestion.question_date <= end_day,
            )
        ),
        "answers": _count(
            db.query(func.count(DailyQuestionAnswer.id))
            .join(DailyQuestion, DailyQuestion.id == DailyQuestionAnswer.question_id)
            .filter(
                DailyQuestion.deleted_at.is_(None),
                DailyQuestion.question_date >= start_day,
                DailyQuestion.question_date <= end_day,
            )
        ),
        "chat_messages": _count(
            db.query(func.count(ChatMessage.id)).filter(
                ChatMessage.deleted_at.is_(None),
                ChatMessage.created_at >= start_dt,
                ChatMessage.created_at < end_dt,
            )
        ),
        "wishes_created": _count(
            db.query(func.count(Wish.id)).filter(
                Wish.deleted_at.is_(None),
                Wish.created_at >= start_dt,
                Wish.created_at < end_dt,
            )
        ),
        "wishes_completed": _count(
            db.query(func.count(Wish.id)).filter(
                Wish.deleted_at.is_(None),
                Wish.status == WishStatus.completed.value,
                Wish.completed_at >= start_dt,
                Wish.completed_at < end_dt,
            )
        ),
        "plans_created": _count(
            db.query(func.count(CottagePlan.id)).filter(
                CottagePlan.deleted_at.is_(None),
                CottagePlan.created_at >= start_dt,
                CottagePlan.created_at < end_dt,
            )
        ),
        "plans_completed": _count(
            db.query(func.count(CottagePlan.id)).filter(
                CottagePlan.deleted_at.is_(None),
                CottagePlan.status == CottagePlanStatus.done.value,
                CottagePlan.completed_at >= start_dt,
                CottagePlan.completed_at < end_dt,
            )
        ),
        "reminders_created": _count(
            db.query(func.count(CottageReminder.id)).filter(
                CottageReminder.deleted_at.is_(None),
                CottageReminder.created_at >= start_dt,
                CottageReminder.created_at < end_dt,
            )
        ),
    }

    mood_rows = (
        db.query(MoodCheckin.mood, MoodCheckin.emoji, func.count(MoodCheckin.id))
        .filter(MoodCheckin.mood_date >= start_day, MoodCheckin.mood_date <= end_day)
        .group_by(MoodCheckin.mood, MoodCheckin.emoji)
        .order_by(func.count(MoodCheckin.id).desc(), MoodCheckin.mood.asc())
        .limit(5)
        .all()
    )
    top_moods = [
        CottageMoodStat(mood=row[0], emoji=row[1], count=int(row[2] or 0))
        for row in mood_rows
    ]

    highlights: list[CottageReportHighlight] = []
    completed_wish = (
        db.query(Wish)
        .filter(
            Wish.deleted_at.is_(None),
            Wish.status == WishStatus.completed.value,
            Wish.completed_at >= start_dt,
            Wish.completed_at < end_dt,
        )
        .order_by(Wish.completed_at.desc())
        .first()
    )
    if completed_wish is not None:
        highlights.append(
            CottageReportHighlight(
                kind="wish",
                title=completed_wish.title,
                subtitle="Wish completed",
                occurred_at=completed_wish.completed_at,
            )
        )

    completed_plan = (
        db.query(CottagePlan)
        .filter(
            CottagePlan.deleted_at.is_(None),
            CottagePlan.status == CottagePlanStatus.done.value,
            CottagePlan.completed_at >= start_dt,
            CottagePlan.completed_at < end_dt,
        )
        .order_by(CottagePlan.completed_at.desc())
        .first()
    )
    if completed_plan is not None:
        highlights.append(
            CottageReportHighlight(
                kind="plan",
                title=completed_plan.title,
                subtitle="Plan completed",
                occurred_at=completed_plan.completed_at,
            )
        )

    question = (
        db.query(DailyQuestion)
        .filter(
            DailyQuestion.deleted_at.is_(None),
            DailyQuestion.question_date >= start_day,
            DailyQuestion.question_date <= end_day,
        )
        .order_by(DailyQuestion.question_date.desc(), DailyQuestion.created_at.desc())
        .first()
    )
    if question is not None:
        highlights.append(
            CottageReportHighlight(
                kind="question",
                title=question.prompt,
                subtitle="Latest daily question",
                occurred_at=question.created_at,
            )
        )

    return CottageMonthlyReportResponse(
        year=year,
        month=month,
        start_date=start_day.isoformat(),
        end_date=end_day.isoformat(),
        generated_at=datetime.now(timezone.utc),
        stats=stats,
        top_moods=top_moods,
        highlights=highlights[:6],
    )
