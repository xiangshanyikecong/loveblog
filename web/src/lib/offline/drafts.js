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

// 文章编辑草稿的本地持久化（P0）：编辑中的内容实时落 IndexedDB，断网、
// 关页、崩溃后均可恢复。与 30s 的服务端自动保存并存——本地草稿毫秒级
// 落盘且必成功，网络自动保存失败时不再等于丢稿。
//
// 草稿以明文存储（与 Android 端 Room 本地库同一密级，见设计文档 §8），
// 仅存标题/正文/封面地址等编辑态；访问密码字段永不落盘。

import { offlineStore } from "./db";

const DRAFT_PREFIX = "article:";

export function draftKeyForArticle(aid) {
  return `${DRAFT_PREFIX}${aid || "new"}`;
}

/**
 * 保存（或更新）一篇文章的本地草稿。标题与正文都为空时删除已有草稿，
 * 避免空编辑会话留下无法恢复的占位记录。
 */
export async function saveArticleDraft({
  aid,
  title,
  content,
  coverUrl = null,
  baseVersion = null,
  serverUpdatedAt = null,
}) {
  const store = await offlineStore("drafts");
  if (!store) return false;
  const key = draftKeyForArticle(aid);
  try {
    if (!String(title || "").trim() && !String(content || "").trim()) {
      await store.delete(key);
      return true;
    }
    await store.put({
      key,
      aid: aid || null,
      title: title || "",
      content: content || "",
      coverUrl: coverUrl || null,
      baseVersion: baseVersion ?? null,
      serverUpdatedAt: serverUpdatedAt ?? null,
      updatedAt: Date.now(),
    });
    return true;
  } catch {
    return false;
  }
}

/** 读取一篇文章的本地草稿；不存在或存储不可用时返回 null。 */
export async function loadArticleDraft(aid) {
  const store = await offlineStore("drafts", "readonly");
  if (!store) return null;
  try {
    return (await store.get(draftKeyForArticle(aid))) || null;
  } catch {
    return null;
  }
}

export async function removeArticleDraft(aid) {
  const store = await offlineStore("drafts");
  if (!store) return false;
  try {
    await store.delete(draftKeyForArticle(aid));
    return true;
  } catch {
    return false;
  }
}

/** 服务端 updated_at（ISO 字符串）转毫秒；解析失败返回 0（视为未知）。 */
export function updatedAtToMs(iso) {
  if (!iso) return 0;
  const ms = Date.parse(iso);
  return Number.isFinite(ms) ? ms : 0;
}

/**
 * 恢复判定：本地草稿比服务端已知版本新（或服务端时间未知）时才值得提示
 * 恢复。草稿里保存了打开编辑器时的服务端 updated_at，两边一致说明服务端
 * 在草稿产生后没有变化，此时无论时间戳如何都提示恢复。
 */
export function draftIsWorthRestoring(draft, serverUpdatedAtIso) {
  if (!draft) return false;
  const serverMs = updatedAtToMs(serverUpdatedAtIso);
  if (serverMs === 0) return true;
  if (draft.serverUpdatedAt && updatedAtToMs(draft.serverUpdatedAt) === serverMs) {
    return true;
  }
  return draft.updatedAt > serverMs;
}
