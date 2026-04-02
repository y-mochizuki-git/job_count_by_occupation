from __future__ import annotations

import argparse
from pathlib import Path

from job_count_by_occupation.chart_report import (
    generate_major_category_comparison_report,
    generate_top20_report,
)
from job_count_by_occupation.coverage import (
    aggregate_major_category_monthly,
    build_national_market_scenarios,
    build_jobmedley_market_scenarios,
    create_major_category_coverage_template,
    create_occupation_coverage_master,
    estimate_national_jobs_from_coverage_template,
    estimate_occupation_national_jobs,
)
from job_count_by_occupation.estat import fetch_job_counts_from_year, fetch_latest_job_counts
from job_count_by_occupation.prefecture import (
    build_prefecture_major_occupation_scenarios,
    estimate_prefecture_occupation_jobs,
    estimate_prefecture_occupation_jobs_with_coverage,
    fetch_prefecture_total_monthly,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="job-count-by-occupation",
        description="全国の職種別有効求人数を e-Stat から取得します。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="最新の職種別有効求人数を取得します。")
    fetch_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="出力先ディレクトリ。default: ./outputs",
    )
    fetch_parser.add_argument(
        "--format",
        choices=["both", "csv", "json"],
        default="both",
        help="出力形式。default: both",
    )
    fetch_parser.add_argument(
        "--start-year",
        type=int,
        help="指定年の1月以降をまとめて取得します。例: 2010",
    )
    fetch_parser.add_argument(
        "--job-metric",
        choices=["both", "valid", "new"],
        default="both",
        help="取得する指標。both=有効求人数+新規求人数 / valid=有効求人数 / new=新規求人数",
    )

    chart_parser = subparsers.add_parser("chart", help="2022年4月以降のTOP20折れ線グラフHTMLを作ります。")
    chart_parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("outputs/job_counts_2010-01_to_2026-02.csv"),
        help="入力CSV。default: outputs/job_counts_2010-01_to_2026-02.csv",
    )
    chart_parser.add_argument(
        "--output-html",
        type=Path,
        default=Path("outputs/job_counts_top20_since_2022-04.html"),
        help="出力HTML。default: outputs/job_counts_top20_since_2022-04.html",
    )

    major_chart_parser = subparsers.add_parser("major-chart", help="大分類ごとの時系列比較HTMLを作ります。")
    major_chart_parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("outputs/occupation_national_estimate_since_2022-04.csv"),
        help="入力CSV。default: outputs/occupation_national_estimate_since_2022-04.csv",
    )
    major_chart_parser.add_argument(
        "--output-html",
        type=Path,
        default=Path("outputs/major_category_hellowork_vs_base_since_2022-04.html"),
        help="出力HTML。default: outputs/major_category_hellowork_vs_base_since_2022-04.html",
    )
    major_chart_parser.add_argument(
        "--start-year",
        type=int,
        default=2022,
        help="開始年。default: 2022",
    )
    major_chart_parser.add_argument(
        "--start-month",
        type=int,
        default=4,
        help="開始月。default: 4",
    )

    aggregate_parser = subparsers.add_parser("aggregate-major", help="大分類ごとの月次集計CSVを作ります。")
    aggregate_parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("outputs/job_counts_2010-01_to_2026-02.csv"),
        help="入力CSV。default: outputs/job_counts_2010-01_to_2026-02.csv",
    )
    aggregate_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/major_category_monthly_since_2022-04.csv"),
        help="出力CSV。default: outputs/major_category_monthly_since_2022-04.csv",
    )
    aggregate_parser.add_argument(
        "--start-year",
        type=int,
        default=2022,
        help="開始年。default: 2022",
    )
    aggregate_parser.add_argument(
        "--start-month",
        type=int,
        default=4,
        help="開始月。default: 4",
    )

    template_parser = subparsers.add_parser("coverage-template", help="大分類カバー率入力用のテンプレCSVを作ります。")
    template_parser.add_argument(
        "--aggregate-csv",
        type=Path,
        default=Path("outputs/major_category_monthly_since_2022-04.csv"),
        help="大分類月次集計CSV。default: outputs/major_category_monthly_since_2022-04.csv",
    )
    template_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/major_category_coverage_template_since_2022-04.csv"),
        help="出力テンプレCSV。default: outputs/major_category_coverage_template_since_2022-04.csv",
    )
    template_parser.add_argument(
        "--seed-defaults",
        action="store_true",
        help="仮説ベースの初期 coverage_rate を自動投入します。",
    )

    estimate_parser = subparsers.add_parser("coverage-estimate", help="入力済みカバー率テンプレから全国求人推計CSVを作ります。")
    estimate_parser.add_argument(
        "--template-csv",
        type=Path,
        default=Path("outputs/major_category_coverage_template_since_2022-04.csv"),
        help="カバー率入力済みテンプレCSV。default: outputs/major_category_coverage_template_since_2022-04.csv",
    )
    estimate_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/major_category_national_estimate_since_2022-04.csv"),
        help="推計結果CSV。default: outputs/major_category_national_estimate_since_2022-04.csv",
    )

    occupation_master_parser = subparsers.add_parser("occupation-coverage-master", help="occupation 単位の補正係数マスタを作ります。")
    occupation_master_parser.add_argument(
        "--occupation-master-csv",
        type=Path,
        default=Path("outputs/occupation_master_since_2022-04.csv"),
        help="説明付き occupation master。default: outputs/occupation_master_since_2022-04.csv",
    )
    occupation_master_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/occupation_coverage_master_since_2022-04.csv"),
        help="出力CSV。default: outputs/occupation_coverage_master_since_2022-04.csv",
    )

    occupation_estimate_parser = subparsers.add_parser("occupation-coverage-estimate", help="大分類カバー率と occupation 係数から occupation 単位の全国求人推計を作ります。")
    occupation_estimate_parser.add_argument(
        "--occupation-csv",
        type=Path,
        default=Path("outputs/job_counts_2010-01_to_2026-02.csv"),
        help="occupation 単位の元データCSV。default: outputs/job_counts_2010-01_to_2026-02.csv",
    )
    occupation_estimate_parser.add_argument(
        "--major-template-csv",
        type=Path,
        default=Path("outputs/major_category_coverage_template_since_2022-04.csv"),
        help="大分類カバー率入力済みテンプレCSV。default: outputs/major_category_coverage_template_since_2022-04.csv",
    )
    occupation_estimate_parser.add_argument(
        "--occupation-master-csv",
        type=Path,
        default=Path("outputs/occupation_coverage_master_since_2022-04.csv"),
        help="occupation 補正係数マスタ。default: outputs/occupation_coverage_master_since_2022-04.csv",
    )
    occupation_estimate_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/occupation_national_estimate_since_2022-04.csv"),
        help="推計結果CSV。default: outputs/occupation_national_estimate_since_2022-04.csv",
    )
    occupation_estimate_parser.add_argument(
        "--start-year",
        type=int,
        default=2022,
        help="開始年。default: 2022",
    )
    occupation_estimate_parser.add_argument(
        "--start-month",
        type=int,
        default=4,
        help="開始月。default: 4",
    )

    national_scenario_parser = subparsers.add_parser("national-scenarios", help="全国全体の月次市場規模シナリオCSVを作ります。")
    national_scenario_parser.add_argument(
        "--occupation-estimate-csv",
        type=Path,
        default=Path("outputs/occupation_national_estimate_since_2022-04.csv"),
        help="occupation 単位の全国推計CSV。default: outputs/occupation_national_estimate_since_2022-04.csv",
    )
    national_scenario_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/national_market_scenarios_since_2022-04.csv"),
        help="出力CSV。default: outputs/national_market_scenarios_since_2022-04.csv",
    )
    national_scenario_parser.add_argument(
        "--low-multiplier",
        type=float,
        default=0.70,
        help="base に掛ける low シナリオ倍率。default: 0.70",
    )
    national_scenario_parser.add_argument(
        "--high-multiplier",
        type=float,
        default=1.30,
        help="base に掛ける high シナリオ倍率。default: 1.30",
    )

    prefecture_total_parser = subparsers.add_parser("prefecture-total", help="都道府県別総量の月次CSVを作ります。")
    prefecture_total_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/prefecture_total_monthly_since_2022-04.csv"),
        help="出力CSV。default: outputs/prefecture_total_monthly_since_2022-04.csv",
    )
    prefecture_total_parser.add_argument(
        "--start-year",
        type=int,
        default=2022,
        help="開始年。default: 2022",
    )
    prefecture_total_parser.add_argument(
        "--start-month",
        type=int,
        default=4,
        help="開始月。default: 4",
    )

    prefecture_approx_parser = subparsers.add_parser("prefecture-occupation-approx", help="都道府県別総量 × 全国職業構成で都道府県別職業別の近似CSVを作ります。")
    prefecture_approx_parser.add_argument(
        "--prefecture-total-csv",
        type=Path,
        default=Path("outputs/prefecture_total_monthly_since_2022-04.csv"),
        help="都道府県別総量CSV。default: outputs/prefecture_total_monthly_since_2022-04.csv",
    )
    prefecture_approx_parser.add_argument(
        "--national-occupation-csv",
        type=Path,
        default=Path("outputs/job_counts_2010-01_to_2026-02.csv"),
        help="全国職業別CSV。default: outputs/job_counts_2010-01_to_2026-02.csv",
    )
    prefecture_approx_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/prefecture_occupation_approx_since_2022-04.csv"),
        help="出力CSV。default: outputs/prefecture_occupation_approx_since_2022-04.csv",
    )
    prefecture_approx_parser.add_argument(
        "--start-year",
        type=int,
        default=2022,
        help="開始年。default: 2022",
    )
    prefecture_approx_parser.add_argument(
        "--start-month",
        type=int,
        default=4,
        help="開始月。default: 4",
    )

    prefecture_coverage_parser = subparsers.add_parser("prefecture-occupation-coverage-approx", help="occupation 補正率を乗せた全国推計を都道府県総量に配賦して、都道府県×occupation×yearmonth の推計CSVを作ります。")
    prefecture_coverage_parser.add_argument(
        "--prefecture-total-csv",
        type=Path,
        default=Path("outputs/prefecture_total_monthly_since_2022-04.csv"),
        help="都道府県別総量CSV。default: outputs/prefecture_total_monthly_since_2022-04.csv",
    )
    prefecture_coverage_parser.add_argument(
        "--national-estimate-csv",
        type=Path,
        default=Path("outputs/occupation_national_estimate_since_2022-04.csv"),
        help="occupation 補正済み全国推計CSV。default: outputs/occupation_national_estimate_since_2022-04.csv",
    )
    prefecture_coverage_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/prefecture_occupation_coverage_approx_since_2022-04.csv"),
        help="出力CSV。default: outputs/prefecture_occupation_coverage_approx_since_2022-04.csv",
    )
    prefecture_coverage_parser.add_argument(
        "--start-year",
        type=int,
        default=2022,
        help="開始年。default: 2022",
    )
    prefecture_coverage_parser.add_argument(
        "--start-month",
        type=int,
        default=4,
        help="開始月。default: 4",
    )

    prefecture_scenarios_parser = subparsers.add_parser("prefecture-scenarios", help="年月×都道府県×大分類×職種で、ハローワーク / base / low / high のシナリオCSVを作ります。")
    prefecture_scenarios_parser.add_argument(
        "--prefecture-total-csv",
        type=Path,
        default=Path("archive/outputs/prefecture_total_monthly_since_2022-04.csv"),
        help="都道府県別総量CSV。default: archive/outputs/prefecture_total_monthly_since_2022-04.csv",
    )
    prefecture_scenarios_parser.add_argument(
        "--national-occupation-csv",
        type=Path,
        default=Path("outputs/job_counts_2010-01_to_2026-02.csv"),
        help="全国職業別CSV。default: outputs/job_counts_2010-01_to_2026-02.csv",
    )
    prefecture_scenarios_parser.add_argument(
        "--major-template-csv",
        type=Path,
        default=Path("outputs/major_category_coverage_template_since_2022-04.csv"),
        help="大分類カバー率テンプレCSV。default: outputs/major_category_coverage_template_since_2022-04.csv",
    )
    prefecture_scenarios_parser.add_argument(
        "--occupation-master-csv",
        type=Path,
        default=Path("outputs/occupation_coverage_master_since_2022-04.csv"),
        help="occupation 補正係数マスタ。default: outputs/occupation_coverage_master_since_2022-04.csv",
    )
    prefecture_scenarios_parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("outputs/prefecture_major_occupation_scenarios_since_2022-04.csv"),
        help="出力CSV。default: outputs/prefecture_major_occupation_scenarios_since_2022-04.csv",
    )
    prefecture_scenarios_parser.add_argument(
        "--start-year",
        type=int,
        default=2022,
        help="開始年。default: 2022",
    )
    prefecture_scenarios_parser.add_argument(
        "--start-month",
        type=int,
        default=4,
        help="開始月。default: 4",
    )
    prefecture_scenarios_parser.add_argument(
        "--low-multiplier",
        type=float,
        default=0.70,
        help="base に掛ける low シナリオ倍率。default: 0.70",
    )
    prefecture_scenarios_parser.add_argument(
        "--high-multiplier",
        type=float,
        default=1.30,
        help="base に掛ける high シナリオ倍率。default: 1.30",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "fetch":
        if args.start_year:
            records, created_files = fetch_job_counts_from_year(
                start_year=args.start_year,
                output_dir=args.output_dir,
                output_format=args.format,
                job_metric=args.job_metric,
            )
            print(f"取得開始年: {args.start_year}")
            print(f"取得期間: {records[0].year}-{records[0].month:02d} 〜 {records[-1].year}-{records[-1].month:02d}")
        else:
            dataset, records, created_files = fetch_latest_job_counts(
                output_dir=args.output_dir,
                output_format=args.format,
                job_metric=args.job_metric,
            )
            print(f"対象統計: {dataset.title}")
            print(f"調査年月: {dataset.surveyed_at}")
            print(f"公開日: {dataset.published_at}")
        print(f"取得指標: {args.job_metric}")
        print(f"取得件数: {len(records)}")
        for path in created_files:
            print(f"出力: {path}")
        return 0

    if args.command == "chart":
        output_path = generate_top20_report(
            csv_path=args.input_csv,
            output_path=args.output_html,
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "major-chart":
        output_path = generate_major_category_comparison_report(
            csv_path=args.input_csv,
            output_path=args.output_html,
            start_year=args.start_year,
            start_month=args.start_month,
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "aggregate-major":
        output_path = aggregate_major_category_monthly(
            input_csv=args.input_csv,
            output_csv=args.output_csv,
            start=(args.start_year, args.start_month),
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "coverage-template":
        output_path = create_major_category_coverage_template(
            aggregate_csv=args.aggregate_csv,
            output_csv=args.output_csv,
            seed_defaults=args.seed_defaults,
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "coverage-estimate":
        output_path = estimate_national_jobs_from_coverage_template(
            template_csv=args.template_csv,
            output_csv=args.output_csv,
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "occupation-coverage-master":
        output_path = create_occupation_coverage_master(
            occupation_master_csv=args.occupation_master_csv,
            output_csv=args.output_csv,
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "occupation-coverage-estimate":
        output_path = estimate_occupation_national_jobs(
            occupation_csv=args.occupation_csv,
            major_template_csv=args.major_template_csv,
            occupation_master_csv=args.occupation_master_csv,
            output_csv=args.output_csv,
            start=(args.start_year, args.start_month),
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "national-scenarios":
        output_path = build_national_market_scenarios(
            occupation_estimate_csv=args.occupation_estimate_csv,
            output_csv=args.output_csv,
            low_multiplier=args.low_multiplier,
            high_multiplier=args.high_multiplier,
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "jobmedley-scenarios":
        output_path = build_jobmedley_market_scenarios(
            occupation_estimate_csv=args.occupation_estimate_csv,
            output_csv=args.output_csv,
            low_multiplier=args.low_multiplier,
            high_multiplier=args.high_multiplier,
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "prefecture-total":
        output_path = fetch_prefecture_total_monthly(
            output_csv=args.output_csv,
            start=(args.start_year, args.start_month),
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "prefecture-occupation-approx":
        output_path = estimate_prefecture_occupation_jobs(
            prefecture_total_csv=args.prefecture_total_csv,
            national_occupation_csv=args.national_occupation_csv,
            output_csv=args.output_csv,
            start=(args.start_year, args.start_month),
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "prefecture-occupation-coverage-approx":
        output_path = estimate_prefecture_occupation_jobs_with_coverage(
            prefecture_total_csv=args.prefecture_total_csv,
            national_occupation_estimate_csv=args.national_estimate_csv,
            output_csv=args.output_csv,
            start=(args.start_year, args.start_month),
        )
        print(f"出力: {output_path}")
        return 0

    if args.command == "prefecture-scenarios":
        output_path = build_prefecture_major_occupation_scenarios(
            prefecture_total_csv=args.prefecture_total_csv,
            national_occupation_csv=args.national_occupation_csv,
            major_template_csv=args.major_template_csv,
            occupation_master_csv=args.occupation_master_csv,
            output_csv=args.output_csv,
            start=(args.start_year, args.start_month),
            low_multiplier=args.low_multiplier,
            high_multiplier=args.high_multiplier,
        )
        print(f"出力: {output_path}")
        return 0

    parser.error("未対応のコマンドです。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
