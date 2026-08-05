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

from pydantic import ValidationError

# Secrets that are NEVER acceptable, in any environment (unset or the literal
# placeholder shipped in config defaults).
_ALWAYS_INSECURE_SECRETS = {"change-this-secret-before-production"}

# Secrets that are fine for local dev but must be rejected in production-like
# environments because they are committed to the repo (and therefore public).
# Anyone could sign a valid token with these → account takeover (R-sev-4).
_PUBLISHED_DEV_SECRETS = {"love-journal-local-dev-secret-not-for-production"}

# Minimum length for an HS256 signing secret in production. Shorter keys have
# too little entropy and are brute-forceable offline.
_MIN_PROD_SECRET_LENGTH = 32


def _is_production_like(app_env: str) -> bool:
    return app_env.strip().lower() not in {"development", "dev", "local", "test"}


def has_insecure_jwt_secret(jwt_secret_key: str, *, production_like: bool = False) -> bool:
    """Return True if ``jwt_secret_key`` must be rejected.

    Empty and the placeholder default are rejected everywhere. In a
    production-like environment we additionally reject the published dev secret
    and any secret shorter than :data:`_MIN_PROD_SECRET_LENGTH` (entropy floor),
    upgrading the old literal-match check to a length/known-bad check.
    """
    secret = jwt_secret_key.strip()
    if not secret or secret in _ALWAYS_INSECURE_SECRETS:
        return True
    if production_like:
        if secret in _PUBLISHED_DEV_SECRETS:
            return True
        if len(secret) < _MIN_PROD_SECRET_LENGTH:
            return True
    return False


def validate_startup_configuration(
    *,
    app_env: str,
    partner_count: int,
    bootstrap_setup_token: str,
    jwt_secret_key: str,
    cookie_vault_key: str = "",
) -> None:
    is_production_like = _is_production_like(app_env)

    if has_insecure_jwt_secret(jwt_secret_key, production_like=is_production_like):
        raise RuntimeError(
            "Startup self-check failed: JWT_SECRET_KEY is unset, using a known/default "
            "insecure value, or too short for production (need >= "
            f"{_MIN_PROD_SECRET_LENGTH} chars). Set a unique strong secret before "
            "starting the service."
        )

    if not is_production_like:
        return

    # --- production-like hardening ----------------------------------------
    # COOKIE_VAULT_KEY must be set AND distinct from the JWT secret. Otherwise
    # the NetEase cookie vault silently falls back to JWT_SECRET_KEY, so a
    # single leaked secret both forges auth tokens AND decrypts stored cookies
    # (R-sev-2: key separation).
    vault = cookie_vault_key.strip()
    if not vault:
        raise RuntimeError(
            "Startup self-check failed: COOKIE_VAULT_KEY must be set in production so the "
            "NetEase cookie vault does not fall back to JWT_SECRET_KEY. Set a unique value."
        )
    if vault == jwt_secret_key.strip():
        raise RuntimeError(
            "Startup self-check failed: COOKIE_VAULT_KEY must differ from JWT_SECRET_KEY "
            "to preserve key separation."
        )

    if partner_count == 0 and not bootstrap_setup_token.strip():
        raise RuntimeError(
            "Startup self-check failed: no partner account exists in non-development mode. "
            "Set BOOTSTRAP_SETUP_TOKEN and call /v1/auth/bootstrap first."
        )


def validate_schema_contracts() -> None:
    from app.models.user import UserRole
    from app.schemas.auth import PartnerRegisterRequest
    from app.schemas.event import EventPatchRequest
    from app.schemas.message import MessageCreateRequest

    # Ensure date field annotations still build and parse after Python upgrades.
    EventPatchRequest.model_validate({"date": "2026-01-01"})

    # Local registration must remain partner-only until SSO visitor onboarding is live.
    try:
        PartnerRegisterRequest.model_validate(
            {
                "username": "visitor_demo",
                "password": "abc12345",
                "nickname": "Visitor Demo",
                "role": UserRole.visitor.value,
            }
        )
    except ValidationError:
        pass
    else:
        raise RuntimeError("Startup self-check failed: visitor role must not be accepted by local register.")

    # Anonymous message payloads must stay disabled while SSO is pending.
    try:
        MessageCreateRequest.model_validate({"content": "hello", "visitor_name": "anonymous"})
    except ValidationError:
        pass
    else:
        raise RuntimeError("Startup self-check failed: message payload unexpectedly accepts visitor_name.")
