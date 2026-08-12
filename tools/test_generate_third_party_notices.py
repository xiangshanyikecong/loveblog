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


if __name__ == "__main__":
    unittest.main()
