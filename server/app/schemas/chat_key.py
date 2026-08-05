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

"""Schemas for the cottage 端到端加密聊天 (E2E chat) KDF endpoints.

The server is a blind store: it only ever sees the user's public KDF
parameters (salt, iterations, algo) and a verifier blob. The derived
key never leaves the browser / Android app, and the server cannot
decrypt messages.
"""
from pydantic import BaseModel, Field, field_validator


class ChatKeySetupRequest(BaseModel):
    """One-time setup of the couple's shared E2E chat key.

    Carries the public KDF parameters and a small "verifier"
    ciphertext so the user can confirm a passphrase is correct on
    subsequent unlocks.
    """

    salt: str = Field(min_length=8, max_length=128)
    kdf: str = Field(default="PBKDF2", max_length=32)
    kdf_hash: str = Field(default="SHA-256", max_length=32)
    iterations: int = Field(ge=10_000, le=5_000_000)
    algo: str = Field(default="AES-GCM", max_length=32)
    verifier_iv: str = Field(min_length=8, max_length=64)
    verifier_cipher: str = Field(min_length=8, max_length=512)
    verifier_hash: str = Field(min_length=8, max_length=128)

    @field_validator("salt", "verifier_iv", "verifier_cipher", "verifier_hash")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class ChatKeyMetaResponse(BaseModel):
    """Partner-only view of the couple's shared chat key setup."""

    initialized: bool
    salt: str | None = None
    kdf: str | None = None
    kdf_hash: str | None = None
    iterations: int | None = None
    algo: str | None = None
    # Partner-only verifier used locally to reject an incorrect passphrase.
    verifier_iv: str | None = None
    verifier_cipher: str | None = None
    needs_re_encrypt: bool = False


class ChatKeyVerifyRequest(BaseModel):
    """Compatibility payload sent after a client-side verified unlock.

    The server deliberately does not treat this ciphertext as independent
    proof because it does not possess the derived key.
    """

    proof_iv: str = Field(min_length=8, max_length=64)
    proof_cipher: str = Field(min_length=8, max_length=512)


class ChatKeyRekeyRequest(ChatKeySetupRequest):
    """Rotate the passphrase only while no encrypted messages exist."""

    new_salt: str = Field(min_length=8, max_length=128)
    new_verifier_iv: str = Field(min_length=8, max_length=64)
    new_verifier_cipher: str = Field(min_length=8, max_length=512)
    new_verifier_hash: str = Field(min_length=8, max_length=128)
