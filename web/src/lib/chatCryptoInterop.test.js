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

// E2EE 媒体互通向量（web 侧镜像）：与 Android 端
// app/src/test/.../ChatCryptoTest.kt 的 `web media interop known answer
// vector` 共用同一组固定值。向量由 Node WebCrypto 按 chatCrypto.js 的
// encryptChatRaw 参数离线生成，两端任一侧改动算法/编码/编码顺序都会让
// 对应单测失败，从而把「加密图片双端互通」固化进 CI。
//
// 真机互通矩阵（Web↔Android 收发双向）仍需人工验证：
// docs/design/E2EE_CHAT_IMAGE_DESIGN.md §8。

import { describe, expect, it } from "vitest";

import { decryptBytes, deriveKey, encryptBytes } from "./vaultCrypto";

// 与 Android 测试同源的固定向量。
const PASSPHRASE = "interop-passphrase-互通测试-💜";
const SALT_B64 = "vICBxiLZPFD8fqb5WUE1uw==";
const IV_B64 = "h269VbdTCG/3qYqq";
const CIPHERTEXT_B64 =
  "KdCD84vLc6vg+EmGZOGzKTBb1eSaM5m5gugKjgKCbgiQPmt57CdHMWS//pAjYCfFMpzlUaDRbN6T2Vm2DsC3QCA1FYSFuc94hV8=";

// 明文 = JPEG 魔数头 + UTF-8 中文注释 + JPEG 尾。
const PLAINTEXT = new Uint8Array([
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
  ...new TextEncoder().encode("love-journal e2ee media interop 互通向量"),
  0xff, 0xd9,
]);

describe("e2ee media interop vector (shared with Android ChatCryptoTest)", () => {
  it("derives the same key and decrypts the web-generated media vector", async () => {
    const key = await deriveKey(PASSPHRASE, SALT_B64);
    const plain = await decryptBytes(key, IV_B64, CIPHERTEXT_B64);
    expect(new Uint8Array(plain)).toEqual(PLAINTEXT);
  });

  it("re-encrypts the plaintext to a decryptable GCM envelope", async () => {
    const key = await deriveKey(PASSPHRASE, SALT_B64);
    const { iv, ciphertext } = await encryptBytes(key, PLAINTEXT);
    expect(iv).not.toBe(IV_B64); // 每次加密随机 IV
    const roundtrip = await decryptBytes(key, iv, ciphertext);
    expect(new Uint8Array(roundtrip)).toEqual(PLAINTEXT);
  });
});
