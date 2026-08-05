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

import { createRouter, createWebHistory } from "vue-router";
import MainLayout from "../layouts/MainLayout.vue";
import AdminLayout from "../layouts/AdminLayout.vue";
import DashboardView from "../views/DashboardView.vue";
import { useAuth } from "../stores/auth";
import { fetchBootstrapStatus } from "../lib/api";

// Cache bootstrap status to avoid repeated network requests
let bootstrapChecked = false;
let bootstrapDone = false;
let bootstrapPromise = null;

async function checkBootstrap() {
  if (bootstrapChecked) return bootstrapDone;
  if (bootstrapPromise) return bootstrapPromise;
  bootstrapPromise = fetchBootstrapStatus()
    .then((status) => {
      bootstrapDone = Boolean(status.bootstrapped);
      bootstrapChecked = true;
      return bootstrapDone;
    })
    .catch(() => {
      // Unknown is deliberately not cached. Allow this navigation so a brief
      // outage does not create a setup redirect loop, then retry next time.
      return null;
    })
    .finally(() => {
      bootstrapPromise = null;
    });
  return bootstrapPromise;
}

/** Call this after setup completes so next navigation re-checks */
export function invalidateBootstrapCache() {
  bootstrapChecked = false;
  bootstrapPromise = null;
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/setup",
      name: "setup",
      component: () => import("../views/SetupView.vue"),
      meta: { isSetup: true }
    },
    {
      path: "/",
      component: MainLayout,
      children: [
        {
          path: "",
          name: "dashboard",
          component: DashboardView
        },
        {
          path: "articles",
          name: "articles",
          component: () => import("../views/ArticlesView.vue")
        },
        {
          path: "articles/:aid",
          name: "article-detail",
          component: () => import("../views/ArticleDetailView.vue")
        },
        {
          path: "editor/:aid?",
          name: "article-editor",
          component: () => import("../views/ArticleEditorView.vue"),
          meta: { requiresPartner: true }
        },
        {
          path: "search",
          name: "search",
          component: () => import("../views/SearchView.vue")
        },
        {
          path: "albums",
          name: "albums",
          component: () => import("../views/AlbumsView.vue")
        },
        {
          path: "albums/:alb_id",
          name: "album-detail",
          component: () => import("../views/AlbumDetailView.vue")
        },
        {
          path: "events",
          name: "events",
          component: () => import("../views/EventsView.vue")
        },
        {
          path: "timeline",
          name: "timeline",
          component: () => import("../views/TimelineView.vue")
        },
        {
          path: "messages",
          name: "messages",
          component: () => import("../views/MessagesView.vue")
        },
        {
          path: "notifications",
          name: "notifications",
          component: () => import("../views/NotificationsView.vue"),
          meta: { requiresAuth: true }
        },
        {
          path: "capsules",
          name: "capsules",
          component: () => import("../views/CapsulesView.vue"),
          meta: { requiresPartner: true }
        },
        {
          path: "privacy",
          name: "privacy",
          component: () => import("../views/PrivacyCenterView.vue"),
          meta: { requiresPartner: true }
        },
        {
          path: "cottage",
          component: () => import("../views/cottage/CottageLayout.vue"),
          meta: { requiresPartner: true },
          children: [
            {
              path: "",
              name: "cottage",
              component: () => import("../views/cottage/CottageHomeView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "check-in",
              name: "cottage-check-in",
              component: () => import("../views/cottage/checkin/CottageCheckInView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "chat",
              name: "cottage-chat",
              component: () => import("../views/cottage/chat/CottageChatView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "mood",
              name: "cottage-mood",
              component: () => import("../views/cottage/mood/CottageMoodView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "questions",
              name: "cottage-questions",
              component: () => import("../views/cottage/questions/CottageQuestionsView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "plans",
              name: "cottage-plans",
              component: () => import("../views/cottage/plans/CottagePlansView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "reminders",
              name: "cottage-reminders",
              component: () => import("../views/cottage/reminders/CottageRemindersView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "reports",
              name: "cottage-reports",
              component: () => import("../views/cottage/reports/CottageReportsView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "calendar",
              name: "cottage-calendar",
              component: () => import("../views/cottage/calendar/CottageCalendarView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "check-in/history",
              name: "cottage-check-in-history",
              component: () => import("../views/cottage/CottageCheckInHistoryView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "listen",
              name: "cottage-listen",
              component: () => import("../views/cottage/listen/CottageListenView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "wishlist",
              name: "cottage-wishlist",
              component: () => import("../views/cottage/wishlist/CottageWishlistView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "coupons",
              name: "cottage-coupons",
              component: () => import("../views/cottage/coupons/CottageCouponsView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "ledger",
              name: "cottage-ledger",
              component: () => import("../views/cottage/ledger/CottageLedgerView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "period",
              name: "cottage-period",
              component: () => import("../views/cottage/period/CottagePeriodView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "footprints",
              name: "cottage-footprints",
              component: () => import("../views/cottage/footprints/CottageFootprintsView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "vault",
              name: "cottage-vault",
              component: () => import("../views/cottage/vault/CottageVaultView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "watch",
              name: "cottage-watch",
              component: () => import("../views/cottage/watch/CottageWatchView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games",
              name: "cottage-games",
              component: () => import("../views/cottage/games/CottageGamesView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/stats",
              name: "cottage-games-stats",
              component: () => import("../views/cottage/games/CottageGamesStatsView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/gomoku",
              name: "cottage-games-gomoku",
              component: () => import("../views/cottage/games/gomoku/GomokuView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/tictactoe",
              name: "cottage-games-tictactoe",
              component: () => import("../views/cottage/games/tictactoe/TicTacToeView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/reversi",
              name: "cottage-games-reversi",
              component: () => import("../views/cottage/games/reversi/ReversiView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/memory",
              name: "cottage-games-memory",
              component: () => import("../views/cottage/games/memory/MemoryView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/linklink",
              name: "cottage-games-linklink",
              component: () => import("../views/cottage/games/linklink/LinkLinkView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/canvas",
              name: "cottage-games-canvas",
              component: () => import("../views/cottage/games/canvas/CanvasView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/canvas/gallery",
              name: "cottage-games-canvas-gallery",
              component: () => import("../views/cottage/games/canvas/CanvasArtworksView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/canvas/gallery/:caid",
              name: "cottage-games-canvas-artwork",
              component: () => import("../views/cottage/games/canvas/CanvasArtworkDetailView.vue"),
              meta: { requiresPartner: true }
            },
            {
              path: "games/draw",
              name: "cottage-games-draw",
              component: () => import("../views/cottage/games/draw/DrawView.vue"),
              meta: { requiresPartner: true }
            }
          ]
        },
        {
          path: "licenses",
          name: "licenses",
          component: () => import("../views/LicensesView.vue")
        },
        {
          path: "login",
          name: "login",
          component: () => import("../views/LoginView.vue")
        }
      ]
    },
    {
      path: "/admin",
      component: AdminLayout,
      meta: { requiresPartner: true },
      children: [
        {
          path: "",
          name: "admin",
          component: () => import("../views/AdminView.vue")
        },
        {
          path: "articles",
          name: "admin-articles",
          component: () => import("../views/AdminArticlesView.vue")
        },
        {
          path: "albums",
          name: "admin-albums",
          component: () => import("../views/AdminAlbumsView.vue")
        },
        {
          path: "messages",
          name: "admin-messages",
          component: () => import("../views/AdminMessagesView.vue")
        },
        {
          path: "timeline",
          name: "admin-timeline",
          component: () => import("../views/AdminTimelineView.vue")
        },
        {
          path: "capsules",
          name: "admin-capsules",
          component: () => import("../views/AdminCapsulesView.vue")
        },
        {
          path: "accounts",
          name: "admin-accounts",
          component: () => import("../views/AdminAccountsView.vue")
        },
        {
          path: "export",
          name: "admin-export",
          component: () => import("../views/AdminExportView.vue")
        },
        {
          path: "security",
          name: "admin-security",
          component: () => import("../views/AdminSecurityLogView.vue")
        },
        {
          path: "recycle-bin",
          name: "admin-recycle-bin",
          component: () => import("../views/AdminRecycleBinView.vue")
        }
      ]
    }
  ]
});

router.beforeEach(async (to, from, next) => {
  const { canManageContent, token, initAuth } = useAuth();

  // ── Bootstrap check ──────────────────────────────────────────────────────
  // Skip the check when already heading to /setup to prevent redirect loops
  if (!to.meta.isSetup) {
    const done = await checkBootstrap();
    if (done === false) {
      // Site not yet initialized → force setup wizard
      next({ name: "setup" });
      return;
    }
  } else {
    // If site is already bootstrapped, don't let users visit /setup again
    const done = await checkBootstrap();
    if (done === true) {
      next({ name: "dashboard" });
      return;
    }
  }

  // ── Auth guard ───────────────────────────────────────────────────────────
  if (to.meta.requiresAuth || to.meta.requiresPartner) {
    await initAuth();
  }

  if (to.meta.requiresAuth && !token.value) {
    next({ name: "login", query: { redirect: to.fullPath } });
    return;
  }

  if (to.meta.requiresPartner && !canManageContent.value) {
    next(token.value ? { name: "dashboard" } : { name: "login", query: { redirect: to.fullPath } });
    return;
  }

  next();
});

export default router;
