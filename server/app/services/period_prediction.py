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

"""Pure helpers for menstrual-cycle statistics and next-start prediction.

Kept free of FastAPI / Session imports so both the REST layer
(``cottage_period``) and the background notification scheduler can share the
exact same prediction logic.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.models.period_cycle import PeriodCycle


# Fallback when there isn't enough history to estimate a personal cycle length.
DEFAULT_CYCLE_DAYS = 28
# Typical bleeding duration fallback when no finished cycle is on record.
DEFAULT_PERIOD_DAYS = 5
# How many days before a predicted start we begin nudging the partner.
CARE_LEAD_DAYS = 2


def _phase(
    last: PeriodCycle,
    today: date,
    avg_period_days: int | None,
    predicted_days_until: int | None,
) -> str:
    period_len = avg_period_days or DEFAULT_PERIOD_DAYS
    end = last.end_date or (last.start_date + timedelta(days=period_len - 1))
    if last.start_date <= today <= end:
        return "in_period"
    if predicted_days_until is not None:
        if predicted_days_until < 0:
            return "overdue"
        if predicted_days_until <= CARE_LEAD_DAYS:
            return "due_soon"
    return "normal"


def compute_period_stats(cycles: list[PeriodCycle], today: date) -> dict:
    """Derive cycle statistics + a next-start prediction from raw cycle rows.

    ``cycles`` may be in any order. Filtering out soft-deleted rows is the
    caller's responsibility. Returns a dict matching ``PeriodSummaryResponse``.
    """
    ordered = sorted(cycles, key=lambda c: c.start_date)
    cycle_count = len(ordered)
    if cycle_count == 0:
        return {
            "cycle_count": 0,
            "avg_cycle_days": None,
            "avg_period_days": None,
            "last_start": None,
            "last_end": None,
            "predicted_next_start": None,
            "predicted_days_until": None,
            "phase": "unknown",
        }

    gaps = [
        (ordered[i].start_date - ordered[i - 1].start_date).days
        for i in range(1, cycle_count)
    ]
    gaps = [g for g in gaps if g > 0]
    avg_cycle_days = round(sum(gaps) / len(gaps)) if gaps else None

    durations = [
        (c.end_date - c.start_date).days + 1
        for c in ordered
        if c.end_date is not None
    ]
    avg_period_days = round(sum(durations) / len(durations)) if durations else None

    last = ordered[-1]
    effective_cycle = avg_cycle_days or DEFAULT_CYCLE_DAYS
    predicted_next_start = last.start_date + timedelta(days=effective_cycle)
    predicted_days_until = (predicted_next_start - today).days

    return {
        "cycle_count": cycle_count,
        "avg_cycle_days": avg_cycle_days,
        "avg_period_days": avg_period_days,
        "last_start": last.start_date,
        "last_end": last.end_date,
        "predicted_next_start": predicted_next_start,
        "predicted_days_until": predicted_days_until,
        "phase": _phase(last, today, avg_period_days, predicted_days_until),
    }
