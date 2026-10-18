"""Offline evaluation tests, no cloud connections."""
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from evaluate import describe


class EvaluationTests(unittest.TestCase):
    def test_quality_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "processed_data.csv"
            pd.DataFrame({
                "time": ["2026-10-18T00:00:00Z", "2026-10-18T00:01:00Z",
                         "2026-10-18T00:01:00Z"],
                "temperature": [20, None, 23],
                "humidity": [50, 60, 70],
                "distance_cm": [10, 12, 13],
                "temperature_outlier": [0, 1, 0],
            }).to_csv(str(path), index=False)
            report = describe(path)
            self.assertEqual(report["rows"], 3)
            self.assertEqual(report["duplicate_timestamp_rows"], 1)
            self.assertEqual(report["sensor_stats"]["temperature"]["missing"], 1)
            self.assertEqual(report["sensor_stats"]["temperature"]["outliers_flagged"], 1)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(describe(Path(directory)/"missing.csv")["status"], "not_found")


if __name__ == "__main__":
    unittest.main()
