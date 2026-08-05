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

"""Fernet derivation for cottage-listen NetEase cookie encryption.

The Fernet key is derived once at module import via HKDF-SHA256 from a
dedicated ``COOKIE_VAULT_KEY`` (falling back to ``JWT_SECRET_KEY`` only when
unset, for backward compatibility) plus a fixed salt. Consequences:

- Using a SEPARATE ``COOKIE_VAULT_KEY`` enforces key separation: leaking the
  JWT signing secret no longer lets an attacker decrypt stored NetEase
  cookies / login IPs, and vice-versa.
- Rotating the source secret invalidates every existing ciphertext —
  partners must re-scan to log into NetEase. This is documented as expected
  behavior in the spec (R2.8).
- The Fernet key itself is NEVER persisted (no DB, no disk, no log) and
  NEVER exposed via response or WebSocket message (privacy invariant R3).

Used exclusively by ``cookie_vault`` to encrypt cookies before storing them
under ``cottage_listen:cookies:<user_uid>`` in Redis, and to decrypt them
on the small number of code paths permitted to call NetEase upstream.
"""
from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

# Code-constant salt. Together with the runtime ``JWT_SECRET_KEY`` it forms
# the input material to HKDF. Changing this value would invalidate stored
# ciphertexts in the same way as rotating the secret — don't change unless
# you intend to invalidate every partner's NetEase login.
_FERNET_HKDF_SALT = b"cottage-listen-together/v1"


def _vault_secret() -> str:
    """Return the source secret for cookie encryption.

    Prefers the dedicated ``COOKIE_VAULT_KEY`` (key separation); falls back to
    ``JWT_SECRET_KEY`` when it is unset so local dev keeps working. The fallback
    is intentionally NOT allowed in production: the startup self-check
    (``validate_startup_configuration``) refuses to boot a production-like
    environment unless ``COOKIE_VAULT_KEY`` is set and distinct from the JWT
    secret, so this branch only ever uses the fallback in dev/test.
    """
    dedicated = (settings.cookie_vault_key or "").strip()
    return dedicated if dedicated else settings.jwt_secret_key


def _derive_fernet() -> Fernet:
    """Derive the process-wide Fernet instance from the vault secret + salt."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_FERNET_HKDF_SALT,
        info=b"cottage_listen.cookie_vault",
    )
    raw = hkdf.derive(_vault_secret().encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(raw))


# Module-level singleton — derived once on first import. Held in process
# memory; never written elsewhere.
_fernet = _derive_fernet()


def encrypt(plaintext: str) -> str:
    """Encrypt a NetEase cookie string for Redis storage."""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str | None:
    """Decrypt a stored ciphertext.

    Returns ``None`` if the token is invalid (key rotation, ciphertext
    corruption). Callers treat this as "cookie is gone" — equivalent to
    ``has_cookie == False`` — and trigger the re-login flow.
    """
    try:
        return _fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
