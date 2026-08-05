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

"""Shared KDF params for the cottage 端到端加密聊天 (E2E encrypted chat).

The chat is end-to-end encrypted: only the two partners' devices can
decrypt messages. The server is a blind store for ciphertext + the
public KDF parameters (salt, iterations) + a small "verifier"
ciphertext the client uses to confirm it derived the right key.

Trust model: a verifier blob is a tiny AES-GCM ciphertext of a known constant
under the derived key. Both authenticated partners receive it and validate
candidate passphrases locally. The server never receives the passphrase or
derived key, but a database holder can test guesses offline against the
verifier; PBKDF2 cost and a strong shared passphrase remain essential.

The active contract uses one canonical row shared by both partners. ``user_id``
records who created it and remains unique for backward compatibility; callers
must always select the oldest row as the canonical shared key.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChatKey(Base):
    """The couple's E2E chat KDF parameters + verifier hash.

    Both authenticated partners receive the verifier because they must derive
    and validate the same shared key. The server still never sees the
    passphrase or derived AES key.
    """

    __tablename__ = "chat_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    # Public KDF params (mirrors the vault meta so we can reuse vaultCrypto.js).
    salt: Mapped[str] = mapped_column(String(128), nullable=False)
    kdf: Mapped[str] = mapped_column(String(32), default="PBKDF2", nullable=False)
    kdf_hash: Mapped[str] = mapped_column(String(32), default="SHA-256", nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, default=210_000, nullable=False)
    algo: Mapped[str] = mapped_column(String(32), default="AES-GCM", nullable=False)
    # Verifier blob (only ever returned to the owning user).
    verifier_iv: Mapped[str] = mapped_column(String(64), nullable=False)
    verifier_cipher: Mapped[str] = mapped_column(String(512), nullable=False)
    # Hash of the verifier blob (server-side dedup / sanity check).
    verifier_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    # When true, the server still has the legacy rows (decryptable by
    # the old key) and the user is being asked to re-encrypt next time
    # they open chat. Currently always False on first setup; we keep
    # the column so a future migration has a place to land.
    needs_re_encrypt: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", foreign_keys=[user_id])
