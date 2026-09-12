<!--
  Love Journal - a private journal + blog + real-time interaction platform for couples.
  Copyright (C) 2026 Love Journal Contributors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published
  by the Free Software Foundation, version 3 of the License.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
-->

<template>
  <teleport to="body">
    <transition name="pp-pop">
      <div v-if="open" ref="rootRef" class="pp-popover" :style="posStyle">
        <p class="pp-song" :title="songName">{{ songName }}</p>

        <div class="pp-list">
          <p v-if="loading" class="pp-hint">…</p>
          <template v-else>
            <button
              v-for="p in playlists"
              :key="p.pid"
              type="button"
              class="pp-item"
              :disabled="saving"
              @click="$emit('select', p)"
            >
              <span class="pp-item-name">{{ p.name }}</span>
              <span class="pp-item-count">{{ t("listenLibrary.tracksCount", { count: p.track_count }) }}</span>
            </button>
            <p v-if="!playlists.length" class="pp-hint">{{ t("listenLibrary.emptyPlaylists") }}</p>
          </template>
        </div>

        <form v-if="creating" class="pp-create" @submit.prevent="onCreate">
          <input
            ref="nameInputRef"
            v-model="newName"
            class="pp-input"
            :placeholder="t('listenLibrary.playlistNamePlaceholder')"
            maxlength="60"
            @keydown.esc.prevent="creating = false"
          />
          <div class="pp-create-actions">
            <button type="button" class="pp-btn" :disabled="saving" @click="creating = false">
              {{ t("listenLibrary.cancel") }}
            </button>
            <button
              type="submit"
              class="pp-btn pp-btn--primary"
              :disabled="saving || !newName.trim()"
            >
              {{ t("listenLibrary.create") }}
            </button>
          </div>
        </form>
        <button v-else type="button" class="pp-item pp-item--new" @click="startCreate">
          <span class="pp-item-name">＋ {{ t("listenLibrary.createPlaylist") }}</span>
        </button>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps({
  open: { type: Boolean, default: false },
  playlists: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  songName: { type: String, default: "" },
  // Element that opened the picker; the popover is anchored below (or above)
  // it and clicks on it are not treated as "outside".
  anchor: { type: HTMLElement, default: null }
});

const emit = defineEmits(["select", "create", "close"]);

const { t } = useI18n();

const rootRef = ref(null);
const nameInputRef = ref(null);
const posStyle = ref({});
const creating = ref(false);
const newName = ref("");

const POPOVER_WIDTH = 248;
const POPOVER_HEIGHT = 300;

// Anchor the popover below the trigger button, flipping above it when there
// is no room, and clamping horizontally into the viewport.
function updatePosition() {
  const el = props.anchor;
  if (!el) {
    posStyle.value = {};
    return;
  }
  const rect = el.getBoundingClientRect();
  let left = rect.left;
  if (left + POPOVER_WIDTH > window.innerWidth - 8) {
    left = Math.max(8, window.innerWidth - POPOVER_WIDTH - 8);
  }
  let top = rect.bottom + 6;
  if (top + POPOVER_HEIGHT > window.innerHeight - 8) {
    top = Math.max(8, rect.top - POPOVER_HEIGHT - 6);
  }
  posStyle.value = { left: `${left}px`, top: `${top}px` };
}

function onDocPointerDown(evt) {
  if (!props.open) return;
  const target = evt.target;
  if (rootRef.value?.contains(target)) return;
  if (props.anchor?.contains(target)) return;
  emit("close");
}

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    creating.value = false;
    newName.value = "";
    updatePosition();
  }
);

// The trigger lives inside scrollable lists: follow it on scroll/resize.
watch(() => props.anchor, updatePosition);

async function startCreate() {
  creating.value = true;
  newName.value = "";
  await nextTick();
  nameInputRef.value?.focus();
}

function onCreate() {
  if (!newName.value.trim()) return;
  emit("create", newName.value.trim());
}

onMounted(() => {
  document.addEventListener("mousedown", onDocPointerDown, true);
  window.addEventListener("resize", updatePosition);
  window.addEventListener("scroll", updatePosition, true);
});

onBeforeUnmount(() => {
  document.removeEventListener("mousedown", onDocPointerDown, true);
  window.removeEventListener("resize", updatePosition);
  window.removeEventListener("scroll", updatePosition, true);
});
</script>

<style scoped>
.pp-popover {
  position: fixed;
  z-index: 90;
  width: 248px;
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.6rem;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.32);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.18);
}

.pp-song {
  margin: 0;
  padding: 0 0.3rem;
  font-size: 0.8rem;
  font-weight: 600;
  color: #2f3754;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pp-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.pp-hint {
  margin: 0;
  padding: 0.4rem 0.3rem;
  font-size: 0.78rem;
  color: #94a3b8;
  line-height: 1.4;
}

.pp-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  min-height: 36px;
  padding: 0.3rem 0.55rem;
  border-radius: 10px;
  border: none;
  background: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  text-align: left;
}

.pp-item:hover {
  background: rgba(255, 138, 181, 0.14);
}

.pp-item:disabled {
  opacity: 0.6;
  cursor: default;
}

.pp-item-name {
  font-size: 0.84rem;
  color: #2f3754;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pp-item-count {
  flex: 0 0 auto;
  font-size: 0.72rem;
  color: #94a3b8;
}

.pp-item--new .pp-item-name {
  color: #ff5c8a;
  font-weight: 600;
}

.pp-create {
  display: grid;
  gap: 0.4rem;
  padding-top: 0.35rem;
  border-top: 1px solid rgba(148, 163, 184, 0.24);
}

.pp-input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.4);
  border-radius: 10px;
  padding: 0.45rem 0.6rem;
  font-size: 0.84rem;
  background: rgba(255, 255, 255, 0.9);
  color: #2f3754;
}

.pp-create-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.35rem;
}

.pp-btn {
  min-height: 32px;
  padding: 0.28rem 0.7rem;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(255, 255, 255, 0.85);
  color: #3d4665;
  font-size: 0.78rem;
  cursor: pointer;
}

.pp-btn--primary {
  border-color: transparent;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
}

.pp-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

.pp-pop-enter-active,
.pp-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.pp-pop-enter-from,
.pp-pop-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
