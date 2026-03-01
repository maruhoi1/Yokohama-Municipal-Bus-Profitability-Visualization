# Yokohama Municipal Bus Profitability Visualization

## Data workflow

1. Place source PDFs/images in `data/raw/` using year/page naming:
   - `YYYY_pNN_<description>.pdf`
   - `YYYY_pNN_<description>.png`
2. Run OCR extraction:
   - `python3 scripts/extract_table.py data/raw/2023_p01_route_profit_report.pdf --fiscal-year 2023`
3. Manually correct into canonical table `data/cleaned/routes_profit.csv` columns:
   - `route_id,from_stop,to_stop,revenue,cost,profit,operating_ratio,daily_passengers,fiscal_year`
4. Validate OCR vs cleaned:
   - `python3 scripts/validate_table.py`

Validation outputs `data/interim/validation_diff.csv` for key-level mismatches.
