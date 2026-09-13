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

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const backendProxyTarget = process.env.BACKEND_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        // Rolldown-vite only supports the function form of manualChunks: split
        // heavyweight / stable dependencies into dedicated chunks so app code
        // changes do not invalidate them and the editor only loads where it is
        // actually routed to.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/[\\/]node_modules[\\/](vue|@vue|vue-router|vue-i18n)[\\/]/.test(id)) return "vendor-vue";
          if (/[\\/]node_modules[\\/]axios[\\/]/.test(id)) return "vendor-http";
          if (/[\\/]node_modules[\\/](marked|dompurify)[\\/]/.test(id)) return "vendor-markdown";
          if (/[\\/]node_modules[\\/]vditor[\\/]/.test(id)) return "vendor-vditor";
          return undefined;
        }
      }
    }
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: backendProxyTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        ws: true  // 启用 WebSocket 代理
      },
      "/uploads": {
        target: backendProxyTarget,
        changeOrigin: true
      }
    }
  }
});
