import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_count_by_occupation.coverage import (
    aggregate_major_category_monthly,
    build_national_market_scenarios,
    build_jobmedley_market_scenarios,
    create_major_category_coverage_template,
    create_occupation_coverage_master,
    estimate_national_jobs_from_coverage_template,
    estimate_occupation_national_jobs,
)


class CoverageTests(unittest.TestCase):
    def test_aggregate_major_category_monthly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "input.csv"
            out = Path(tmp_dir) / "agg.csv"
            src.write_text(
                "\n".join(
                    [
                        "year,month,major_category,occupation_name,job_count",
                        "2022,4,サービス,A,10",
                        "2022,4,サービス,B,20",
                        "2022,4,専門・技術,C,5",
                        "2022,4,総計,職業計,35",
                        "2022,5,サービス,A,12",
                    ]
                ),
                encoding="utf-8",
            )

            aggregate_major_category_monthly(src, out, start=(2022, 4))
            with out.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(
                rows,
                [
                    {"year": "2022", "month": "4", "major_category": "サービス", "estat_job_count": "30"},
                    {"year": "2022", "month": "4", "major_category": "専門・技術", "estat_job_count": "5"},
                    {"year": "2022", "month": "5", "major_category": "サービス", "estat_job_count": "12"},
                ],
            )

    def test_create_template_and_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            agg = Path(tmp_dir) / "agg.csv"
            template = Path(tmp_dir) / "template.csv"
            estimate = Path(tmp_dir) / "estimate.csv"
            agg.write_text(
                "\n".join(
                    [
                        "year,month,major_category,estat_job_count",
                        "2022,4,サービス,100",
                        "2022,4,専門・技術,50",
                    ]
                ),
                encoding="utf-8",
            )

            create_major_category_coverage_template(agg, template, seed_defaults=True)
            with template.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(rows[0]["coverage_rate"], "0.45")

            rows[0]["coverage_rate"] = "0.25"
            rows[0]["coverage_source"] = "test"
            rows[1]["coverage_rate"] = "0.5"
            with template.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            estimate_national_jobs_from_coverage_template(template, estimate)
            with estimate.open(encoding="utf-8") as fh:
                estimated_rows = list(csv.DictReader(fh))
            self.assertEqual(estimated_rows[0]["estimated_national_job_count"], "400")
            self.assertEqual(estimated_rows[1]["estimated_national_job_count"], "100")

    def test_create_occupation_master_and_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            occupation_master = Path(tmp_dir) / "occupation_master.csv"
            generated_master = Path(tmp_dir) / "occupation_coverage_master.csv"
            occupation_csv = Path(tmp_dir) / "occupation.csv"
            major_template = Path(tmp_dir) / "major_template.csv"
            estimate = Path(tmp_dir) / "occupation_estimate.csv"

            occupation_master.write_text(
                "\n".join(
                    [
                        "occupation_name,major_category,description,examples_or_scope,jobmedley_related",
                        "情報処理・通信技術者,専門・技術,IT職,開発など,false",
                        "保健師，助産師，看護師,専門・技術,看護職,看護業務,true",
                    ]
                ),
                encoding="utf-8",
            )
            create_occupation_coverage_master(occupation_master, generated_master)
            with generated_master.open(encoding="utf-8") as fh:
                master_rows = list(csv.DictReader(fh))
            self.assertEqual(master_rows[0]["occupation_relative_factor"], "0.55")
            self.assertEqual(master_rows[1]["jobmedley_related"], "true")

            occupation_csv.write_text(
                "\n".join(
                    [
                        "year,month,job_metric,major_category,occupation_name,job_count",
                        "2022,4,有効求人数,専門・技術,情報処理・通信技術者,100",
                        "2022,4,有効求人数,専門・技術,保健師，助産師，看護師,200",
                    ]
                ),
                encoding="utf-8",
            )
            major_template.write_text(
                "\n".join(
                    [
                        "year,month,major_category,estat_job_count,coverage_rate,estimated_national_job_count,coverage_source,notes",
                        "2022,4,専門・技術,300,0.2,1500,test,",
                    ]
                ),
                encoding="utf-8",
            )
            estimate_occupation_national_jobs(
                occupation_csv=occupation_csv,
                major_template_csv=major_template,
                occupation_master_csv=generated_master,
                output_csv=estimate,
                start=(2022, 4),
            )
            with estimate.open(encoding="utf-8") as fh:
                estimated_rows = list(csv.DictReader(fh))
            self.assertEqual(estimated_rows[0]["coverage_rate"], "0.110000")
            self.assertEqual(estimated_rows[0]["estimated_national_job_count"], "909")
            self.assertEqual(estimated_rows[1]["jobmedley_related"], "true")

    def test_build_jobmedley_market_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "occupation_estimate.csv"
            out = Path(tmp_dir) / "jobmedley_scenarios.csv"
            src.write_text(
                "\n".join(
                    [
                        "year,month,major_category,occupation_name,jobmedley_related,estat_job_count,estimated_national_job_count",
                        "2022,4,専門・技術,保健師，助産師，看護師,true,200,800",
                        "2022,4,サービス,介護サービス職業従事者,true,300,900",
                        "2022,4,専門・技術,情報処理・通信技術者,false,100,700",
                    ]
                ),
                encoding="utf-8",
            )

            build_jobmedley_market_scenarios(src, out, low_multiplier=0.5, high_multiplier=1.5)
            with out.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["hellowork_active_job_count"], "500")
            self.assertEqual(rows[0]["estimated_national_active_job_count_base"], "1700")
            self.assertEqual(rows[0]["estimated_national_active_job_count_low"], "850")
            self.assertEqual(rows[0]["estimated_national_active_job_count_high"], "2550")

    def test_build_national_market_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "occupation_estimate.csv"
            out = Path(tmp_dir) / "national_scenarios.csv"
            src.write_text(
                "\n".join(
                    [
                        "year,month,occupation_name,estat_job_count,estimated_national_job_count",
                        "2022,4,職業計,1000,",
                        "2022,4,A,200,800",
                        "2022,4,B,300,900",
                    ]
                ),
                encoding="utf-8",
            )

            build_national_market_scenarios(src, out, low_multiplier=0.5, high_multiplier=1.5)
            with out.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["estimated_occupation_count"], "2")
            self.assertEqual(rows[0]["hellowork_active_job_count"], "1000")
            self.assertEqual(rows[0]["estimated_national_active_job_count_base"], "1700")
            self.assertEqual(rows[0]["estimated_national_active_job_count_low"], "850")
            self.assertEqual(rows[0]["estimated_national_active_job_count_high"], "2550")


if __name__ == "__main__":
    unittest.main()
