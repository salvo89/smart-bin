#!/usr/bin/env python3
"""Genera webapp/icon-192.png: cassonetto stile taglio laser (PNG palette leggero)."""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "webapp" / "icon-192.png"

# Palette: sfondo app / legno / linea taglio / vano / led
BG = (31, 92, 66)       # --accent
WOOD = (214, 186, 140)  # compensato
CUT = (36, 28, 20)      # tratto laser
VOID = (20, 58, 42)     # vano (mostra lo sfondo scuro)
LED = (80, 220, 120)


def main() -> None:
    s = 192
    img = Image.new("RGB", (s, s), BG)
    d = ImageDraw.Draw(img)

    # Safe zone per maschera Android (cerchio/squircle): contenuto ~48% del canvas.
    # Margine ampio così angoli/pettini non vengono tagliati.
    content = int(s * 0.48)
    ox = (s - content) / 2
    oy = (s - content) / 2
    mid = s / 2

    top = oy + content * 0.18
    bot = oy + content * 0.88
    top_w = content * 0.70
    bot_w = content * 0.54
    tl, tr = mid - top_w / 2, mid + top_w / 2
    bl, br = mid - bot_w / 2, mid + bot_w / 2
    finger = 4.0
    step = 7.0

    # Lid (barra superiore, tipica del cassonetto)
    lid_h = 10
    lid = [
        (tl - 4, top - lid_h - 3),
        (tr + 4, top - lid_h - 3),
        (tr + 1, top - 1),
        (tl - 1, top - 1),
    ]
    d.polygon(lid, fill=WOOD, outline=CUT)
    # Maniglia / svasatura coperchio (incisione)
    d.rounded_rectangle(
        (mid - 14, top - lid_h + 1, mid + 14, top - lid_h + 5),
        radius=2,
        outline=CUT,
        width=2,
    )

    # Corpo trapezoidale con pettini laterali (stile pannello laser)
    def x_at(y: float, side: str) -> float:
        t = (y - top) / (bot - top)
        if side == "L":
            return tl + (bl - tl) * t
        return tr + (br - tr) * t

    # Costruisci contorno: top → right fingers → bottom → left fingers (reverse)
    outline: list[tuple[float, float]] = [(tl, top), (tr, top)]

    # Right finger edge along tapered side
    y = top
    out = True
    while y < bot - 0.01:
        yn = min(y + step, bot)
        xo = x_at((y + yn) / 2, "R")
        xi = xo - finger
        x = xo if out else xi
        outline.append((x, y))
        outline.append((x, yn))
        y = yn
        out = not out
    outline.append((br, bot))
    outline.append((bl, bot))

    # Left finger edge upward
    y = bot
    out = True
    while y > top + 0.01:
        yn = max(y - step, top)
        xo = x_at((y + yn) / 2, "L")
        xi = xo + finger
        x = xo if out else xi
        outline.append((x, y))
        outline.append((x, yn))
        y = yn
        out = not out

    d.polygon(outline, fill=WOOD, outline=CUT)
    # Rinforza tratto (look laser 2px)
    d.line(outline + [outline[0]], fill=CUT, width=2)

    # Vano trapezoidale (taglio interno, come front-vetrina)
    vx0 = mid - content * 0.18
    vx1 = mid + content * 0.18
    vy0 = top + content * 0.16
    vy1 = bot - content * 0.20
    inset = content * 0.05
    window = [
        (vx0, vy0),
        (vx1, vy0),
        (vx1 - inset, vy1),
        (vx0 + inset, vy1),
    ]
    d.polygon(window, fill=VOID, outline=CUT)
    d.line(window + [window[0]], fill=CUT, width=2)

    # Linea incisione orizzontale sotto il vano
    d.line((bl + 8, bot - 10, br - 8, bot - 10), fill=CUT, width=2)

    # LED “smart” (cerchio piccolo, tipico indicatore)
    cx, cy, r = int(tr - 12), int(top + 10), 4
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=CUT)
    d.ellipse((cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1), fill=LED)

    # Palette PNG (pochi colori → file piccolo)
    pal = img.convert("P", palette=Image.ADAPTIVE, colors=8)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pal.save(OUT, format="PNG", optimize=True)
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
