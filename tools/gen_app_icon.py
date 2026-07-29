#!/usr/bin/env python3
"""Genera icone PWA (192/512/1024) e brand-mark.png da sorgente ad alta risoluzione."""
from __future__ import annotations

import pathlib

from PIL import Image, ImageChops

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "webapp" / "icon-proposals" / "icon-source-1024.png"
ICON_SIZES = (192, 512, 1024)
ICON_OUT_DIRS = (ROOT / "webapp", ROOT / "docs")
MARK_OUT_DIRS = (ROOT / "webapp", ROOT / "docs")
MINT = (232, 245, 233)  # #e8f5e9
ACCENT = (31, 92, 66)  # #1f5c42


def _fill_near_black(im: Image.Image, fill: tuple[int, int, int]) -> Image.Image:
    """Angoli neri della PNG sorgente (fuori dallo squircle) → colore di sfondo."""
    out = im.convert("RGB").copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b = px[x, y]
            if r + g + b < 40:
                px[x, y] = fill
    return out


def _trim_content(im: Image.Image, bg: tuple[int, int, int], threshold: int = 12) -> Image.Image:
    ref = Image.new("RGB", im.size, bg)
    diff = ImageChops.difference(im.convert("RGB"), ref)
    bbox = diff.convert("L").point(lambda p: 255 if p > threshold else 0).getbbox()
    if not bbox:
        raise SystemExit("nessun contenuto nell'immagine sorgente")
    pad = max(4, im.width // 128)
    x0, y0, x1, y1 = bbox
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(im.width, x1 + pad), min(im.height, y1 + pad)
    return im.crop((x0, y0, x1, y1))


def _square_canvas(im: Image.Image, fill: tuple[int, int, int]) -> Image.Image:
    side = max(im.size)
    canvas = Image.new("RGB", (side, side), fill)
    canvas.paste(im.convert("RGB"), ((side - im.width) // 2, (side - im.height) // 2))
    return canvas


def _write_app_icons(square: Image.Image) -> None:
    for size in ICON_SIZES:
        out_img = square.resize((size, size), Image.Resampling.LANCZOS)
        for base in ICON_OUT_DIRS:
            dest = base / f"icon-{size}.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            out_img.save(dest, format="PNG", optimize=True)
            print(f"Wrote {dest} ({dest.stat().st_size} bytes) size={size}")


def _is_glyph(r: int, g: int, b: int) -> bool:
    """Solo il glifo scuro (calendario + frecce), non sfondo mint né angoli neri."""
    total = r + g + b
    if total < 60:
        return False
    if total > 400:
        return False
    return True


def _write_brand_mark(clean: Image.Image) -> None:
    rgba = clean.convert("RGBA")
    px = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, _ = px[x, y]
            if _is_glyph(r, g, b):
                px[x, y] = (*ACCENT, 255)
            else:
                px[x, y] = (0, 0, 0, 0)

    bbox = rgba.getbbox()
    if not bbox:
        raise SystemExit("glifo brand-mark vuoto dopo estrazione")
    mark = rgba.crop(bbox)

    pad = max(8, mark.width // 32)
    canvas = Image.new("RGBA", (mark.width + pad * 2, mark.height + pad * 2), (0, 0, 0, 0))
    canvas.paste(mark, (pad, pad), mark)

    target = 512
    scale = target / max(canvas.size)
    out = canvas.resize(
        (max(1, int(canvas.width * scale)), max(1, int(canvas.height * scale))),
        Image.Resampling.LANCZOS,
    )
    for dest_dir in MARK_OUT_DIRS:
        dest = dest_dir / "brand-mark.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        out.save(dest, format="PNG", optimize=True)
        print(f"Wrote {dest} ({dest.stat().st_size} bytes) size={out.size}")


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"Sorgente icona mancante: {SRC}")
    src = Image.open(SRC)
    if src.size[0] < 512 or src.size[1] < 512:
        raise SystemExit(f"Sorgente troppo piccola: {src.size}")
    clean = _fill_near_black(src, MINT)
    cropped = _trim_content(clean, MINT)
    square = _square_canvas(cropped, MINT)
    _write_app_icons(square)
    _write_brand_mark(clean)


if __name__ == "__main__":
    main()
