# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Request/response schemas for TOTP two-factor-authentication management."""

from pydantic import BaseModel, ConfigDict, Field


class TotpSetupResponse(BaseModel):
    """Freshly generated secret plus the otpauth:// URI for QR apps.

    The secret is NOT active yet — the user must confirm a code via
    ``POST /enable`` before the second factor takes effect.
    """

    secret: str
    uri: str


class TotpEnableRequest(BaseModel):
    """A 6-digit code from the authenticator app to finish enabling TOTP."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=10)


class TotpEnableResponse(BaseModel):
    """Enable confirmation; plaintext recovery codes are shown exactly once."""

    enabled: bool
    recovery_codes: list[str]


class TotpDisableRequest(BaseModel):
    """A second-factor code (TOTP or recovery code) plus the account password."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=16)
    password: str = Field(min_length=1, max_length=128)


class TotpStatusResponse(BaseModel):
    """Current 2FA state of the account."""

    enabled: bool
    recovery_codes_remaining: int
