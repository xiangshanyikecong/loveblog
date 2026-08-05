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

"""Nominatim (OpenStreetMap) geocoding provider.

Free, no API key required. Used as the default zero-config fallback when
``GEOCODING_PROVIDER`` is unset or set to ``nominatim``. Chinese mainland
place names are typically less precise than commercial providers — the
frontend surfaces this caveat via the ``location_provider`` field on the
response (Requirement 9.8 / 5.7).

Nominatim does not provide an IP→location endpoint, so
:meth:`reverse_lookup_ip` always returns ``not_supported``.
"""
from __future__ import annotations

import httpx

from app.services.geocoding.base import (
    GeocodingProvider,
    GeocodingResult,
    _safe_call,
    join_components,
)

_NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
# Nominatim usage policy requires a descriptive User-Agent identifying the
# application and a contact path. We use the project name plus version.
_USER_AGENT = "love-node-checkin/1.0"


class NominatimGeocodingProvider(GeocodingProvider):
    name = "nominatim"

    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=3.0,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        )

    @_safe_call
    def reverse_geocode(self, latitude: float, longitude: float) -> GeocodingResult:
        params = {
            "lat": f"{latitude:.6f}",
            "lon": f"{longitude:.6f}",
            "format": "jsonv2",
            "accept-language": "zh-CN",
            "zoom": "12",
        }
        response = self._client.get(_NOMINATIM_REVERSE_URL, params=params)
        response.raise_for_status()
        payload = response.json()

        address = payload.get("address") or {}
        # Try medium-coarse to fine: state → city → suburb. If those are
        # all empty, fall back to display_name (the full one-liner).
        candidate = join_components([
            address.get("state"),
            address.get("city") or address.get("town") or address.get("village"),
            address.get("suburb") or address.get("district"),
        ])
        if candidate is None:
            display = (payload.get("display_name") or "").strip()
            candidate = display or None
        if not candidate:
            return GeocodingResult(False, None, self.name, error_kind="parse_error")
        return GeocodingResult(True, candidate, self.name)

    @_safe_call
    def reverse_lookup_ip(self, ip: str) -> GeocodingResult:
        # Nominatim has no IP-based endpoint; signal not_supported so the
        # caller knows to mark the CheckIn as lookup_failed.
        return GeocodingResult(False, None, self.name, error_kind="not_supported")
