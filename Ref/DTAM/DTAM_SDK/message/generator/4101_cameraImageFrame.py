"""Camera Image Frame (MSG 4101) payload generator.

This user-side example avoids external image libraries. It creates a small
PNG test pattern and returns the header plus image bytes.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import random
import struct
import zlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from dtam_client.schema.msg_4101 import validate_header


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _generate_rgb(width: int, height: int) -> bytes:
    """Create an RGB test pattern."""
    out = bytearray()
    accent = random.randint(64, 220)
    for y in range(height):
        for x in range(width):
            r = (x * 255) // max(1, width - 1)
            g = (y * 255) // max(1, height - 1)
            b = accent
            if x == width // 2 or y == height // 2:
                r, g, b = 255, 240, 0
            out.extend((r, g, b))
    return bytes(out)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def _encode_png_rgb(width: int, height: int, rgb: bytes) -> bytes:
    """Encode RGB bytes as a minimal PNG file."""
    stride = width * 3
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter type 0
        start = y * stride
        rows.extend(rgb[start:start + stride])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows)))
        + _png_chunk(b"IEND", b"")
    )


def generate_with_bytes(
    vehicle_id: Optional[str] = None,
    camera_name: Optional[str] = None,
    image_type: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    sequence: Optional[int] = None,
    validate: bool = True,
    **_ignored: Any,
) -> Tuple[Dict[str, Any], bytes]:
    w = int(width) if width else 320
    h = int(height) if height else 240
    rgb = _generate_rgb(w, h)
    image_bytes = _encode_png_rgb(w, h, rgb)
    checksum = "sha256:" + hashlib.sha256(image_bytes).hexdigest()[:40]

    header: Dict[str, Any] = {
        "message_id": 4101,
        "message_name": "Camera Image Frame",
        "timestamp": _now_iso(),
        "vehicle_id": vehicle_id or f"UAM{random.randint(1, 9999):04d}",
        "camera_name": camera_name or random.choice([
            "front_center",
            "front_left",
            "bottom_center",
        ]),
        "image_type": image_type or "scene",
        "sequence": int(sequence) if sequence is not None else random.randint(1, 99999),
        "width": w,
        "height": h,
        "channels": 3,
        "pixel_format": "rgb8",
        "encoding": "png",
        "payload_size": len(image_bytes),
        "checksum": checksum,
        "_image_base64": base64.b64encode(image_bytes).decode("ascii"),
    }

    if validate:
        ok, errs, _ = validate_header(header)
        if not ok:
            raise RuntimeError("4101 generator self-check failed: " + "; ".join(errs))
    return header, image_bytes


def generate(**kwargs: Any) -> Dict[str, Any]:
    """Return only the JSON header.

    Use ``generate_with_bytes()`` when sending the camera frame.
    """
    header, _ = generate_with_bytes(**kwargs)
    return header


if __name__ == "__main__":
    import json

    header, payload = generate_with_bytes()
    print(json.dumps(header, ensure_ascii=False, indent=2))
    print(f"payload bytes: {len(payload)}")
