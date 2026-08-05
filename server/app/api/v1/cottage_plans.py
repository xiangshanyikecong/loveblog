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

"""Shared plans for the cottage."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.cottage_plan import CottagePlan, CottagePlanStatus
from app.models.user import User
from app.schemas.cottage_plan import (
    CottagePlanCreateRequest,
    CottagePlanListResponse,
    CottagePlanResponse,
    CottagePlanUpdateRequest,
    PlanChecklistItem,
)
from app.services.notifications import notify_partners


router = APIRouter(prefix="/cottage/plans", tags=["cottage-plans"])


def _normalize_checklist(items: list[PlanChecklistItem]) -> list[dict]:
    normalized: list[dict] = []
    for item in items:
        normalized.append(
            {
                "key": item.key or str(uuid.uuid4()),
                "text": item.text.strip(),
                "done": bool(item.done),
            }
        )
    return normalized


def _to_response(plan: CottagePlan) -> CottagePlanResponse:
    checklist = [PlanChecklistItem.model_validate(item) for item in list(plan.checklist or [])]
    return CottagePlanResponse(
        pid=plan.pid,
        title=plan.title,
        description=plan.description,
        location=plan.location,
        plan_date=plan.plan_date,
        status=plan.status,
        priority=plan.priority,
        checklist=checklist,
        author_uid=plan.author.uid if plan.author else "",
        author_nickname=plan.author.nickname if plan.author else "",
        completed_at=plan.completed_at,
        completed_by_uid=plan.completed_by.uid if plan.completed_by else None,
        completed_by_nickname=plan.completed_by.nickname if plan.completed_by else None,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _load_plan(db: Session, pid: str) -> CottagePlan:
    plan = (
        db.query(CottagePlan)
        .options(joinedload(CottagePlan.author), joinedload(CottagePlan.completed_by))
        .filter(CottagePlan.pid == pid, CottagePlan.deleted_at.is_(None))
        .first()
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


def _set_status(plan: CottagePlan, value: str, current_user: User) -> None:
    plan.status = value
    if value == CottagePlanStatus.done.value:
        plan.completed_at = datetime.now(timezone.utc)
        plan.completed_by_id = current_user.id
    elif value != CottagePlanStatus.done.value:
        plan.completed_at = None
        plan.completed_by_id = None


@router.post("", response_model=CottagePlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: CottagePlanCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottagePlanResponse:
    ensure_partner(current_user)
    plan = CottagePlan(
        author_id=current_user.id,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        plan_date=payload.plan_date,
        priority=payload.priority,
        checklist=_normalize_checklist(payload.checklist),
        status=CottagePlanStatus.planned.value,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    notify_partners(
        db,
        type="cottage_plan.created",
        title=f"{current_user.nickname} added a new cottage plan",
        body=plan.title[:160],
        link="/cottage/plans",
        source_type="cottage_plan",
        source_id=plan.pid,
        exclude_user_id=current_user.id,
    )
    db.commit()
    return _to_response(_load_plan(db, plan.pid))


@router.get("", response_model=CottagePlanListResponse)
def list_plans(
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottagePlanListResponse:
    ensure_partner(current_user)
    base = db.query(CottagePlan).filter(CottagePlan.deleted_at.is_(None))
    total = base.count()
    completed = base.filter(CottagePlan.status == CottagePlanStatus.done.value).count()
    cancelled = base.filter(CottagePlan.status == CottagePlanStatus.cancelled.value).count()
    active = total - completed - cancelled

    query = (
        db.query(CottagePlan)
        .options(joinedload(CottagePlan.author), joinedload(CottagePlan.completed_by))
        .filter(CottagePlan.deleted_at.is_(None))
    )
    valid_statuses = {item.value for item in CottagePlanStatus}
    if status_filter in valid_statuses:
        query = query.filter(CottagePlan.status == status_filter)

    inactive_last = case(
        (CottagePlan.status == CottagePlanStatus.done.value, 2),
        (CottagePlan.status == CottagePlanStatus.cancelled.value, 3),
        else_=0,
    )
    items = (
        query.order_by(
            inactive_last.asc(),
            CottagePlan.plan_date.is_(None).asc(),
            CottagePlan.plan_date.asc(),
            CottagePlan.priority.desc(),
            CottagePlan.created_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return CottagePlanListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        active=active,
        completed=completed,
        cancelled=cancelled,
    )


@router.get("/{pid}", response_model=CottagePlanResponse)
def get_plan(
    pid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottagePlanResponse:
    ensure_partner(current_user)
    return _to_response(_load_plan(db, pid))


@router.patch("/{pid}", response_model=CottagePlanResponse)
def update_plan(
    pid: str,
    payload: CottagePlanUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottagePlanResponse:
    ensure_partner(current_user)
    plan = _load_plan(db, pid)

    data = payload.model_dump(exclude_unset=True)
    for field in ("title", "description", "location", "plan_date", "priority"):
        if field in data:
            setattr(plan, field, data[field])
    if payload.checklist is not None:
        plan.checklist = _normalize_checklist(payload.checklist)
    if payload.status is not None:
        _set_status(plan, payload.status, current_user)
    plan.version += 1
    db.commit()
    return _to_response(_load_plan(db, pid))


@router.post("/{pid}/complete", response_model=CottagePlanResponse)
def complete_plan(
    pid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottagePlanResponse:
    ensure_partner(current_user)
    plan = _load_plan(db, pid)
    if plan.status != CottagePlanStatus.done.value:
        _set_status(plan, CottagePlanStatus.done.value, current_user)
        plan.version += 1
        db.commit()
        notify_partners(
            db,
            type="cottage_plan.completed",
            title="A cottage plan was completed",
            body=plan.title[:160],
            link="/cottage/plans",
            source_type="cottage_plan",
            source_id=plan.pid,
            exclude_user_id=current_user.id,
        )
        db.commit()
    return _to_response(_load_plan(db, pid))


@router.post("/{pid}/reopen", response_model=CottagePlanResponse)
def reopen_plan(
    pid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CottagePlanResponse:
    ensure_partner(current_user)
    plan = _load_plan(db, pid)
    if plan.status != CottagePlanStatus.planned.value:
        _set_status(plan, CottagePlanStatus.planned.value, current_user)
        plan.version += 1
        db.commit()
    return _to_response(_load_plan(db, pid))


@router.delete("/{pid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_plan(
    pid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)
    plan = _load_plan(db, pid)
    plan.deleted_at = datetime.now(timezone.utc)
    db.commit()
