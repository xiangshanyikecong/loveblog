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

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Love Node API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = ""
    postgres_user: str = "love"
    postgres_password: str = ""
    postgres_db: str = "love_node"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    jwt_secret_key: str = "change-this-secret-before-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24
    bootstrap_setup_token: str = ""

    # Dedicated secret for encrypting at-rest NetEase cookies / login IPs in
    # Redis (cottage listen-together). Keeping it SEPARATE from
    # ``jwt_secret_key`` enforces key separation: a leak of one secret no
    # longer both forges auth tokens AND decrypts stored third-party
    # credentials. Empty (default) falls back to ``jwt_secret_key`` for
    # backward compatibility — set a unique value in production. Rotating it
    # invalidates stored cookies (partners must re-scan), same as the spec's
    # JWT-rotation behavior (R2.8).
    cookie_vault_key: str = ""

    # Per-IP rate limit applied to every endpoint by the global limiter
    # middleware. Generous by default so it never bothers a real user/SPA but
    # still caps runaway abuse; sensitive routes (e.g. login) add their own
    # stricter explicit limits on top.
    rate_limit_default: str = "600/minute"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Secure flag for the auth cookie. None (default) = auto-detect from the
    # request's forwarded scheme, so a deployment served over plain HTTP works
    # (browsers silently drop Secure cookies on HTTP) and auto-upgrades to
    # Secure once HTTPS is enabled. Set COOKIE_SECURE=true/false to force it.
    cookie_secure: bool | None = None

    # Geocoding provider for cottage check-in (reverse-geocode lat/lng + IP).
    # Allowed values: amap | baidu | tencent | nominatim. nominatim is the
    # zero-config default and does NOT require an API key, but Chinese
    # mainland place names may be inaccurate. amap/baidu/tencent require
    # geocoding_api_key to be set; missing key logs a warning and the
    # provider degrades to lookup_failed at request time.
    geocoding_provider: str = "nominatim"
    geocoding_api_key: str = ""

    # NeteaseCloudMusicApi (cottage listen-together) — internal docker service.
    # `netease_api_base_url` points to the in-network NeteaseCloudMusicApi
    # container; the host is intentionally unreachable from outside the docker
    # network. `cottage_listen_cookie_ttl_days` caps how long a partner's
    # encrypted NetEase cookie lives in Redis after scan-login.
    netease_api_base_url: str = "http://netease:3000"
    cottage_listen_cookie_ttl_days: int = 30

    # Spoofed client IP forwarded to NetEase (as X-Real-IP / X-Forwarded-For)
    # on every upstream call. NetEase's risk-control judges "foreign/abnormal
    # login" mainly by source IP; a server-room / out-of-town egress IP gets
    # logins blocked or cookies down-ranked. Pinning ONE stable mainland-China
    # IP makes the couple's account look like a single fixed environment, which
    # is far less suspicious than the server's real IP — and than a per-request
    # random IP (an account "jumping around" is itself a risk signal). Leave
    # empty to auto-pick one stable IP at process start (kept fixed for the
    # process lifetime). Set to a specific IP to make it deterministic across
    # restarts (ideally one near where the couple normally logs in).
    netease_real_ip: str = ""

    # Background notification scheduler (event / cottage reminder / capsule unlock).
    notification_scheduler_interval_seconds: int = 60
    notification_scheduler_days_ahead: int = 7

    # Optional external push for scheduler-generated notifications.
    notification_push_email_enabled: bool = False
    notification_smtp_host: str = ""
    notification_smtp_port: int = 587
    notification_smtp_user: str = ""
    notification_smtp_password: str = ""
    notification_smtp_from: str = ""
    notification_smtp_use_tls: bool = True
    notification_push_email_partner_a: str = ""
    notification_push_email_partner_b: str = ""
    web_push_enabled: bool = False
    web_push_vapid_public_key: str = ""
    web_push_vapid_private_key: str = ""
    web_push_subject: str = "mailto:noreply@love-node"
    fcm_push_enabled: bool = False
    fcm_service_account_file: str = ""
    fcm_service_account_json: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("cookie_secure", mode="before")
    @classmethod
    def _coerce_cookie_secure(cls, value):
        """Treat an empty env value as "auto-detect" (None).

        docker-compose interpolates an unset ``${COOKIE_SECURE:-}`` to the empty
        string, which would otherwise fail boolean parsing and crash startup.
        """
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "":
                return None
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production_like(self) -> bool:
        return self.app_env.strip().lower() not in {"development", "dev", "local", "test"}

    @property
    def resolved_database_url(self) -> str:
        """Build a safely escaped PostgreSQL URL from discrete env fields.

        An explicitly configured DATABASE_URL remains authoritative. Compose
        deployments can instead provide POSTGRES_* values, allowing passwords
        containing URL delimiters such as ``@``, ``:`` and ``/``.
        """
        if self.database_url.strip() or not self.postgres_password:
            return self.database_url

        from sqlalchemy.engine import URL

        return URL.create(
            "postgresql+psycopg2",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def resolved_redis_url(self) -> str:
        """Build an escaped Redis URL while preserving explicit overrides."""
        if ("redis_url" in self.model_fields_set and self.redis_url.strip()) or not self.redis_password:
            return self.redis_url

        from urllib.parse import quote

        host = self.redis_host.strip()
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        password = quote(self.redis_password, safe="")
        return f"redis://:{password}@{host}:{self.redis_port}/{self.redis_db}"

    @property
    def web_push_configured(self) -> bool:
        return bool(
            self.web_push_vapid_public_key.strip()
            and self.web_push_vapid_private_key.strip()
            and self.web_push_subject.strip()
        )

    @property
    def fcm_configured(self) -> bool:
        return bool(
            self.fcm_service_account_file.strip()
            or self.fcm_service_account_json.strip()
        )


settings = Settings()
