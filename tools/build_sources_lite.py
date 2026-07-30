"""Build docs/calendars/sources-lite.json from sources.json (PWA footer fields only)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "docs" / "calendars" / "sources.json"
OUT = ROOT / "docs" / "calendars" / "sources-lite.json"


def main() -> int:
    data = json.loads(SOURCES.read_text(encoding="utf-8"))
    comuni = data.get("comuni") or []
    lite = {
        "generatedAt": data.get("generatedAt"),
        "comuni": [
            {
                "id": c.get("id"),
                "provider": c.get("provider") or "",
                "sourcePage": c.get("sourcePage") or "",
            }
            for c in comuni
            if c.get("id")
        ],
    }
    OUT.write_text(json.dumps(lite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(lite['comuni'])} comuni)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
