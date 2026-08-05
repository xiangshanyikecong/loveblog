# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
app/core/media.py
=================
Image processing utilities used by the upload pipeline.

Responsibilities
----------------
* Validate MIME type against the per-setting whitelist
* Strip EXIF metadata (privacy / security)
* Re-compress images to target quality to reduce storage
* Generate a thumbnail alongside the original
* Enforce a maximum file-size after compression

All operations are performed in-memory so no temp files are created.
The caller receives processed bytes and optional thumbnail bytes.

Dependencies
------------
Pillow is declared in requirements.txt (Pillow==10.4.0).
If Pillow is not installed the module still imports cleanly, but
processing functions will raise RuntimeError.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Maps MIME type → save format string for Pillow
_PILLOW_FORMAT: dict[str, str] = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
    "image/gif": "GIF",
}

# Output extension for each MIME type
_EXT_MAP: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# All MIME types the system will ever handle for images
ALL_IMAGE_TYPES: frozenset[str] = frozenset(_PILLOW_FORMAT)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MediaPolicy:
    """
    Media processing policy read from SiteSetting.
    All fields have safe defaults.
    """
    max_image_kb: int = 1024          # 0 = no limit
    thumb_width: int = 400            # 0 = no thumbnail
    compress_quality: int = 82        # 1-95, for JPEG and WebP
    strip_exif: bool = True
    # Parsed list of allowed MIME types
    allowed_mime_types: list[str] = field(
        default_factory=lambda: ["image/jpeg", "image/png", "image/webp", "image/gif"]
    )

    @classmethod
    def from_setting(cls, setting) -> "MediaPolicy":
        """Build a MediaPolicy from a SiteSetting ORM object."""
        raw_types = getattr(setting, "allowed_image_types", "") or ""
        allowed = [
            t.strip().lower()
            for t in raw_types.split(",")
            if t.strip()
        ]
        if not allowed:
            allowed = list(ALL_IMAGE_TYPES)

        return cls(
            max_image_kb=int(getattr(setting, "max_image_kb", 1024) or 1024),
            thumb_width=int(getattr(setting, "thumb_width", 400) or 400),
            compress_quality=max(1, min(95, int(getattr(setting, "compress_quality", 82) or 82))),
            strip_exif=bool(getattr(setting, "strip_exif", True)),
            allowed_mime_types=allowed,
        )


@dataclass
class ProcessedImage:
    """Result returned by process_image()."""
    data: bytes               # processed (possibly compressed) image bytes
    thumbnail: bytes | None   # thumbnail bytes, or None if skipped
    mime_type: str            # effective MIME type after processing
    extension: str            # file extension to use when saving
    original_size: int        # original size in bytes
    final_size: int           # bytes after compression


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_mime_type(content_type: str, policy: MediaPolicy) -> None:
    """
    Raise ValueError if the MIME type is not on the whitelist.
    """
    ct = content_type.lower().strip()
    if ct not in policy.allowed_mime_types:
        allowed_str = ", ".join(sorted(policy.allowed_mime_types))
        raise ValueError(
            f"不支持的文件类型 {content_type!r}。"
            f"当前白名单：{allowed_str}"
        )


def process_image(
    raw_bytes: bytes,
    content_type: str,
    policy: MediaPolicy,
) -> ProcessedImage:
    """
    Apply the full media processing pipeline to raw image bytes.

    Steps
    -----
    1. Decode with Pillow
    2. Strip EXIF (if policy.strip_exif)
    3. Re-encode at policy.compress_quality
    4. Enforce policy.max_image_kb (raise ValueError if exceeded after compress)
    5. Generate thumbnail (if policy.thumb_width > 0)

    GIF files are passed through without re-encoding (preserve animation).
    """
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is not installed. Run: pip install Pillow"
        ) from exc

    ct = content_type.lower().strip()
    pil_format = _PILLOW_FORMAT.get(ct, "JPEG")
    extension = _EXT_MAP.get(ct, ".jpg")
    original_size = len(raw_bytes)

    # ── Open ─────────────────────────────────────────────────────────────
    # Use a context manager so the decoder's file handle is released on every
    # path (normal return and exceptions). Re-binding ``img`` below is safe:
    # the ``with`` closes the object returned by Image.open(), not whatever
    # ``img`` happens to point at later.
    with Image.open(io.BytesIO(raw_bytes)) as img:

        # ── GIF pass-through ──────────────────────────────────────────────
        # Animated GIFs cannot be round-tripped through a single save without
        # losing frames, so we skip re-encoding entirely.
        if ct == "image/gif":
            _enforce_size(raw_bytes, policy.max_image_kb)
            thumb = _make_thumbnail(img, policy.thumb_width, "GIF")
            return ProcessedImage(
                data=raw_bytes,
                thumbnail=thumb,
                mime_type=ct,
                extension=extension,
                original_size=original_size,
                final_size=original_size,
            )

        # ── Fix orientation from EXIF ─────────────────────────────────────
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass  # non-fatal

        # ── Convert to RGB / RGBA for encode compatibility ────────────────
        if pil_format == "JPEG" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif pil_format == "WEBP" and img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")

        # ── Strip EXIF ────────────────────────────────────────────────────
        if policy.strip_exif:
            # Create a fresh image without EXIF info attached
            clean = Image.new(img.mode, img.size)
            clean.putdata(list(img.get_flattened_data()))
            img = clean

        # ── Re-encode ─────────────────────────────────────────────────────
        buf = io.BytesIO()
        save_kwargs: dict = {}
        if pil_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = policy.compress_quality
            save_kwargs["optimize"] = True
        if pil_format == "JPEG":
            save_kwargs["progressive"] = True

        img.save(buf, format=pil_format, **save_kwargs)
        processed_bytes = buf.getvalue()

        # ── Size guard ─────────────────────────────────────────────────────
        _enforce_size(processed_bytes, policy.max_image_kb)

        # ── Thumbnail ──────────────────────────────────────────────────────
        thumb = _make_thumbnail(img, policy.thumb_width, pil_format)

        return ProcessedImage(
            data=processed_bytes,
            thumbnail=thumb,
            mime_type=ct,
            extension=extension,
            original_size=original_size,
            final_size=len(processed_bytes),
        )


# ---------------------------------------------------------------------------
# Storage stats helper
# ---------------------------------------------------------------------------

def compute_storage_stats(uploads_root) -> dict:
    """
    Walk uploads_root and return per-subdirectory and total size/count.
    uploads_root should be a pathlib.Path.
    """
    from pathlib import Path
    root = Path(uploads_root)
    if not root.exists():
        return {"total_bytes": 0, "total_files": 0, "directories": {}}

    directories: dict[str, dict] = {}
    total_bytes = 0
    total_files = 0

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        dir_bytes = 0
        dir_files = 0
        for f in child.rglob("*"):
            if f.is_file():
                try:
                    sz = f.stat().st_size
                    dir_bytes += sz
                    dir_files += 1
                except OSError:
                    pass
        directories[child.name] = {"bytes": dir_bytes, "files": dir_files}
        total_bytes += dir_bytes
        total_files += dir_files

    # Also count loose files at root level
    for f in root.iterdir():
        if f.is_file():
            try:
                total_bytes += f.stat().st_size
                total_files += 1
            except OSError:
                pass

    return {
        "total_bytes": total_bytes,
        "total_files": total_files,
        "directories": directories,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _enforce_size(data: bytes, max_kb: int) -> None:
    """Raise ValueError if data exceeds max_kb. 0 means unlimited."""
    if max_kb <= 0:
        return
    limit = max_kb * 1024
    if len(data) > limit:
        raise ValueError(
            f"处理后图片仍超出限制 {max_kb} KB "
            f"（当前 {len(data) // 1024} KB）。请上传更小的图片或调低质量限制。"
        )


def _make_thumbnail(img, width: int, pil_format: str) -> bytes | None:
    """Generate a thumbnail and return as bytes, or None if width==0."""
    if width <= 0:
        return None
    try:
        from PIL import Image
        thumb = img.copy()
        thumb.thumbnail((width, width * 10), Image.LANCZOS)
        buf = io.BytesIO()
        save_kw: dict = {}
        if pil_format in ("JPEG", "WEBP"):
            save_kw["quality"] = 75
            save_kw["optimize"] = True
        thumb.save(buf, format=pil_format, **save_kw)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Thumbnail generation failed: %s", exc)
        return None
