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

from __future__ import annotations

import email
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("generate_third_party_notices.py")
SPEC = importlib.util.spec_from_file_location("third_party_notice_generator", SCRIPT_PATH)
assert SPEC and SPEC.loader
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


class ThirdPartyNoticeGeneratorTests(unittest.TestCase):
    def test_lock_entries_require_exact_versions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock_path = Path(temporary_directory) / "requirements.lock"
            lock_path.write_text("example==1.2.3\n", encoding="utf-8")
            self.assertEqual(generator.locked_requirement_entries(lock_path), {"example": "1.2.3"})

            lock_path.write_text("example>=1.2.3\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "exact == version"):
                generator.locked_requirement_entries(lock_path)

    def test_maven_license_is_inherited_from_parent_pom(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_root = Path(temporary_directory)

            def write_pom(group: str, module: str, version: str, content: str) -> None:
                path = cache_root / "caches" / "modules-2" / "files-2.1" / group / module / version / "hash" / f"{module}.pom"
                path.parent.mkdir(parents=True)
                path.write_text(content, encoding="utf-8")

            write_pom(
                "com.example",
                "parent",
                "1.0.0",
                """<project><licenses><license><name>Apache License, Version 2.0</name><url>https://www.apache.org/licenses/LICENSE-2.0.txt</url></license></licenses></project>""",
            )
            write_pom(
                "com.example",
                "child",
                "1.0.0",
                """<project><parent><groupId>com.example</groupId><artifactId>parent</artifactId><version>1.0.0</version></parent></project>""",
            )

            metadata = generator.maven_metadata(
                cache_root,
                "com.example",
                "child",
                "1.0.0",
                cache={},
                visiting=set(),
            )
            self.assertEqual(metadata.license_names, ["Apache-2.0"])
            self.assertEqual(metadata.license_urls, ["https://www.apache.org/licenses/LICENSE-2.0.txt"])

    def test_license_text_fallback_only_recognizes_standard_text(self) -> None:
        apache_text = "Apache License\nVersion 2.0, January 2004\n"
        self.assertEqual(generator.license_from_files([("LICENSE", apache_text)]), "Apache-2.0")
        self.assertEqual(generator.license_from_files([("NOTICE", "custom legal notice")]), "NOASSERTION")

    def test_python_full_mit_license_metadata_is_normalized(self) -> None:
        message = email.message_from_string(
            "License: The MIT License (MIT) Copyright (c) Example Permission is hereby granted\n"
        )
        self.assertEqual(generator.metadata_license(message), "MIT")

    def test_inventory_rejects_unknown_and_untraceable_copyleft_licenses(self) -> None:
        unknown = generator.PackageRecord("unknown", "1.0", "NOASSERTION", "")
        copyleft = generator.PackageRecord("copyleft", "1.0", "LGPL-3.0-only", "")
        external_sdk = generator.PackageRecord(
            "external-sdk", "1.0", "Android Software Development Kit License", ""
        )
        with self.assertRaisesRegex(RuntimeError, "unknown license declarations"):
            generator.validate_license_inventory([("test", [unknown])])
        with self.assertRaisesRegex(RuntimeError, "copyleft dependencies without a source link"):
            generator.validate_license_inventory([("test", [copyleft])])
        with self.assertRaisesRegex(RuntimeError, "external Android SDK dependencies without a terms link"):
            generator.validate_license_inventory([("test", [external_sdk])])

    def test_android_license_index_json_is_not_treated_as_license_text(self) -> None:
        self.assertFalse(generator.is_license_filename("res/raw/third_party_licenses.json"))
        self.assertTrue(generator.is_license_filename("res/raw/third_party_licenses.txt"))
        self.assertTrue(generator.is_license_filename("META-INF/LICENSE"))

    def test_service_disclosure_does_not_add_an_agpl_use_restriction(self) -> None:
        rendered = generator.render_notice(
            [("NetEase API helper", 1)],
            disclosures=[generator.NETEASE_SERVICE_DISCLOSURE],
        )
        self.assertIn("does not add a field-of-use restriction", rendered)
        self.assertIn("不对 Love Journal 代码的 AGPL 授权增加用途限制", rendered)

    def test_android_sdk_disclosure_marks_external_binary_components(self) -> None:
        record = generator.PackageRecord(
            name="com.google.android.gms:play-services-base",
            version="1.0",
            license_name="Android Software Development Kit License",
            license_url="https://developer.android.com/studio/terms.html",
            source="",
        )
        disclosure = generator.android_sdk_disclosure([record])
        self.assertIsNotNone(disclosure)
        assert disclosure is not None
        self.assertIn("not composed exclusively of open-source software", disclosure[0])


if __name__ == "__main__":
    unittest.main()
