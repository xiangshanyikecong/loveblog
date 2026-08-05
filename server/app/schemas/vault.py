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

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VaultMetaResponse(BaseModel):
    """Public KDF params + verifier. Safe to expose: it contains no plaintext
    and no key — only the parameters a client needs to derive the key itself."""

    model_config = ConfigDict(from_attributes=True)

    initialized: bool
    salt: str | None = None
    kdf: str | None = None
    kdf_hash: str | None = None
    iterations: int | None = None
    algo: str | None = None
    verifier_iv: str | None = None
    verifier_cipher: str | None = None


class VaultSetupRequest(BaseModel):
    salt: str = Field(min_length=8, max_length=128)
    kdf: str = Field(default="PBKDF2", max_length=32)
    kdf_hash: str = Field(default="SHA-256", max_length=32)
    iterations: int = Field(ge=10_000, le=5_000_000)
    algo: str = Field(default="AES-GCM", max_length=32)
    verifier_iv: str = Field(min_length=8, max_length=64)
    verifier_cipher: str = Field(min_length=8, max_length=512)


class VaultEntryCreateRequest(BaseModel):
    iv: str = Field(min_length=8, max_length=64)
    ciphertext: str = Field(min_length=1, max_length=2_000_000)


class VaultEntryUpdateRequest(BaseModel):
    iv: str = Field(min_length=8, max_length=64)
    ciphertext: str = Field(min_length=1, max_length=2_000_000)


class VaultEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vid: str
    iv: str
    ciphertext: str
    author_uid: str
    created_at: datetime
    updated_at: datetime


class VaultRekeyEntry(BaseModel):
    """One entry's new ciphertext under the new key (re-encrypted in browser)."""

    vid: str = Field(min_length=1, max_length=36)
    iv: str = Field(min_length=8, max_length=64)
    ciphertext: str = Field(min_length=1, max_length=2_000_000)


class VaultRekeyRequest(BaseModel):
    """Change passphrase: new KDF meta + every entry re-encrypted under it."""

    salt: str = Field(min_length=8, max_length=128)
    kdf: str = Field(default="PBKDF2", max_length=32)
    kdf_hash: str = Field(default="SHA-256", max_length=32)
    iterations: int = Field(ge=10_000, le=5_000_000)
    algo: str = Field(default="AES-GCM", max_length=32)
    verifier_iv: str = Field(min_length=8, max_length=64)
    verifier_cipher: str = Field(min_length=8, max_length=512)
    entries: list[VaultRekeyEntry] = Field(default_factory=list)
