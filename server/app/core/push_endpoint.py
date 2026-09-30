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

"""Safety policy for Web Push subscription endpoints.

The server itself POSTs to a stored endpoint (``pywebpush`` in
``notification_delivery``), so a client-supplied endpoint is a server-side
request forgery primitive: without validation any authenticated account could
register ``http://169.254.169.254/latest/meta-data/`` and make the server probe
internal addresses whenever a notification is delivered (or redelivered).

Layers, all enforced:

1. ``https`` only, no userinfo, no fragment.
2. The host must be a DNS name — IP literals are rejected outright, so
   ``https://10.0.0.1/`` and ``https://[::1]/`` never pass.
3. Local / single-label names (``localhost``, ``*.local``, ``*.internal``,
   ``intranet`` …) are rejected.
4. The host must belong to a known browser push provider, or to an extra suffix
   an operator opted into via ``WEB_PUSH_ENDPOINT_EXTRA_HOSTS``.

Layer 4 is what actually keeps the destination space closed; layers 1–3 also
protect the operator-extended list. Legitimate Web Push endpoints always come
from the browser vendor's push service (Chrome/Edge FCM, Firefox autopush,
Safari APNs, …), so an allowlist is both accurate and sufficient.
"""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from app.core.config import settings


# Browser-vendor push services. Every entry is a suffix: it matches the domain
# itself and any subdomain of it.
_DEFAULT_ALLOWED_HOST_SUFFIXES: tuple[str, ...] = (
    # Chrome / Chromium / Brave / Opera / Vivaldi (Firebase Cloud Messaging)
    "fcm.googleapis.com",
    # Firefox / autopush (also self-hosted Mozilla deployments)
    "push.services.mozilla.com",
    "mozilla.com",
    "mozilla.org",
    # Safari / WebKit (Apple Push Notification service)
    "push.apple.com",
    # Edge (Windows Notification Service)
    "notify.windows.com",
    # Huawei Browser
    "push.hicloud.com",
    "push.cloud.huawei.com",
    # Samsung Internet
    "push.samsungosp.com",
    # Yandex Browser
    "push.yandex.ru",
)

# Single-label / reserved names that must never be resolved by the server.
_BLOCKED_HOST_SUFFIXES: tuple[str, ...] = (
    "localhost",
    "local",
    "internal",
    "localdomain",
    "home.arpa",
    "in-addr.arpa",
    "ip6.arpa",
)


class PushEndpointError(ValueError):
    """Raised when an endpoint fails the safety policy."""


def _extra_allowed_suffixes() -> tuple[str, ...]:
    raw = getattr(settings, "web_push_endpoint_extra_hosts", "") or ""
    return tuple(part.strip().lower().lstrip(".") for part in raw.split(",") if part.strip())


def _host_matches(host: str, suffix: str) -> bool:
    return host == suffix or host.endswith(f".{suffix}")


def _is_blocked_name(host: str) -> bool:
    if "." not in host:
        # Single-label names can only resolve inside the deployment's own DNS.
        return True
    return any(_host_matches(host, suffix) for suffix in _BLOCKED_HOST_SUFFIXES)


def allowed_host_suffixes() -> tuple[str, ...]:
    return _DEFAULT_ALLOWED_HOST_SUFFIXES + _extra_allowed_suffixes()


def validate_web_push_endpoint(endpoint: str) -> str:
    """Return the normalized endpoint or raise :class:`PushEndpointError`."""
    raw = (endpoint or "").strip()
    if not raw:
        raise PushEndpointError("Endpoint cannot be blank")

    parts = urlsplit(raw)
    if parts.scheme != "https":
        raise PushEndpointError("Endpoint must use https://")
    if parts.username or parts.password:
        raise PushEndpointError("Endpoint must not contain userinfo")
    if parts.fragment:
        raise PushEndpointError("Endpoint must not contain a fragment")

    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise PushEndpointError("Endpoint must include a host")

    # IP literals are never valid push endpoints and are the classic SSRF
    # payloads (loopback, RFC1918, link-local, metadata addresses).
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise PushEndpointError("Endpoint host must be a DNS name, not an IP address")

    if _is_blocked_name(host):
        raise PushEndpointError("Endpoint host is not reachable from this server")

    if not any(_host_matches(host, suffix) for suffix in allowed_host_suffixes()):
        raise PushEndpointError(
            "Endpoint host is not a recognized push service "
            "(set WEB_PUSH_ENDPOINT_EXTRA_HOSTS for a custom provider)"
        )
    return raw


def is_safe_web_push_endpoint(endpoint: str) -> bool:
    """Non-raising variant of the full registration policy."""
    try:
        validate_web_push_endpoint(endpoint)
    except PushEndpointError:
        return False
    return True


def is_deliverable_web_push_endpoint(endpoint: str) -> bool:
    """Shape check applied on the delivery path.

    Rows can predate the registration policy (or be restored from a backup), so
    the sender re-checks the properties that make a destination categorically
    dangerous to POST to: a non-https scheme, an IP literal (loopback, RFC1918,
    link-local, cloud metadata) or a local single-label name. The provider
    allowlist is intentionally *not* enforced here so a deployment that opted
    into a custom push service keeps working.
    """
    raw = (endpoint or "").strip()
    if not raw:
        return False
    parts = urlsplit(raw)
    if parts.scheme != "https" or parts.username or parts.password:
        return False
    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return not _is_blocked_name(host)
    return False
