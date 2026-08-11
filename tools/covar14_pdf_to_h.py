import argparse
import html
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin

import fitz
import requests


MONTHS = {
    "GENNAIO": 1,
    "FEBBRAIO": 2,
    "MARZO": 3,
    "APRILE": 4,
    "MAGGIO": 5,
    "GIUGNO": 6,
    "LUGLIO": 7,
    "AGOSTO": 8,
    "SETTEMBRE": 9,
    "OTTOBRE": 10,
    "NOVEMBRE": 11,
    "DICEMBRE": 12,
}

BIN_MAP = {
    "CARTA": 0,
    "ORGANICO": 1,
    "RU": 2,
    "PLASTICA": 3,
    "VERDE": 4,
}

ADDRESS_PREFIXES = (
    "VIA ",
    "VICOLO ",
    "PIAZZA ",
    "STRADA ",
    "CASCINA ",
    "CORSO ",
    "LOCALITA",
    "LOCALITÀ",
    "BORGATA ",
    "VIALE ",
)


def fetch_text(url: str) -> str:
    return requests.get(url, timeout=60).text


def list_pdfs(page_url: str) -> list[tuple[str, str]]:
    text = fetch_text(page_url)
    pairs = re.findall(
        r'<a[^>]+href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\'][^>]*>(.*?)</a>',
        text,
        flags=re.I | re.S,
    )
    out = []
    for href, inner in pairs:
        label = re.sub(r"<[^>]+>", " ", inner)
        label = " ".join(html.unescape(label).split())
        out.append((label, urljoin(page_url, href)))
    return out


def download_if_needed(source: str, download_to: Path) -> Path:
    if source.startswith("http://") or source.startswith("https://"):
        data = requests.get(source, timeout=120).content
        download_to.write_bytes(data)
        return download_to
    return Path(source)


def normalize_text(text: str) -> str:
    text = text.replace("�", "'")
    text = text.replace("LAV =", "")
    text = text.replace("+LAV", "")
    text = text.replace("*", "")
    return " ".join(text.split())


def extract_addresses(doc: fitz.Document) -> list[str]:
    page = doc[1]
    text = page.get_text("text")
    lines = [normalize_text(x.strip()) for x in text.splitlines()]
    out = []
    for line in lines:
        if not line:
            continue
        if line.startswith(ADDRESS_PREFIXES):
            out.append(line)
    uniq = []
    seen = set()
    for line in out:
        if line not in seen:
            seen.add(line)
            uniq.append(line)
    return uniq


def parse_event_bins(text: str) -> list[int]:
    text = normalize_text(text.upper())
    for blocked in (
        "TAGLIANDO",
        "SACCHI",
        "FORNITURA",
        "MODALITA' DI RITIRO",
        "MODALITA DI RITIRO",
        "SAPEVI",
        "TONNELLATA",
        "BOTTIGLIA",
        "RICICLARE",
    ):
        if blocked in text:
            return []
    bins = []
    for key, idx in BIN_MAP.items():
        if re.search(r"\b" + re.escape(key) + r"\b", text):
            bins.append(idx)
    return sorted(set(bins))


def parse_day_row_block(text: str, x0: float, x1: float) -> list[int]:
    clean = normalize_text(text)
    width = x1 - x0

    if re.fullmatch(r"\d{1,2}", clean) and width <= 40:
        return [int(clean)]

    if re.fullmatch(r"\d{1,2}\s+\d{1,2}", clean) and width <= 320:
        return [int(x) for x in clean.split()]

    # Wide "DOMENICA 17" blocks can span left weekday + right day number.
    if re.fullmatch(r"[A-Za-zÀ-ÿ' ]+\s+\d{1,2}", clean) and width <= 360:
        return [int(re.search(r"(\d{1,2})$", clean).group(1))]

    return []


def match_event_to_day(
    target_rows: dict[int, float],
    y0: float,
    y1: float | None = None,
) -> int | None:
    if not target_rows:
        return None

    # Use label center, then take the latest day header still above that center.
    y_center = (y0 + (y1 if y1 is not None else y0)) / 2.0
    above = [d for d, row_y in target_rows.items() if row_y <= y_center]
    if above:
        return max(above, key=lambda d: target_rows[d])
    return min(target_rows, key=lambda d: abs(target_rows[d] - y_center))


def extract_entries(doc: fitz.Document) -> list[tuple[int, int, int, int]]:
    entries = []
    page_months: dict[int, tuple[int, int]] = {}

    for page_index in range(7, doc.page_count - 1):
        page = doc[page_index]
        for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
            t = " ".join(text.split())
            m = re.search(
                r"\b(" + "|".join(MONTHS.keys()) + r")\b\s+(\d{4})\b",
                t.upper(),
            )
            if m and x0 < 90 and y0 < 180:
                page_months[page_index] = (MONTHS[m.group(1)], int(m.group(2)))
                if page_index + 1 < doc.page_count - 1:
                    page_months[page_index + 1] = page_months[page_index]
                break

    for page_index in range(7, doc.page_count - 1):
        page = doc[page_index]
        blocks = page.get_text("blocks")
        month_year = page_months.get(page_index)
        if month_year is None:
            continue
        current_month, current_year = month_year

        left_rows = {}
        right_rows = {}

        for x0, y0, x1, y1, text, *_ in blocks:
            nums = parse_day_row_block(text, x0, x1)
            if not nums:
                continue
            if x0 < 100:
                if len(nums) == 1:
                    # If the block stretches into the right column, the number is right-side.
                    if x1 > 300:
                        right_rows[nums[0]] = y0
                    else:
                        left_rows[nums[0]] = y0
                elif len(nums) == 2:
                    left_rows[nums[0]] = y0
                    right_rows[nums[1]] = y0
            elif 300 < x0 < 340 and len(nums) == 1:
                right_rows[nums[0]] = y0

        # Word-level events avoid cross-column merges and educational tip boxes.
        words = page.get_text("words")
        left_bounds = None
        right_bounds = None
        if left_rows:
            left_bounds = (min(left_rows.values()) - 10, max(left_rows.values()) + 45)
        if right_rows:
            right_bounds = (min(right_rows.values()) - 10, max(right_rows.values()) + 45)

        event_words = []
        for x0, y0, x1, y1, word, *_ in words:
            bounds = left_bounds if x0 < 320 else right_bounds
            if bounds is None or y0 < bounds[0] or y0 > bounds[1]:
                continue
            token = normalize_text(word).upper().strip(" ,;")
            if not token:
                continue
            if token in {"NOTE", "LAV", "RACCOLTA", "LAVAGGIO", "RIFIUTI", "INDIFFERENZIATI"}:
                continue
            if token.startswith("SAPEVI") or token in {"TONNELLATA", "BOTTIGLIA", "RICICLARE"}:
                continue
            clean = token.replace("+LAV", "").replace("*", "")
            if clean in BIN_MAP:
                event_words.append((x0, y0, x1, y1, clean))

        clusters: dict[tuple[str, int], list[tuple[float, float, float, float, str]]] = defaultdict(list)
        for x0, y0, x1, y1, token in event_words:
            side = "left" if x0 < 320 else "right"
            # Bucket by approximate row using 20pt bins.
            row_key = int(round(y0 / 20.0))
            clusters[(side, row_key)].append((x0, y0, x1, y1, token))

        for (side, _row_key), group in clusters.items():
            group = sorted(group, key=lambda item: item[0])
            raw = " ".join(token for *_coords, token in group)
            bins = parse_event_bins(raw)
            if not bins:
                continue
            y0 = min(item[1] for item in group)
            y1 = max(item[3] for item in group)
            x0 = min(item[0] for item in group)
            # Ignore tip/paragraph leftovers that somehow survived token filters.
            width = max(item[2] for item in group) - x0
            if width > 180:
                continue
            target_rows = left_rows if side == "left" else right_rows
            day = match_event_to_day(target_rows, y0, y1)
            if day is None:
                continue
            for bin_idx in bins:
                entries.append((current_year, current_month, day, bin_idx))

    uniq = sorted(set(entries))
    return uniq


def calendar_data_header_lines(
    comune_name: str,
    zone_label: str,
    provider: str,
    addresses: list[str],
    year: int,
) -> list[str]:
    lines: list[str] = []
    if addresses:
        addr_text = ", ".join(addresses)
        lines.append(f"// {comune_name} {zone_label} ({provider}): {addr_text}")
    else:
        lines.append(f"// {comune_name} {zone_label} ({provider})")
    lines.append(f"// Anno {year} — solo dati; struct e helper in docs/calendar.h")
    lines.append(
        "// Mappa: 0 Carta, 1 Organico, 2 Indifferenziata, 3 Plastica, 4 Verde, 5 Vetro; PWA-only 6 Spazzamento"
    )
    lines.append("// Lista ORDINATA (YYYYMMDD) per ricerca binaria.")
    return lines


def write_year_file(
    out_path: Path,
    comune_name: str,
    zone_label: str,
    provider: str,
    addresses: list[str],
    year: int,
    entries: list[tuple[int, int, int, int]],
) -> None:
    bins_name = {
        0: "Carta",
        1: "Organico",
        2: "Indifferenziata",
        3: "Plastica",
        4: "Verde",
        5: "Vetro",
        6: "Spazzamento",
    }
    lines = calendar_data_header_lines(
        comune_name, zone_label, provider, addresses, year
    )
    lines.append("")
    for y, m, d, b in entries:
        label = bins_name.get(b, f"bin{b}")
        lines.append(f"  {{{y}, {m}, {d}, {b}}},  // {d:02d}/{m:02d}/{y} {label}")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def strip_calendar_to_data_only(path: Path) -> bool:
    """Converte un file legacy (fragment + standalone) in solo-dati."""
    text = path.read_text(encoding="utf-8")
    if "#if defined(ESCILO_CALENDAR_FRAGMENT)" not in text:
        return False

    frag_match = re.search(
        r"#if defined\(ESCILO_CALENDAR_FRAGMENT\)\s*\n([\s\S]*?)\n#else",
        text,
    )
    if not frag_match:
        raise ValueError(f"Fragment non trovato in {path}")

    data_lines = [ln.rstrip() for ln in frag_match.group(1).splitlines() if ln.strip()]

    header_lines: list[str] = []
    else_match = re.search(r"#else[^\n]*\n([\s\S]*?)struct CalendarEntry", text)
    if else_match:
        for line in else_match.group(1).splitlines():
            stripped = line.strip()
            if stripped.startswith("//"):
                header_lines.append(stripped)

    year_match = re.search(r"-(\d{4})\.h$", path.name)
    year = year_match.group(1) if year_match else "?"

    out_header: list[str] = []
    for line in header_lines:
        if re.search(r"Anno \d{4}", line):
            out_header.append(
                f"// Anno {year} — solo dati; struct e helper in docs/calendar.h"
            )
        elif "Mappa cassonetti" in line or line.startswith("// 0 Carta"):
            continue
        elif "LAV" in line or "ORDINATA" in line:
            continue
        else:
            out_header.append(line)

    if not out_header:
        stem = path.stem
        out_header = [f"// {stem}", f"// Anno {year} — solo dati; struct e helper in docs/calendar.h"]
    elif not any("solo dati" in line for line in out_header):
        out_header.append(
            f"// Anno {year} — solo dati; struct e helper in docs/calendar.h"
        )
    if not any("Mappa cassonetti" in line for line in out_header):
        out_header.append(
            "// Mappa cassonetti: 0 Carta, 1 Organico, 2 Indifferenziata, 3 Plastica, 4 Verde, 5 Vetro"
        )
    if not any("ORDINATA" in line or "ordinata" in line.lower() for line in out_header):
        out_header.append("// Lista ORDINATA (YYYYMMDD) per ricerca binaria.")

    lines = out_header + [""] + data_lines + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return True


def parse_existing_header(path: Path) -> list[tuple[int, int, int, int]]:
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(-?\d+)\s*\}", text)
    return [(int(y), int(m), int(d), int(b)) for y, m, d, b in matches]


def convert_pdf(args: argparse.Namespace) -> int:
    tmp_pdf = Path(args.work_pdf or "_covar14_tmp.pdf")
    pdf_path = download_if_needed(args.source, tmp_pdf)
    doc = fitz.open(pdf_path)

    addresses = extract_addresses(doc)
    entries = extract_entries(doc)
    if not entries:
        raise SystemExit("Nessuna entry calendario estratta dal PDF.")

    grouped: dict[int, list[tuple[int, int, int, int]]] = defaultdict(list)
    for item in entries:
        grouped[item[0]].append(item)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    for year, year_entries in sorted(grouped.items()):
        out_path = outdir / f"{args.slug}-{year}.h"
        write_year_file(
            out_path=out_path,
            comune_name=args.comune,
            zone_label=args.zone,
            provider=args.provider,
            addresses=addresses,
            year=year,
            entries=year_entries,
        )
        print(f"Wrote {out_path}")

    return 0


def validate_against_header(args: argparse.Namespace) -> int:
    tmp_pdf = Path(args.work_pdf or "_covar14_validate.pdf")
    pdf_path = download_if_needed(args.source, tmp_pdf)
    doc = fitz.open(pdf_path)
    header_path = Path(args.header)
    expected = sorted(set(parse_existing_header(header_path)))
    years = sorted({y for y, _, _, _ in expected})
    extracted_all = sorted(set(extract_entries(doc)))
    extracted = [item for item in extracted_all if item[0] in years]

    extracted_set = set(extracted)
    expected_set = set(expected)

    missing = sorted(expected_set - extracted_set)
    extra = sorted(extracted_set - expected_set)

    print(f"expected={len(expected)} extracted={len(extracted)} missing={len(missing)} extra={len(extra)}")
    if missing:
        print("MISSING:")
        for item in missing[:50]:
            print(item)
    if extra:
        print("EXTRA:")
        for item in extra[:50]:
            print(item)
    return 0 if not missing and not extra else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list-pdfs")
    p_list.add_argument("page_url")

    p_conv = sub.add_parser("convert")
    p_conv.add_argument("source")
    p_conv.add_argument("--slug", required=True)
    p_conv.add_argument("--comune", required=True)
    p_conv.add_argument("--zone", required=True)
    p_conv.add_argument("--provider", default="Covar14")
    p_conv.add_argument("--outdir", default="docs/calendars")
    p_conv.add_argument("--work-pdf")

    p_val = sub.add_parser("validate")
    p_val.add_argument("source")
    p_val.add_argument("header")
    p_val.add_argument("--work-pdf")

    p_strip = sub.add_parser(
        "strip-all",
        help="Converte file calendario legacy in formato solo-dati",
    )
    p_strip.add_argument(
        "--dir",
        default="docs/calendars",
        help="Cartella con i file *.h da convertire",
    )

    args = parser.parse_args()

    if args.cmd == "list-pdfs":
        for label, href in list_pdfs(args.page_url):
            print(f"{label} => {href}")
        return 0

    if args.cmd == "convert":
        return convert_pdf(args)

    if args.cmd == "validate":
        return validate_against_header(args)

    if args.cmd == "strip-all":
        cal_dir = Path(args.dir)
        converted = 0
        skipped = 0
        for path in sorted(cal_dir.glob("*.h")):
            if strip_calendar_to_data_only(path):
                converted += 1
                print(f"Stripped {path.name}")
            else:
                skipped += 1
        print(f"Done: {converted} converted, {skipped} already data-only")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

