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

"""Baidu (百度地图) geocoding provider.

Requires ``GEOCODING_API_KEY`` (apply at https://lbsyun.baidu.com/).

Endpoints used:

- reverse geocoding: https://api.map.baidu.com/reverse_geocoding/v3
- IP locate: https://api.map.baidu.com/location/ip
"""
from __future__ import annotations

import httpx

from app.services.geocoding.base import (
    GeocodingProvider,
    GeocodingResult,
    _safe_call,
    join_components,
)

_BAIDU_REVERSE_URL = "https://api.map.baidu.com/reverse_geocoding/v3"
_BAIDU_IP_URL = "https://api.map.baidu.com/location/ip"


class BaiduGeocodingProvider(GeocodingProvider):
    name = "baidu"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.Client(timeout=3.0)

    @_safe_call
    def reverse_geocode(self, latitude: float, longitude: float) -> GeocodingResult:
        params = {
            "ak": self._api_key,
            "location": f"{latitude:.6f},{longitude:.6f}",
            "output": "json",
            "coordtype": "wgs84ll",
        }
        response = self._client.get(_BAIDU_REVERSE_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("status", -1)) != 0:
            return GeocodingResult(False, None, self.name, error_kind="http_error")
        address = (payload.get("result") or {}).get("addressComponent") or {}
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
        params = {"ak": self._api_key, "ip": ip, "coor": "bd09ll"}
        response = self._client.get(_BAIDU_IP_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("status", -1)) != 0:
            return GeocodingResult(False, None, self.name, error_kind="http_error")
        detail = (payload.get("content") or {}).get("address_detail") or {}
        text = join_components([
            detail.get("province"),
            detail.get("city"),
            detail.get("district"),
        ])
        if text is None:
            # Some Baidu responses only fill the flat 'address' string.
            flat = (payload.get("content") or {}).get("address")
            if flat:
                return GeocodingResult(True, flat, self.name)
            return GeocodingResult(False, None, self.name, error_kind="parse_error")
        return GeocodingResult(True, text, self.name)
