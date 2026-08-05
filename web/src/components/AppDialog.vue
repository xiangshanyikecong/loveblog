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
  <Teleport to="body">
    <transition name="app-dialog-fade">
      <div
        v-if="state.visible"
        class="app-dialog-overlay"
        @click.self="onCancel"
      >
        <div class="app-dialog glass-card" role="dialog" aria-modal="true">
          <h3 class="app-dialog-title">{{ state.title }}</h3>
          <p class="app-dialog-message">{{ state.message }}</p>
          <div class="app-dialog-actions">
            <!-- Two-button mode (alert / confirm) -->
            <template v-if="state.mode !== 'choice'">
              <button
                v-if="state.mode === 'confirm'"
                type="button"
                class="app-dialog-btn app-dialog-btn--cancel"
                @click="onCancel"
              >
                {{ state.cancelText }}
              </button>
              <button
                type="button"
                class="app-dialog-btn app-dialog-btn--confirm"
                :class="{ 'app-dialog-btn--danger': state.danger }"
                @click="onConfirm"
              >
                {{ state.confirmText }}
              </button>
            </template>

            <!-- Multi-choice mode (e.g. article co-edit conflict) -->
            <template v-else>
              <button
                type="button"
                class="app-dialog-btn app-dialog-btn--cancel"
                @click="onCancel"
              >
                {{ state.cancelText }}
              </button>
              <button
                v-for="(choice, idx) in state.choices"
                :key="idx"
                type="button"
                class="app-dialog-btn app-dialog-btn--confirm"
                :class="{ 'app-dialog-btn--danger': choice.danger }"
                @click="onChoice(choice.value)"
              >
                {{ choice.label }}
              </button>
            </template>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { dialogState, resolveDialog } from "../lib/dialog";

const state = dialogState;

function onConfirm() {
  resolveDialog(true);
}

function onCancel() {
  // Two-button modes resolve to `false`; choice mode resolves to `null` so
  // the caller can distinguish a deliberate cancel from any of the options.
  resolveDialog(state.mode === "choice" ? null : false);
}

function onChoice(value) {
  resolveDialog(value);
}
</script>

<style scoped>
.app-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 100000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.45);
}

.app-dialog {
  width: 100%;
  max-width: 360px;
  padding: 1.25rem 1.25rem 1rem;
  border-radius: 16px;
}

.app-dialog-title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-main, #334155);
}

.app-dialog-message {
  margin: 0 0 1.25rem;
  font-size: 0.92rem;
  line-height: 1.6;
  color: var(--text-soft, #64748b);
  white-space: pre-wrap;
  word-break: break-word;
}

.app-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
}

.app-dialog-btn {
  border: none;
  border-radius: 10px;
  padding: 0.5rem 1.1rem;
  font-size: 0.9rem;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.app-dialog-btn:hover {
  opacity: 0.85;
}

.app-dialog-btn--cancel {
  background: rgba(148, 163, 184, 0.18);
  color: var(--text-main, #334155);
}

.app-dialog-btn--confirm {
  background: linear-gradient(135deg, #60a5fa, #818cf8);
  color: #fff;
}

.app-dialog-btn--danger {
  background: linear-gradient(135deg, #fb7185, #ef4444);
}

.app-dialog-fade-enter-active,
.app-dialog-fade-leave-active {
  transition: opacity 0.18s ease;
}

.app-dialog-fade-enter-from,
.app-dialog-fade-leave-to {
  opacity: 0;
}
</style>
