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

import { describe, expect, it, vi } from "vitest";

import { createChatKeySetup, verifyChatPassphrase } from "./chatCrypto";
import {
  createRecoveryKit,
  encryptionMetaFingerprint,
  recoverPassphrase,
} from "./privacyRecovery";


describe("chat passphrase verification", () => {
  it("uses the chat verifier token and rejects a wrong passphrase", async () => {
    const passphrase = "shared-chat-passphrase";
    const { publicMeta } = await createChatKeySetup(passphrase);
    const meta = { initialized: true, ...publicMeta };

    await expect(verifyChatPassphrase(passphrase, meta)).resolves.toBe(true);
    await expect(verifyChatPassphrase("wrong-passphrase", meta)).resolves.toBe(false);
  });
});


describe("privacy recovery kits", () => {
  it("round-trips a passphrase only with the matching code and fingerprint", async () => {
    const passphrase = "vault-passphrase-for-recovery";
    const meta = {
      salt: "c2FsdA==",
      kdf: "PBKDF2",
      kdf_hash: "SHA-256",
      iterations: 210000,
      algo: "AES-GCM",
      verifier_iv: "aXY=",
      verifier_cipher: "Y2lwaGVy",
    };
    const fingerprint = await encryptionMetaFingerprint("vault", meta);
    const created = await createRecoveryKit({ scope: "vault", passphrase, fingerprint });

    await expect(recoverPassphrase({
      kit: created.kit,
      recoveryCode: created.recoveryCode,
      expectedScope: "vault",
      expectedFingerprint: fingerprint,
    })).resolves.toBe(passphrase);

    await expect(recoverPassphrase({
      kit: created.kit,
      recoveryCode: "wrong-code",
      expectedScope: "vault",
      expectedFingerprint: fingerprint,
    })).rejects.toThrow("恢复码");

    await expect(recoverPassphrase({
      kit: created.kit,
      recoveryCode: created.recoveryCode,
      expectedScope: "vault",
      expectedFingerprint: "stale-fingerprint",
    })).rejects.toThrow("旧密钥");
  });

  it("preserves URL-safe hyphens that are part of the recovery code", async () => {
    const randomSpy = vi.spyOn(crypto, "getRandomValues").mockImplementation((bytes) => {
      bytes.fill(0);
      if (bytes.byteLength === 32) bytes[0] = 251;
      return bytes;
    });
    try {
      const fingerprint = "current-key-fingerprint";
      const created = await createRecoveryKit({
        scope: "chat",
        passphrase: "chat-passphrase",
        fingerprint,
      });
      expect(created.recoveryCode.startsWith("-")).toBe(true);
      await expect(recoverPassphrase({
        kit: created.kit,
        recoveryCode: created.recoveryCode,
        expectedScope: "chat",
        expectedFingerprint: fingerprint,
      })).resolves.toBe("chat-passphrase");
    } finally {
      randomSpy.mockRestore();
    }
  });
});
