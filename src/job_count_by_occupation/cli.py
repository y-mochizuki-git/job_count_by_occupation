from __future__ import annotations

import argparse
from pathlib import Path

from job_count_by_occupation.chart_report import generate_top20_report
from job_count_by_occupation.estat import fetch_job_counts_from_year, fetch_latest_job_counts


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
            )
            print(f"取得開始年: {args.start_year}")
            print(f"取得期間: {records[0].year}-{records[0].month:02d} 〜 {records[-1].year}-{records[-1].month:02d}")
        else:
            dataset, records, created_files = fetch_latest_job_counts(
                output_dir=args.output_dir,
                output_format=args.format,
            )
            print(f"対象統計: {dataset.title}")
            print(f"調査年月: {dataset.surveyed_at}")
            print(f"公開日: {dataset.published_at}")
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

    parser.error("未対応のコマンドです。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
