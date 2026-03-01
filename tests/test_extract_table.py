import unittest

from scripts.extract_table import ExtractionError, normalize_profit, parse_rows


class ExtractTableTests(unittest.TestCase):
    def test_normalize_profit_triangle_to_negative(self):
        self.assertEqual(normalize_profit("▲1,234"), "-1234")

    def test_parse_rows_accepts_valid_numeric_row(self):
        text = "系統,主な運行区間,収入,費用,差引損益,営業係数,1日当たり輸送人員\n101,横浜駅前〜本牧車庫前,1200000,1450000,▲250000,120.8,842"
        rows = parse_rows(text, fiscal_year=2023, strict=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["差引損益"], "-250000")

    def test_parse_rows_strict_mode_raises_for_invalid_numeric(self):
        text = "101,横浜駅前〜本牧車庫前,1200000,1450000,ABC,120.8,842"
        with self.assertRaises(ExtractionError):
            parse_rows(text, fiscal_year=2023, strict=True)


if __name__ == "__main__":
    unittest.main()
