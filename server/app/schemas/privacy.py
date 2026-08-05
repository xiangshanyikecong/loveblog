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

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PrivacyAccessCounts(BaseModel):
    public: int = 0
    signed_in: int = 0
    partners: int = 0
    author_only: int = 0
    password: int = 0


class PrivacyProtectionCounts(BaseModel):
    end_to_end_encrypted: int = 0
    server_readable: int = 0
    server_masked: int = 0


class PrivacyModuleSummary(BaseModel):
    key: str
    label: str
    total: int
    access: PrivacyAccessCounts
    protection: PrivacyProtectionCounts
    manage_path: str
    note: str


class PrivacyEncryptionStatus(BaseModel):
    scope: Literal["chat", "vault"]
    label: str
    initialized: bool
    algorithm: str | None = None
    kdf: str | None = None
    iterations: int | None = None
    item_count: int = 0
    encrypted_count: int = 0
    manage_path: str


class PrivacyExportPolicy(BaseModel):
    archive_encrypted: bool
    uploads_included: bool
    server_readable_content_plaintext: bool
    end_to_end_content_plaintext: bool
    account_password_hashes_included: bool
    encryption_passphrases_included: bool
    push_credentials_included: bool


class PrivacyAccountSnapshot(BaseModel):
    uid: str
    nickname: str
    last_login_at: datetime | None
    last_login_ip: str | None
    password_changed_at: datetime | None
    session_version: int


class PrivacyActivityItem(BaseModel):
    log_id: str
    action: str
    result: str
    actor: str | None
    resource_type: str | None
    resource_name: str | None
    created_at: datetime


class PrivacySummaryResponse(BaseModel):
    generated_at: datetime
    totals: PrivacyAccessCounts
    protection: PrivacyProtectionCounts
    modules: list[PrivacyModuleSummary]
    encryption: list[PrivacyEncryptionStatus]
    export_policy: PrivacyExportPolicy
    account: PrivacyAccountSnapshot
    recent_activity: list[PrivacyActivityItem]
    activity_scope: str


class PrivacyRecoveryEventRequest(BaseModel):
    scope: Literal["chat", "vault"]
    event: Literal["kit_created", "kit_recovered"]


class PrivacyRecoveryEventResponse(BaseModel):
    recorded: bool
