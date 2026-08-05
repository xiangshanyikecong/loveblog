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

"""Tests for the cottage 加密保险箱 (true end-to-end encrypted vault).

The server is a *blind store*: it only ever receives opaque ciphertext + KDF
parameters, never the passphrase or derived key. These tests therefore exercise
the storage / lifecycle contract (not real crypto):

* ``/meta`` reports not-initialized until ``/setup`` runs, then echoes the KDF
  params + verifier so any client can re-derive the key.
* ``/setup`` is one-shot — a second attempt is rejected (409) so existing
  entries can't be orphaned by a new key.
* Entries can only be created once the vault is initialized; create / list /
  update / delete round-trip the ciphertext verbatim.
* ``/reset`` is the forgotten-passphrase escape hatch: it wipes meta + every
  entry so the couple can start over.
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_optional_user, get_token, get_token_optional
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.site_setting import SiteSetting
from app.models.user import User, UserRole

# A minimal valid setup payload (values are opaque base64-ish blobs to the API).
_SETUP = {
    "salt": "c2FsdHNhbHRzYWx0",
    "kdf": "PBKDF2",
    "kdf_hash": "SHA-256",
    "iterations": 210_000,
    "algo": "AES-GCM",
    "verifier_iv": "aXZpdml2aXY=",
    "verifier_cipher": "dmVyaWZpZXJjaXBoZXJ0ZXh0",
}


class VaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(
            bind=cls.engine, autoflush=False, autocommit=False, class_=Session
        )

        db = cls.SessionLocal()
        try:
            partner = User(
                username="vault_partner",
                nickname="Vault Partner",
                role=UserRole.partner_a,
                password_hash="x",
            )
            db.add(partner)
            db.add(SiteSetting(id=1, site_name="Test Site"))
            db.commit()
            db.refresh(partner)
            cls.partner_id = int(partner.id)
        finally:
            db.close()

        def _get_db_override():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def _get_current_user_override():
            db = cls.SessionLocal()
            try:
                user = db.query(User).filter(User.id == cls.partner_id).first()
                if user is not None:
                    db.expunge(user)
                return user
            finally:
                db.close()

        app.dependency_overrides[get_db] = _get_db_override
        app.dependency_overrides[get_current_user] = _get_current_user_override
        app.dependency_overrides[get_optional_user] = _get_current_user_override
        app.dependency_overrides[get_token] = lambda: "test-token"
        app.dependency_overrides[get_token_optional] = lambda: "test-token"

        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self) -> None:
        # Each test starts from an empty vault.
        self.client.post("/v1/cottage/vault/reset")

    # -- meta / setup -------------------------------------------------------

    def test_meta_reports_uninitialized_before_setup(self) -> None:
        resp = self.client.get("/v1/cottage/vault/meta")
        self.assertEqual(resp.status_code, 200, msg=resp.text)
        body = resp.json()
        self.assertFalse(body["initialized"])
        self.assertIsNone(body["salt"])

    def test_setup_then_meta_echoes_params(self) -> None:
        resp = self.client.post("/v1/cottage/vault/setup", json=_SETUP)
        self.assertEqual(resp.status_code, 201, msg=resp.text)

        meta = self.client.get("/v1/cottage/vault/meta").json()
        self.assertTrue(meta["initialized"])
        self.assertEqual(meta["salt"], _SETUP["salt"])
        self.assertEqual(meta["iterations"], _SETUP["iterations"])
        self.assertEqual(meta["verifier_cipher"], _SETUP["verifier_cipher"])

    def test_double_setup_is_rejected(self) -> None:
        self.assertEqual(self.client.post("/v1/cottage/vault/setup", json=_SETUP).status_code, 201)
        again = self.client.post("/v1/cottage/vault/setup", json=_SETUP)
        self.assertEqual(again.status_code, 409, msg=again.text)

    # -- entries ------------------------------------------------------------

    def test_entry_requires_initialized_vault(self) -> None:
        resp = self.client.post(
            "/v1/cottage/vault/entries",
            json={"iv": "aXZpdml2", "ciphertext": "Y2lwaGVy"},
        )
        self.assertEqual(resp.status_code, 400, msg=resp.text)

    def test_entry_crud_roundtrip(self) -> None:
        self.client.post("/v1/cottage/vault/setup", json=_SETUP)

        created = self.client.post(
            "/v1/cottage/vault/entries",
            json={"iv": "aXZvbmU=", "ciphertext": "Y2lwaGVyb25l"},
        )
        self.assertEqual(created.status_code, 201, msg=created.text)
        entry = created.json()
        vid = entry["vid"]
        self.assertEqual(entry["ciphertext"], "Y2lwaGVyb25l")

        listed = self.client.get("/v1/cottage/vault/entries").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["vid"], vid)

        updated = self.client.put(
            f"/v1/cottage/vault/entries/{vid}",
            json={"iv": "aXZ0d28=", "ciphertext": "Y2lwaGVydHdv"},
        )
        self.assertEqual(updated.status_code, 200, msg=updated.text)
        self.assertEqual(updated.json()["ciphertext"], "Y2lwaGVydHdv")

        deleted = self.client.delete(f"/v1/cottage/vault/entries/{vid}")
        self.assertEqual(deleted.status_code, 204, msg=deleted.text)
        self.assertEqual(len(self.client.get("/v1/cottage/vault/entries").json()), 0)

    def test_update_missing_entry_404(self) -> None:
        self.client.post("/v1/cottage/vault/setup", json=_SETUP)
        resp = self.client.put(
            "/v1/cottage/vault/entries/does-not-exist",
            json={"iv": "aXZpdml2aXY=", "ciphertext": "Y2lwaGVy"},
        )
        self.assertEqual(resp.status_code, 404, msg=resp.text)

    # -- rekey (change passphrase) -----------------------------------------

    def _create_entry(self, iv: str, ct: str) -> str:
        resp = self.client.post(
            "/v1/cottage/vault/entries", json={"iv": iv, "ciphertext": ct}
        )
        self.assertEqual(resp.status_code, 201, msg=resp.text)
        return resp.json()["vid"]

    def test_rekey_replaces_meta_and_ciphertext(self) -> None:
        self.client.post("/v1/cottage/vault/setup", json=_SETUP)
        vid1 = self._create_entry("aXZvbmUx", "Y2lwaGVyb25l")
        vid2 = self._create_entry("aXZ0d28y", "Y2lwaGVydHdv")

        new_meta = {
            "salt": "bmV3c2FsdG5ld3NhbHQ=",
            "kdf": "PBKDF2",
            "kdf_hash": "SHA-256",
            "iterations": 300_000,
            "algo": "AES-GCM",
            "verifier_iv": "bmV3aXZuZXdpdg==",
            "verifier_cipher": "bmV3dmVyaWZpZXI=",
            "entries": [
                {"vid": vid1, "iv": "bmV3aXYx", "ciphertext": "bmV3Y2lwaGVyMQ=="},
                {"vid": vid2, "iv": "bmV3aXYy", "ciphertext": "bmV3Y2lwaGVyMg=="},
            ],
        }
        resp = self.client.post("/v1/cottage/vault/rekey", json=new_meta)
        self.assertEqual(resp.status_code, 200, msg=resp.text)

        meta = self.client.get("/v1/cottage/vault/meta").json()
        self.assertEqual(meta["salt"], new_meta["salt"])
        self.assertEqual(meta["iterations"], 300_000)

        by_vid = {e["vid"]: e for e in self.client.get("/v1/cottage/vault/entries").json()}
        self.assertEqual(by_vid[vid1]["ciphertext"], "bmV3Y2lwaGVyMQ==")
        self.assertEqual(by_vid[vid2]["ciphertext"], "bmV3Y2lwaGVyMg==")

    def test_rekey_rejects_partial_entry_set(self) -> None:
        self.client.post("/v1/cottage/vault/setup", json=_SETUP)
        vid1 = self._create_entry("aXZvbmUx", "Y2lwaGVyb25l")
        self._create_entry("aXZ0d28y", "Y2lwaGVydHdv")  # second entry omitted below

        resp = self.client.post(
            "/v1/cottage/vault/rekey",
            json={
                **{k: v for k, v in _SETUP.items()},
                "salt": "bmV3c2FsdG5ld3NhbHQ=",
                "entries": [{"vid": vid1, "iv": "bmV3aXYx", "ciphertext": "bmV3Yw=="}],
            },
        )
        self.assertEqual(resp.status_code, 400, msg=resp.text)

    def test_rekey_requires_initialized_vault(self) -> None:
        resp = self.client.post(
            "/v1/cottage/vault/rekey",
            json={**_SETUP, "entries": []},
        )
        self.assertEqual(resp.status_code, 400, msg=resp.text)

    # -- reset --------------------------------------------------------------

    def test_reset_wipes_meta_and_entries(self) -> None:
        self.client.post("/v1/cottage/vault/setup", json=_SETUP)
        self.client.post(
            "/v1/cottage/vault/entries",
            json={"iv": "aXZvbmU=", "ciphertext": "Y2lwaGVyb25l"},
        )

        reset = self.client.post("/v1/cottage/vault/reset")
        self.assertEqual(reset.status_code, 204, msg=reset.text)

        # Meta gone, entries gone, and we can set up a fresh vault again.
        self.assertFalse(self.client.get("/v1/cottage/vault/meta").json()["initialized"])
        self.assertEqual(len(self.client.get("/v1/cottage/vault/entries").json()), 0)
        self.assertEqual(self.client.post("/v1/cottage/vault/setup", json=_SETUP).status_code, 201)


if __name__ == "__main__":
    unittest.main()
