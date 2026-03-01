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


def normalize_numeric(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().replace(",", "").replace("▲", "-").replace("−", "-")
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
        for row in load_csv(path):
            if "route_id" in row:
                row = {
                    "系統": row.get("route_id", ""),
                    "主な運行区間": f"{row.get('from_stop', '')}〜{row.get('to_stop', '')}",
                    "収入": row.get("revenue", ""),
                    "費用": row.get("cost", ""),
                    "差引損益": row.get("profit", ""),
                    "営業係数": row.get("operating_ratio", ""),
                    "1日当たり輸送人員": row.get("daily_passengers", ""),
                    "fiscal_year": row.get("fiscal_year", ""),
                }
            rows.append(row)
    return rows


def count_missing_cells(rows: list[dict[str, str]]) -> int:
    missing = 0
    for row in rows:
        for value in row.values():
            if value is None or str(value).strip() == "":
                missing += 1
    return missing


def count_numeric_conversion_failures(rows: list[dict[str, str]], numeric_cols: list[str]) -> int:
    failures = 0
    for row in rows:
        for col in numeric_cols:
            raw_value = row.get(col)
            normalized = normalize_numeric(raw_value)
            if normalized is None:
                continue
            try:
                float(normalized)
            except ValueError:
                failures += 1
    return failures


def build_summary(interim_rows: list[dict[str, str]], cleaned_rows: list[dict[str, str]]) -> ValidationSummary:
    return ValidationSummary(
        interim_rows=len(interim_rows),
        cleaned_rows=len(cleaned_rows),
        row_diff=abs(len(interim_rows) - len(cleaned_rows)),
        interim_missing_cells=count_missing_cells(interim_rows),
        cleaned_missing_cells=count_missing_cells(cleaned_rows),
        interim_conversion_failures=count_numeric_conversion_failures(interim_rows, INTERIM_NUMERIC_COLS),
        cleaned_conversion_failures=count_numeric_conversion_failures(cleaned_rows, CLEANED_NUMERIC_COLS),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interim-dir", default="data/interim", help="Directory containing OCR CSV outputs")
    parser.add_argument(
        "--cleaned", default="data/cleaned/routes_profit.csv", help="Manually corrected routes profit CSV"
    )
    args = parser.parse_args()

    interim_rows = load_interim(Path(args.interim_dir))
    cleaned_rows = load_csv(Path(args.cleaned))
    summary = build_summary(interim_rows, cleaned_rows)

    print("=== OCR vs Cleaned Validation ===")
    print(f"rows(interim): {summary.interim_rows}")
    print(f"rows(cleaned): {summary.cleaned_rows}")
    print(f"row_count_diff: {summary.row_diff}")
    print(f"missing_cells(interim): {summary.interim_missing_cells}")
    print(f"missing_cells(cleaned): {summary.cleaned_missing_cells}")
    print(f"numeric_conversion_failures(interim): {summary.interim_conversion_failures}")
    print(f"numeric_conversion_failures(cleaned): {summary.cleaned_conversion_failures}")

    has_issue = any(
        [
            summary.row_diff > 0,
            summary.interim_missing_cells > 0,
            summary.cleaned_missing_cells > 0,
            summary.interim_conversion_failures > 0,
            summary.cleaned_conversion_failures > 0,
        ]
    )
    if has_issue:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
