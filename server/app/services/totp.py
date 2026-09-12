# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""RFC 6238 TOTP (Time-based One-Time Password) helpers.

Implemented with the Python standard library only (hmac/hashlib/base64/base32)
so no new runtime dependency is needed. Compatible with Google Authenticator,
Aegis, 1Password and any other standard TOTP app.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time

# Standard TOTP parameters (RFC 6238 defaults, SHA-1 / 6 digits / 30s).
TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
TOTP_ISSUER = "Love Journal"

# Accept codes from the previous/current/next step to tolerate clock drift.
TOTP_VALID_WINDOW = 1

RECOVERY_CODE_COUNT = 8


def generate_secret() -> str:
    """Return a fresh base32-encoded 160-bit secret."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = TOTP_DIGITS) -> str:
    pad = (8 - len(secret_b32) % 8) % 8
    key = base64.b32decode(secret_b32.upper() + "=" * pad, casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_at(secret_b32: str, timestamp_s: int) -> str:
    """Compute the expected code for the given unix timestamp."""
    return _hotp(secret_b32, counter=int(timestamp_s // TOTP_PERIOD_SECONDS))


def verify_totp(secret_b32: str, code: str, window: int = TOTP_VALID_WINDOW, timestamp_s: int | None = None) -> bool:
    """Constant-time check of a 6-digit code against the current ±window steps."""
    if not secret_b32 or not code or not code.isdigit() or len(code) != TOTP_DIGITS:
        return False
    now = int(timestamp_s if timestamp_s is not None else time.time())
    for drift in range(-window, window + 1):
        expected = _hotp(secret_b32, counter=(now + drift * TOTP_PERIOD_SECONDS) // TOTP_PERIOD_SECONDS)
        if hmac.compare_digest(expected, code):
            return True
    return False


def provisioning_uri(secret_b32: str, account: str, issuer: str = TOTP_ISSUER) -> str:
    """otpauth:// URI that TOTP apps scan as a QR code."""
    from urllib.parse import quote

    label = quote(f"{issuer}:{account}")
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret_b32}&issuer={quote(issuer)}"
        f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD_SECONDS}"
    )


# ── Recovery codes ──────────────────────────────────────────────────────────
# A recovery code is a one-time secret like "7f3a-9c2e". We store only a
# SHA-256 hash; verification removes the code from the user's list.

def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    return [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().lower().encode("utf-8")).hexdigest()
