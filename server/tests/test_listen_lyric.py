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

"""Unit tests for the cottage-listen lyric parsing/normalization helpers.

These cover the pure functions only (no Redis / NetEase / FastAPI needed):
``_parse_lrc`` (LRC text -> sorted (time_ms, text) pairs) and
``_lyric_from_payload`` (upstream /lyric JSON -> SongLyricResponse).
"""
import unittest

from app.api.v1.cottage_listen import _lyric_from_payload, _parse_lrc


class ParseLrcTests(unittest.TestCase):
    def test_basic_centiseconds(self):
        # [mm:ss.xx] — 2-digit fraction is centiseconds -> *10 for ms.
        self.assertEqual(
            _parse_lrc("[00:01.50]hello"),
            [(1500, "hello")],
        )

    def test_milliseconds_three_digits(self):
        self.assertEqual(
            _parse_lrc("[01:02.345]world"),
            [(62345, "world")],
        )

    def test_no_fraction(self):
        self.assertEqual(_parse_lrc("[00:05]hi"), [(5000, "hi")])

    def test_colon_fraction_separator(self):
        # Some upstreams use ':' instead of '.' before the fraction.
        self.assertEqual(_parse_lrc("[00:01:50]hello"), [(1500, "hello")])

    def test_multiple_timestamps_one_line(self):
        # A line shared across several timestamps expands to one pair each.
        self.assertEqual(
            _parse_lrc("[00:01.00][00:05.00]chorus"),
            [(1000, "chorus"), (5000, "chorus")],
        )

    def test_skips_metadata_and_blank_lines(self):
        lrc = "[ti:Title]\n[ar:Artist]\n[by:maker]\n\n[00:03.00]real line\n[00:04.00]   "
        self.assertEqual(_parse_lrc(lrc), [(3000, "real line")])

    def test_sorted_by_time(self):
        out = _parse_lrc("[00:09.00]b\n[00:02.00]a")
        self.assertEqual(out, [(2000, "a"), (9000, "b")])

    def test_empty_and_none(self):
        self.assertEqual(_parse_lrc(""), [])
        self.assertEqual(_parse_lrc(None), [])


class LyricFromPayloadTests(unittest.TestCase):
    def test_plain_lyric_no_translation(self):
        payload = {"code": 200, "lrc": {"lyric": "[00:01.00]中文歌词"}}
        resp = _lyric_from_payload("123", payload)
        self.assertEqual(resp.kind, "lrc")
        self.assertEqual(len(resp.lines), 1)
        self.assertEqual(resp.lines[0].time_ms, 1000)
        self.assertEqual(resp.lines[0].text, "中文歌词")
        self.assertIsNone(resp.lines[0].trans)

    def test_translation_merged_by_timestamp(self):
        payload = {
            "code": 200,
            "lrc": {"lyric": "[00:01.00]Hello\n[00:05.00]World"},
            "tlyric": {"lyric": "[00:01.00]你好\n[00:05.00]世界"},
        }
        resp = _lyric_from_payload("123", payload)
        self.assertEqual(resp.kind, "lrc")
        self.assertEqual([l.text for l in resp.lines], ["Hello", "World"])
        self.assertEqual([l.trans for l in resp.lines], ["你好", "世界"])

    def test_translation_partial_match(self):
        # A translation line whose timestamp has no original is simply dropped;
        # originals without a translation get trans=None.
        payload = {
            "code": 200,
            "lrc": {"lyric": "[00:01.00]Hello\n[00:05.00]World"},
            "tlyric": {"lyric": "[00:01.00]你好"},
        }
        resp = _lyric_from_payload("123", payload)
        self.assertEqual(resp.lines[0].trans, "你好")
        self.assertIsNone(resp.lines[1].trans)

    def test_instrumental(self):
        resp = _lyric_from_payload("123", {"code": 200, "nolyric": True})
        self.assertEqual(resp.kind, "instrumental")
        self.assertEqual(resp.lines, [])

    def test_empty_lyric_is_none(self):
        resp = _lyric_from_payload("123", {"code": 200, "lrc": {"lyric": ""}})
        self.assertEqual(resp.kind, "none")
        self.assertEqual(resp.lines, [])

    def test_missing_lrc_key_is_none(self):
        resp = _lyric_from_payload("123", {"code": 200})
        self.assertEqual(resp.kind, "none")


if __name__ == "__main__":
    unittest.main()
