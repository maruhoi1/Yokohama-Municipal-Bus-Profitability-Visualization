import tempfile
import unittest
from pathlib import Path

from scripts.validate_table import build_summary


class ValidateTableTests(unittest.TestCase):
    def test_build_summary_detects_key_mismatch(self):
        interim_rows = [
            {
                "系統": "101",
                "主な運行区間": "横浜駅前〜本牧車庫前",
                "収入": "1200000",
                "費用": "1450000",
                "差引損益": "-250000",
                "営業係数": "120.8",
                "1日当たり輸送人員": "842",
                "fiscal_year": "2023",
            }
        ]
        cleaned_rows = [
            {
                "route_id": "999",
                "from_stop": "横浜駅前",
                "to_stop": "本牧車庫前",
                "revenue": "1200000",
                "cost": "1450000",
                "profit": "-250000",
                "operating_ratio": "120.8",
                "daily_passengers": "842",
                "fiscal_year": "2023",
            }
        ]

        with tempfile.TemporaryDirectory() as d:
            diff_path = Path(d) / "diff.csv"
            summary = build_summary(interim_rows, cleaned_rows, diff_path)

            self.assertEqual(summary.unmatched_in_interim, 1)
            self.assertEqual(summary.unmatched_in_cleaned, 1)
            self.assertTrue(diff_path.exists())


if __name__ == "__main__":
    unittest.main()
