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

"""Create-idempotency for offline client write queues.

When an offline outbox replays a creation request whose first attempt
actually reached the server (the 2xx was lost in transit), the server must
return the originally created resource instead of duplicating it. Routes
validate the ``Idempotency-Key`` header, look the key up in the
``idempotency_records`` table, and — on a miss — remember the created
resource afterwards.

Moment/CheckIn/Chat messages keep their own ``client_idempotency_key``
columns (pre-existing); this registry covers resources that have no such
column, starting with articles and comments.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.idempotency_record import IdempotencyRecord
from app.models.user import User

MAX_IDEMPOTENCY_KEY_LENGTH = 128


def normalize_idempotency_key(raw: object) -> str | None:
    """Validate a raw ``Idempotency-Key`` header value.

    Returns the stripped key, or ``None`` when the header is absent. Raises
    400 for blank/oversized keys — same contract as the chat routes so all
    idempotent endpoints behave identically.
    """
    if raw is None or not isinstance(raw, str):
        return None
    key = raw.strip()
    if not key:
        return None
    if len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Idempotency-Key",
        )
    return key


def find_created_resource_id(
    db: Session,
    user: User,
    resource_type: str,
    idempotency_key: str,
) -> str | None:
    """Return the resource id previously created under this key, if any."""
    record = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.user_id == user.id,
            IdempotencyRecord.idempotency_key == idempotency_key,
            IdempotencyRecord.resource_type == resource_type,
        )
        .first()
    )
    return record.resource_id if record else None


def remember_created_resource(
    db: Session,
    user: User,
    resource_type: str,
    idempotency_key: str,
    resource_id: str,
) -> None:
    """Record (or move) the key → resource mapping after a successful create.

    An upsert (rather than insert) also covers the rare replay-after-delete
    case: the original resource is gone, the record is re-pointed at the new
    one so subsequent replays still converge on a single row.
    """
    record = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.user_id == user.id,
            IdempotencyRecord.idempotency_key == idempotency_key,
            IdempotencyRecord.resource_type == resource_type,
        )
        .first()
    )
    if record is not None:
        record.resource_id = resource_id
    else:
        db.add(
            IdempotencyRecord(
                user_id=user.id,
                idempotency_key=idempotency_key,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        )
    # Committed by the caller together with the resource itself.
