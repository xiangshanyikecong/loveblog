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
 * Client-side image compression used before upload.
 *
 * Mirrors the Android pipeline (UploadRepository.kt): downsample so the
 * longest edge is at most 1600px, then re-encode as JPEG at 85% quality.
 * Compressing in the browser cuts mobile data usage and upload latency
 * dramatically for phone-camera originals (typically 4000x3000 / 4-8MB).
 *
 * Animated GIFs are passed through untouched (single-frame re-encode would
 * lose animation), and any unexpected failure falls back to the original
 * file so an upload never breaks because of compression.
 */

const MAX_EDGE = 1600;
const JPEG_QUALITY = 0.85;

function loadImageElement(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("image decode failed"));
    };
    img.src = url;
  });
}

function toJpegName(name) {
  const stem = name.replace(/\.[^.]+$/, "");
  return `${stem || "image"}.jpg`;
}

/**
 * Downsample + re-encode an image File. Returns a JPEG File, or the original
 * file when compression does not apply (GIF, non-image, or when the encoded
 * result would be larger than the source).
 */
export async function compressImage(file) {
  if (!file || typeof document === "undefined") return file;
  if (!file.type || !file.type.startsWith("image/")) return file;
  if (file.type === "image/gif") return file; // keep animation

  try {
    let source;
    let width;
    let height;
    if (typeof createImageBitmap === "function") {
      // `from-image` bakes EXIF orientation into the bitmap, matching the
      // backend's exif_transpose step.
      source = await createImageBitmap(file, { imageOrientation: "from-image" });
      width = source.width;
      height = source.height;
    } else {
      source = await loadImageElement(file);
      width = source.naturalWidth || source.width;
      height = source.naturalHeight || source.height;
    }
    if (!width || !height) return file;

    const scale = Math.min(1, MAX_EDGE / Math.max(width, height));
    const targetW = Math.max(1, Math.round(width * scale));
    const targetH = Math.max(1, Math.round(height * scale));

    const canvas = document.createElement("canvas");
    canvas.width = targetW;
    canvas.height = targetH;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    // Flatten transparency onto white — the JPEG target has no alpha channel.
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, targetW, targetH);
    ctx.drawImage(source, 0, 0, targetW, targetH);
    if (typeof source.close === "function") {
      source.close();
    }

    const blob = await new Promise((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY)
    );
    canvas.width = 0;
    canvas.height = 0;
    if (!blob) return file;

    // Never make an upload bigger than it was.
    if (blob.size >= file.size) return file;

    return new File([blob], toJpegName(file.name || "image.jpg"), {
      type: "image/jpeg",
      lastModified: Date.now()
    });
  } catch {
    // Compression is best-effort; always fall back to the original file.
    return file;
  }
}
