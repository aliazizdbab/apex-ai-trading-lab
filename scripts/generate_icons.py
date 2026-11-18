"""Generate crisp unified APEX AI Trading Lab PNG, ICO, and Android mipmap icons using stdlib only."""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SVG_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0%" stop-color="#36C5F0"/><stop offset="100%" stop-color="#19C995"/>'
    "</linearGradient></defs>"
    '<rect width="64" height="64" rx="14" fill="#0B1220"/>'
    '<rect x="2" y="2" width="60" height="60" rx="12" fill="none" stroke="#1E304A" stroke-width="2"/>'
    '<path d="M32 11 53 51h-9.5L32 28.5 20.5 51H11z" fill="url(#g)"/>'
    '<rect x="22" y="38" width="20" height="5" rx="2.5" fill="#0B1220"/>'
    '<circle cx="49" cy="15" r="4" fill="#19C995"/>'
    "</svg>\n"
)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _point_in_poly(px: float, py: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def _render_rgba(size: int) -> bytes:
    """Render unified APEX delta + emerald live node icon at given square size (2x supersampled)."""
    outer_poly = [(32.0, 11.0), (53.0, 51.0), (43.5, 51.0), (32.0, 28.5), (20.5, 51.0), (11.0, 51.0)]
    buf = bytearray(size * size * 4)
    radius = size * 0.22
    scale = 64.0 / size

    for y in range(size):
        for x in range(size):
            r_acc = g_acc = b_acc = a_acc = 0.0
            for sy in (0.25, 0.75):
                for sx in (0.25, 0.75):
                    px_abs = x + sx
                    py_abs = y + sy
                    # Rounded square clip
                    dx = max(0.0, abs(px_abs - size / 2.0) - (size / 2.0 - radius))
                    dy = max(0.0, abs(py_abs - size / 2.0) - (size / 2.0 - radius))
                    dist = math.hypot(dx, dy)
                    if dist > radius:
                        continue

                    gx = px_abs * scale
                    gy = py_abs * scale
                    # Background gradient dark obsidian navy
                    r, g, b = 11.0, 18.0, 32.0

                    # Subtle steel border
                    if gx < 3.0 or gx > 61.0 or gy < 3.0 or gy > 61.0 or dist > radius - 1.5:
                        r, g, b = 34.0, 56.0, 88.0

                    # APEX Delta Gradient Crest (Cyan #36C5F0 -> Emerald #19C995)
                    if _point_in_poly(gx, gy, outer_poly):
                        # Cut horizontal bridge notch at y in [38.5, 43.5], x in [21, 43]
                        if not (38.5 <= gy <= 43.5 and 21.0 <= gx <= 43.0):
                            t = min(1.0, max(0.0, (gx + gy - 22.0) / 80.0))
                            r = _lerp(54.0, 25.0, t)
                            g = _lerp(197.0, 201.0, t)
                            b = _lerp(240.0, 149.0, t)

                    # Top-right Emerald live signal dot
                    if math.hypot(gx - 49.0, gy - 15.0) <= 4.2:
                        r, g, b = 25.0, 201.0, 149.0

                    r_acc += r
                    g_acc += g
                    b_acc += b
                    a_acc += 255.0

            idx = (y * size + x) * 4
            if a_acc > 0:
                samples = 4.0
                buf[idx] = int(round(r_acc / samples))
                buf[idx + 1] = int(round(g_acc / samples))
                buf[idx + 2] = int(round(b_acc / samples))
                buf[idx + 3] = int(round(a_acc / samples))
            else:
                buf[idx : idx + 4] = b"\x00\x00\x00\x00"
    return bytes(buf)


def _write_png(path: Path, size: int, rgba: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    stride = size * 4
    for row in range(size):
        raw.append(0)
        raw.extend(rgba[row * stride : (row + 1) * stride])

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), level=9)
    png_bytes = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    path.write_bytes(png_bytes)


def _write_ico(path: Path, png_map: dict[int, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    blobs = []
    offset = 6 + 16 * len(png_map)
    for size, blob in sorted(png_map.items()):
        w_byte = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", w_byte, w_byte, 0, 0, 1, 32, len(blob), offset))
        blobs.append(blob)
        offset += len(blob)
    header = struct.pack("<HHH", 0, 1, len(png_map))
    path.write_bytes(header + b"".join(entries) + b"".join(blobs))


def main() -> None:
    (ROOT / "frontend" / "public" / "favicon.svg").write_text(SVG_ICON, encoding="utf-8")

    targets: dict[Path, int] = {
        ROOT / "frontend" / "public" / "icon-192.png": 192,
        ROOT / "frontend" / "public" / "icon-512.png": 512,
        ROOT / "frontend" / "public" / "apple-touch-icon.png": 180,
        ROOT / "desktop" / "icons" / "icon.png": 512,
        ROOT / "android" / "res" / "mipmap-mdpi" / "ic_launcher.png": 48,
        ROOT / "android" / "res" / "mipmap-hdpi" / "ic_launcher.png": 72,
        ROOT / "android" / "res" / "mipmap-xhdpi" / "ic_launcher.png": 96,
        ROOT / "android" / "res" / "mipmap-xxhdpi" / "ic_launcher.png": 144,
        ROOT / "android" / "res" / "mipmap-xxxhdpi" / "ic_launcher.png": 192,
    }

    cache: dict[int, bytes] = {}
    for out_path, sz in targets.items():
        if sz not in cache:
            rgba = _render_rgba(sz)
            _write_png(out_path, sz, rgba)
            cache[sz] = out_path.read_bytes()
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(cache[sz])

    ico_blobs: dict[int, bytes] = {}
    for sz in (32, 48, 64, 128, 256):
        tmp_path = ROOT / "desktop" / "icons" / f".tmp-{sz}.png"
        _write_png(tmp_path, sz, _render_rgba(sz))
        ico_blobs[sz] = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
    _write_ico(ROOT / "desktop" / "icons" / "icon.ico", ico_blobs)
    print(f"Generated {len(targets)} PNG icons + icon.ico + favicon.svg")


if __name__ == "__main__":
    main()
