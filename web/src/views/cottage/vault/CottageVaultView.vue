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
  <div class="content-section vault-view">
    <article class="glass-card section-block">
      <div class="section-header">
        <h2>{{ t('cottageVault.title') }}</h2>
        <div v-if="mode === 'unlocked'" class="head-actions">
          <button class="ghost-btn" @click="toggleChange">{{ changing ? t('cottageVault.cancel') : t('cottageVault.changePassphrase') }}</button>
          <button class="ghost-btn" @click="lock">{{ t('cottageVault.lock') }}</button>
        </div>
      </div>
      <p class="hint">
        {{ t('cottageVault.hintBefore') }}<strong>{{ t('cottageVault.hintStrong') }}</strong>{{ t('cottageVault.hintAfter') }}
      </p>

      <!-- Change passphrase (re-encrypts every entry under the new key) -->
      <form v-if="mode === 'unlocked' && changing" class="vault-form change-form" @submit.prevent="doRekey">
        <h3>{{ t('cottageVault.changeTitle') }}</h3>
        <p class="sub">{{ t('cottageVault.changeSub') }}</p>
        <input
          v-model="newPass1"
          type="password"
          class="input"
          :placeholder="t('cottageVault.newPassPlaceholder')"
          autocomplete="new-password"
        />
        <div v-if="newPass1" class="pw-strength">
          <div class="pw-bar"><span class="pw-fill" :class="'s' + changeStrength"></span></div>
          <span class="pw-label">{{ STRENGTH_LABELS[changeStrength] }}</span>
        </div>
        <input
          v-model="newPass2"
          type="password"
          class="input"
          :placeholder="t('cottageVault.newPassConfirmPlaceholder')"
          autocomplete="new-password"
        />
        <p v-if="changeError" class="notice error">{{ changeError }}</p>
        <button class="btn-primary" :disabled="busy">{{ busy ? t('cottageVault.resetting') : t('cottageVault.confirmChange') }}</button>
      </form>

      <!-- Loading -->
      <p v-if="mode === 'loading'" class="state-text">{{ t('cottageVault.loading') }}</p>

      <!-- WebCrypto unavailable -->
      <div v-else-if="mode === 'unavailable'" class="notice error">
        {{ t('cottageVault.unavailableError') }}
      </div>

      <!-- First-time setup -->
      <form v-else-if="mode === 'setup'" class="vault-form" @submit.prevent="doSetup">
        <h3>{{ t('cottageVault.setupTitle') }}</h3>
        <p class="sub">{{ t('cottageVault.setupSub') }}</p>
        <input
          v-model="pass1"
          type="password"
          class="input"
          :placeholder="t('cottageVault.setupPassPlaceholder')"
          autocomplete="new-password"
        />
        <div v-if="pass1" class="pw-strength">
          <div class="pw-bar"><span class="pw-fill" :class="'s' + setupStrength"></span></div>
          <span class="pw-label">{{ STRENGTH_LABELS[setupStrength] }}</span>
        </div>
        <input
          v-model="pass2"
          type="password"
          class="input"
          :placeholder="t('cottageVault.setupPassConfirmPlaceholder')"
          autocomplete="new-password"
        />
        <p v-if="formError" class="notice error">{{ formError }}</p>
        <button class="btn-primary" :disabled="busy">{{ busy ? t('cottageVault.creating') : t('cottageVault.createVault') }}</button>
      </form>

      <!-- Locked: unlock -->
      <form v-else-if="mode === 'locked'" class="vault-form" @submit.prevent="doUnlock">
        <h3>{{ t('cottageVault.unlockTitle') }}</h3>
        <p class="sub">{{ t('cottageVault.unlockSub') }}</p>
        <input
          v-model="pass1"
          type="password"
          class="input"
          :placeholder="t('cottageVault.unlockPassPlaceholder')"
          autocomplete="current-password"
          autofocus
        />
        <p v-if="formError" class="notice error">{{ formError }}</p>
        <button class="btn-primary" :disabled="busy">{{ busy ? t('cottageVault.unlocking') : t('cottageVault.unlock') }}</button>
        <button type="button" class="link-danger" @click="confirmReset">{{ t('cottageVault.forgotReset') }}</button>
      </form>
    </article>

    <!-- Unlocked: entries -->
    <template v-if="mode === 'unlocked'">
      <article class="glass-card section-block">
        <div class="editor-head">
          <h3>{{ editing ? (editing.vid ? t('cottageVault.editEntry') : t('cottageVault.newEntry')) : t('cottageVault.myEntries') }}</h3>
          <button v-if="!editing" class="btn-primary sm" @click="startCreate">{{ t('cottageVault.createNew') }}</button>
        </div>

        <form v-if="editing" class="entry-editor" @submit.prevent="saveEntry">
          <input v-model="editing.title" class="input" :placeholder="t('cottageVault.titlePlaceholder')" maxlength="120" />
          <textarea v-model="editing.body" class="input area" :placeholder="t('cottageVault.bodyPlaceholder')" rows="6" maxlength="20000"></textarea>
          <p v-if="formError" class="notice error">{{ formError }}</p>
          <div class="editor-actions">
            <button class="btn-primary" :disabled="busy">{{ busy ? t('cottageVault.saving') : t('cottageVault.saveEncrypted') }}</button>
            <button type="button" class="ghost-btn" :disabled="busy" @click="cancelEdit">{{ t('cottageVault.cancel') }}</button>
          </div>
        </form>
      </article>

      <article class="glass-card section-block">
        <p v-if="!entries.length" class="state-text">{{ t('cottageVault.emptyEntries') }}</p>
        <ul v-else class="entry-list">
          <li v-for="e in entries" :key="e.vid" class="entry-item">
            <div class="entry-main">
              <div class="entry-title">
                {{ e.error ? t('cottageVault.decryptFailed') : (e.title || t('cottageVault.untitled')) }}
              </div>
              <pre v-if="!e.error" class="entry-body">{{ e.body }}</pre>
              <p v-else class="entry-body err">{{ t('cottageVault.decryptErrorBody') }}</p>
              <div class="entry-meta">{{ t('cottageVault.updatedAt', { time: formatTime(e.updated_at) }) }}</div>
            </div>
            <div class="entry-ops">
              <button v-if="!e.error" class="icon-btn" :title="t('cottageVault.editTitle')" @click="startEdit(e)">✏️</button>
              <button class="icon-btn" :title="t('cottageVault.deleteTitle')" @click="removeEntry(e)">🗑️</button>
            </div>
          </li>
        </ul>
      </article>
    </template>
  </div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  createVaultEntry,
  deleteVaultEntry,
  fetchVaultEntries,
  fetchVaultMeta,
  rekeyVault,
  resetVault,
  setupVault,
  updateVaultEntry,
} from "../../../lib/api";
import {
  VAULT_DEFAULTS,
  createVerifier,
  decryptJSON,
  deriveKey,
  encryptJSON,
  generateSalt,
  isCryptoAvailable,
  verifyKey,
} from "../../../lib/vaultCrypto";
import { parseError } from "../../../utils/helpers";

const showMessage = inject("showMessage", () => {});
const { t } = useI18n();

const mode = ref("loading"); // loading | unavailable | setup | locked | unlocked
const meta = ref(null);
const entries = ref([]);
const editing = ref(null);
const pass1 = ref("");
const pass2 = ref("");
const formError = ref("");
const busy = ref(false);

// Change-passphrase (re-key) state.
const changing = ref(false);
const newPass1 = ref("");
const newPass2 = ref("");
const changeError = ref("");

// Auto-lock the vault after a few minutes of inactivity so an unlocked screen
// left unattended doesn't expose decrypted content.
const IDLE_LIMIT_MS = 5 * 60 * 1000;
let idleTimer = null;

const STRENGTH_LABELS = computed(() => [
  t('cottageVault.strength0'),
  t('cottageVault.strength1'),
  t('cottageVault.strength2'),
  t('cottageVault.strength3'),
  t('cottageVault.strength4'),
]);
function passScore(p) {
  if (!p) return 0;
  let s = 0;
  if (p.length >= 6) s += 1;
  if (p.length >= 10) s += 1;
  if (/[0-9]/.test(p) && /[a-zA-Z]/.test(p)) s += 1;
  if (/[^a-zA-Z0-9]/.test(p)) s += 1;
  return Math.min(s, 4);
}
const setupStrength = computed(() => passScore(pass1.value));
const changeStrength = computed(() => passScore(newPass1.value));

// The derived key is kept in a plain (non-reactive) variable so it never leaks
// into devtools/state snapshots and is dropped the moment we lock.
let vaultKey = null;

function formatTime(value) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString();
}

function resetForm() {
  pass1.value = "";
  pass2.value = "";
  formError.value = "";
}

async function loadMeta() {
  if (!isCryptoAvailable()) {
    mode.value = "unavailable";
    return;
  }
  try {
    meta.value = await fetchVaultMeta();
    mode.value = meta.value.initialized ? "locked" : "setup";
  } catch (error) {
    showMessage(parseError(error));
  }
}

async function doSetup() {
  formError.value = "";
  if (pass1.value.length < 6) {
    formError.value = t('cottageVault.errPassTooShort');
    return;
  }
  if (pass1.value !== pass2.value) {
    formError.value = t('cottageVault.errPassMismatch');
    return;
  }
  busy.value = true;
  try {
    const salt = generateSalt();
    const key = await deriveKey(pass1.value, salt, VAULT_DEFAULTS);
    const verifier = await createVerifier(key);
    meta.value = await setupVault({
      salt,
      kdf: VAULT_DEFAULTS.kdf,
      kdf_hash: VAULT_DEFAULTS.kdf_hash,
      iterations: VAULT_DEFAULTS.iterations,
      algo: VAULT_DEFAULTS.algo,
      verifier_iv: verifier.verifier_iv,
      verifier_cipher: verifier.verifier_cipher,
    });
    vaultKey = key;
    entries.value = [];
    resetForm();
    mode.value = "unlocked";
    bumpIdle();
    showMessage(t('cottageVault.createdUnlocked'));
  } catch (error) {
    formError.value = parseError(error);
  } finally {
    busy.value = false;
  }
}

async function decryptEntries(rows) {
  const result = [];
  for (const row of rows) {
    try {
      const data = await decryptJSON(vaultKey, row.iv, row.ciphertext);
      if (data && typeof data === "object") {
        result.push({ vid: row.vid, title: data.title || "", body: data.body || "", updated_at: row.updated_at, error: false });
      } else {
        result.push({ vid: row.vid, title: "", body: "", updated_at: row.updated_at, error: true });
      }
    } catch {
      result.push({ vid: row.vid, title: "", body: "", updated_at: row.updated_at, error: true });
    }
  }
  return result;
}

async function doUnlock() {
  formError.value = "";
  if (!pass1.value) {
    formError.value = t('cottageVault.errPassRequired');
    return;
  }
  busy.value = true;
  try {
    const key = await deriveKey(pass1.value, meta.value.salt, {
      iterations: meta.value.iterations,
      kdf_hash: meta.value.kdf_hash,
    });
    const ok = await verifyKey(key, meta.value.verifier_iv, meta.value.verifier_cipher);
    if (!ok) {
      formError.value = t('cottageVault.errPassWrong');
      return;
    }
    vaultKey = key;
    const rows = await fetchVaultEntries();
    entries.value = await decryptEntries(rows);
    resetForm();
    mode.value = "unlocked";
    bumpIdle();
  } catch (error) {
    formError.value = parseError(error);
  } finally {
    busy.value = false;
  }
}

function startCreate() {
  formError.value = "";
  editing.value = { vid: null, title: "", body: "" };
}

function startEdit(entry) {
  formError.value = "";
  editing.value = { vid: entry.vid, title: entry.title, body: entry.body };
}

function cancelEdit() {
  editing.value = null;
  formError.value = "";
}

async function saveEntry() {
  if (!editing.value) return;
  const title = (editing.value.title || "").trim();
  const body = editing.value.body || "";
  if (!title && !body.trim()) {
    formError.value = t('cottageVault.errTitleBodyEmpty');
    return;
  }
  busy.value = true;
  formError.value = "";
  try {
    const payload = await encryptJSON(vaultKey, { title, body });
    if (editing.value.vid) {
      const updated = await updateVaultEntry(editing.value.vid, payload);
      const idx = entries.value.findIndex((e) => e.vid === editing.value.vid);
      if (idx >= 0) entries.value[idx] = { vid: updated.vid, title, body, updated_at: updated.updated_at, error: false };
    } else {
      const created = await createVaultEntry(payload);
      entries.value.unshift({ vid: created.vid, title, body, updated_at: created.updated_at, error: false });
    }
    editing.value = null;
    showMessage(t('cottageVault.saved'));
  } catch (error) {
    formError.value = parseError(error);
  } finally {
    busy.value = false;
  }
}

async function removeEntry(entry) {
  if (!window.confirm(t('cottageVault.confirmDelete'))) return;
  try {
    await deleteVaultEntry(entry.vid);
    entries.value = entries.value.filter((e) => e.vid !== entry.vid);
    showMessage(t('cottageVault.deleted'));
  } catch (error) {
    showMessage(parseError(error));
  }
}

function lock() {
  vaultKey = null;
  entries.value = [];
  editing.value = null;
  changing.value = false;
  newPass1.value = "";
  newPass2.value = "";
  changeError.value = "";
  clearIdle();
  resetForm();
  mode.value = "locked";
}

function clearIdle() {
  if (idleTimer) {
    clearTimeout(idleTimer);
    idleTimer = null;
  }
}

function bumpIdle() {
  if (mode.value !== "unlocked") return;
  clearIdle();
  idleTimer = setTimeout(() => {
    lock();
    showMessage(t('cottageVault.autoLocked'));
  }, IDLE_LIMIT_MS);
}

function toggleChange() {
  changing.value = !changing.value;
  changeError.value = "";
  newPass1.value = "";
  newPass2.value = "";
}

async function doRekey() {
  changeError.value = "";
  if (newPass1.value.length < 6) {
    changeError.value = t('cottageVault.errNewPassTooShort');
    return;
  }
  if (newPass1.value !== newPass2.value) {
    changeError.value = t('cottageVault.errNewPassMismatch');
    return;
  }
  if (entries.value.some((e) => e.error)) {
    changeError.value = t('cottageVault.errUndecryptable');
    return;
  }
  busy.value = true;
  try {
    const salt = generateSalt();
    const newKey = await deriveKey(newPass1.value, salt, VAULT_DEFAULTS);
    const verifier = await createVerifier(newKey);
    const reEntries = [];
    for (const e of entries.value) {
      const enc = await encryptJSON(newKey, { title: e.title, body: e.body });
      reEntries.push({ vid: e.vid, iv: enc.iv, ciphertext: enc.ciphertext });
    }
    meta.value = await rekeyVault({
      salt,
      kdf: VAULT_DEFAULTS.kdf,
      kdf_hash: VAULT_DEFAULTS.kdf_hash,
      iterations: VAULT_DEFAULTS.iterations,
      algo: VAULT_DEFAULTS.algo,
      verifier_iv: verifier.verifier_iv,
      verifier_cipher: verifier.verifier_cipher,
      entries: reEntries,
    });
    vaultKey = newKey;
    changing.value = false;
    newPass1.value = "";
    newPass2.value = "";
    showMessage(t('cottageVault.passphraseUpdated'));
  } catch (error) {
    changeError.value = parseError(error);
  } finally {
    busy.value = false;
  }
}

async function confirmReset() {
  if (!window.confirm(t('cottageVault.confirmReset'))) return;
  try {
    await resetVault();
    vaultKey = null;
    entries.value = [];
    editing.value = null;
    resetForm();
    await loadMeta(); // meta is gone → back to setup
    showMessage(t('cottageVault.vaultReset'));
  } catch (error) {
    showMessage(parseError(error));
  }
}

onMounted(() => {
  loadMeta();
  window.addEventListener("pointerdown", bumpIdle);
  window.addEventListener("keydown", bumpIdle);
});
onBeforeUnmount(() => {
  clearIdle();
  window.removeEventListener("pointerdown", bumpIdle);
  window.removeEventListener("keydown", bumpIdle);
  vaultKey = null; // drop the key when leaving the page
});
</script>

<style scoped>
.vault-view { display: grid; gap: 1rem; }
.hint { margin: 0 0 0.5rem; color: var(--text-soft); font-size: 0.85rem; line-height: 1.6; }
.state-text { color: var(--text-soft); font-size: 0.9rem; margin: 0.5rem 0; }
.notice {
  margin: 0.5rem 0;
  padding: 0.5rem 0.75rem;
  border-radius: 10px;
  font-size: 0.84rem;
}
.notice.error { background: rgba(239, 68, 68, 0.12); color: #b91c1c; }

.vault-form { display: grid; gap: 0.7rem; max-width: 420px; }
.vault-form h3 { margin: 0; color: #2f3754; }
.vault-form .sub { margin: 0; font-size: 0.84rem; color: var(--text-soft); }
.input {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-radius: 10px;
  font-size: 0.9rem;
  box-sizing: border-box;
  background: #fff;
}
.input.area { resize: vertical; font-family: inherit; line-height: 1.5; }
.btn-primary {
  border: none;
  background: linear-gradient(120deg, #ff8ab5, #8f9bff);
  color: #fff;
  border-radius: 999px;
  padding: 0.5rem 1.2rem;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  justify-self: start;
}
.btn-primary.sm { padding: 0.35rem 0.9rem; font-size: 0.82rem; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.ghost-btn {
  border: 1px solid rgba(148, 163, 184, 0.45);
  background: #fff;
  border-radius: 999px;
  padding: 0.35rem 0.9rem;
  font-size: 0.82rem;
  cursor: pointer;
}
.link-danger {
  background: none;
  border: none;
  color: #b91c1c;
  font-size: 0.8rem;
  cursor: pointer;
  justify-self: start;
  padding: 0;
  text-decoration: underline;
}
.head-actions { display: flex; gap: 0.5rem; }
.change-form { margin-top: 0.75rem; }

.pw-strength { display: flex; align-items: center; gap: 0.5rem; }
.pw-bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.25);
  overflow: hidden;
}
.pw-fill { display: block; height: 100%; width: 0; border-radius: 999px; transition: width 0.2s ease, background 0.2s ease; }
.pw-fill.s0 { width: 8%; background: #ef4444; }
.pw-fill.s1 { width: 30%; background: #f97316; }
.pw-fill.s2 { width: 55%; background: #f59e0b; }
.pw-fill.s3 { width: 80%; background: #10b981; }
.pw-fill.s4 { width: 100%; background: #16a34a; }
.pw-label { font-size: 0.74rem; color: var(--text-soft); white-space: nowrap; }

.editor-head, .section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}
.editor-head h3 { margin: 0; color: #2f3754; font-size: 1rem; }
.entry-editor { display: grid; gap: 0.6rem; margin-top: 0.75rem; }
.editor-actions { display: flex; gap: 0.6rem; }

.entry-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.6rem; }
.entry-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 0.9rem;
  border-radius: 12px;
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid rgba(148, 163, 184, 0.18);
}
.entry-main { min-width: 0; flex: 1; }
.entry-title { font-weight: 600; color: #2f3754; margin-bottom: 0.25rem; }
.entry-body {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 0.86rem;
  color: #475569;
}
.entry-body.err { color: #b91c1c; }
.entry-meta { margin-top: 0.4rem; font-size: 0.72rem; color: var(--text-soft); }
.entry-ops { display: flex; gap: 0.3rem; flex: 0 0 auto; }
.icon-btn {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 1rem;
  padding: 0.2rem 0.35rem;
  border-radius: 8px;
}
.icon-btn:hover { background: rgba(148, 163, 184, 0.2); }
</style>
