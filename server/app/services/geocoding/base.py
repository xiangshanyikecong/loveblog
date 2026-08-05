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

"""Abstract base for geocoding providers.

The two operations every provider must support are:

- ``reverse_geocode(latitude, longitude)`` — translate coordinates to a
  city/locality text (Provider-specific format; broadly "Province + City +
  District" for Chinese providers and "State + City" for Nominatim).
- ``reverse_lookup_ip(ip)`` — translate a public IP to a city text. Used as
  a tertiary fallback when geo-coordinates are unavailable. Nominatim does
  not implement this; it returns ``success=False, error_kind="not_supported"``.

All HTTP failures, JSON parse errors, missing fields, and timeouts are
absorbed by the ``_safe_call`` decorator and surfaced as ``success=False``
:class:`GeocodingResult` instances. Routes never see a raised exception
from this layer (see Requirement 9.6).
"""
from __future__ import annotations

import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, ClassVar

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeocodingResult:
    """Outcome of a single geocoding call.

    Attributes:
        success: True only when ``text`` is a non-empty city string.
        text: Resolved place name, or None on failure.
        provider: The provider name that produced this result.
        error_kind: One of ``timeout`` / ``http_error`` / ``parse_error`` /
            ``not_supported`` / None. Useful for telemetry / debugging but
            never persisted with the CheckIn record.
    """

    success: bool
    text: str | None
    provider: str
    error_kind: str | None = None


class GeocodingProvider(ABC):
    """Common interface for all geocoding backends."""

    name: ClassVar[str]

    @abstractmethod
    def reverse_geocode(self, latitude: float, longitude: float) -> GeocodingResult:
        """Translate coordinates to city text. Never raises."""

    @abstractmethod
    def reverse_lookup_ip(self, ip: str) -> GeocodingResult:
        """Translate IP to city text. Never raises."""


def _safe_call(
    func: Callable[..., GeocodingResult],
) -> Callable[..., GeocodingResult]:
    """Wrap a provider method to absorb all expected exceptions and emit a
    failure :class:`GeocodingResult` instead. Routes layer must never see a
    raised exception from a provider call.
    """

    @functools.wraps(func)
    def wrapper(self: GeocodingProvider, *args, **kwargs) -> GeocodingResult:  # type: ignore[no-untyped-def]
        try:
            return func(self, *args, **kwargs)
        except httpx.TimeoutException:
            logger.debug("[geocoding %s] timeout", self.name)
            return GeocodingResult(False, None, self.name, error_kind="timeout")
        except httpx.HTTPError as exc:
            logger.debug("[geocoding %s] http_error: %s", self.name, exc)
            return GeocodingResult(False, None, self.name, error_kind="http_error")
        except (KeyError, TypeError, ValueError) as exc:
            # json.JSONDecodeError is a subclass of ValueError, so ValueError
            # already covers malformed-JSON cases — listing both is redundant.
            logger.debug("[geocoding %s] parse_error: %s", self.name, exc)
            return GeocodingResult(False, None, self.name, error_kind="parse_error")

    return wrapper


def join_components(parts: list[str | None]) -> str | None:
    """Join non-empty address components with a single space; return None
    if every part is missing/empty.

    Used by every provider to assemble final ``location_text`` after pulling
    province / city / district fields from the upstream response.
    """
    cleaned = [str(p).strip() for p in parts if p]
    cleaned = [p for p in cleaned if p]
    return " ".join(cleaned) if cleaned else None
