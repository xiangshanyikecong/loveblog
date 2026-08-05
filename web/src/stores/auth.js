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

import { computed, ref } from "vue";
import { fetchMe, logoutApi, setUnauthorizedHandler } from "../lib/api";
import { disposeListenPlayer } from "./listenPlayer";

const LOGOUT_PENDING_KEY = "love_logout_pending";
const logoutWasPending = localStorage.getItem(LOGOUT_PENDING_KEY) === "true";
const isAuth = ref(!logoutWasPending && localStorage.getItem("love_is_auth") === "true");
const currentUserRole = ref(logoutWasPending ? "" : (localStorage.getItem("love_role") || ""));
let initPromise = null;
let pendingLogoutPromise = null;
let unauthorizedHandlerBound = false;
let onlineRetryBound = false;
let authGeneration = 0;

function hasPendingLogout() {
  return localStorage.getItem(LOGOUT_PENDING_KEY) === "true";
}

function completePendingLogout() {
  localStorage.removeItem(LOGOUT_PENDING_KEY);
}

export function useAuth() {
  async function initAuth() {
    if (initPromise) {
      return initPromise;
    }

    if (hasPendingLogout()) {
      clearAuthState({ disposeResources: true });
      initPromise = retryPendingLogout().then(() => false).finally(() => {
        initPromise = null;
      });
      return initPromise;
    }

    const generation = authGeneration;
    initPromise = fetchMe()
      .then((user) => {
        if (generation !== authGeneration || hasPendingLogout()) {
          return false;
        }
        setAuthToken("legacy", user.role);
        return true;
      })
      .catch((error) => {
        // The response interceptor clears a genuinely expired session. A
        // transient network/5xx failure must not silently log the user out.
        if (generation === authGeneration && error?.response?.status === 401) {
          clearAuthState();
        }
        return generation === authGeneration ? isAuth.value : false;
      })
      .finally(() => {
        initPromise = null;
      });

    return initPromise;
  }

  function setAuthToken(newToken, role, { newSession = false } = {}) {
    if (!newToken) {
      clearAuthState();
      return;
    }
    if (newSession) {
      authGeneration += 1;
      disposeListenPlayer();
      completePendingLogout();
    }
    isAuth.value = true;
    currentUserRole.value = role || "";
    localStorage.setItem("love_is_auth", "true");
    if (role) {
      localStorage.setItem("love_role", role);
    }
  }

  function clearAuthState({ disposeResources = true } = {}) {
    authGeneration += 1;
    if (disposeResources) {
      disposeListenPlayer();
    }
    isAuth.value = false;
    currentUserRole.value = "";
    localStorage.removeItem("love_is_auth");
    localStorage.removeItem("love_role");
  }

  async function logout() {
    // Stop user-bound resources immediately. The server request can still be
    // slow or fail while offline, but old audio and authenticated sockets must
    // never survive a local logout/account switch.
    localStorage.setItem(LOGOUT_PENDING_KEY, "true");
    clearAuthState({ disposeResources: true });
    return retryPendingLogout();
  }

  async function prepareForLogin() {
    // A delayed logout response can clear a newly-issued session cookie. Wait
    // until any logout attempt has settled before creating the next session.
    if (pendingLogoutPromise || hasPendingLogout()) {
      return retryPendingLogout();
    }
    return true;
  }

  function retryPendingLogout() {
    if (!hasPendingLogout()) return Promise.resolve(true);
    if (pendingLogoutPromise) return pendingLogoutPromise;

    pendingLogoutPromise = logoutApi()
      .then(() => {
        completePendingLogout();
        return true;
      })
      .catch((error) => {
        // An expired/missing session is already logged out server-side.
        if (error?.response?.status === 401) {
          completePendingLogout();
          return true;
        }
        return false;
      })
      .finally(() => {
        pendingLogoutPromise = null;
      });
    return pendingLogoutPromise;
  }

  const isPartnerUser = computed(() => ["PartnerA", "PartnerB"].includes(currentUserRole.value));
  const canManageContent = computed(() => isAuth.value && isPartnerUser.value);

  if (!unauthorizedHandlerBound) {
    setUnauthorizedHandler(clearAuthState);
    unauthorizedHandlerBound = true;
  }

  if (!onlineRetryBound && typeof window !== "undefined") {
    window.addEventListener("online", () => {
      if (hasPendingLogout()) void retryPendingLogout();
    });
    onlineRetryBound = true;
  }

  return {
    token: computed(() => isAuth.value ? "legacy" : ""), // Some components might check token.value
    currentUserRole,
    isPartnerUser,
    canManageContent,
    initAuth,
    prepareForLogin,
    setAuthToken,
    logout
  };
}
