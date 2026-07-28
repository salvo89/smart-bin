#!/usr/bin/env python3
"""Genera icon-192.png (con sfondo) e brand-mark.png (solo glifo trasparente)."""
from __future__ import annotations

import pathlib

from PIL import Image, ImageChops

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "webapp" / "icon-proposals" / "icon-proposal-2-calendar-leaf.png"
ICON_OUTS = (
    ROOT / "webapp" / "icon-192.png",
    ROOT / "docs" / "icon-192.png",
)
MARK_OUTS = (
    ROOT / "webapp" / "brand-mark.png",
    ROOT / "docs" / "brand-mark.png",
)
MINT = (228, 243, 235)
ACCENT = (31, 92, 66)


def _trim_white(im: Image.Image, threshold: int = 12) -> Image.Image:
    white = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im.convert("RGB"), white)
    bbox = diff.convert("L").point(lambda p: 255 if p > threshold else 0).getbbox()
    if not bbox:
        raise SystemExit("nessun contenuto nell'immagine sorgente")
    pad = 8
    x0, y0, x1, y1 = bbox
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(im.width, x1 + pad), min(im.height, y1 + pad)
    return im.crop((x0, y0, x1, y1))


def _write_app_icon(cropped: Image.Image) -> None:
    side = max(cropped.size)
    canvas = Image.new("RGB", (side, side), MINT)
    canvas.paste(
        cropped.convert("RGB"),
        ((side - cropped.width) // 2, (side - cropped.height) // 2),
    )
    px = canvas.load()
    for y in range(side):
        for x in range(side):
            r, g, b = px[x, y]
            if r > 245 and g > 245 and b > 245:
                px[x, y] = MINT
            elif r > 235 and g > 235 and b > 235 and abs(r - g) < 8 and abs(g - b) < 8:
                px[x, y] = MINT

    out192 = canvas.resize((192, 192), Image.Resampling.LANCZOS)
    pal = out192.convert("P", palette=Image.ADAPTIVE, colors=32)
    for out in ICON_OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        pal.save(out, format="PNG", optimize=True)
        print(f"Wrote {out} ({out.stat().st_size} bytes)")


def _is_background(r: int, g: int, b: int) -> bool:
    # bianco, mint chiaro, ombre soft — non il tratto verde
    brightness = (r + g + b) / 3
    if brightness > 210:
        return True
    # mint plate (#e4f3eb-ish)
    if g > r and g > b - 5 and r > 180 and g > 200 and b > 180:
        return True
    return False


def _write_brand_mark(cropped: Image.Image) -> None:
    rgba = cropped.convert("RGBA")
    px = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = px[x, y]
            if _is_background(r, g, b):
                px[x, y] = (0, 0, 0, 0)
            else:
                # unifica al verde accent per tratto nitido
                px[x, y] = (*ACCENT, 255)

    bbox = rgba.getbbox()
    if not bbox:
        raise SystemExit("glifo brand-mark vuoto dopo rimozione sfondo")
    mark = rgba.crop(bbox)

    # padding stretto intorno al glifo
    pad = max(4, mark.width // 40)
    canvas = Image.new("RGBA", (mark.width + pad * 2, mark.height + pad * 2), (0, 0, 0, 0))
    canvas.paste(mark, (pad, pad), mark)

    # ~256px sul lato lungo per retina
    scale = 256 / max(canvas.size)
    out = canvas.resize(
        (max(1, int(canvas.width * scale)), max(1, int(canvas.height * scale))),
        Image.Resampling.LANCZOS,
    )
    for dest in MARK_OUTS:
        dest.parent.mkdir(parents=True, exist_ok=True)
        out.save(dest, format="PNG", optimize=True)
        print(f"Wrote {dest} ({dest.stat().st_size} bytes) size={out.size}")


def main() -> None:
    if not SRC.is_file():
        raise SystemExit(f"Sorgente icona mancante: {SRC}")
    cropped = _trim_white(Image.open(SRC))
    _write_app_icon(cropped)
    _write_brand_mark(cropped)


if __name__ == "__main__":
    main()
