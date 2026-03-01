#!/usr/bin/env python3
"""Extract route profitability table from PDF/image/text and save CSV(s) to data/interim."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable

EXPECTED_COLUMNS = [
    "系統",
    "主な運行区間",
    "収入",
    "費用",
    "差引損益",
    "営業係数",
    "1日当たり輸送人員",
    "fiscal_year",
]


def normalize_numeric(value: str) -> str:
    """Normalize Japanese numeric notations (comma, spaces, ▲ for minus)."""
    text = str(value).strip().replace(",", "")
    if not text:
        return ""
    if text.startswith("▲"):
        text = f"-{text[1:]}"
    text = text.replace("−", "-")
    return text


def normalize_profit(value: str) -> str:
    """Normalize 差引損益 value and keep as numeric string."""
    return normalize_numeric(value)


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".csv"}:
        return path.read_text(encoding="utf-8")

    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "pytesseract is required for PDF/image OCR extraction. "
            "Install dependencies or provide a .txt/.csv source for dry-run parsing."
        ) from exc

    if suffix == ".pdf":
        try:
            from pdf2image import convert_from_path
        except ImportError as exc:
            raise RuntimeError("pdf2image is required to OCR PDF files.") from exc
        pages = convert_from_path(path)
        return "\n".join(pytesseract.image_to_string(page, lang="jpn") for page in pages)

    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        from PIL import Image

        image = Image.open(path)
        return pytesseract.image_to_string(image, lang="jpn")

    raise ValueError(f"Unsupported file type: {path}")


def detect_rows(text: str) -> Iterable[list[str]]:
    """Parse table-like lines separated by comma/tab/multi-space."""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "," in line:
            parts = [p.strip() for p in next(csv.reader([line]))]
        elif "\t" in line:
            parts = [p.strip() for p in line.split("\t")]
        else:
            parts = [p.strip() for p in re.split(r"\s{2,}", line)]

        if len(parts) < 7:
            continue
        yield parts


def parse_rows(text: str, fiscal_year: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for parts in detect_rows(text):
        if parts[0] in {"系統", "route_id"}:
            continue

        route_id = parts[0]
        section = parts[1]
        revenue = normalize_numeric(parts[2])
        cost = normalize_numeric(parts[3])
        profit = normalize_profit(parts[4])
        operating_ratio = normalize_numeric(parts[5])
        daily_passengers = normalize_numeric(parts[6])

        rows.append(
            {
                "系統": route_id,
                "主な運行区間": section,
                "収入": revenue,
                "費用": cost,
                "差引損益": profit,
                "営業係数": operating_ratio,
                "1日当たり輸送人員": daily_passengers,
                "fiscal_year": str(fiscal_year),
            }
        )
    return rows


def output_filename(source: Path) -> str:
    match = re.search(r"(\d{4}).*?p(\d+)", source.stem, flags=re.IGNORECASE)
    if match:
        year, page = match.groups()
        return f"{year}_p{int(page):02d}_routes.csv"
    return f"{source.stem}_routes.csv"


def write_csv(rows: list[dict[str, str]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", help="Raw source files (PDF/image/text)")
    parser.add_argument("--fiscal-year", type=int, required=True, help="Fiscal year for extracted rows")
    parser.add_argument("--output-dir", default="data/interim", help="Directory for generated interim CSV")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    for source_str in args.inputs:
        source = Path(source_str)
        text = extract_text(source)
        rows = parse_rows(text, args.fiscal_year)
        out_name = output_filename(source)
        out_path = output_dir / out_name
        write_csv(rows, out_path)
        print(f"wrote {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
