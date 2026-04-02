import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_count_by_occupation.prefecture import _clean_prefecture_name, estimate_prefecture_occupation_jobs
from job_count_by_occupation.prefecture import estimate_prefecture_occupation_jobs_with_coverage


class PrefectureTests(unittest.TestCase):
    def test_clean_prefecture_name(self) -> None:
        self.assertEqual("青森県", _clean_prefecture_name("青森県ケン"))
        self.assertEqual("北海道", _clean_prefecture_name("北海道"))

    def test_estimate_prefecture_occupation_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            prefecture_total = Path(tmp_dir) / "pref.csv"
            national = Path(tmp_dir) / "national.csv"
            output = Path(tmp_dir) / "out.csv"

            prefecture_total.write_text(
                "\n".join(
                    [
                        "year,month,prefecture,prefecture_total_job_count,national_total_job_count,source_sheet,source_url",
                        "2022,4,北海道,280,1000,sheet,url",
                    ]
                ),
                encoding="utf-8",
            )
            national.write_text(
                "\n".join(
                    [
                        "year,month,major_category,occupation_name,job_count",
                        "2022,4,総計,職業計,1000",
                        "2022,4,専門・技術,情報処理・通信技術者,100",
                        "2022,4,サービス,サービス職業従事者,300",
                    ]
                ),
                encoding="utf-8",
            )

            estimate_prefecture_occupation_jobs(prefecture_total, national, output, start=(2022, 4))
            with output.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["prefecture"], "北海道")
            self.assertEqual(rows[0]["estimated_prefecture_occupation_job_count"], "28")
            self.assertEqual(rows[1]["estimated_prefecture_occupation_job_count"], "84")

    def test_estimate_prefecture_occupation_jobs_with_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            prefecture_total = Path(tmp_dir) / "pref.csv"
            national_estimate = Path(tmp_dir) / "national_est.csv"
            output = Path(tmp_dir) / "out.csv"

            prefecture_total.write_text(
                "\n".join(
                    [
                        "year,month,prefecture,prefecture_total_job_count,national_total_job_count,source_sheet,source_url",
                        "2022,4,北海道,280,1000,sheet,url",
                    ]
                ),
                encoding="utf-8",
            )
            national_estimate.write_text(
                "\n".join(
                    [
                        "year,month,major_category,occupation_name,estat_job_count,major_category_coverage_rate,occupation_relative_factor,coverage_rate,estimated_national_job_count,factor_source,confidence,notes",
                        "2022,4,専門・技術,情報処理・通信技術者,100,0.18,0.55,0.099,200,heuristic,low,",
                        "2022,4,サービス,サービス職業従事者,300,0.28,0.95,0.266,800,heuristic,low,",
                    ]
                ),
                encoding="utf-8",
            )

            estimate_prefecture_occupation_jobs_with_coverage(prefecture_total, national_estimate, output, start=(2022, 4))
            with output.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["estimated_prefecture_occupation_job_count"], "56")
            self.assertEqual(rows[1]["estimated_prefecture_occupation_job_count"], "224")


if __name__ == "__main__":
    unittest.main()
