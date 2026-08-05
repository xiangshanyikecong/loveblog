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

"""Amap (高德地图) geocoding provider.

Requires ``GEOCODING_API_KEY`` (apply at https://console.amap.com/). When
the key is missing we still construct the provider (so ``get_provider()``
returns a usable object) but every call will hit the ``unauthorized``
response shape from upstream and degrade to ``http_error`` / ``parse_error``,
which the caller maps to ``location_status="lookup_failed"``.

Endpoints used:

- regeo: https://restapi.amap.com/v3/geocode/regeo
- IP locate: https://restapi.amap.com/v3/ip
"""
from __future__ import annotations

import httpx

from app.services.geocoding.base import (
    GeocodingProvider,
    GeocodingResult,
    _safe_call,
    join_components,
)

_AMAP_REGEO_URL = "https://restapi.amap.com/v3/geocode/regeo"
_AMAP_IP_URL = "https://restapi.amap.com/v3/ip"


class AmapGeocodingProvider(GeocodingProvider):
    name = "amap"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.Client(timeout=3.0)

    @_safe_call
    def reverse_geocode(self, latitude: float, longitude: float) -> GeocodingResult:
        # Amap's location format is "lng,lat" (note: longitude first).
        params = {
            "key": self._api_key,
            "location": f"{longitude:.6f},{latitude:.6f}",
            "extensions": "base",
        }
        response = self._client.get(_AMAP_REGEO_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("status", "")) != "1":
            return GeocodingResult(False, None, self.name, error_kind="http_error")
        address = (payload.get("regeocode") or {}).get("addressComponent") or {}
        # district can be a list when on a province border; coerce to a
        # single string by taking the first element.
        district = address.get("district")
        if isinstance(district, list):
            district = district[0] if district else None
        text = join_components([
            address.get("province"),
            address.get("city") if not isinstance(address.get("city"), list) else None,
            district,
        ])
        if text is None:
            return GeocodingResult(False, None, self.name, error_kind="parse_error")
        return GeocodingResult(True, text, self.name)

    @_safe_call
    def reverse_lookup_ip(self, ip: str) -> GeocodingResult:
        params = {"key": self._api_key, "ip": ip}
        response = self._client.get(_AMAP_IP_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("status", "")) != "1":
            return GeocodingResult(False, None, self.name, error_kind="http_error")
        # Amap IP response uses possibly-empty strings for province/city when
        # the IP can't be located precisely; treat them as missing.
        province = payload.get("province") or None
        city = payload.get("city") or None
        # Sometimes 'province' is a placeholder list "[]"; coerce.
        if isinstance(province, list):
            province = None
        if isinstance(city, list):
            city = None
        text = join_components([province, city])
        if text is None:
            return GeocodingResult(False, None, self.name, error_kind="parse_error")
        return GeocodingResult(True, text, self.name)
