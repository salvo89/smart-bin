#!/usr/bin/env python3
"""Genera icone PWA (192/512/1024), brand-mark, badge e notify da glifo 'giorno del ritiro'."""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICON_SIZES = (192, 512, 1024)
ICON_OUT_DIRS = (ROOT / "webapp", ROOT / "docs")
MARK_OUT_DIRS = (ROOT / "webapp", ROOT / "docs")
SRC_OUT = ROOT / "webapp" / "icon-proposals" / "icon-source-1024.png"

BG = (238, 246, 241)  # #eef6f1
INK = (31, 92, 66)  # #1f5c42
DARK = (22, 61, 44)  # #163d2c
SIZE = 1024
K = SIZE / 192

NOTIFY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192" role="img" aria-label="Giorno del ritiro">
  <rect width="192" height="192" rx="42" fill="#eef6f1"/>
  <circle cx="70" cy="44" r="11" fill="#1f5c42"/>
  <circle cx="122" cy="44" r="11" fill="#1f5c42"/>
  <circle cx="70" cy="44" r="5" fill="#eef6f1"/>
  <circle cx="122" cy="44" r="5" fill="#eef6f1"/>
  <rect x="40" y="50" width="112" height="118" rx="18" fill="#1f5c42"/>
  <path d="M40 50h112v28H40z" fill="#163d2c"/>
  <rect x="40" y="50" width="112" height="18" rx="18" fill="#163d2c"/>
  <rect x="54" y="90" width="24" height="20" rx="5" fill="#eef6f1"/>
  <rect x="84" y="90" width="24" height="20" rx="5" fill="#eef6f1"/>
  <rect x="114" y="90" width="24" height="20" rx="5" fill="#eef6f1"/>
  <rect x="54" y="118" width="24" height="20" rx="5" fill="#eef6f1"/>
  <rect x="114" y="118" width="24" height="20" rx="5" fill="#eef6f1"/>
  <rect x="84" y="118" width="24" height="20" rx="5" fill="#eef6f1"/>
  <rect x="91" y="123.6" width="10" height="2.1" rx="0.8" fill="#1f5c42"/>
  <path d="M92 126.4h8l-1.1 5.6h-5.8z" fill="#1f5c42"/>
  <circle cx="94.2" cy="132.8" r="1.05" fill="#1f5c42"/>
  <circle cx="97.8" cy="132.8" r="1.05" fill="#1f5c42"/>
</svg>
"""


def S(*vals: float) -> list[float]:
    return [v * K for v in vals]


def box(x: float, y: float, w: float, h: float) -> list[float]:
    return S(x, y, x + w, y + h)


def rr(d: ImageDraw.ImageDraw, x, y, w, h, r, fill):
    d.rounded_rectangle(box(x, y, w, h), radius=max(1, r * K), fill=fill)


def oval(d: ImageDraw.ImageDraw, cx, cy, r, fill):
    d.ellipse(S(cx - r, cy - r, cx + r, cy + r), fill=fill)


def mini_bin(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, fill, hole) -> None:
    lid_w, lid_h = s * 1.55, s * 0.32
    rr(d, cx - lid_w / 2, cy - s * 0.72, lid_w, lid_h, s * 0.12, fill)
    d.polygon(
        [
            ((cx - s * 0.62) * K, (cy - s * 0.38) * K),
            ((cx + s * 0.62) * K, (cy - s * 0.38) * K),
            ((cx + s * 0.48) * K, (cy + s * 0.55) * K),
            ((cx - s * 0.48) * K, (cy + s * 0.55) * K),
        ],
        fill=fill,
    )
    oval(d, cx - s * 0.28, cy + s * 0.62, s * 0.16, fill)
    oval(d, cx + s * 0.28, cy + s * 0.62, s * 0.16, fill)
    oval(d, cx - s * 0.28, cy + s * 0.62, s * 0.07, hole)
    oval(d, cx + s * 0.28, cy + s * 0.62, s * 0.07, hole)


def render_app_icon() -> Image.Image:
    """Proposta 2: calendario, giorno evidenziato con cassonetto."""
    im = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(im)
    for cx in (70, 122):
        oval(d, cx, 44, 11, INK)
        oval(d, cx, 44, 5, BG)
    rr(d, 40, 50, 112, 118, 18, INK)
    rr(d, 40, 50, 112, 28, 18, DARK)
    d.rectangle(S(40, 64, 152, 78), fill=DARK)
    for x, y in ((54, 90), (84, 90), (114, 90), (54, 118), (114, 118), (84, 118)):
        rr(d, x, y, 24, 20, 5, BG)
    mini_bin(d, 96, 128.2, 6.4, INK, BG)
    return im


def _is_bg(r: int, g: int, b: int) -> bool:
    return abs(r - BG[0]) < 18 and abs(g - BG[1]) < 18 and abs(b - BG[2]) < 18


def extract_glyph(im: Image.Image, fill: tuple[int, int, int]) -> Image.Image:
    src = im.convert("RGB")
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    sp, op = src.load(), out.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b = sp[x, y]
            if _is_bg(r, g, b) or r + g + b < 36:
                continue
            op[x, y] = (*fill, 255)
    bbox = out.getbbox()
    if not bbox:
        raise SystemExit("glifo vuoto dopo estrazione")
    return out.crop(bbox)


def pad_to_square(glyph: Image.Image, target: int) -> Image.Image:
    pad = max(8, max(glyph.size) // 32)
    side = max(glyph.size) + pad * 2
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(glyph, ((side - glyph.width) // 2, (side - glyph.height) // 2), glyph)
    scale = target / side
    return canvas.resize(
        (max(1, int(canvas.width * scale)), max(1, int(canvas.height * scale))),
        Image.Resampling.LANCZOS,
    )


def write_app_icons(square: Image.Image) -> None:
    SRC_OUT.parent.mkdir(parents=True, exist_ok=True)
    square.save(SRC_OUT, format="PNG", optimize=True)
    print(f"Wrote {SRC_OUT} {square.size}")
    for size in ICON_SIZES:
        out_img = square.resize((size, size), Image.Resampling.LANCZOS)
        for base in ICON_OUT_DIRS:
            dest = base / f"icon-{size}.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            out_img.save(dest, format="PNG", optimize=True)
            print(f"Wrote {dest} ({dest.stat().st_size} bytes) size={size}")


def write_brand_mark(glyph: Image.Image) -> Image.Image:
    mark = pad_to_square(glyph, 512)
    for dest_dir in MARK_OUT_DIRS:
        dest = dest_dir / "brand-mark.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        mark.save(dest, format="PNG", optimize=True)
        print(f"Wrote {dest} ({dest.stat().st_size} bytes) size={mark.size}")
    return mark


def write_badge(glyph: Image.Image) -> None:
    white = Image.new("RGBA", glyph.size, (0, 0, 0, 0))
    wp = white.load()
    gp = glyph.load()
    for y in range(glyph.height):
        for x in range(glyph.width):
            r, g, b, a = gp[x, y]
            wp[x, y] = (255, 255, 255, a) if a > 10 else (0, 0, 0, 0)
    badge = pad_to_square(white, 96)
    dest = ROOT / "docs" / "badge-96.png"
    badge.save(dest, format="PNG", optimize=True)
    print(f"Wrote {dest} ({dest.stat().st_size} bytes) size={badge.size}")


def write_notify(icon_192: Image.Image) -> None:
    dest_png = ROOT / "docs" / "notify-icon-192.png"
    icon_192.save(dest_png, format="PNG", optimize=True)
    dest_svg = ROOT / "docs" / "notify-icon.svg"
    dest_svg.write_text(NOTIFY_SVG, encoding="utf-8")
    print(f"Wrote {dest_png} ({dest_png.stat().st_size} bytes)")
    print(f"Wrote {dest_svg} ({dest_svg.stat().st_size} bytes)")


def main() -> None:
    app = render_app_icon()
    write_app_icons(app)
    glyph = extract_glyph(app, INK)
    mark = write_brand_mark(glyph)
    write_badge(glyph)
    write_notify(app.resize((192, 192), Image.Resampling.LANCZOS))
    print(f"brand-mark aspect {mark.size[0]}x{mark.size[1]}")


if __name__ == "__main__":
    main()
