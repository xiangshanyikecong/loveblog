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

"""REST endpoints for the cottage 加密保险箱 (end-to-end encrypted vault).

The server is a *blind store*: it never sees the passphrase, the derived key,
or any plaintext. Every payload here is opaque ciphertext produced in the
browser. Consequently vault data is excluded from search / export-markdown /
any server-side content feature — there is nothing readable to index.

- ``GET    /v1/cottage/vault/meta``      — KDF params + verifier (or not-initialized)
- ``POST   /v1/cottage/vault/setup``     — first-time vault creation
- ``GET    /v1/cottage/vault/entries``   — list ciphertext entries
- ``POST   /v1/cottage/vault/entries``   — create a ciphertext entry
- ``PUT    /v1/cottage/vault/entries/{vid}`` — replace a ciphertext entry
- ``DELETE /v1/cottage/vault/entries/{vid}`` — soft-delete an entry

All endpoints are partner-only (shared between PartnerA and PartnerB).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import ensure_partner, get_current_user
from app.core.i18n import get_message
from app.db.session import get_db
from app.models.user import User
from app.models.vault import VaultEntry, VaultMeta
from app.schemas.vault import (
    VaultEntryCreateRequest,
    VaultEntryResponse,
    VaultEntryUpdateRequest,
    VaultMetaResponse,
    VaultRekeyRequest,
    VaultSetupRequest,
)
from app.services.audit import write_audit_log

router = APIRouter(prefix="/cottage/vault", tags=["cottage-vault"])


def _entry_to_response(entry: VaultEntry) -> VaultEntryResponse:
    return VaultEntryResponse(
        vid=entry.vid,
        iv=entry.iv,
        ciphertext=entry.ciphertext,
        author_uid=entry.author.uid if entry.author else "",
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.get("/meta", response_model=VaultMetaResponse)
def get_vault_meta(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VaultMetaResponse:
    ensure_partner(current_user)
    meta = db.query(VaultMeta).filter(VaultMeta.id == 1).first()
    if meta is None:
        return VaultMetaResponse(initialized=False)
    return VaultMetaResponse(
        initialized=True,
        salt=meta.salt,
        kdf=meta.kdf,
        kdf_hash=meta.kdf_hash,
        iterations=meta.iterations,
        algo=meta.algo,
        verifier_iv=meta.verifier_iv,
        verifier_cipher=meta.verifier_cipher,
    )


@router.post("/setup", response_model=VaultMetaResponse, status_code=status.HTTP_201_CREATED)
def setup_vault(
    payload: VaultSetupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VaultMetaResponse:
    ensure_partner(current_user)
    existing = db.query(VaultMeta).filter(VaultMeta.id == 1).first()
    if existing is not None:
        # Re-initialising would orphan every existing entry (different key), so
        # refuse — a deliberate reset must delete entries first (not exposed).
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=get_message("error.vault_already_initialized"))

    meta = VaultMeta(
        id=1,
        salt=payload.salt,
        kdf=payload.kdf,
        kdf_hash=payload.kdf_hash,
        iterations=payload.iterations,
        algo=payload.algo,
        verifier_iv=payload.verifier_iv,
        verifier_cipher=payload.verifier_cipher,
    )
    db.add(meta)
    db.commit()
    db.refresh(meta)
    write_audit_log(
        db,
        action="privacy.key_setup",
        actor=current_user,
        resource_type="encryption_key",
        resource_id="vault",
        detail={"algorithm": meta.algo, "kdf_hash": meta.kdf_hash, "iterations": meta.iterations},
    )
    return VaultMetaResponse(
        initialized=True,
        salt=meta.salt,
        kdf=meta.kdf,
        kdf_hash=meta.kdf_hash,
        iterations=meta.iterations,
        algo=meta.algo,
        verifier_iv=meta.verifier_iv,
        verifier_cipher=meta.verifier_cipher,
    )


@router.get("/entries", response_model=list[VaultEntryResponse])
def list_vault_entries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[VaultEntryResponse]:
    ensure_partner(current_user)
    entries = (
        db.query(VaultEntry)
        .options(joinedload(VaultEntry.author))
        .filter(VaultEntry.deleted_at.is_(None))
        .order_by(VaultEntry.updated_at.desc())
        .all()
    )
    return [_entry_to_response(e) for e in entries]


@router.post("/entries", response_model=VaultEntryResponse, status_code=status.HTTP_201_CREATED)
def create_vault_entry(
    payload: VaultEntryCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VaultEntryResponse:
    ensure_partner(current_user)
    if db.query(VaultMeta).filter(VaultMeta.id == 1).first() is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.vault_not_initialized"))
    entry = VaultEntry(
        author_id=current_user.id,
        iv=payload.iv,
        ciphertext=payload.ciphertext,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    entry = (
        db.query(VaultEntry)
        .options(joinedload(VaultEntry.author))
        .filter(VaultEntry.id == entry.id)
        .first()
    )
    return _entry_to_response(entry)


@router.put("/entries/{vid}", response_model=VaultEntryResponse)
def update_vault_entry(
    vid: str,
    payload: VaultEntryUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VaultEntryResponse:
    ensure_partner(current_user)
    entry = (
        db.query(VaultEntry)
        .options(joinedload(VaultEntry.author))
        .filter(VaultEntry.vid == vid, VaultEntry.deleted_at.is_(None))
        .first()
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=get_message("error.vault_entry_not_found"))
    entry.iv = payload.iv
    entry.ciphertext = payload.ciphertext
    db.commit()
    db.refresh(entry)
    return _entry_to_response(entry)


@router.delete("/entries/{vid}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_vault_entry(
    vid: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ensure_partner(current_user)
    entry = db.query(VaultEntry).filter(VaultEntry.vid == vid, VaultEntry.deleted_at.is_(None)).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=get_message("error.vault_entry_not_found"))
    entry.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def reset_vault(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Forgotten-passphrase escape hatch: wipe the entire vault.

    Because the vault is genuinely end-to-end encrypted, a lost passphrase makes
    every stored entry permanently undecryptable — there is no server-side key to
    recover it. This endpoint hard-deletes the meta row *and* all entries so the
    couple can re-initialise with a new passphrase. It is intentionally
    destructive and irreversible; the UI must confirm before calling it.
    """
    ensure_partner(current_user)
    entry_count = db.query(VaultEntry).count()
    # Hard delete: the ciphertext is useless once the meta (salt/verifier) is
    # gone, so leaving soft-deleted rows around would only retain dead bytes.
    db.query(VaultEntry).delete(synchronize_session=False)
    db.query(VaultMeta).delete(synchronize_session=False)
    db.commit()
    write_audit_log(
        db,
        action="privacy.vault_reset",
        actor=current_user,
        resource_type="encryption_key",
        resource_id="vault",
        detail={"deleted_entry_count": entry_count},
    )


@router.post("/rekey", response_model=VaultMetaResponse)
def rekey_vault(
    payload: VaultRekeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VaultMetaResponse:
    """Change the vault passphrase without losing data.

    The client decrypts every entry with the *old* key, re-encrypts each one with
    a *new* key (derived from the new passphrase + a fresh salt), and posts the
    new KDF meta + all re-encrypted ciphertexts here. The meta swap and every
    ciphertext update happen in a single transaction, so a failure leaves the old
    vault fully intact. We refuse a partial re-key (any entry missing from the
    payload would become permanently undecryptable once the meta changes).
    """
    ensure_partner(current_user)
    meta = db.query(VaultMeta).filter(VaultMeta.id == 1).first()
    if meta is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_message("error.vault_not_initialized"))

    existing = {
        e.vid: e
        for e in db.query(VaultEntry).filter(VaultEntry.deleted_at.is_(None)).all()
    }
    provided = {e.vid for e in payload.entries}
    if set(existing) - provided:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_message("error.rekey_requires_all_entries"),
        )

    meta.salt = payload.salt
    meta.kdf = payload.kdf
    meta.kdf_hash = payload.kdf_hash
    meta.iterations = payload.iterations
    meta.algo = payload.algo
    meta.verifier_iv = payload.verifier_iv
    meta.verifier_cipher = payload.verifier_cipher

    for item in payload.entries:
        entry = existing.get(item.vid)
        if entry is not None:  # ignore unknown vids; never create on re-key
            entry.iv = item.iv
            entry.ciphertext = item.ciphertext

    db.commit()
    db.refresh(meta)
    write_audit_log(
        db,
        action="privacy.key_rotated",
        actor=current_user,
        resource_type="encryption_key",
        resource_id="vault",
        detail={
            "algorithm": meta.algo,
            "kdf_hash": meta.kdf_hash,
            "iterations": meta.iterations,
            "entry_count": len(existing),
        },
    )
    return VaultMetaResponse(
        initialized=True,
        salt=meta.salt,
        kdf=meta.kdf,
        kdf_hash=meta.kdf_hash,
        iterations=meta.iterations,
        algo=meta.algo,
        verifier_iv=meta.verifier_iv,
        verifier_cipher=meta.verifier_cipher,
    )
