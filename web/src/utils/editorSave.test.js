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

import { editorRouteKey, isCurrentEditorSave } from "./editorSave";

describe("article editor save identity", () => {
  const request = {
    saveGeneration: 4,
    loadGeneration: 2,
    routeKey: "article-a"
  };

  it("accepts only the same save, load, and route identity", () => {
    expect(isCurrentEditorSave(request, { ...request })).toBe(true);
  });

  it("rejects a response after route reuse loads another article", () => {
    expect(isCurrentEditorSave(request, {
      ...request,
      loadGeneration: 3,
      routeKey: "article-b"
    })).toBe(false);
  });

  it("normalizes an empty editor route to the new-article identity", () => {
    expect(editorRouteKey()).toBe("new");
    expect(editorRouteKey("article-a")).toBe("article-a");
  });
});
