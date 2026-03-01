#!/usr/bin/env python3
"""Validate OCR interim tables against manually cleaned route profitability table."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

INTERIM_NUMERIC_COLS = ["収入", "費用", "差引損益", "営業係数", "1日当たり輸送人員"]
CLEANED_NUMERIC_COLS = ["revenue", "cost", "profit", "operating_ratio", "daily_passengers"]


@dataclass
class ValidationSummary:
    interim_rows: int
    cleaned_rows: int
    row_diff: int
    interim_missing_cells: int
    cleaned_missing_cells: int
    interim_conversion_failures: int
    cleaned_conversion_failures: int
    unmatched_in_interim: int
    unmatched_in_cleaned: int


def normalize_numeric(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().replace(",", "").replace("▲", "-").replace("−", "-")
    if normalized in {"", "nan", "None"}:
        return None
    return normalized


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_interim(interim_dir: Path) -> list[dict[str, str]]:
    paths = sorted(interim_dir.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No interim CSV found in {interim_dir}")

    rows: list[dict[str, str]] = []
    for path in paths:
        rows.extend(load_csv(path))
    return rows


def map_interim_to_cleaned(row: dict[str, str]) -> dict[str, str]:
    if "route_id" in row:
        return row

    section = row.get("主な運行区間", "")
    from_stop, to_stop = "", ""
    if "〜" in section:
        from_stop, to_stop = [x.strip() for x in section.split("〜", 1)]

    return {
        "route_id": row.get("系統", ""),
        "from_stop": from_stop,
        "to_stop": to_stop,
        "revenue": row.get("収入", ""),
        "cost": row.get("費用", ""),
        "profit": row.get("差引損益", ""),
        "operating_ratio": row.get("営業係数", ""),
        "daily_passengers": row.get("1日当たり輸送人員", ""),
        "fiscal_year": row.get("fiscal_year", ""),
    }


def count_missing_cells(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows for value in row.values() if value is None or str(value).strip() == "")


def count_numeric_conversion_failures(rows: list[dict[str, str]], numeric_cols: list[str]) -> int:
    failures = 0
    for row in rows:
        for col in numeric_cols:
            normalized = normalize_numeric(row.get(col))
            if normalized is None:
                continue
            try:
                float(normalized)
            except ValueError:
                failures += 1
    return failures


def key_row(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        str(row.get("route_id", "")).strip(),
        str(row.get("from_stop", "")).strip(),
        str(row.get("to_stop", "")).strip(),
        str(row.get("fiscal_year", "")).strip(),
    )


def write_diff_report(
    interim_rows: list[dict[str, str]], cleaned_rows: list[dict[str, str]], output_path: Path
) -> tuple[int, int]:
    interim_map = {key_row(r): r for r in interim_rows}
    cleaned_map = {key_row(r): r for r in cleaned_rows}

    missing_in_interim = sorted(set(cleaned_map.keys()) - set(interim_map.keys()))
    missing_in_cleaned = sorted(set(interim_map.keys()) - set(cleaned_map.keys()))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["side", "route_id", "from_stop", "to_stop", "fiscal_year", "reason"])
        for key in missing_in_interim:
            writer.writerow(["missing_in_interim", *key, "key not found in interim"])
        for key in missing_in_cleaned:
            writer.writerow(["missing_in_cleaned", *key, "key not found in cleaned"])

    return len(missing_in_interim), len(missing_in_cleaned)


def build_summary(interim_rows: list[dict[str, str]], cleaned_rows: list[dict[str, str]], diff_output: Path) -> ValidationSummary:
    mapped_interim = [map_interim_to_cleaned(r) for r in interim_rows]
    unmatched_in_interim, unmatched_in_cleaned = write_diff_report(mapped_interim, cleaned_rows, diff_output)

    return ValidationSummary(
        interim_rows=len(mapped_interim),
        cleaned_rows=len(cleaned_rows),
        row_diff=abs(len(mapped_interim) - len(cleaned_rows)),
        interim_missing_cells=count_missing_cells(mapped_interim),
        cleaned_missing_cells=count_missing_cells(cleaned_rows),
        interim_conversion_failures=count_numeric_conversion_failures(mapped_interim, CLEANED_NUMERIC_COLS),
        cleaned_conversion_failures=count_numeric_conversion_failures(cleaned_rows, CLEANED_NUMERIC_COLS),
        unmatched_in_interim=unmatched_in_interim,
        unmatched_in_cleaned=unmatched_in_cleaned,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interim-dir", default="data/interim", help="Directory containing OCR CSV outputs")
    parser.add_argument("--cleaned", default="data/cleaned/routes_profit.csv", help="Manually corrected CSV")
    parser.add_argument("--diff-output", default="data/interim/validation_diff.csv", help="Diff report path")
    args = parser.parse_args()

    interim_rows = load_interim(Path(args.interim_dir))
    cleaned_rows = load_csv(Path(args.cleaned))
    summary = build_summary(interim_rows, cleaned_rows, Path(args.diff_output))

    print("=== OCR vs Cleaned Validation ===")
    print(f"rows(interim): {summary.interim_rows}")
    print(f"rows(cleaned): {summary.cleaned_rows}")
    print(f"row_count_diff: {summary.row_diff}")
    print(f"missing_cells(interim): {summary.interim_missing_cells}")
    print(f"missing_cells(cleaned): {summary.cleaned_missing_cells}")
    print(f"numeric_conversion_failures(interim): {summary.interim_conversion_failures}")
    print(f"numeric_conversion_failures(cleaned): {summary.cleaned_conversion_failures}")
    print(f"unmatched_keys_missing_in_interim: {summary.unmatched_in_interim}")
    print(f"unmatched_keys_missing_in_cleaned: {summary.unmatched_in_cleaned}")
    print(f"diff_report: {args.diff_output}")

    has_issue = any(
        [
            summary.row_diff > 0,
            summary.interim_missing_cells > 0,
            summary.cleaned_missing_cells > 0,
            summary.interim_conversion_failures > 0,
            summary.cleaned_conversion_failures > 0,
            summary.unmatched_in_interim > 0,
            summary.unmatched_in_cleaned > 0,
        ]
    )
    if has_issue:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
