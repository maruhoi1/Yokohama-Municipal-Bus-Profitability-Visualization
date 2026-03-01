#!/usr/bin/env python3
"""Build a GeoJSON for Yokohama municipal bus profitability visualization.

No external dependencies are required.
"""

from __future__ import annotations

import csv
import json
import re
import struct
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DBF_PATH = ROOT / "data/raw/N07-11_14.dbf"
SHP_PATH = ROOT / "data/raw/N07-11_14.shp"
CSV_PATH = ROOT / "data/raw/2024.csv"
OUT_PATH = ROOT / "web/data/routes_2024.geojson"


def read_dbf(path: Path) -> List[Dict[str, str]]:
    data = path.read_bytes()
    num_records = struct.unpack("<I", data[4:8])[0]
    header_length = struct.unpack("<H", data[8:10])[0]
    record_length = struct.unpack("<H", data[10:12])[0]

    fields: List[Tuple[str, int]] = []
    offset = 32
    while data[offset] != 0x0D:
        name = data[offset : offset + 11].split(b"\x00", 1)[0].decode("ascii")
        field_length = data[offset + 16]
        fields.append((name, field_length))
        offset += 32

    records: List[Dict[str, str]] = []
    position = header_length
    for _ in range(num_records):
        record_data = data[position : position + record_length]
        position += record_length
        if not record_data or record_data[0] == 0x2A:
            continue

        values: Dict[str, str] = {}
        p = 1
        for name, field_length in fields:
            raw = record_data[p : p + field_length]
            p += field_length
            values[name] = raw.decode("cp932", errors="ignore").strip()
        records.append(values)

    return records


def read_shp_polylines(path: Path) -> List[List[List[Tuple[float, float]]]]:
    data = path.read_bytes()
    if len(data) < 100:
        raise ValueError("Invalid .shp file")

    records: List[List[List[Tuple[float, float]]]] = []
    pos = 100  # shapefile header

    while pos + 8 <= len(data):
        # Record header (big endian): record number, content length (16-bit words)
        _, content_length_words = struct.unpack(">ii", data[pos : pos + 8]
        )
        content_length = content_length_words * 2
        content = data[pos + 8 : pos + 8 + content_length]
        pos += 8 + content_length

        if len(content) < 4:
            continue

        shape_type = struct.unpack("<i", content[0:4])[0]
        if shape_type == 0:
            records.append([])
            continue
        if shape_type not in (3, 13, 23):  # PolyLine / PolyLineZ / PolyLineM
            raise ValueError(f"Unexpected shape type: {shape_type}")

        num_parts, num_points = struct.unpack("<ii", content[36:44])
        parts = struct.unpack(f"<{num_parts}i", content[44 : 44 + 4 * num_parts])

        points_offset = 44 + 4 * num_parts
        points: List[Tuple[float, float]] = []
        for i in range(num_points):
            x, y = struct.unpack(
                "<dd", content[points_offset + i * 16 : points_offset + (i + 1) * 16]
            )
            points.append((x, y))

        geometry_parts: List[List[Tuple[float, float]]] = []
        for i, start in enumerate(parts):
            end = parts[i + 1] if i + 1 < num_parts else num_points
            geometry_parts.append(points[start:end])

        records.append(geometry_parts)

    return records


def load_profitability(path: Path) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            route_id = row["route_id"].strip()
            result[route_id] = row
    return result


def extract_numeric_route_tokens(system_name: str) -> List[str]:
    # e.g. "123", "12急行", "1系統" -> ["123"] etc.
    return re.findall(r"\d+", system_name)


def build() -> None:
    attrs = read_dbf(DBF_PATH)
    geoms = read_shp_polylines(SHP_PATH)
    profitability = load_profitability(CSV_PATH)

    if len(attrs) != len(geoms):
        raise ValueError(f"Record count mismatch: dbf={len(attrs)} shp={len(geoms)}")

    features = []
    matched, total = 0, 0

    for attr, parts in zip(attrs, geoms):
        if attr.get("N07_002") != "横浜市":
            continue
        total += 1
        if not parts:
            continue

        system_name = attr.get("N07_003", "")
        tokens = extract_numeric_route_tokens(system_name)

        route_data = None
        matched_route_id = None
        for token in tokens:
            if token in profitability:
                route_data = profitability[token]
                matched_route_id = token
                break

        coordinates = [[[x, y] for x, y in part] for part in parts]

        props = {
            "operator": attr.get("N07_002"),
            "system_name": system_name,
            "weekday_freq": attr.get("N07_004"),
            "saturday_freq": attr.get("N07_005"),
            "holiday_freq": attr.get("N07_006"),
            "route_id": matched_route_id,
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
    print(f"Yokohama city-operated route geometries: {total}")
    print(f"Matched profitability rows: {matched}")


if __name__ == "__main__":
    build()
