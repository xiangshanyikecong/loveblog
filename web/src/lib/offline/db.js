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

// 离线能力的唯一 IndexedDB 入口（设计见 docs/design/WEB_OFFLINE_WEAK_NETWORK_DESIGN.md）。
//
// v1 一次性创建全部对象仓库，后续阶段新增使用方时无需再迁移：
// - drafts:    P0 写作草稿（keyPath: key）
// - outbox:    P1 离线写入队列（keyPath: id, autoIncrement）
// - snapshots: P2 只读快照（keyPath: key）
// - meta:      杂项游标/计数
//
// 隐私边界（同一设计文档 §8）：本库绝不写入「一起听」（R8.4 永不持久化）、
// 密码保护内容、聊天 E2EE 明文/密钥信封。登出时由 wipeOfflineData() 清库。

import { openDB } from "idb";

export const OFFLINE_DB_NAME = "love-offline";
export const OFFLINE_DB_VERSION = 1;

let dbPromise = null;

function getDb() {
  // SSR / 隐私模式兜底：没有 indexedDB 时所有上层调用静默 no-op。
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  if (!dbPromise) {
    dbPromise = openDB(OFFLINE_DB_NAME, OFFLINE_DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains("drafts")) {
          db.createObjectStore("drafts", { keyPath: "key" });
        }
        if (!db.objectStoreNames.contains("outbox")) {
          const outbox = db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
          outbox.createIndex("status", "status");
        }
        if (!db.objectStoreNames.contains("snapshots")) {
          db.createObjectStore("snapshots", { keyPath: "key" });
        }
        if (!db.objectStoreNames.contains("meta")) {
          db.createObjectStore("meta", { keyPath: "key" });
        }
      },
    }).catch(() => {
      // 存储被禁用（如 Safari 无痕模式的旧策略）时退化为不可用，不阻塞应用。
      dbPromise = null;
      return null;
    });
  }
  return dbPromise;
}

/** 供上层模块按 store 名直接访问；不可用时 resolve 为 null。 */
export async function offlineStore(storeName, mode = "readwrite") {
  const db = await getDb();
  if (!db) return null;
  return db.transaction(storeName, mode).objectStore(storeName);
}

/** 仅测试用：丢弃缓存的连接，让下一次访问按当前 IndexedDB 工厂重开。 */
export async function resetOfflineDbForTests() {
  if (dbPromise) {
    const db = await dbPromise.catch(() => null);
    db?.close?.();
  }
  dbPromise = null;
}

/** 登出时清空全部离线数据（共享电脑场景）。 */
export async function wipeOfflineData() {
  const db = await getDb();
  if (!db) return;
  await Promise.all(
    ["drafts", "outbox", "snapshots", "meta"].map(async (name) => {
      try {
        await db.clear(name);
      } catch {
        // 清理失败不影响登出流程。
      }
    }),
  );
}
