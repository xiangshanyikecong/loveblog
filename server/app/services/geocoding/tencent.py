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

"""Tencent (腾讯位置服务) geocoding provider.

Requires ``GEOCODING_API_KEY`` (apply at https://lbs.qq.com/).

Endpoints used:

- reverse geocoding: https://apis.map.qq.com/ws/geocoder/v1/
- IP locate: https://apis.map.qq.com/ws/location/v1/ip
"""
from __future__ import annotations

import httpx

from app.services.geocoding.base import (
    GeocodingProvider,
    GeocodingResult,
    _safe_call,
    join_components,
)

_TENCENT_REVERSE_URL = "https://apis.map.qq.com/ws/geocoder/v1/"
_TENCENT_IP_URL = "https://apis.map.qq.com/ws/location/v1/ip"


class TencentGeocodingProvider(GeocodingProvider):
    name = "tencent"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.Client(timeout=3.0)

    @_safe_call
    def reverse_geocode(self, latitude: float, longitude: float) -> GeocodingResult:
        params = {
            "key": self._api_key,
            "location": f"{latitude:.6f},{longitude:.6f}",
        }
        response = self._client.get(_TENCENT_REVERSE_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("status", -1)) != 0:
            return GeocodingResult(False, None, self.name, error_kind="http_error")
        address = (payload.get("result") or {}).get("address_component") or {}
        text = join_components([
            address.get("province"),
            address.get("city"),
            address.get("district"),
        ])
        if text is None:
            return GeocodingResult(False, None, self.name, error_kind="parse_error")
        return GeocodingResult(True, text, self.name)

    @_safe_call
    def reverse_lookup_ip(self, ip: str) -> GeocodingResult:
        params = {"key": self._api_key, "ip": ip}
        response = self._client.get(_TENCENT_IP_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("status", -1)) != 0:
            return GeocodingResult(False, None, self.name, error_kind="http_error")
        ad_info = (payload.get("result") or {}).get("ad_info") or {}
        text = join_components([
            ad_info.get("province"),
            ad_info.get("city"),
            ad_info.get("district"),
        ])
        if text is None:
            return GeocodingResult(False, None, self.name, error_kind="parse_error")
        return GeocodingResult(True, text, self.name)
