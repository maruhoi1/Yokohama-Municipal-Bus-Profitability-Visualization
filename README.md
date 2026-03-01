# 横浜市営バス収支ビジュアライゼーション（MapLibre GL JS）

国土数値情報のバスルート Shapefile（`N07-11_14.*`）と、収支データ（`2024.csv`）を突合して、地図上で黒字/赤字を色分け表示するサンプルです。フロントエンドは **MapLibre GL JS** を使っています。

## 結論（調査結果）

- `N07-11_14.shp/.dbf/.shx` は、`N07_003`（バス系統）と線形ジオメトリを持っており、地図描画に利用可能です。
- このリポジトリの `2024.csv` と突合して `GeoJSON` を生成できることを確認しました。
- 単純な数値系統ID（例: `7`, `106`）は多くが自動マッチ可能です。
- 一方で、`A（中区・磯子区）` などの文字系統名や循環系統は、別途対応表を作ると精度が上がります。

## 生成手順

```bash
python scripts/build_geojson.py
```

実行後に `web/data/routes_2024.geojson` が生成されます。

## ローカル表示

```bash
python -m http.server 8000
# ブラウザで http://localhost:8000/web/index.html を開く
```

## GitHub Pages で公開する（無料）

このリポジトリには `web/` をそのまま GitHub Pages にデプロイするワークフローを追加しています。

1. GitHub リポジトリのデフォルトブランチを `main` にする（ワークフローは `main` push で起動）。
2. `python scripts/build_geojson.py` を実行して `web/data/routes_2024.geojson` を更新。
3. 変更を `main` に push。
4. GitHub の **Settings > Pages** で Source を **GitHub Actions** に設定。
5. Actions の `Deploy static map to GitHub Pages` が成功すると公開URLが発行されます。

## 今後の改善案

1. `N07_003` と `route_id` の対応表（CSV）を作り、未マッチ系統を解消。
2. 路線重複の統合（同一路線の上下便・区間便の取り扱い）ルールを整理。
3. 年度切り替えUIを追加し、複数年度を比較。
4. GitHub Actions で `GeoJSON` 自動更新。
