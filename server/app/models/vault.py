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

"""Models for the cottage 加密保险箱 (true end-to-end encrypted vault).

Unlike the legacy ``is_encrypted`` visibility flag — where the server can still
read the plaintext — the vault is genuinely E2EE: the server only ever stores
opaque ciphertext. All encryption / decryption happens in the browser with a
key derived from a passphrase that is **never** sent to the server.

``VaultMeta`` (single row) records the KDF parameters + a verifier blob so the
client can confirm a passphrase is correct without decrypting real entries.
``VaultEntry`` rows are individual encrypted notes. Because the contents are
opaque, vault data is intentionally excluded from full-text search and the
plaintext is never available to server-side features (AI reports, etc.).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VaultMeta(Base):
    """Singleton (id=1) holding the couple's vault KDF params + verifier.

    The verifier is a small ciphertext of a known constant: on unlock the
    client decrypts it with the derived key and checks the result, proving the
    passphrase is correct without touching any real entry.
    """

    __tablename__ = "vault_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # base64 KDF salt + parameters (so any client can re-derive the same key).
    salt: Mapped[str] = mapped_column(String(128), nullable=False)
    kdf: Mapped[str] = mapped_column(String(32), default="PBKDF2", nullable=False)
    kdf_hash: Mapped[str] = mapped_column(String(32), default="SHA-256", nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, default=210_000, nullable=False)
    algo: Mapped[str] = mapped_column(String(32), default="AES-GCM", nullable=False)
    # Passphrase verifier (iv + ciphertext of a known token).
    verifier_iv: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier_cipher: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class VaultEntry(Base):
    """One end-to-end-encrypted note. The server stores only ciphertext."""

    __tablename__ = "vault_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vid: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # AES-GCM iv (base64) + ciphertext (base64). Plaintext shape is decided by
    # the client (currently a JSON {title, body}).
    iv: Mapped[str] = mapped_column(String(64), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author = relationship("User", foreign_keys=[author_id])
