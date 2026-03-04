#!/usr/bin/env python3
"""Build a GeoJSON for Yokohama municipal bus profitability visualization.

Uses GTFS-JP data (routes.txt, trips.txt, shapes.txt) from ODPT instead of
the legacy National Land Numerical Information Shapefile.

No external dependencies are required.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "data/raw/routes.txt"
ROUTES_JP_PATH = ROOT / "data/raw/routes_jp.txt"
TRIPS_PATH = ROOT / "data/raw/trips.txt"
SHAPES_PATH = ROOT / "data/raw/shapes.txt"
CSV_PATH = ROOT / "data/raw/2024.csv"
OUT_PATH = ROOT / "web/data/routes_2024.geojson"

# Manual mapping for non-numeric CSV route_ids to GTFS jp_parent_route_id.
# These routes have special names in the CSV that don't match the numeric
# "NNN系統" naming used in GTFS.
SPECIAL_ROUTE_MAP: Dict[str, str] = {
    "ぶらり野毛山動物園BUS": "089",
    "ベイサイドブルー": "200",
    "鴨居・東本郷線": "221",
    "ふれあい緑区十日市場": "272",
    "ふれあい緑区中山": "240",
    "ぶらり三渓園BUS": "280",
    "聖隷横浜病院循環": "288",
    "三井アウトレット線": "299",
}


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_profitability(path: Path) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    for row in load_csv(path):
        route_id = row["route_id"].strip()
        result[route_id] = row
    return result


def load_shapes(path: Path) -> Dict[str, List[Tuple[float, float]]]:
    """Load shapes.txt and return {shape_id: [(lon, lat), ...]} sorted by sequence."""
    raw: Dict[str, List[Tuple[int, float, float]]] = defaultdict(list)
    for row in load_csv(path):
        shape_id = row["shape_id"]
        seq = int(row["shape_pt_sequence"])
        lat = float(row["shape_pt_lat"])
        lon = float(row["shape_pt_lon"])
        raw[shape_id].append((seq, lon, lat))

    shapes: Dict[str, List[Tuple[float, float]]] = {}
    for shape_id, pts in raw.items():
        pts.sort(key=lambda x: x[0])
        shapes[shape_id] = [(lon, lat) for _, lon, lat in pts]
    return shapes


def build_route_to_shapes(
    routes_rows: List[Dict[str, str]],
    trips_rows: List[Dict[str, str]],
) -> Dict[str, List[str]]:
    """Map jp_parent_route_id -> list of unique shape_ids for that parent route."""
    # route_id -> jp_parent_route_id
    route_to_parent: Dict[str, str] = {}
    for row in routes_rows:
        route_to_parent[row["route_id"]] = row["jp_parent_route_id"]

    # jp_parent_route_id -> set of shape_ids
    parent_shapes: Dict[str, set] = defaultdict(set)
    for row in trips_rows:
        route_id = row["route_id"]
        shape_id = row.get("shape_id", "").strip()
        if not shape_id:
            continue
        parent_id = route_to_parent.get(route_id)
        if parent_id:
            parent_shapes[parent_id].add(shape_id)

    return {pid: sorted(sids) for pid, sids in parent_shapes.items()}


def build_route_names(routes_rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Map jp_parent_route_id -> route_short_name (e.g. '001' -> '001系統')."""
    names: Dict[str, str] = {}
    for row in routes_rows:
        pid = row["jp_parent_route_id"]
        if pid not in names:
            names[pid] = row["route_short_name"]
    return names


def match_csv_route_id(parent_id: str, profitability: Dict[str, Dict[str, str]]) -> str | None:
    """Find the CSV route_id that matches a GTFS jp_parent_route_id."""
    # Try stripping leading zeros: "001" -> "1", "089" -> "89"
    numeric_id = str(int(parent_id))
    if numeric_id in profitability:
        return numeric_id

    # Check special mapping (reverse lookup)
    for csv_id, gtfs_pid in SPECIAL_ROUTE_MAP.items():
        if gtfs_pid == parent_id and csv_id in profitability:
            return csv_id

    return None


def build() -> None:
    routes_rows = load_csv(ROUTES_PATH)
    trips_rows = load_csv(TRIPS_PATH)
    shapes = load_shapes(SHAPES_PATH)
    profitability = load_profitability(CSV_PATH)

    parent_to_shapes = build_route_to_shapes(routes_rows, trips_rows)
    route_names = build_route_names(routes_rows)

    features = []
    matched = 0
    total = len(parent_to_shapes)

    for parent_id, shape_ids in sorted(parent_to_shapes.items()):
        system_name = route_names.get(parent_id, f"{parent_id}系統")

        # Collect all shape geometries for this parent route
        coordinates: List[List[List[float]]] = []
        for sid in shape_ids:
            pts = shapes.get(sid)
            if pts:
                coordinates.append([[lon, lat] for lon, lat in pts])

        if not coordinates:
            continue

        csv_route_id = match_csv_route_id(parent_id, profitability)
        route_data = profitability.get(csv_route_id) if csv_route_id else None

        props: dict = {
            "system_name": system_name,
            "route_id": csv_route_id,
        }

        if route_data:
            profit = float(route_data["profit"])
            props.update(
                {
                    "from_stop": route_data["from_stop"],
                    "to_stop": route_data["to_stop"],
                    "revenue": float(route_data["revenue"]),
                    "cost": float(route_data["cost"]),
                    "profit": profit,
                    "operating_ratio": float(route_data["operating_ratio"]),
                    "daily_passengers": float(route_data["daily_passengers"]),
                    "fiscal_year": route_data["fiscal_year"],
                    "profit_status": "黒字" if profit >= 0 else "赤字",
                }
            )
            matched += 1
        else:
            props.update(
                {
                    "profit": None,
                    "profit_status": "不明",
                }
            )

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "MultiLineString", "coordinates": coordinates},
                "properties": props,
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    geojson = {"type": "FeatureCollection", "features": features}
    OUT_PATH.write_text(json.dumps(geojson, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote {OUT_PATH}")
    print(f"Parent routes with shapes: {total}")
    print(f"Features written: {len(features)}")
    print(f"Matched profitability rows: {matched} / {len(profitability)}")
    unmatched = [
        rid for rid in profitability
        if not any(match_csv_route_id(pid, {rid: profitability[rid]}) == rid for pid in parent_to_shapes)
    ]
    if unmatched:
        print(f"Unmatched CSV route_ids: {', '.join(unmatched)}")


if __name__ == "__main__":
    build()
