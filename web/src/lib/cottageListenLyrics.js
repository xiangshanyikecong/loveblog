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

/**
 * Lyric cache for cottage-listen-together.
 *
 * Unlike direct URLs, lyrics are stable for a given song, so we can cache
 * them for much longer. We still keep them in a module-level Map only (no
 * localStorage / sessionStorage / IndexedDB) and let them die with the page.
 *
 * Each entry is the parsed backend response:
 *   { song_id, lines: [{ time_ms, text, trans }], kind }
 * where `kind` is "lrc" | "instrumental" | "none". On a fetch error we return
 * a `none` shape (and DON'T cache it) so a later attempt can still succeed.
 */

import { listenSongLyric } from "./api";

const TTL_MS = 3_600_000; // 1 hour
const cache = new Map(); // song_id -> { data, fetched_at_ms }

export async function getLyric(songId) {
  const key = String(songId);
  const hit = cache.get(key);
  if (hit && Date.now() - hit.fetched_at_ms < TTL_MS) {
    return hit.data;
  }
  let data;
  try {
    data = await listenSongLyric(key);
  } catch (_error) {
    return { song_id: key, lines: [], kind: "none" };
  }
  const normalized = {
    song_id: key,
    lines: data?.lines || [],
    kind: data?.kind || "none"
  };
  cache.set(key, { data: normalized, fetched_at_ms: Date.now() });
  return normalized;
}

export function clearLyricCache() {
  cache.clear();
}
