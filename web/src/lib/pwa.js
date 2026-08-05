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
import {
  deletePushSubscription,
  fetchPushPublicKey,
  markNotificationRead,
  savePushSubscription
} from "./api";
import { t } from "../locales";

const installPromptEvent = ref(null);
const isInstalled = ref(false);
const serviceWorkerReady = ref(false);
const pushPermission = ref("default");
const hasPushSubscription = ref(false);
const pushServerEnabled = ref(false);
const pushBusy = ref(false);

const canInstallApp = computed(() => Boolean(installPromptEvent.value) && !isInstalled.value);
const pushSupported = computed(
  () =>
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
);

let initialized = false;
let routerRef = null;
const handledNotificationIds = new Set();

function detectInstalled() {
  if (typeof window === "undefined") {
    return false;
  }
  return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = `${base64String}${padding}`.replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(base64);
  return Uint8Array.from([...raw].map((ch) => ch.charCodeAt(0)));
}

async function getRegistration() {
  if (!("serviceWorker" in navigator)) {
    throw new Error(t("pwa.swUnsupported"));
  }
  const registration = await navigator.serviceWorker.ready;
  serviceWorkerReady.value = true;
  return registration;
}

async function consumeNotificationId(nid, route) {
  if (!nid || handledNotificationIds.has(nid)) {
    return;
  }
  handledNotificationIds.add(nid);
  try {
    await markNotificationRead(nid);
  } catch {
    // Ignore failures here: push clicks should still navigate even if read sync fails.
  }

  if (routerRef && route?.query?._nid) {
    const nextQuery = { ...route.query };
    delete nextQuery._nid;
    routerRef.replace({ path: route.path, query: nextQuery, hash: route.hash }).catch(() => {});
  }
}

async function syncBrowserSubscription() {
  if (!pushSupported.value) {
    serviceWorkerReady.value = false;
    hasPushSubscription.value = false;
    return;
  }

  pushPermission.value = window.Notification.permission;
  const registration = await getRegistration();
  const subscription = await registration.pushManager.getSubscription();
  hasPushSubscription.value = Boolean(subscription);
}

export async function initPwa(router) {
  if (initialized) {
    return;
  }
  initialized = true;
  routerRef = router || null;
  isInstalled.value = detectInstalled();

  if (typeof window === "undefined") {
    return;
  }

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPromptEvent.value = event;
  });
  window.addEventListener("appinstalled", () => {
    installPromptEvent.value = null;
    isInstalled.value = true;
  });

  if ("serviceWorker" in navigator) {
    try {
      await navigator.serviceWorker.register("/sw.js");
      await syncBrowserSubscription();
      navigator.serviceWorker.addEventListener("message", (event) => {
        const nid = event?.data?.nid;
        consumeNotificationId(nid, routerRef?.currentRoute?.value);
      });
    } catch {
      // Push is optional; registration failures should not block the app.
    }
  }

  if (routerRef) {
    await routerRef.isReady();
    await consumeNotificationId(routerRef.currentRoute.value?.query?._nid, routerRef.currentRoute.value);
    routerRef.afterEach((to) => {
      consumeNotificationId(to.query?._nid, to);
    });
  }
}

export async function refreshPushState() {
  if (typeof window !== "undefined" && "Notification" in window) {
    pushPermission.value = window.Notification.permission;
  }

  try {
    const data = await fetchPushPublicKey();
    pushServerEnabled.value = Boolean(data?.enabled);
  } catch {
    pushServerEnabled.value = false;
  }

  try {
    await syncBrowserSubscription();
  } catch {
    hasPushSubscription.value = false;
  }
}

export async function promptInstall() {
  if (!installPromptEvent.value) {
    return false;
  }
  await installPromptEvent.value.prompt();
  const choice = await installPromptEvent.value.userChoice;
  if (choice?.outcome === "accepted") {
    installPromptEvent.value = null;
  }
  return choice?.outcome === "accepted";
}

export async function enablePushNotifications() {
  if (!pushSupported.value) {
    throw new Error(t("pwa.pushUnsupported"));
  }

  pushBusy.value = true;
  try {
    const config = await fetchPushPublicKey();
    pushServerEnabled.value = Boolean(config?.enabled);
    if (!config?.enabled || !config?.public_key) {
      throw new Error(t("pwa.pushServerOff"));
    }

    const permission =
      window.Notification.permission === "granted"
        ? "granted"
        : await window.Notification.requestPermission();
    pushPermission.value = permission;
    if (permission !== "granted") {
      throw new Error(t("pwa.permissionDenied"));
    }

    const registration = await getRegistration();
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(config.public_key)
      });
    }

    const json = subscription.toJSON();
    await savePushSubscription({
      endpoint: json.endpoint,
      expiration_time: json.expirationTime ?? null,
      keys: {
        p256dh: json.keys?.p256dh || "",
        auth: json.keys?.auth || ""
      },
      user_agent: window.navigator.userAgent
    });
    hasPushSubscription.value = true;
  } finally {
    pushBusy.value = false;
  }
}

export async function disablePushNotifications() {
  if (!pushSupported.value) {
    return;
  }

  pushBusy.value = true;
  try {
    const registration = await getRegistration();
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      await deletePushSubscription({ endpoint: subscription.endpoint }).catch(() => {});
      await subscription.unsubscribe().catch(() => {});
    }
    hasPushSubscription.value = false;
  } finally {
    pushBusy.value = false;
  }
}

export function usePwa() {
  return {
    canInstallApp,
    hasPushSubscription,
    isInstalled,
    pushBusy,
    pushPermission,
    pushServerEnabled,
    pushSupported
  };
}
