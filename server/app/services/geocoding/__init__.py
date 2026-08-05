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

"""Geocoding service for cottage check-in.

Pluggable provider architecture: the active provider is selected by the
``GEOCODING_PROVIDER`` env var (``amap`` / ``baidu`` / ``tencent`` /
``nominatim``, default ``nominatim``). All providers implement the same
:class:`GeocodingProvider` interface and return the same
:class:`GeocodingResult` shape so callers don't branch on provider name.

Privacy invariant: providers are passed raw IPs and lat/lng *only as
function arguments*. They MUST NOT persist these values to disk, database,
or long-lived caches; in-memory single-process LRU caches are permitted
but not required.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings
from app.services.geocoding.amap import AmapGeocodingProvider
from app.services.geocoding.baidu import BaiduGeocodingProvider
from app.services.geocoding.base import GeocodingProvider, GeocodingResult
from app.services.geocoding.nominatim import NominatimGeocodingProvider
from app.services.geocoding.tencent import TencentGeocodingProvider

logger = logging.getLogger(__name__)

__all__ = ["get_provider", "GeocodingProvider", "GeocodingResult"]

_KEYED_PROVIDERS = {"amap", "baidu", "tencent"}


@lru_cache(maxsize=1)
def get_provider() -> GeocodingProvider:
    """Return the configured geocoding provider as a process-wide singleton.

    Reads ``settings.geocoding_provider``. Unknown values fall back to
    Nominatim (with a warning log). amap/baidu/tencent without a configured
    ``geocoding_api_key`` are still constructed but log a warning that calls
    will degrade to ``lookup_failed`` at request time — we deliberately do
    NOT block startup on missing keys (Requirement 9.4).
    """
    name = (settings.geocoding_provider or "").strip().lower() or "nominatim"
    api_key = (settings.geocoding_api_key or "").strip()

    if name in _KEYED_PROVIDERS and not api_key:
        logger.warning(
            "[geocoding] provider %r requires GEOCODING_API_KEY but none is set; "
            "all reverse-lookup calls will degrade to lookup_failed.",
            name,
        )

    if name == "amap":
        return AmapGeocodingProvider(api_key)
    if name == "baidu":
        return BaiduGeocodingProvider(api_key)
    if name == "tencent":
        return TencentGeocodingProvider(api_key)
    if name == "nominatim":
        return NominatimGeocodingProvider()

    logger.warning(
        "[geocoding] unknown GEOCODING_PROVIDER %r, falling back to nominatim", name,
    )
    return NominatimGeocodingProvider()
