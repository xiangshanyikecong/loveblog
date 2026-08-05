/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

import { describe, expect, it } from "vitest";

import { formatLocalDate, localDateKey, localMonthKey, parseDisplayDate } from "./date";

describe("local date helpers", () => {
  it("uses calendar fields instead of UTC for date and month inputs", () => {
    const lateAfternoon = new Date(2026, 6, 17, 17, 30);
    expect(localDateKey(lateAfternoon)).toBe("2026-07-17");
    expect(localMonthKey(lateAfternoon)).toBe("2026-07");
  });

  it("parses an API date-only value at local midnight", () => {
    const parsed = parseDisplayDate("2026-07-17");
    expect(parsed.getFullYear()).toBe(2026);
    expect(parsed.getMonth()).toBe(6);
    expect(parsed.getDate()).toBe(17);
    expect(parsed.getHours()).toBe(0);
  });

  it("does not shift a date-only value to the previous day", () => {
    expect(formatLocalDate("2026-07-17", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    })).toBe(new Date(2026, 6, 17).toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit"
    }));
    expect(parseDisplayDate("not-a-date").getTime()).toBeNaN();
  });
});
