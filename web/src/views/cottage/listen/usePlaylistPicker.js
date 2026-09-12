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

import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";

import {
  addTrackToMyPlaylist,
  createMyPlaylist,
  fetchMyPlaylists
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

/**
 * Shared state for the "add song to one of our couple playlists" picker.
 * Any component that can add a song to a playlist calls
 * `openPicker(song, anchorEl)` from a row button and renders a single
 * <PlaylistPickerPopover> fed with the returned refs — the popover teleports
 * to <body>, so it is never clipped by the scrolling song lists.
 */
export function usePlaylistPicker() {
  const { t } = useI18n();
  const showMessage = inject("showMessage", () => {});

  const pickerOpen = ref(false);
  const pickerSong = ref(null);
  const pickerAnchor = ref(null);
  const pickerPlaylists = ref([]);
  const pickerLoading = ref(false);
  const pickerSaving = ref(false);

  async function openPicker(song, anchorEl) {
    if (!song) return;
    pickerSong.value = song;
    pickerAnchor.value = anchorEl || null;
    pickerOpen.value = true;
    pickerLoading.value = true;
    try {
      const data = await fetchMyPlaylists();
      pickerPlaylists.value = data.items || [];
    } catch (error) {
      pickerOpen.value = false;
      showMessage(parseError(error));
    } finally {
      pickerLoading.value = false;
    }
  }

  function closePicker() {
    pickerOpen.value = false;
    pickerSong.value = null;
    pickerAnchor.value = null;
  }

  function handlePickerError(error) {
    if (error?.response?.status === 409) {
      showMessage(t("listenLibrary.duplicateTrack"));
    } else {
      showMessage(parseError(error));
    }
  }

  async function addToPlaylist(playlist) {
    const song = pickerSong.value;
    if (!song || !playlist || pickerSaving.value) return;
    pickerSaving.value = true;
    try {
      await addTrackToMyPlaylist(playlist.pid, song);
      closePicker();
    } catch (error) {
      handlePickerError(error);
    } finally {
      pickerSaving.value = false;
    }
  }

  async function createPlaylistAndAdd(name) {
    const song = pickerSong.value;
    const trimmed = String(name || "").trim();
    if (!song || !trimmed || pickerSaving.value) return;
    pickerSaving.value = true;
    try {
      const created = await createMyPlaylist({ name: trimmed });
      await addTrackToMyPlaylist(created.pid, song);
      closePicker();
    } catch (error) {
      handlePickerError(error);
    } finally {
      pickerSaving.value = false;
    }
  }

  return {
    pickerOpen,
    pickerSong,
    pickerAnchor,
    pickerPlaylists,
    pickerLoading,
    pickerSaving,
    openPicker,
    closePicker,
    addToPlaylist,
    createPlaylistAndAdd
  };
}
