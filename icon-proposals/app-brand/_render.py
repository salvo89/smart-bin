#!/usr/bin/env python3
"""Render 3 Escilo app-icon + brand-mark proposals (SVG + PNG)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent
BG = (238, 246, 241)  # #eef6f1
INK = (31, 92, 66)  # #1f5c42
ACCENT = (61, 154, 110)  # #3d9a6e
DARK = (22, 61, 44)  # #163d2c
SIZE = 1024
K = SIZE / 192


def S(*vals: float) -> list[float]:
    return [v * K for v in vals]


def box(x: float, y: float, w: float, h: float) -> list[float]:
    return S(x, y, x + w, y + h)


def rr(d: ImageDraw.ImageDraw, x, y, w, h, r, fill):
    d.rounded_rectangle(box(x, y, w, h), radius=max(1, r * K), fill=fill)


def oval(d: ImageDraw.ImageDraw, cx, cy, r, fill):
    d.ellipse(S(cx - r, cy - r, cx + r, cy + r), fill=fill)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    im = Image.new("RGB", (SIZE, SIZE), BG)
    return im, ImageDraw.Draw(im)


def paste_leaf(im: Image.Image, cx: float, cy: float, s: float, fill) -> Image.Image:
    """Simple leaf = elongated ellipse, rotated up-right."""
    dim = max(8, int(s * 5 * K))
    tmp = Image.new("RGBA", (dim, dim), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    m = dim / 2
    td.ellipse((m - s * 0.42 * K, m - s * 1.05 * K, m + s * 0.42 * K, m + s * 1.05 * K), fill=(*fill, 255))
    rot = tmp.rotate(-40, resample=Image.Resampling.BICUBIC, expand=True)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px = int(cx * K - rot.width / 2)
    py = int(cy * K - rot.height / 2)
    layer.paste(rot, (px, py), rot)
    return Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")


def mini_bin(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, fill, hole) -> None:
    """Tiny cassonetto inside a calendar cell."""
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


def glyph_from(im: Image.Image) -> Image.Image:
    src = im.convert("RGB")
    out = Image.new("RGBA", src.size, (0, 0, 0, 0))
    sp, op = src.load(), out.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b = sp[x, y]
            if abs(r - BG[0]) < 18 and abs(g - BG[1]) < 18 and abs(b - BG[2]) < 18:
                continue
            if r + g + b < 36:
                continue
            op[x, y] = (*INK, 255)
    bbox = out.getbbox()
    if not bbox:
        raise SystemExit("empty glyph")
    cropped = out.crop(bbox)
    pad = max(16, max(cropped.size) // 20)
    side = max(cropped.size) + pad * 2
    mark = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    mark.paste(cropped, ((side - cropped.width) // 2, (side - cropped.height) // 2), cropped)
    return mark.resize((512, 512), Image.Resampling.LANCZOS)


def save_pair(im: Image.Image, stem: str) -> None:
    app = im.resize((512, 512), Image.Resampling.LANCZOS)
    app.save(OUT / f"{stem}.png", optimize=True)
    im.resize((192, 192), Image.Resampling.LANCZOS).save(OUT / f"{stem}-192.png", optimize=True)
    mark = glyph_from(im)
    mark.save(OUT / f"{stem}-mark.png", optimize=True)
    print(stem, "app", app.size, "mark", mark.size)


def render_01() -> Image.Image:
    """Cassonetto whose lid rings + body grid read as a calendar."""
    im, d = canvas()
    # lid first, then binder rings punched through it
    rr(d, 44, 52, 104, 22, 8, INK)
    for cx in (78, 114):
        oval(d, cx, 52, 12, INK)
        oval(d, cx, 52, 5.8, BG)
    # body
    d.polygon(
        [
            (52 * K, 78 * K),
            (140 * K, 78 * K),
            (131 * K, 146 * K),
            (61 * K, 146 * K),
        ],
        fill=INK,
    )
    rr(d, 58, 132, 76, 22, 11, INK)
    # calendar header on the body
    rr(d, 66, 86, 60, 8, 3, BG)
    # 2×2 cells
    rr(d, 66, 100, 22, 16, 4, BG)
    rr(d, 98, 100, 22, 16, 4, BG)
    rr(d, 66, 122, 22, 16, 4, BG)
    rr(d, 98, 122, 22, 16, 4, BG)
    im = paste_leaf(im, 109, 129.5, 5.4, INK)
    d = ImageDraw.Draw(im)
    oval(d, 74, 156, 9, INK)
    oval(d, 118, 156, 9, INK)
    oval(d, 74, 156, 3.4, BG)
    oval(d, 118, 156, 3.4, BG)
    return im


def render_02() -> Image.Image:
    """Calendar — the highlighted day is when the bin goes out."""
    im, d = canvas()
    for cx in (70, 122):
        oval(d, cx, 44, 11, INK)
        oval(d, cx, 44, 5, BG)
    rr(d, 40, 50, 112, 118, 18, INK)
    rr(d, 40, 50, 112, 28, 18, DARK)
    d.rectangle(S(40, 64, 152, 78), fill=DARK)
    cells = [(54, 90), (84, 90), (114, 90), (54, 118), (114, 118)]
    for x, y in cells:
        rr(d, x, y, 24, 20, 5, BG)
    rr(d, 84, 118, 24, 20, 5, BG)
    mini_bin(d, 96, 128.2, 6.4, INK, BG)
    return im


def render_03() -> Image.Image:
    """Cassonetto with lid open — esci lo."""
    im, d = canvas()
    d.polygon(
        [
            (58 * K, 98 * K),
            (134 * K, 98 * K),
            (126 * K, 152 * K),
            (66 * K, 152 * K),
        ],
        fill=INK,
    )
    rr(d, 64, 138, 64, 20, 10, INK)
    rr(d, 80, 112, 32, 28, 7, BG)
    oval(d, 78, 160, 9, INK)
    oval(d, 114, 160, 9, INK)
    oval(d, 78, 160, 3.4, BG)
    oval(d, 114, 160, 3.4, BG)
    lid = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lid)
    hinge = (128 * K, 92 * K)
    ld.rounded_rectangle(box(50, 80, 84, 20), radius=8 * K, fill=INK)
    ld.rounded_rectangle(box(80, 68, 22, 16), radius=6 * K, fill=ACCENT)
    lid_r = lid.rotate(-44, resample=Image.Resampling.BICUBIC, center=hinge)
    return Image.alpha_composite(im.convert("RGBA"), lid_r).convert("RGB")


SVG_01 = """<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192" role="img" aria-label="Cassonetto-calendario">
  <rect width="192" height="192" rx="42" fill="#eef6f1"/>
  <rect x="44" y="52" width="104" height="22" rx="8" fill="#1f5c42"/>
  <circle cx="78" cy="52" r="12" fill="#1f5c42"/>
  <circle cx="114" cy="52" r="12" fill="#1f5c42"/>
  <circle cx="78" cy="52" r="5.8" fill="#eef6f1"/>
  <circle cx="114" cy="52" r="5.8" fill="#eef6f1"/>
  <path d="M52 78h88l-9 68H61L52 78z" fill="#1f5c42"/>
  <rect x="58" y="132" width="76" height="22" rx="11" fill="#1f5c42"/>
  <rect x="66" y="86" width="60" height="8" rx="3" fill="#eef6f1"/>
  <rect x="66" y="100" width="22" height="16" rx="4" fill="#eef6f1"/>
  <rect x="98" y="100" width="22" height="16" rx="4" fill="#eef6f1"/>
  <rect x="66" y="122" width="22" height="16" rx="4" fill="#eef6f1"/>
  <rect x="98" y="122" width="22" height="16" rx="4" fill="#eef6f1"/>
  <g transform="translate(109 129.5) rotate(-40)">
    <ellipse cx="0" cy="0" rx="2.3" ry="5.7" fill="#1f5c42"/>
  </g>
  <circle cx="74" cy="156" r="9" fill="#1f5c42"/>
  <circle cx="118" cy="156" r="9" fill="#1f5c42"/>
  <circle cx="74" cy="156" r="3.4" fill="#eef6f1"/>
  <circle cx="118" cy="156" r="3.4" fill="#eef6f1"/>
</svg>
"""

SVG_01_MARK = """<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="24 28 144 148" role="img" aria-label="Marchio Escilo — cassonetto-calendario">
  <rect x="44" y="52" width="104" height="22" rx="8" fill="#1f5c42"/>
  <circle cx="78" cy="52" r="12" fill="#1f5c42"/>
  <circle cx="114" cy="52" r="12" fill="#1f5c42"/>
  <circle cx="78" cy="52" r="5.8" fill="#fff"/>
  <circle cx="114" cy="52" r="5.8" fill="#fff"/>
  <path d="M52 78h88l-9 68H61L52 78z" fill="#1f5c42"/>
  <rect x="58" y="132" width="76" height="22" rx="11" fill="#1f5c42"/>
  <rect x="66" y="86" width="60" height="8" rx="3" fill="#fff"/>
  <rect x="66" y="100" width="22" height="16" rx="4" fill="#fff"/>
  <rect x="98" y="100" width="22" height="16" rx="4" fill="#fff"/>
  <rect x="66" y="122" width="22" height="16" rx="4" fill="#fff"/>
  <rect x="98" y="122" width="22" height="16" rx="4" fill="#fff"/>
  <g transform="translate(109 129.5) rotate(-40)">
    <ellipse cx="0" cy="0" rx="2.3" ry="5.7" fill="#1f5c42"/>
  </g>
  <circle cx="74" cy="156" r="9" fill="#1f5c42"/>
  <circle cx="118" cy="156" r="9" fill="#1f5c42"/>
  <circle cx="74" cy="156" r="3.4" fill="#fff"/>
  <circle cx="118" cy="156" r="3.4" fill="#fff"/>
</svg>
"""

SVG_02 = """<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192" role="img" aria-label="Giorno del ritiro">
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

SVG_02_MARK = """<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="28 28 136 148" role="img" aria-label="Marchio Escilo — giorno del ritiro">
  <circle cx="70" cy="44" r="11" fill="#1f5c42"/>
  <circle cx="122" cy="44" r="11" fill="#1f5c42"/>
  <circle cx="70" cy="44" r="5" fill="#fff"/>
  <circle cx="122" cy="44" r="5" fill="#fff"/>
  <rect x="40" y="50" width="112" height="118" rx="18" fill="#1f5c42"/>
  <rect x="54" y="90" width="24" height="20" rx="5" fill="#fff"/>
  <rect x="84" y="90" width="24" height="20" rx="5" fill="#fff"/>
  <rect x="114" y="90" width="24" height="20" rx="5" fill="#fff"/>
  <rect x="54" y="118" width="24" height="20" rx="5" fill="#fff"/>
  <rect x="114" y="118" width="24" height="20" rx="5" fill="#fff"/>
  <rect x="84" y="118" width="24" height="20" rx="5" fill="#fff"/>
  <rect x="91" y="123.6" width="10" height="2.1" rx="0.8" fill="#1f5c42"/>
  <path d="M92 126.4h8l-1.1 5.6h-5.8z" fill="#1f5c42"/>
  <circle cx="94.2" cy="132.8" r="1.05" fill="#1f5c42"/>
  <circle cx="97.8" cy="132.8" r="1.05" fill="#1f5c42"/>
</svg>
"""

SVG_03 = """<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192" role="img" aria-label="Esci lo">
  <rect width="192" height="192" rx="42" fill="#eef6f1"/>
  <path d="M58 98h76l-8 54H66L58 98z" fill="#1f5c42"/>
  <rect x="64" y="138" width="64" height="20" rx="10" fill="#1f5c42"/>
  <rect x="80" y="112" width="32" height="28" rx="7" fill="#eef6f1"/>
  <circle cx="78" cy="160" r="9" fill="#1f5c42"/>
  <circle cx="114" cy="160" r="9" fill="#1f5c42"/>
  <circle cx="78" cy="160" r="3.4" fill="#eef6f1"/>
  <circle cx="114" cy="160" r="3.4" fill="#eef6f1"/>
  <g transform="rotate(-44 128 92)">
    <rect x="50" y="80" width="84" height="20" rx="8" fill="#1f5c42"/>
    <rect x="80" y="68" width="22" height="16" rx="6" fill="#3d9a6e"/>
  </g>
</svg>
"""

SVG_03_MARK = """<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="44 36 108 140" role="img" aria-label="Marchio Escilo — esci lo">
  <path d="M58 98h76l-8 54H66L58 98z" fill="#1f5c42"/>
  <rect x="64" y="138" width="64" height="20" rx="10" fill="#1f5c42"/>
  <rect x="80" y="112" width="32" height="28" rx="7" fill="#fff"/>
  <circle cx="78" cy="160" r="9" fill="#1f5c42"/>
  <circle cx="114" cy="160" r="9" fill="#1f5c42"/>
  <circle cx="78" cy="160" r="3.4" fill="#fff"/>
  <circle cx="114" cy="160" r="3.4" fill="#fff"/>
  <g transform="rotate(-44 128 92)">
    <rect x="50" y="80" width="84" height="20" rx="8" fill="#1f5c42"/>
    <rect x="80" y="68" width="22" height="16" rx="6" fill="#1f5c42"/>
  </g>
</svg>
"""


def write_svg() -> None:
    pairs = [
        ("01-cassonetto-cal", SVG_01, SVG_01_MARK),
        ("02-giorno-ritiro", SVG_02, SVG_02_MARK),
        ("03-esci-lo", SVG_03, SVG_03_MARK),
    ]
    for stem, app, mark in pairs:
        (OUT / f"{stem}.svg").write_text(app, encoding="utf-8")
        (OUT / f"{stem}-mark.svg").write_text(mark, encoding="utf-8")


def main() -> None:
    write_svg()
    save_pair(render_01(), "01-cassonetto-cal")
    save_pair(render_02(), "02-giorno-ritiro")
    save_pair(render_03(), "03-esci-lo")


if __name__ == "__main__":
    main()
