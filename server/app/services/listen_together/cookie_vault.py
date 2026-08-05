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

"""Redis-backed vault for encrypted NetEase cookies.

One key per partner: ``cottage_listen:cookies:<user_uid>``. Value is the
Fernet ciphertext from :mod:`app.services.listen_together.crypto`.

Alongside each cookie we also persist the partner's *login IP* under
``cottage_listen:login_ip:<user_uid>`` — the real client IP captured when they
scan-logged in. It is forwarded to NetEase as the spoofed ``realIP`` on every
subsequent call made with that cookie, so the account always looks like it's
logging in from where the partner actually is (rather than the server room).
It's PII (coarse location), so it's encrypted at rest just like the cookie.

Privacy invariant: no plaintext cookie ever leaves this module except as
the function-local return value of :func:`get_cookie`. Callers must keep
the plaintext lifetime bounded to a single request.
"""
from __future__ import annotations

from redis import Redis

from app.services.listen_together.crypto import decrypt, encrypt


def cookie_key(user_uid: str) -> str:
    return f"cottage_listen:cookies:{user_uid}"


def login_ip_key(user_uid: str) -> str:
    return f"cottage_listen:login_ip:{user_uid}"


def set_cookie(redis_client: Redis, user_uid: str, cookie: str, ttl_seconds: int) -> None:
    """Store an encrypted cookie under the partner's key with TTL."""
    redis_client.setex(cookie_key(user_uid), ttl_seconds, encrypt(cookie))


def get_cookie(redis_client: Redis, user_uid: str) -> str | None:
    """Return the plaintext NetEase cookie for the user, or None if absent
    or undecryptable (key rotation / corruption).
    """
    raw = redis_client.get(cookie_key(user_uid))
    if not raw:
        return None
    plaintext = decrypt(raw)
    return plaintext  # may be None if decryption failed


def delete_cookie(redis_client: Redis, user_uid: str) -> None:
    # Drop the login IP in lock-step with the cookie so a stale IP can never
    # outlive the session it belonged to.
    redis_client.delete(cookie_key(user_uid), login_ip_key(user_uid))


def set_login_ip(redis_client: Redis, user_uid: str, ip: str, ttl_seconds: int) -> None:
    """Persist the partner's real login IP (encrypted) with the same TTL as
    their cookie. No-op for a falsy IP so we never store an empty marker."""
    if not ip:
        return
    redis_client.setex(login_ip_key(user_uid), ttl_seconds, encrypt(ip))


def get_login_ip(redis_client: Redis, user_uid: str) -> str | None:
    """Return the partner's stored login IP, or None if absent/undecryptable."""
    raw = redis_client.get(login_ip_key(user_uid))
    if not raw:
        return None
    return decrypt(raw)  # may be None if decryption failed


def has_cookie(redis_client: Redis, user_uid: str) -> bool:
    """Existence check with decryption validation.

    Returns True only if the cookie exists AND can be successfully decrypted.
    Invalid/corrupted cookies are automatically cleaned up.
    """
    if redis_client.exists(cookie_key(user_uid)) != 1:
        return False

    # Verify the cookie can be decrypted
    raw = redis_client.get(cookie_key(user_uid))
    if not raw:
        return False

    plaintext = decrypt(raw)
    if not plaintext:
        # Cookie exists but cannot be decrypted (key rotation, corruption)
        # Clean it up so the UI shows the correct state
        delete_cookie(redis_client, user_uid)
        return False

    return True
