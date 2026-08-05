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
 * Direct-URL cache for cottage-listen-together.
 *
 * Backend hands out signed mp3 URLs that expire (typically 30 min - 24h).
 * We cache them in a module-level Map so we don't hit /songs/<id>/url on
 * every play, but we cap any single entry at 10 minutes (R8.5) and we
 * never persist (no localStorage / sessionStorage / IndexedDB — R8.4).
 *
 * Songs that come back with `error_kind` (copyright / VIP / region) are
 * NOT cached — the next attempt should still hit the backend in case
 * the situation changed (e.g., the partner who started the song has
 * since re-logged in).
 */

import { listenSongUrl } from "./api";

const TTL_MS = 600_000; // 10 minutes
const cache = new Map(); // song_id -> { url, fetched_at_ms }

export async function getDirectUrl(songId) {
  const hit = cache.get(songId);
  if (hit && Date.now() - hit.fetched_at_ms < TTL_MS && hit.url) {
    return { url: hit.url };
  }
  let data;
  try {
    data = await listenSongUrl(songId);
  } catch (_error) {
    return { url: null, error_kind: "fetch_error" };
  }
  if (!data || !data.url) {
    cache.delete(songId);
    return { url: null, error_kind: data?.error_kind || "unavailable" };
  }
  cache.set(songId, { url: data.url, fetched_at_ms: Date.now() });
  return { url: data.url };
}

export function clearDirectUrlCache() {
  cache.clear();
}
