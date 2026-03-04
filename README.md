# 横浜市営バス収支ビジュアライゼーション

横浜市営バスの路線別収支データ（`2024.csv`）と GTFS-JP データ（`routes.txt`, `trips.txt`, `shapes.txt`）を突合し、地図上で黒字／赤字を色分け表示する Web アプリケーションです。フロントエンドには **MapLibre GL JS** を使用しています。

## データソース

| ファイル | 概要 |
|---|---|
| `data/raw/routes.txt` | GTFS 路線定義（`route_id` ↔ `jp_parent_route_id` の対応） |
| `data/raw/routes_jp.txt` | 路線の日本語名・起終点情報 |
| `data/raw/trips.txt` | 便（トリップ）データ（`route_id` → `shape_id` の紐付け） |
| `data/raw/shapes.txt` | 路線の地理座標（描画用ポリライン） |
| `data/raw/2024.csv` | 2024年度の路線別収支データ（収入・費用・損益・営業係数・1日あたり乗客数） |

## 仕組み

1. **ビルドスクリプト** (`scripts/build_geojson_gtfs.py`) が GTFS データと収支 CSV を突合し、`web/data/routes_2024.geojson` を生成します。
2. 各路線は `jp_parent_route_id`（親路線ID）で集約されます。上り・下りなど複数の `route_id` が同じ親路線に属する場合でも、**代表の 1 方向のみの形状を採用**し、電車の路線図のように 1 系統＝1 本の線で表示します。
3. 数値系統名（例: `1` → `001`）は自動マッチされます。特殊名称の路線（例: `ベイサイドブルー` → `200`）はスクリプト内の対応表で手動マッピングしています。

## GeoJSON 生成手順

```bash
python scripts/build_geojson_gtfs.py
```

実行後に `web/data/routes_2024.geojson` が生成されます。

> **注**: レガシーの Shapefile ベースのビルドスクリプト (`scripts/build_geojson.py`) も残っていますが、現在は GTFS 版を使用してください。

## ローカル表示

```bash
python -m http.server 8000
# ブラウザで http://localhost:8000/web/index.html を開く
```

## GitHub Pages で公開する

このリポジトリには `web/` を GitHub Pages にデプロイするワークフロー (`.github/workflows/deploy-pages.yml`) が含まれています。

1. デフォルトブランチを `main` にする（ワークフローは `main` push で起動）。
2. `python scripts/build_geojson_gtfs.py` を実行して `web/data/routes_2024.geojson` を更新。
3. 変更を `main` に push。
4. GitHub の **Settings > Pages** で Source を **GitHub Actions** に設定。
5. Actions の `Deploy static map to GitHub Pages` が成功すると公開 URL が発行されます。

## 今後の改善案

1. 未マッチ系統の解消（一部の路線は GTFS データとの対応が取れていない）。
2. 年度切り替え UI を追加し、複数年度を比較。
3. GitHub Actions で GeoJSON 自動生成。
