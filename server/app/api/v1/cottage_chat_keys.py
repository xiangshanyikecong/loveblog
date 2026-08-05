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

"""Shared E2E chat KDF endpoints.

The server never sees the derived key, only the public KDF parameters
(salt, iterations) and a verifier blob the user keeps in their
browser / Android app.

- ``GET    /v1/cottage/chat/keys/meta`` — partner-only shared KDF + verifier
- ``POST   /v1/cottage/chat/keys/setup`` — one-time initialisation
- ``POST   /v1/cottage/chat/keys/verify`` — client-side unlock proof
- ``POST   /v1/cottage/chat/keys/rekey`` — rotate the passphrase

All endpoints are partner-only (we have at most two accounts).
"""
from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.chat_key import ChatKey
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.schemas.chat_key import (
    ChatKeyMetaResponse,
    ChatKeyRekeyRequest,
    ChatKeySetupRequest,
    ChatKeyVerifyRequest,
)
from app.services.audit import write_audit_log


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cottage/chat/keys", tags=["cottage-chat-keys"])


def _canonical_key(db: Session) -> ChatKey | None:
    return db.query(ChatKey).order_by(ChatKey.id.asc()).first()


def _to_response(key: ChatKey) -> ChatKeyMetaResponse:
    return ChatKeyMetaResponse(
        initialized=True,
        salt=key.salt,
        kdf=key.kdf,
        kdf_hash=key.kdf_hash,
        iterations=key.iterations,
        algo=key.algo,
        verifier_iv=key.verifier_iv,
        verifier_cipher=key.verifier_cipher,
        needs_re_encrypt=key.needs_re_encrypt,
    )


@router.get("/meta", response_model=ChatKeyMetaResponse)
def get_chat_key_meta(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatKeyMetaResponse:
    """Return the shared chat key state to either authenticated partner."""
    ensure_partner(current_user)
    key = _canonical_key(db)
    if key is None:
        return ChatKeyMetaResponse(initialized=False)
    return _to_response(key)


@router.post("/setup", response_model=ChatKeyMetaResponse, status_code=status.HTTP_201_CREATED)
def setup_chat_key(
    payload: ChatKeySetupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatKeyMetaResponse:
    ensure_partner(current_user)
    existing = _canonical_key(db)
    if existing is not None:
        # Deliberate refuse: rotating the key mid-stream would orphan
        # every in-flight ciphertext the partner is holding. The
        # rekey endpoint handles that flow explicitly.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已存在加密聊天口令，请使用 rekey 切换",
        )

    # Sanity check the verifier hash matches the cipher (catches a
    # client-side bug where the user posts mismatched blobs).
    expected_hash = hashlib.sha256(payload.verifier_cipher.encode("utf-8")).hexdigest()
    if expected_hash != payload.verifier_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="verifier_hash 与 verifier_cipher 不匹配",
        )

    key = ChatKey(
        user_id=current_user.id,
        salt=payload.salt,
        kdf=payload.kdf,
        kdf_hash=payload.kdf_hash,
        iterations=payload.iterations,
        algo=payload.algo,
        verifier_iv=payload.verifier_iv,
        verifier_cipher=payload.verifier_cipher,
        verifier_hash=payload.verifier_hash,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    write_audit_log(
        db,
        action="privacy.key_setup",
        actor=current_user,
        resource_type="encryption_key",
        resource_id="chat",
        detail={"algorithm": key.algo, "kdf_hash": key.kdf_hash, "iterations": key.iterations},
    )
    return _to_response(key)


@router.post("/verify", status_code=status.HTTP_204_NO_CONTENT)
def verify_unlock(
    payload: ChatKeyVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Compatibility no-op after the client has verified the passphrase.

    The server cannot validate this proof without the derived key, so it must
    not mutate key metadata or claim that an unlock was independently verified.
    """
    ensure_partner(current_user)
    key = _canonical_key(db)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="尚未启用加密聊天"
        )
    _ = payload


@router.post("/rekey", response_model=ChatKeyMetaResponse)
def rekey_chat_key(
    payload: ChatKeyRekeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatKeyMetaResponse:
    """Rotate the shared passphrase only before encrypted messages exist."""
    ensure_partner(current_user)
    key = _canonical_key(db)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="尚未启用加密聊天"
        )
    encrypted_count = (
        db.query(ChatMessage)
        .filter(ChatMessage.deleted_at.is_(None), ChatMessage.is_encrypted.is_(True))
        .count()
    )
    if encrypted_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已有加密消息，必须先在客户端重新加密全部消息后才能更换口令",
        )
    expected = hashlib.sha256(payload.new_verifier_cipher.encode("utf-8")).hexdigest()
    if expected != payload.new_verifier_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="verifier_hash 与 verifier_cipher 不匹配",
        )
    key.salt = payload.new_salt
    key.verifier_iv = payload.new_verifier_iv
    key.verifier_cipher = payload.new_verifier_cipher
    key.verifier_hash = payload.new_verifier_hash
    db.commit()
    db.refresh(key)
    write_audit_log(
        db,
        action="privacy.key_rotated",
        actor=current_user,
        resource_type="encryption_key",
        resource_id="chat",
        detail={"algorithm": key.algo, "kdf_hash": key.kdf_hash, "iterations": key.iterations},
    )
    return _to_response(key)
