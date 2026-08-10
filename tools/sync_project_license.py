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

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "LICENSE"
TARGETS = (
    ROOT / "server" / "LICENSE",
    ROOT / "netease-api" / "LICENSE",
    ROOT / "web" / "public" / "LICENSE",
    ROOT / "Android" / "app" / "src" / "main" / "res" / "raw" / "agpl_3_0.txt",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronize the project's AGPL text into release targets.")
    parser.add_argument("--check", action="store_true", help="Fail if any release target differs from the root LICENSE.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_content = SOURCE.read_bytes()
    stale = [target for target in TARGETS if not target.is_file() or target.read_bytes() != source_content]

    if args.check:
        if stale:
            relative = ", ".join(str(path.relative_to(ROOT)) for path in stale)
            raise SystemExit(f"Project license copies are missing or stale: {relative}")
        print("Project license copies match LICENSE.")
        return

    for target in stale:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source_content)
        print(f"Synchronized {target.relative_to(ROOT)}")

    if not stale:
        print("Project license copies already match LICENSE.")


if __name__ == "__main__":
    main()
