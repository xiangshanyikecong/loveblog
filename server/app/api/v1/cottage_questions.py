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

"""Cottage daily blind questions.

Each day can have one shared question. Partners answer privately; the response
only reveals the other side after both active partners have answered.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.daily_question import DailyQuestion, DailyQuestionAnswer
from app.models.user import User, UserRole
from app.schemas.daily_question import (
    DailyQuestionAnswerRequest,
    DailyQuestionAnswerResponse,
    DailyQuestionCreateRequest,
    DailyQuestionListResponse,
    DailyQuestionResponse,
    DailyQuestionTodayResponse,
)
from app.services.notifications import notify_partners


router = APIRouter(prefix="/cottage/questions", tags=["cottage-questions"])


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _active_partners(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(
            User.role.in_([UserRole.partner_a, UserRole.partner_b]),
            User.deleted_at.is_(None),
        )
        .order_by(User.id.asc())
        .all()
    )


def _load_question(db: Session, qid: str) -> DailyQuestion:
    question = (
        db.query(DailyQuestion)
        .options(
            joinedload(DailyQuestion.author),
            joinedload(DailyQuestion.answers).joinedload(DailyQuestionAnswer.author),
        )
        .filter(DailyQuestion.qid == qid, DailyQuestion.deleted_at.is_(None))
        .first()
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


def _question_for_date(db: Session, question_date: date) -> DailyQuestion | None:
    return (
        db.query(DailyQuestion)
        .options(
            joinedload(DailyQuestion.author),
            joinedload(DailyQuestion.answers).joinedload(DailyQuestionAnswer.author),
        )
        .filter(DailyQuestion.question_date == question_date, DailyQuestion.deleted_at.is_(None))
        .first()
    )


def _is_revealed(question: DailyQuestion, partners: list[User]) -> bool:
    partner_ids = {partner.id for partner in partners}
    answered_ids = {answer.author_id for answer in question.answers}
    return len(partner_ids) >= 2 and partner_ids.issubset(answered_ids)


def _to_response(question: DailyQuestion, current_user: User, partners: list[User]) -> DailyQuestionResponse:
    revealed = _is_revealed(question, partners)
    answers_by_author = {answer.author_id: answer for answer in question.answers}
    response_answers: list[DailyQuestionAnswerResponse] = []

    for partner in partners:
        answer = answers_by_author.get(partner.id)
        is_self = partner.id == current_user.id
        content_visible = bool(answer and (revealed or is_self))
        response_answers.append(
            DailyQuestionAnswerResponse(
                aid=answer.aid if answer else None,
                author_uid=partner.uid,
                author_nickname=partner.nickname,
                is_self=is_self,
                answered=answer is not None,
                content_visible=content_visible,
                content=answer.content if content_visible and answer else None,
                created_at=answer.created_at if answer else None,
                updated_at=answer.updated_at if answer else None,
            )
        )

    return DailyQuestionResponse(
        qid=question.qid,
        question_date=question.question_date,
        prompt=question.prompt,
        author_uid=question.author.uid if question.author else "",
        author_nickname=question.author.nickname if question.author else "",
        revealed=revealed,
        answered_count=len({answer.author_id for answer in question.answers}),
        partner_count=len(partners),
        answers=response_answers,
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


@router.post("", response_model=DailyQuestionResponse, status_code=status.HTTP_201_CREATED)
def create_question(
    payload: DailyQuestionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyQuestionResponse:
    ensure_partner(current_user)
    question_date = payload.question_date or _today_utc()

    existing = _question_for_date(db, question_date)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question already exists for this date")

    question = DailyQuestion(
        author_id=current_user.id,
        question_date=question_date,
        prompt=payload.prompt,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    notify_partners(
        db,
        type="daily_question.created",
        title=f"{current_user.nickname} 写下了今天的问题",
        body=question.prompt[:160],
        link="/cottage/questions",
        source_type="daily_question",
        source_id=question.qid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    return _to_response(_load_question(db, question.qid), current_user, _active_partners(db))


@router.get("/today", response_model=DailyQuestionTodayResponse)
def get_today_question(
    on: Annotated[date | None, Query()] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyQuestionTodayResponse:
    ensure_partner(current_user)
    question = _question_for_date(db, on or _today_utc())
    if question is None:
        return DailyQuestionTodayResponse(item=None)
    return DailyQuestionTodayResponse(item=_to_response(question, current_user, _active_partners(db)))


@router.get("", response_model=DailyQuestionListResponse)
def list_questions(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyQuestionListResponse:
    ensure_partner(current_user)
    partners = _active_partners(db)
    base = db.query(DailyQuestion).filter(DailyQuestion.deleted_at.is_(None))
    items = (
        base.options(
            joinedload(DailyQuestion.author),
            joinedload(DailyQuestion.answers).joinedload(DailyQuestionAnswer.author),
        )
        .order_by(DailyQuestion.question_date.desc(), DailyQuestion.created_at.desc())
        .limit(limit)
        .all()
    )
    return DailyQuestionListResponse(
        items=[_to_response(item, current_user, partners) for item in items],
        total=base.count(),
    )


@router.get("/{qid}", response_model=DailyQuestionResponse)
def get_question(
    qid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyQuestionResponse:
    ensure_partner(current_user)
    return _to_response(_load_question(db, qid), current_user, _active_partners(db))


@router.post("/{qid}/answer", response_model=DailyQuestionResponse)
def answer_question(
    qid: str,
    payload: DailyQuestionAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyQuestionResponse:
    ensure_partner(current_user)
    question = _load_question(db, qid)
    partners_before = _active_partners(db)
    was_revealed = _is_revealed(question, partners_before)

    answer = (
        db.query(DailyQuestionAnswer)
        .filter(DailyQuestionAnswer.question_id == question.id, DailyQuestionAnswer.author_id == current_user.id)
        .first()
    )
    if answer is None:
        answer = DailyQuestionAnswer(
            question_id=question.id,
            author_id=current_user.id,
            content=payload.content,
        )
        db.add(answer)
    else:
        answer.content = payload.content
    question.version += 1
    db.commit()

    question = _load_question(db, qid)
    partners_after = _active_partners(db)
    is_revealed = _is_revealed(question, partners_after)
    if is_revealed and not was_revealed:
        notify_partners(
            db,
            type="daily_question.revealed",
            title="今天的答案已经揭晓",
            body=question.prompt[:160],
            link="/cottage/questions",
            source_type="daily_question",
            source_id=question.qid,
            dedupe=True,
        )
    elif not is_revealed:
        notify_partners(
            db,
            type="daily_question.answered",
            title=f"{current_user.nickname} 回答了今天的问题",
            body="等你也写完后就能一起看答案。",
            link="/cottage/questions",
            source_type="daily_question",
            source_id=question.qid,
            exclude_user_id=current_user.id,
        )
    db.commit()
    return _to_response(_load_question(db, qid), current_user, partners_after)
