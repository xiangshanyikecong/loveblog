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

/**
 * Browser-side crypto for the cottage 加密保险箱 (true end-to-end encrypted vault).
 *
 * The passphrase and the derived key NEVER leave the browser. The server only
 * ever stores opaque ciphertext + the public KDF parameters (salt / iterations)
 * and a "verifier" blob used to confirm a passphrase is correct without
 * decrypting any real entry.
 *
 *   passphrase ──PBKDF2(salt, iterations, SHA-256)──▶ AES-GCM 256-bit key
 *   plaintext  ──AES-GCM(key, random iv)───────────▶ { iv, ciphertext }
 *
 * Each entry uses a fresh random 96-bit IV. The derived key is non-extractable
 * (`extractable = false`) so it can't be read back out of memory via the API.
 */

const VERIFIER_TOKEN = "cottage-vault::verify::v1";

export const VAULT_DEFAULTS = Object.freeze({
  kdf: "PBKDF2",
  kdf_hash: "SHA-256",
  iterations: 210_000,
  algo: "AES-GCM",
});

const encoder = new TextEncoder();
const decoder = new TextDecoder();

export function isCryptoAvailable() {
  return (
    typeof crypto !== "undefined" &&
    !!crypto.subtle &&
    typeof crypto.getRandomValues === "function"
  );
}

function bufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function randomBytes(length) {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return bytes;
}

/** Fresh random 128-bit salt, base64-encoded (stored in vault meta). */
export function generateSalt() {
  return bufferToBase64(randomBytes(16));
}

/**
 * Derive a non-extractable AES-GCM key from a passphrase + KDF params.
 * @param {string} passphrase
 * @param {string} saltB64
 * @param {object} [opts]
 */
export async function deriveKey(passphrase, saltB64, opts = {}) {
  const iterations = opts.iterations || VAULT_DEFAULTS.iterations;
  const hash = opts.kdf_hash || VAULT_DEFAULTS.kdf_hash;
  const baseKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(passphrase),
    { name: "PBKDF2" },
    false,
    ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: base64ToBytes(saltB64), iterations, hash },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false, // non-extractable
    ["encrypt", "decrypt"]
  );
}

/** Encrypt a UTF-8 string → { iv, ciphertext } (both base64). */
export async function encryptString(key, plaintext) {
  const iv = randomBytes(12);
  const cipher = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    encoder.encode(plaintext)
  );
  return { iv: bufferToBase64(iv), ciphertext: bufferToBase64(cipher) };
}

/** Decrypt { iv, ciphertext } (base64) -> UTF-8 string. Throws on bad key/data. */
export async function decryptString(key, ivB64, ciphertextB64) {
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64ToBytes(ivB64) },
    key,
    base64ToBytes(ciphertextB64)
  );
  return decoder.decode(plain);
}

/** Encrypt raw bytes (ArrayBuffer) -> { iv, ciphertext } (both base64). */
export async function encryptBytes(key, plaintext) {
  const iv = randomBytes(12);
  const cipher = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    plaintext
  );
  return { iv: bufferToBase64(iv), ciphertext: bufferToBase64(cipher) };
}

/** Decrypt { iv, ciphertext } (base64) -> ArrayBuffer. Throws on bad key/data. */
export async function decryptBytes(key, ivB64, ciphertextB64) {
  return crypto.subtle.decrypt(
    { name: "AES-GCM", iv: base64ToBytes(ivB64) },
    key,
    base64ToBytes(ciphertextB64)
  );
}

/** Encrypt a JSON-serialisable object. */
export async function encryptJSON(key, value) {
  return encryptString(key, JSON.stringify(value));
}

/** Decrypt back into an object (returns null if the JSON is malformed). */
export async function decryptJSON(key, ivB64, ciphertextB64) {
  const text = await decryptString(key, ivB64, ciphertextB64);
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Build the verifier blob stored at setup time. */
export async function createVerifier(key) {
  const { iv, ciphertext } = await encryptString(key, VERIFIER_TOKEN);
  return { verifier_iv: iv, verifier_cipher: ciphertext };
}

/** Return true iff `key` correctly decrypts the stored verifier. */
export async function verifyKey(key, verifierIv, verifierCipher) {
  try {
    const token = await decryptString(key, verifierIv, verifierCipher);
    return token === VERIFIER_TOKEN;
  } catch {
    return false;
  }
}
