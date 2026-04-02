import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_count_by_occupation.offer_rate_chart import (
    create_sample_offer_rate_csv,
    generate_offer_rate_explorer_html,
)


class OfferRateChartTests(unittest.TestCase):
    def test_create_sample_offer_rate_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "sample.csv"
            create_sample_offer_rate_csv(output)
            with output.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["date"], "2025-11")
            self.assertEqual(rows[0]["prefecture_hellowork_job_count"], "1200")
            self.assertEqual(rows[0]["job_offer_count"], "180")

    def test_generate_offer_rate_explorer_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_csv = Path(tmp_dir) / "input.csv"
            output_html = Path(tmp_dir) / "out.html"
            input_csv.write_text(
                "\n".join(
                    [
                        "date,prefecture,major_category,occupation_name,prefecture_hellowork_job_count,prefecture_base_job_count,job_offer_count",
                        "2026-01,北海道,サービス,介護サービス職業従事者,100,200,10",
                        "2026-02,北海道,サービス,介護サービス職業従事者,120,240,12",
                    ]
                ),
                encoding="utf-8",
            )

            generate_offer_rate_explorer_html(input_csv, output_html)
            text = output_html.read_text(encoding="utf-8")
            self.assertIn("job_offer_count / prefecture_hellowork_job_count", text)
            self.assertIn("北海道", text)
            self.assertIn("2026-02", text)
            self.assertIn('<option value="total">合算</option>', text)

    def test_generate_offer_rate_explorer_html_treats_blank_offer_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_csv = Path(tmp_dir) / "input.csv"
            output_html = Path(tmp_dir) / "out.html"
            input_csv.write_text(
                "\n".join(
                    [
                        "date,prefecture,major_category,occupation_name,prefecture_hellowork_job_count,prefecture_base_job_count,job_offer_count",
                        "2026-01,北海道,サービス,介護サービス職業従事者,100,200,",
                        "2026-02,北海道,サービス,介護サービス職業従事者,120,240,12",
                    ]
                ),
                encoding="utf-8",
            )

            generate_offer_rate_explorer_html(input_csv, output_html)
            text = output_html.read_text(encoding="utf-8")
            self.assertIn('"rows":[[0,0,0,0,100,200,0],[1,0,0,0,120,240,12]]', text)


if __name__ == "__main__":
    unittest.main()
