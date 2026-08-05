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
  <div class="content-section privacy-center">
    <header class="privacy-header">
      <div class="privacy-heading">
        <span class="privacy-heading-icon" aria-hidden="true">
          <ShieldCheck :size="24" :stroke-width="2" />
        </span>
        <div>
          <h1>{{ t('privacyCenter.title') }}</h1>
          <p>{{ t('privacyCenter.subtitle') }}</p>
        </div>
      </div>
      <button class="icon-button" type="button" :disabled="loading" :aria-label="t('privacyCenter.refreshAria')" :title="t('privacyCenter.refresh')" @click="loadSummary">
        <RefreshCw :size="18" :stroke-width="2" :class="{ 'is-spinning': loading }" aria-hidden="true" />
      </button>
    </header>

    <div v-if="loading && !summary" class="privacy-loading" :aria-label="t('privacyCenter.loadingAria')">
      <span v-for="index in 4" :key="index" class="loading-block"></span>
    </div>

    <div v-else-if="loadError && !summary" class="privacy-error" role="alert">
      <AlertTriangle :size="20" :stroke-width="2" aria-hidden="true" />
      <div>
        <strong>{{ t('privacyCenter.loadErrorTitle') }}</strong>
        <p>{{ loadError }}</p>
      </div>
      <button type="button" class="text-button" @click="loadSummary">{{ t('privacyCenter.retry') }}</button>
    </div>

    <template v-else-if="summary">
      <section class="overview-band" :aria-label="t('privacyCenter.overviewAria')">
        <div v-for="item in overviewItems" :key="item.key" class="overview-item">
          <component :is="item.icon" :size="19" :stroke-width="2" aria-hidden="true" />
          <div>
            <strong>{{ item.value }}</strong>
            <span>{{ item.label }}</span>
          </div>
        </div>
      </section>

      <div class="accuracy-note">
        <Info :size="18" :stroke-width="2" aria-hidden="true" />
        <p>
          {{ t('privacyCenter.accuracyNote') }}
        </p>
      </div>

      <section class="privacy-section" aria-labelledby="visibility-title">
        <div class="section-title-row">
          <div>
            <h2 id="visibility-title">{{ t('privacyCenter.visibilityTitle') }}</h2>
            <p>{{ t('privacyCenter.visibilityDesc') }}</p>
          </div>
          <span class="snapshot-time">{{ t('privacyCenter.updatedAt', { date: formatDate(summary.generated_at) }) }}</span>
        </div>

        <div class="visibility-table-wrap">
          <table class="visibility-table">
            <thead>
              <tr>
                <th scope="col">{{ t('privacyCenter.colContent') }}</th>
                <th scope="col">{{ t('privacyCenter.colTotal') }}</th>
                <th scope="col">{{ t('privacyCenter.colPublic') }}</th>
                <th scope="col">{{ t('privacyCenter.colSignedIn') }}</th>
                <th scope="col">{{ t('privacyCenter.colPartners') }}</th>
                <th scope="col">{{ t('privacyCenter.colAuthorOnly') }}</th>
                <th scope="col">{{ t('privacyCenter.colPassword') }}</th>
                <th scope="col">{{ t('privacyCenter.colServerUnreadable') }}</th>
                <th scope="col"><span class="sr-only">{{ t('privacyCenter.colManageSr') }}</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in summary.modules" :key="item.key">
                <th scope="row">
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.note }}</span>
                  <small v-if="item.protection.server_masked">
                    {{ t('privacyCenter.legacyMask', { n: item.protection.server_masked }) }}
                  </small>
                </th>
                <td class="count-total">{{ item.total }}</td>
                <td>{{ displayCount(item.access.public) }}</td>
                <td>{{ displayCount(item.access.signed_in) }}</td>
                <td>{{ displayCount(item.access.partners) }}</td>
                <td>{{ displayCount(item.access.author_only) }}</td>
                <td>{{ displayCount(item.access.password) }}</td>
                <td>
                  <span v-if="item.protection.end_to_end_encrypted" class="e2ee-count">
                    {{ item.protection.end_to_end_encrypted }}
                  </span>
                  <span v-else class="zero-count">0</span>
                </td>
                <td>
                  <router-link :to="item.manage_path" class="row-link" :aria-label="t('privacyCenter.manageAria', { label: item.label })" :title="t('privacyCenter.manage')">
                    <ExternalLink :size="17" :stroke-width="2" aria-hidden="true" />
                  </router-link>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="privacy-section" aria-labelledby="encryption-title">
        <div class="section-title-row">
          <div>
            <h2 id="encryption-title">{{ t('privacyCenter.encryptionTitle') }}</h2>
            <p>{{ t('privacyCenter.encryptionDesc') }}</p>
          </div>
          <span class="local-only-label">{{ t('privacyCenter.localOnlyLabel') }}</span>
        </div>

        <div class="encryption-list">
          <article v-for="item in summary.encryption" :key="item.scope" class="encryption-row">
            <div class="encryption-main">
              <span class="encryption-icon" aria-hidden="true">
                <MessageCircle v-if="item.scope === 'chat'" :size="20" :stroke-width="2" />
                <KeyRound v-else :size="20" :stroke-width="2" />
              </span>
              <div>
                <div class="encryption-name-line">
                  <h3>{{ item.label }}</h3>
                  <span :class="['state-label', item.initialized ? 'state-label--ok' : 'state-label--off']">
                    {{ item.initialized ? t('privacyCenter.stateEnabled') : t('privacyCenter.stateDisabled') }}
                  </span>
                </div>
                <p v-if="item.initialized">
                  {{ t('privacyCenter.kdfInfo', { algo: item.algorithm, kdf: item.kdf, iterations: formatNumber(item.iterations) }) }}
                </p>
                <p v-else>{{ t('privacyCenter.setupHint') }}</p>
                <small>
                  {{ t('privacyCenter.cipherCount', { encrypted: item.encrypted_count, total: item.item_count }) }}
                  <template v-if="localRecoveryLabel(item.scope)"> · {{ localRecoveryLabel(item.scope) }}</template>
                </small>
              </div>
            </div>
            <div class="encryption-actions">
              <router-link :to="item.manage_path" class="secondary-button">{{ t('privacyCenter.configure') }}</router-link>
              <button type="button" class="secondary-button" :disabled="!item.initialized || !cryptoAvailable" @click="openRecovery('recover', item)">
                <Upload :size="16" :stroke-width="2" aria-hidden="true" />
                {{ t('privacyCenter.useRecoveryKit') }}
              </button>
              <button type="button" class="primary-button" :disabled="!item.initialized || !cryptoAvailable" @click="openRecovery('create', item)">
                <Download :size="16" :stroke-width="2" aria-hidden="true" />
                {{ t('privacyCenter.createRecoveryKit') }}
              </button>
            </div>
          </article>
        </div>
        <p v-if="!cryptoAvailable" class="inline-warning" role="alert">
          {{ t('privacyCenter.cryptoUnavailable') }}
        </p>
      </section>

      <div class="lower-grid">
        <section class="privacy-section export-section" aria-labelledby="export-title">
          <div class="section-title-row">
            <div>
              <h2 id="export-title">{{ t('privacyCenter.exportTitle') }}</h2>
              <p>{{ t('privacyCenter.exportDesc') }}</p>
            </div>
            <router-link to="/admin/export" class="row-link" :aria-label="t('privacyCenter.openExportAria')" :title="t('privacyCenter.openExport')">
              <ExternalLink :size="17" :stroke-width="2" aria-hidden="true" />
            </router-link>
          </div>
          <ul class="fact-list">
            <li
              v-for="item in exportFacts"
              :key="item.key"
              :class="['fact-item', { 'fact-item--warning': item.warning }]"
            >
              <AlertTriangle v-if="item.warning" :size="18" :stroke-width="2" aria-hidden="true" />
              <CheckCircle2 v-else :size="18" :stroke-width="2" aria-hidden="true" />
              <span>{{ item.text }}</span>
            </li>
          </ul>
        </section>

        <section class="privacy-section account-section" aria-labelledby="account-title">
          <div class="section-title-row">
            <div>
              <h2 id="account-title">{{ t('privacyCenter.accountTitle') }}</h2>
              <p>{{ summary.account.nickname }}</p>
            </div>
            <router-link to="/admin/security" class="row-link" :aria-label="t('privacyCenter.openSecurityAria')" :title="t('privacyCenter.openSecurity')">
              <ExternalLink :size="17" :stroke-width="2" aria-hidden="true" />
            </router-link>
          </div>
          <dl class="account-list">
            <div>
              <dt>{{ t('privacyCenter.lastLogin') }}</dt>
              <dd>{{ formatDate(summary.account.last_login_at) }}</dd>
            </div>
            <div>
              <dt>{{ t('privacyCenter.lastLoginIp') }}</dt>
              <dd>{{ summary.account.last_login_ip || t('privacyCenter.notRecorded') }}</dd>
            </div>
            <div>
              <dt>{{ t('privacyCenter.passwordChanged') }}</dt>
              <dd>{{ formatDate(summary.account.password_changed_at) }}</dd>
            </div>
            <div>
              <dt>{{ t('privacyCenter.sessionVersion') }}</dt>
              <dd>v{{ summary.account.session_version }}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section class="privacy-section" aria-labelledby="activity-title">
        <div class="section-title-row">
          <div>
            <h2 id="activity-title">{{ t('privacyCenter.activityTitle') }}</h2>
            <p>{{ summary.activity_scope }}</p>
          </div>
          <router-link to="/admin/security" class="text-link">{{ t('privacyCenter.viewFullLog') }}</router-link>
        </div>
        <ol v-if="summary.recent_activity.length" class="activity-list">
          <li v-for="item in summary.recent_activity" :key="item.log_id" class="activity-item">
            <span :class="['activity-mark', item.result === 'success' ? 'activity-mark--ok' : 'activity-mark--fail']" aria-hidden="true"></span>
            <div class="activity-body">
              <div>
                <strong>{{ activityLabel(item.action) }}</strong>
                <span>{{ item.actor || t('privacyCenter.unknownVisitor') }}</span>
              </div>
              <p v-if="item.resource_name">{{ item.resource_name }}</p>
            </div>
            <time :datetime="item.created_at">{{ formatDate(item.created_at) }}</time>
          </li>
        </ol>
        <p v-else class="empty-state">{{ t('privacyCenter.noActivity') }}</p>
      </section>
    </template>

    <Teleport to="body">
      <div v-if="recoveryDialogOpen" class="recovery-overlay" @click.self="closeRecovery">
        <section class="recovery-dialog" role="dialog" aria-modal="true" :aria-labelledby="recoveryTitleId">
          <header class="recovery-dialog-header">
            <div>
              <h2 :id="recoveryTitleId">{{ recoveryTitle }}</h2>
              <p>{{ recoveryTarget?.label }}</p>
            </div>
            <button type="button" class="icon-button" :aria-label="t('privacyCenter.closeAria')" :title="t('privacyCenter.close')" @click="closeRecovery">
              <X :size="18" :stroke-width="2" aria-hidden="true" />
            </button>
          </header>

          <form v-if="recoveryMode === 'create' && !createdRecoveryCode" class="recovery-form" @submit.prevent="createKit">
            <label class="form-label" for="recovery-current-passphrase">{{ t('privacyCenter.currentPassphrase') }}</label>
            <input
              id="recovery-current-passphrase"
              ref="secretInput"
              v-model="recoveryPassphrase"
              class="form-input"
              type="password"
              autocomplete="current-password"
              maxlength="256"
              required
            />
            <p class="form-help">{{ t('privacyCenter.passphraseHelp') }}</p>
            <p v-if="recoveryError" class="form-error" role="alert">{{ recoveryError }}</p>
            <button class="primary-button recovery-submit" type="submit" :disabled="recoveryBusy">
              <Download :size="16" :stroke-width="2" aria-hidden="true" />
              {{ recoveryBusy ? t('privacyCenter.generating') : t('privacyCenter.verifyAndDownload') }}
            </button>
          </form>

          <div v-else-if="recoveryMode === 'create'" class="recovery-result">
            <div class="result-status">
              <CheckCircle2 :size="20" :stroke-width="2" aria-hidden="true" />
              <strong>{{ t('privacyCenter.kitDownloaded') }}</strong>
            </div>
            <p>{{ t('privacyCenter.kitResultHelp') }}</p>
            <div class="secret-output">
              <code>{{ createdRecoveryCode }}</code>
              <button type="button" class="icon-button" :aria-label="t('privacyCenter.copyCodeAria')" :title="t('privacyCenter.copyCodeTitle')" @click="copySecret(createdRecoveryCode)">
                <Copy :size="17" :stroke-width="2" aria-hidden="true" />
              </button>
            </div>
            <button type="button" class="primary-button recovery-submit" @click="closeRecovery">{{ t('privacyCenter.done') }}</button>
          </div>

          <form v-else-if="!recoveredPassphrase" class="recovery-form" @submit.prevent="recoverKit">
            <label class="file-picker" :class="{ 'file-picker--selected': recoveryFileName }">
              <FileArchive :size="20" :stroke-width="2" aria-hidden="true" />
              <span>{{ recoveryFileName || t('privacyCenter.pickRecoveryJson') }}</span>
              <input type="file" accept="application/json,.json" @change="selectRecoveryFile" />
            </label>
            <label class="form-label" for="recovery-code">{{ t('privacyCenter.recoveryCodeLabel') }}</label>
            <input
              id="recovery-code"
              ref="secretInput"
              v-model="recoveryCode"
              class="form-input recovery-code-input"
              type="password"
              autocomplete="off"
              maxlength="80"
              required
            />
            <p class="form-help">{{ t('privacyCenter.recoverHelp') }}</p>
            <p v-if="recoveryError" class="form-error" role="alert">{{ recoveryError }}</p>
            <button class="primary-button recovery-submit" type="submit" :disabled="recoveryBusy || !recoveryKitRaw">
              <KeyRound :size="16" :stroke-width="2" aria-hidden="true" />
              {{ recoveryBusy ? t('privacyCenter.verifying') : t('privacyCenter.recoverPassphrase') }}
            </button>
          </form>

          <div v-else class="recovery-result">
            <div class="result-status">
              <CheckCircle2 :size="20" :stroke-width="2" aria-hidden="true" />
              <strong>{{ t('privacyCenter.kitValid') }}</strong>
            </div>
            <p>{{ t('privacyCenter.kitValidHelp') }}</p>
            <div class="secret-output">
              <input :type="showRecoveredPassphrase ? 'text' : 'password'" :value="recoveredPassphrase" readonly :aria-label="t('privacyCenter.recoveredPassphraseAria')" />
              <button type="button" class="icon-button" :aria-label="showRecoveredPassphrase ? t('privacyCenter.hidePassphraseAria') : t('privacyCenter.showPassphraseAria')" :title="showRecoveredPassphrase ? t('privacyCenter.hidePassphraseAria') : t('privacyCenter.showPassphraseAria')" @click="showRecoveredPassphrase = !showRecoveredPassphrase">
                <EyeOff v-if="showRecoveredPassphrase" :size="17" :stroke-width="2" aria-hidden="true" />
                <Eye v-else :size="17" :stroke-width="2" aria-hidden="true" />
              </button>
              <button type="button" class="icon-button" :aria-label="t('privacyCenter.copyPassphraseAria')" :title="t('privacyCenter.copyPassphraseTitle')" @click="copySecret(recoveredPassphrase)">
                <Copy :size="17" :stroke-width="2" aria-hidden="true" />
              </button>
            </div>
            <button type="button" class="primary-button recovery-submit" @click="closeRecovery">{{ t('privacyCenter.done') }}</button>
          </div>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  Eye,
  EyeOff,
  FileArchive,
  Globe,
  Info,
  KeyRound,
  LockKeyhole,
  MessageCircle,
  RefreshCw,
  ShieldCheck,
  Upload,
  Users,
  X,
} from "@lucide/vue";
import {
  fetchChatKeyMeta,
  fetchPrivacySummary,
  fetchVaultMeta,
  recordPrivacyRecoveryEvent,
} from "../lib/api";
import { verifyChatPassphrase } from "../lib/chatCrypto";
import {
  createRecoveryKit,
  encryptionMetaFingerprint,
  parseRecoveryKit,
  recoverPassphrase as recoverPassphraseFromKit,
  recoveryKitConstants,
} from "../lib/privacyRecovery";
import { deriveKey, isCryptoAvailable, verifyKey } from "../lib/vaultCrypto";
import { parseError } from "../utils/helpers";

const { t } = useI18n();

const LOCAL_RECOVERY_META_KEY = "love_privacy_recovery_meta_v1";
const showMessage = inject("showMessage", () => {});

const summary = ref(null);
const loading = ref(false);
const loadError = ref("");
const localRecoveryMeta = ref(readLocalRecoveryMeta());
const cryptoAvailable = computed(() => isCryptoAvailable());

const recoveryDialogOpen = ref(false);
const recoveryMode = ref("create");
const recoveryTarget = ref(null);
const recoveryPassphrase = ref("");
const recoveryCode = ref("");
const recoveryKitRaw = ref(null);
const recoveryFileName = ref("");
const recoveryError = ref("");
const recoveryBusy = ref(false);
const createdRecoveryCode = ref("");
const recoveredPassphrase = ref("");
const showRecoveredPassphrase = ref(false);
const secretInput = ref(null);

const recoveryTitleId = "privacy-recovery-title";
const recoveryTitle = computed(() => recoveryMode.value === "create" ? t('privacyCenter.createKitTitle') : t('privacyCenter.useKitTitle'));

const overviewItems = computed(() => [
  { key: "public", label: t('privacyCenter.overviewPublic'), value: summary.value?.totals.public || 0, icon: Globe },
  { key: "partners", label: t('privacyCenter.overviewPartners'), value: summary.value?.totals.partners || 0, icon: Users },
  { key: "password", label: t('privacyCenter.overviewPassword'), value: summary.value?.totals.password || 0, icon: LockKeyhole },
  {
    key: "e2ee",
    label: t('privacyCenter.overviewE2ee'),
    value: summary.value?.protection.end_to_end_encrypted || 0,
    icon: ShieldCheck,
  },
]);

const exportFacts = computed(() => {
  const policy = summary.value?.export_policy;
  if (!policy) return [];

  return [
    {
      key: "archive",
      warning: !policy.archive_encrypted,
      text: policy.archive_encrypted
        ? t('privacyCenter.exportArchiveEncrypted')
        : t('privacyCenter.exportArchivePlain'),
    },
    {
      key: "server-content",
      warning: policy.server_readable_content_plaintext,
      text: policy.server_readable_content_plaintext
        ? t('privacyCenter.exportServerPlain')
        : t('privacyCenter.exportServerEncrypted'),
    },
    {
      key: "e2ee",
      warning: policy.end_to_end_content_plaintext,
      text: policy.end_to_end_content_plaintext
        ? t('privacyCenter.exportE2eePlain')
        : t('privacyCenter.exportE2eeEncrypted'),
    },
    {
      key: "secrets",
      warning: policy.account_password_hashes_included || policy.encryption_passphrases_included,
      text: policy.account_password_hashes_included || policy.encryption_passphrases_included
        ? t('privacyCenter.exportSecretsIncluded')
        : t('privacyCenter.exportSecretsExcluded'),
    },
    {
      key: "uploads",
      warning: policy.uploads_included,
      text: policy.uploads_included
        ? t('privacyCenter.exportUploadsIncluded')
        : t('privacyCenter.exportUploadsExcluded'),
    },
    {
      key: "push",
      warning: policy.push_credentials_included,
      text: policy.push_credentials_included
        ? t('privacyCenter.exportPushIncluded')
        : t('privacyCenter.exportPushExcluded'),
    },
  ];
});

function readLocalRecoveryMeta() {
  try {
    const value = JSON.parse(window.localStorage.getItem(LOCAL_RECOVERY_META_KEY) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch (_) {
    return {};
  }
}

function saveLocalRecoveryMeta(scope, fingerprint, createdAt) {
  const next = { ...localRecoveryMeta.value, [scope]: { fingerprint, created_at: createdAt } };
  localRecoveryMeta.value = next;
  try {
    window.localStorage.setItem(LOCAL_RECOVERY_META_KEY, JSON.stringify(next));
  } catch (_) {
    // The recovery file and code are already in the user's possession. This
    // metadata is only a local reminder and must not make creation fail.
  }
}

function localRecoveryLabel(scope) {
  const item = localRecoveryMeta.value?.[scope];
  return item?.created_at ? t('privacyCenter.localRecoveryRecorded', { date: formatDate(item.created_at) }) : t('privacyCenter.localRecoveryNone');
}

async function loadSummary() {
  loading.value = true;
  loadError.value = "";
  try {
    summary.value = await fetchPrivacySummary();
  } catch (error) {
    loadError.value = parseError(error);
  } finally {
    loading.value = false;
  }
}

function displayCount(value) {
  return Number(value || 0) || "0";
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-CN");
}

function formatDate(value) {
  if (!value) return t('privacyCenter.notRecorded');
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? t('privacyCenter.notRecorded')
    : date.toLocaleString("zh-CN", { hour12: false, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function activityLabel(action) {
  return {
    "auth.login": t('privacyCenter.activityLogin'),
    "auth.logout": t('privacyCenter.activityLogout'),
    "security.change_password": t('privacyCenter.activityChangePassword'),
    "security.reset_password": t('privacyCenter.activityResetPassword'),
    "security.revoke_sessions": t('privacyCenter.activityRevokeSessions'),
    "security.revoke_own_sessions": t('privacyCenter.activityRevokeOwnSessions'),
    "security.unlock_account": t('privacyCenter.activityUnlockAccount'),
    "backup.export": t('privacyCenter.activityExport'),
    "backup.auto": t('privacyCenter.activityAutoBackup'),
    "backup.restore": t('privacyCenter.activityRestore'),
    "content.access": t('privacyCenter.activityAccess'),
    "privacy.key_setup": t('privacyCenter.activityKeySetup'),
    "privacy.key_rotated": t('privacyCenter.activityKeyRotated'),
    "privacy.vault_reset": t('privacyCenter.activityVaultReset'),
    "privacy.recovery_kit_created": t('privacyCenter.activityKitCreated'),
    "privacy.recovery_kit_recovered": t('privacyCenter.activityKitRecovered'),
  }[action] || action;
}

async function fetchEncryptionMeta(scope) {
  return scope === "chat" ? fetchChatKeyMeta() : fetchVaultMeta();
}

async function verifyPassphrase(scope, passphrase, meta) {
  if (scope === "chat") return verifyChatPassphrase(passphrase, meta);
  const key = await deriveKey(passphrase, meta.salt, {
    iterations: meta.iterations,
    kdf_hash: meta.kdf_hash,
  });
  return verifyKey(key, meta.verifier_iv, meta.verifier_cipher);
}

function resetRecoveryState() {
  recoveryPassphrase.value = "";
  recoveryCode.value = "";
  recoveryKitRaw.value = null;
  recoveryFileName.value = "";
  recoveryError.value = "";
  recoveryBusy.value = false;
  createdRecoveryCode.value = "";
  recoveredPassphrase.value = "";
  showRecoveredPassphrase.value = false;
}

function openRecovery(mode, item) {
  resetRecoveryState();
  recoveryMode.value = mode;
  recoveryTarget.value = item;
  recoveryDialogOpen.value = true;
  nextTick(() => secretInput.value?.focus());
}

function closeRecovery() {
  recoveryDialogOpen.value = false;
  recoveryTarget.value = null;
  resetRecoveryState();
}

async function createKit() {
  if (!recoveryTarget.value || recoveryBusy.value) return;
  recoveryBusy.value = true;
  recoveryError.value = "";
  try {
    const scope = recoveryTarget.value.scope;
    const meta = await fetchEncryptionMeta(scope);
    if (!meta?.initialized) throw new Error(t('privacyCenter.notInitialized'));
    if (!(await verifyPassphrase(scope, recoveryPassphrase.value, meta))) throw new Error(t('privacyCenter.passphraseIncorrect'));

    const fingerprint = await encryptionMetaFingerprint(scope, meta);
    const { kit, recoveryCode: code } = await createRecoveryKit({
      scope,
      passphrase: recoveryPassphrase.value,
      fingerprint,
    });
    downloadKit(kit);
    saveLocalRecoveryMeta(scope, fingerprint, kit.created_at);
    recoveryPassphrase.value = "";
    createdRecoveryCode.value = code;
    recordPrivacyRecoveryEvent(scope, "kit_created").then(loadSummary).catch(() => {});
  } catch (error) {
    recoveryError.value = parseError(error);
  } finally {
    recoveryBusy.value = false;
  }
}

function downloadKit(kit) {
  const blob = new Blob([JSON.stringify(kit, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `love-recovery-${kit.scope}-${kit.created_at.slice(0, 10)}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
}

async function selectRecoveryFile(event) {
  recoveryError.value = "";
  recoveryKitRaw.value = null;
  const file = event.target.files?.[0];
  if (!file) return;
  recoveryFileName.value = file.name;
  try {
    if (file.size > recoveryKitConstants.maxBytes) throw new Error(t('privacyCenter.kitTooLarge'));
    recoveryKitRaw.value = parseRecoveryKit(await file.text());
  } catch (error) {
    recoveryFileName.value = "";
    recoveryError.value = parseError(error);
  }
}

async function recoverKit() {
  if (!recoveryTarget.value || !recoveryKitRaw.value || recoveryBusy.value) return;
  recoveryBusy.value = true;
  recoveryError.value = "";
  try {
    const scope = recoveryTarget.value.scope;
    const meta = await fetchEncryptionMeta(scope);
    if (!meta?.initialized) throw new Error(t('privacyCenter.notInitialized'));
    const fingerprint = await encryptionMetaFingerprint(scope, meta);
    const passphrase = await recoverPassphraseFromKit({
      kit: recoveryKitRaw.value,
      recoveryCode: recoveryCode.value,
      expectedScope: scope,
      expectedFingerprint: fingerprint,
    });
    if (!(await verifyPassphrase(scope, passphrase, meta))) throw new Error(t('privacyCenter.recoveredPassphraseInvalid'));
    recoveryCode.value = "";
    recoveredPassphrase.value = passphrase;
    recordPrivacyRecoveryEvent(scope, "kit_recovered").then(loadSummary).catch(() => {});
  } catch (error) {
    recoveryError.value = parseError(error);
  } finally {
    recoveryBusy.value = false;
  }
}

async function copySecret(value) {
  try {
    await navigator.clipboard.writeText(value);
    showMessage(t('privacyCenter.copiedToClipboard'));
  } catch (_) {
    showMessage(t('privacyCenter.clipboardDenied'), "error");
  }
}

function onKeydown(event) {
  if (event.key === "Escape" && recoveryDialogOpen.value) closeRecovery();
}

onMounted(() => {
  window.addEventListener("keydown", onKeydown);
  loadSummary();
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
  resetRecoveryState();
});
</script>

<style scoped>
.privacy-center {
  width: 100%;
  grid-template-columns: minmax(0, 1fr);
  gap: 1.1rem;
  max-width: 1180px;
  margin-left: auto;
  margin-right: auto;
}

.privacy-header,
.privacy-heading,
.section-title-row,
.encryption-main,
.encryption-actions,
.privacy-error,
.fact-item,
.result-status,
.secret-output {
  display: flex;
  align-items: center;
}

.privacy-header,
.section-title-row {
  justify-content: space-between;
  gap: 1rem;
}

.privacy-heading {
  gap: 0.75rem;
}

.privacy-heading-icon,
.encryption-icon {
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: #23685f;
  background: var(--mint-soft);
  border-radius: var(--radius-control);
}

.privacy-heading-icon {
  width: 46px;
  height: 46px;
}

.privacy-header h1 {
  margin: 0;
  color: var(--text-main);
  font-size: 1.45rem;
  letter-spacing: 0;
}

.privacy-header p,
.section-title-row p,
.encryption-main p,
.encryption-main small,
.recovery-dialog-header p,
.recovery-result p {
  color: var(--text-soft);
}

.privacy-header p,
.section-title-row p,
.encryption-main p,
.encryption-main small,
.recovery-dialog-header p {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  line-height: 1.5;
}

.icon-button {
  width: 40px;
  height: 40px;
  display: inline-grid;
  place-items: center;
  flex: 0 0 auto;
  padding: 0;
  color: var(--text-main);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  cursor: pointer;
}

.icon-button:hover:not(:disabled) {
  color: var(--brand-strong);
  border-color: #efc3d1;
  background: var(--brand-soft);
}

.icon-button:disabled,
.primary-button:disabled,
.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.privacy-loading,
.overview-band {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.privacy-loading {
  gap: 0.75rem;
}

.loading-block {
  min-height: 78px;
  border-radius: var(--radius-control);
  background: linear-gradient(90deg, #e8efec 25%, #f7faf8 50%, #e8efec 75%);
  background-size: 200% 100%;
  animation: privacy-shimmer 1.2s infinite linear;
}

@keyframes privacy-shimmer {
  to { background-position: -200% 0; }
}

.privacy-error {
  gap: 0.75rem;
  padding: 1rem;
  color: #8f344c;
  border: 1px solid #efb9c8;
  border-radius: var(--radius-control);
  background: #fff2f5;
}

.privacy-error div { flex: 1; }
.privacy-error strong { display: block; }
.privacy-error p { margin: 0.2rem 0 0; font-size: 0.82rem; }

.text-button,
.text-link {
  color: var(--brand-strong);
  border: 0;
  background: transparent;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

.overview-band {
  border-top: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
  background: var(--surface-raised);
}

.overview-item {
  min-height: 84px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.7rem;
  padding: 0.9rem 1rem;
  color: #356d65;
}

.overview-item + .overview-item { border-left: 1px solid var(--border-subtle); }
.overview-item div { display: grid; gap: 0.1rem; }
.overview-item strong { color: var(--text-main); font-size: 1.3rem; line-height: 1; }
.overview-item span { color: var(--text-soft); font-size: 0.75rem; }

.accuracy-note {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  padding: 0.8rem 0.9rem;
  color: #5f5638;
  border-left: 3px solid #c99a39;
  background: #fff9e8;
}

.accuracy-note svg { flex: 0 0 auto; margin-top: 0.05rem; }
.accuracy-note p { margin: 0; font-size: 0.82rem; line-height: 1.6; }

.privacy-section {
  padding: 1rem 0;
  border-top: 1px solid var(--border-subtle);
}

.section-title-row { align-items: flex-start; margin-bottom: 0.85rem; }
.section-title-row h2 { margin: 0; font-size: 1.05rem; color: var(--text-main); }
.snapshot-time,
.local-only-label { color: var(--text-soft); font-size: 0.72rem; white-space: nowrap; }

.visibility-table-wrap { overflow-x: auto; border: 1px solid var(--border-subtle); border-radius: var(--radius-control); }
.visibility-table { width: 100%; min-width: 920px; border-collapse: collapse; background: var(--surface-raised); }
.visibility-table th,
.visibility-table td { padding: 0.72rem 0.65rem; border-bottom: 1px solid var(--border-subtle); text-align: center; font-size: 0.78rem; }
.visibility-table thead th { color: var(--text-soft); background: var(--surface-subtle); font-size: 0.72rem; font-weight: 700; }
.visibility-table tbody tr:last-child th,
.visibility-table tbody tr:last-child td { border-bottom: 0; }
.visibility-table tbody th { width: 290px; text-align: left; }
.visibility-table tbody th strong,
.visibility-table tbody th span,
.visibility-table tbody th small { display: block; }
.visibility-table tbody th strong { color: var(--text-main); font-size: 0.84rem; }
.visibility-table tbody th span { margin-top: 0.15rem; color: var(--text-soft); font-size: 0.7rem; font-weight: 400; line-height: 1.45; }
.visibility-table tbody th small { margin-top: 0.2rem; color: #9a5b21; font-size: 0.66rem; font-weight: 600; }
.count-total { color: var(--text-main); font-weight: 800; }
.zero-count { color: #9aa7a2; }
.e2ee-count { display: inline-grid; min-width: 24px; min-height: 24px; place-items: center; color: #17685e; background: var(--mint-soft); border-radius: 6px; font-weight: 800; }
.row-link { width: 34px; height: 34px; display: inline-grid; place-items: center; color: var(--text-soft); border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--surface-raised); text-decoration: none; }
.row-link:hover { color: var(--brand-strong); border-color: #efc3d1; }

.encryption-list { border: 1px solid var(--border-subtle); border-radius: var(--radius-control); background: var(--surface-raised); }
.encryption-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem; }
.encryption-row + .encryption-row { border-top: 1px solid var(--border-subtle); }
.encryption-main { gap: 0.75rem; min-width: 0; }
.encryption-icon { width: 40px; height: 40px; }
.encryption-name-line { display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem; }
.encryption-name-line h3 { margin: 0; font-size: 0.9rem; color: var(--text-main); }
.state-label { padding: 0.15rem 0.42rem; border-radius: 6px; font-size: 0.65rem; font-weight: 700; }
.state-label--ok { color: #17685e; background: var(--mint-soft); }
.state-label--off { color: #755f28; background: #fff3cf; }
.encryption-actions { justify-content: flex-end; flex-wrap: wrap; gap: 0.5rem; }

.primary-button,
.secondary-button {
  min-height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.45rem 0.75rem;
  border-radius: 8px;
  font-size: 0.76rem;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

.primary-button { color: #fff; border: 1px solid #2b756b; background: #2b756b; }
.primary-button:hover:not(:disabled) { background: #23685f; }
.secondary-button { color: var(--text-main); border: 1px solid var(--border-strong); background: var(--surface-raised); }
.secondary-button:hover:not(:disabled) { border-color: #8ebbb2; background: var(--mint-soft); }
.inline-warning { margin: 0.7rem 0 0; color: #8b5a22; font-size: 0.78rem; }

.lower-grid { display: grid; grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.75fr); gap: 1.25rem; }
.fact-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.6rem; }
.fact-item { align-items: flex-start; gap: 0.55rem; color: var(--text-main); font-size: 0.78rem; line-height: 1.55; }
.fact-item svg { flex: 0 0 auto; color: #2b756b; margin-top: 0.08rem; }
.fact-item--warning svg { color: #b27628; }
.account-list { margin: 0; display: grid; gap: 0; }
.account-list div { display: flex; justify-content: space-between; gap: 1rem; padding: 0.62rem 0; border-bottom: 1px solid var(--border-subtle); }
.account-list div:last-child { border-bottom: 0; }
.account-list dt { color: var(--text-soft); font-size: 0.74rem; }
.account-list dd { margin: 0; color: var(--text-main); font-size: 0.78rem; text-align: right; overflow-wrap: anywhere; }

.activity-list { list-style: none; margin: 0; padding: 0; }
.activity-item { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; align-items: center; gap: 0.7rem; padding: 0.7rem 0; }
.activity-item + .activity-item { border-top: 1px solid var(--border-subtle); }
.activity-mark { width: 8px; height: 8px; border-radius: 50%; }
.activity-mark--ok { background: #2b897d; }
.activity-mark--fail { background: #c9577e; }
.activity-body { min-width: 0; }
.activity-body div { display: flex; align-items: baseline; gap: 0.55rem; }
.activity-body strong { color: var(--text-main); font-size: 0.8rem; }
.activity-body span,
.activity-body p,
.activity-item time { color: var(--text-soft); font-size: 0.7rem; }
.activity-body p { margin: 0.16rem 0 0; overflow-wrap: anywhere; }
.activity-item time { white-space: nowrap; }
.empty-state { margin: 0; padding: 1rem 0; color: var(--text-soft); font-size: 0.8rem; }

.recovery-overlay { position: fixed; inset: 0; z-index: 100001; display: grid; place-items: center; padding: 1rem; background: rgb(20 32 29 / 0.52); }
.recovery-dialog { width: min(100%, 480px); max-height: calc(100dvh - 2rem); overflow-y: auto; padding: 1rem; border: 1px solid var(--border-subtle); border-radius: 12px; background: var(--surface-raised); box-shadow: 0 24px 70px rgb(25 45 39 / 0.24); }
.recovery-dialog-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding-bottom: 0.85rem; border-bottom: 1px solid var(--border-subtle); }
.recovery-dialog-header h2 { margin: 0; font-size: 1.05rem; color: var(--text-main); }
.recovery-form,
.recovery-result { display: grid; gap: 0.75rem; padding-top: 1rem; }
.form-label { color: var(--text-main); font-size: 0.78rem; font-weight: 700; }
.form-input,
.secret-output input { width: 100%; min-height: 42px; padding: 0.55rem 0.65rem; color: var(--text-main); border: 1px solid var(--border-strong); border-radius: 8px; background: #fff; font: inherit; font-size: 0.84rem; }
.recovery-code-input { font-family: Consolas, Menlo, monospace; letter-spacing: 0; }
.form-help { margin: -0.25rem 0 0; color: var(--text-soft); font-size: 0.72rem; line-height: 1.5; }
.form-error { margin: 0; padding: 0.65rem 0.7rem; color: #933d54; border-left: 3px solid #d26a88; background: #fff2f5; font-size: 0.76rem; }
.recovery-submit { width: 100%; }
.file-picker { min-height: 72px; display: flex; align-items: center; justify-content: center; gap: 0.55rem; padding: 0.75rem; color: var(--text-soft); border: 1px dashed var(--border-strong); border-radius: 8px; background: var(--surface-subtle); font-size: 0.8rem; cursor: pointer; overflow-wrap: anywhere; }
.file-picker--selected { color: #23685f; border-color: #8ebbb2; background: var(--mint-soft); }
.file-picker input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
.result-status { gap: 0.5rem; color: #23685f; }
.recovery-result p { margin: 0; font-size: 0.78rem; line-height: 1.55; }
.secret-output { gap: 0.45rem; padding: 0.5rem; border: 1px solid var(--border-subtle); border-radius: 8px; background: var(--surface-subtle); }
.secret-output code { flex: 1; color: var(--text-main); font-size: 0.78rem; line-height: 1.5; overflow-wrap: anywhere; }
.secret-output input { flex: 1; min-width: 0; border: 0; background: transparent; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

@media (max-width: 820px) {
  .overview-band { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .overview-item:nth-child(3) { border-left: 0; border-top: 1px solid var(--border-subtle); }
  .overview-item:nth-child(4) { border-top: 1px solid var(--border-subtle); }
  .lower-grid { grid-template-columns: 1fr; gap: 0; }
  .encryption-row { align-items: flex-start; flex-direction: column; }
  .encryption-actions { width: 100%; justify-content: flex-start; }
}

@media (max-width: 520px) {
  .privacy-header { align-items: flex-start; }
  .privacy-header h1 { font-size: 1.25rem; }
  .privacy-heading-icon { width: 42px; height: 42px; }
  .overview-item { min-height: 72px; justify-content: flex-start; padding: 0.75rem; }
  .overview-item strong { font-size: 1.15rem; }
  .section-title-row { flex-direction: column; }
  .snapshot-time,
  .local-only-label { white-space: normal; }
  .encryption-actions { display: grid; grid-template-columns: 1fr 1fr; }
  .encryption-actions .primary-button { grid-column: 1 / -1; }
  .activity-item { grid-template-columns: 12px minmax(0, 1fr); }
  .activity-item time { grid-column: 2; }
  .activity-body div { align-items: flex-start; flex-direction: column; gap: 0.12rem; }
  .recovery-dialog { padding: 0.85rem; }
}

@media (prefers-reduced-motion: reduce) {
  .loading-block,
  .is-spinning { animation: none; }
}
</style>
