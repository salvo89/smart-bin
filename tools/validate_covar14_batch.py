"""Validate converted Covar14 headers against cached PDFs."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tmp_calendars" / "covar14" / "manifest.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    fail = 0
    for item in manifest:
        pdf = ROOT / "tmp_calendars" / "covar14" / f"{item['file_slug']}.pdf"
        for year in item["years"]:
            header = ROOT / "docs" / "calendars" / f"{item['file_slug']}-{year}.h"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "covar14_pdf_to_h.py"),
                    "validate",
                    str(pdf),
                    str(header),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else proc.stderr
            ok = "missing=0 extra=0" in line
            if not ok:
                print(f"FAIL {item['file_slug']} {year}: {line}")
                fail += 1
    total = sum(len(item["years"]) for item in manifest)
    print(f"validated {total} files, failures {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
