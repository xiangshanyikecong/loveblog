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

// 只读快照（P2）：视图拉取成功后把响应 JSON 存进 IndexedDB；离线或请求
// 失败时读回最近一份，让关键页面（首页/时光轴/文章/相册）离线可浏览，
// 并通过返回的 fetchedAt 显示「离线数据 · 保存于 HH:mm」。
//
// 与 SW 运行时缓存的分工：SW 缓存在 HTTP 层兜底（页面无须感知）；本模块
// 在应用层提供"明知是旧数据"的显式降级展示。两侧互为冗余。
//
// 隐私边界：只允许写入白名单 key（情侣双方的私有内容），与 sw.js 的
// API_READONLY_CACHE 同一范围；密码保护内容与「一起听」数据绝不入快照。

import { offlineStore } from "./db";

const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 快照最长保留 7 天

/**
 * 保存一份快照。返回是否成功（存储不可用/被禁用时 false，调用方忽略）。
 */
export async function saveSnapshot(key, payload) {
  const store = await offlineStore("snapshots");
  if (!store || payload === undefined) return false;
  try {
    await store.put({ key, payload, fetchedAt: Date.now() });
    return true;
  } catch {
    return false;
  }
}

/**
 * 读取最近一份快照；超过保留期视为不存在。无快照时返回 null。
 */
export async function loadSnapshot(key) {
  const store = await offlineStore("snapshots", "readonly");
  if (!store) return null;
  try {
    const record = await store.get(key);
    if (!record) return null;
    if (Date.now() - record.fetchedAt > MAX_AGE_MS) return null;
    return { payload: record.payload, fetchedAt: record.fetchedAt };
  } catch {
    return null;
  }
}

export async function deleteSnapshot(key) {
  const store = await offlineStore("snapshots");
  if (!store) return;
  try {
    await store.delete(key);
  } catch {
    // 清理失败不影响主流程。
  }
}
