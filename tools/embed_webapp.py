#!/usr/bin/env python3
"""Genera bin/web_ui_embed.h da webapp/index.html + icon-192.png (gzip HTML)."""
from __future__ import annotations

import gzip
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "webapp" / "index.html"
ICON = ROOT / "webapp" / "icon-192.png"
OUT = ROOT / "bin" / "web_ui_embed.h"


def emit_bytes_array(lines: list[str], name: str, data: bytes) -> None:
    lines.append(f"static const size_t {name}_LEN = {len(data)};")
    lines.append(f"static const uint8_t {name}[] = {{")
    row: list[str] = []
    for b in data:
        row.append(f"0x{b:02x}")
        if len(row) >= 16:
            lines.append("  " + ", ".join(row) + ",")
            row = []
    if row:
        lines.append("  " + ", ".join(row) + ",")
    lines.append("};")


def main() -> None:
    raw = SRC.read_bytes()
    gz = gzip.compress(raw, compresslevel=9, mtime=0)
    if not ICON.is_file():
        raise SystemExit(f"Missing {ICON} — run tools/gen_app_icon.py first")
    icon = ICON.read_bytes()
    lines = [
        "// Auto-generato da tools/embed_webapp.py — non modificare a mano.",
        "#ifndef SMART_BIN_WEB_UI_EMBED_H",
        "#define SMART_BIN_WEB_UI_EMBED_H",
        "",
        "#include <Arduino.h>",
        "",
        f"// HTML originale: {len(raw)} byte → gzip (flash): {len(gz)} byte",
        f"// Icona PNG: {len(icon)} byte",
        "",
    ]
    emit_bytes_array(lines, "SMART_BIN_WEB_UI_GZ", gz)
    lines.append("")
    emit_bytes_array(lines, "SMART_BIN_WEB_ICON_PNG", icon)
    lines.extend(["", "#endif", ""])
    OUT.write_text("\n".join(lines), encoding="utf-8")
    saved = len(raw) - len(gz)
    pct = 100.0 * saved / len(raw) if raw else 0.0
    print(
        f"Wrote {OUT}  raw={len(raw)}  gzip={len(gz)}  "
        f"icon={len(icon)}  saved={saved} ({pct:.1f}%)"
    )


if __name__ == "__main__":
    main()
