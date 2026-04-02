from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.request import Request, urlopen

from job_count_by_occupation.estat import USER_AGENT, XlsxReader, is_target_job_metric


PREFECTURE_TOTAL_URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040428402&fileKind=0"
PREFECTURE_TOTAL_SHEET = "第１４表ー４（パート含む常用）"


def fetch_prefecture_total_monthly(
    output_csv: Path,
    start: Tuple[int, int] = (2022, 4),
) -> Path:
    request = Request(PREFECTURE_TOTAL_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        workbook_bytes = response.read()

    reader = XlsxReader.from_bytes(workbook_bytes)
    sheet = reader.read_sheet_by_name(PREFECTURE_TOTAL_SHEET)
    prefecture_columns = _find_prefecture_columns(sheet)

    rows: List[Dict[str, str]] = []
    row_number = 29
    while True:
        year_text = sheet.get(f"A{row_number}", "").strip()
        month_text = sheet.get(f"C{row_number}", "").strip()
        if not year_text:
            break
        year_match = re.search(r"(\d{4})年", year_text)
        month_match = re.search(r"(\d{1,2})", month_text)
        if not year_match or not month_match:
            row_number += 1
            continue

        year = int(year_match.group(1))
        month = int(month_match.group(1))
        if (year, month) < start:
            row_number += 1
            continue

        national_total = int(sheet.get(f"D{row_number}", "0") or "0")
        for prefecture_name, column in prefecture_columns:
            raw_value = sheet.get(f"{column}{row_number}", "").strip()
            if not raw_value.isdigit():
                continue
            rows.append(
                {
                    "year": str(year),
                    "month": str(month),
                    "prefecture": prefecture_name,
                    "prefecture_total_job_count": raw_value,
                    "national_total_job_count": str(national_total),
                    "source_sheet": PREFECTURE_TOTAL_SHEET,
                    "source_url": PREFECTURE_TOTAL_URL,
                }
            )
        row_number += 1

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "prefecture",
                "prefecture_total_job_count",
                "national_total_job_count",
                "source_sheet",
                "source_url",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_csv


def estimate_prefecture_occupation_jobs(
    prefecture_total_csv: Path,
    national_occupation_csv: Path,
    output_csv: Path,
    start: Tuple[int, int] = (2022, 4),
) -> Path:
    occupation_rows_by_month: Dict[Tuple[int, int], List[Dict[str, str]]] = {}
    national_total_by_month: Dict[Tuple[int, int], int] = {}

    with national_occupation_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not is_target_job_metric(row):
                continue
            year = int(row["year"])
            month = int(row["month"])
            if (year, month) < start:
                continue
            if row["occupation_name"] == "職業計":
                national_total_by_month[(year, month)] = int(row["job_count"])
                continue
            occupation_rows_by_month.setdefault((year, month), []).append(row)

    estimated_rows: List[Dict[str, str]] = []
    with prefecture_total_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            year = int(row["year"])
            month = int(row["month"])
            month_key = (year, month)
            if month_key not in occupation_rows_by_month:
                continue
            national_total = national_total_by_month.get(month_key)
            if not national_total:
                continue

            prefecture_total = int(row["prefecture_total_job_count"])
            for occupation_row in occupation_rows_by_month[month_key]:
                occupation_name = occupation_row["occupation_name"]
                occupation_job_count = int(occupation_row["job_count"])
                occupation_share = occupation_job_count / national_total
                estimated_prefecture_job_count = round(prefecture_total * occupation_share)
                estimated_rows.append(
                    {
                        "year": str(year),
                        "month": str(month),
                        "prefecture": row["prefecture"],
                        "major_category": occupation_row.get("major_category", ""),
                        "occupation_name": occupation_name,
                        "prefecture_total_job_count": str(prefecture_total),
                        "national_total_job_count": str(national_total),
                        "national_occupation_job_count": str(occupation_job_count),
                        "national_occupation_share": f"{occupation_share:.8f}",
                        "estimated_prefecture_occupation_job_count": str(estimated_prefecture_job_count),
                        "approximation_method": "prefecture_total_x_national_occupation_share",
                    }
                )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "prefecture",
                "major_category",
                "occupation_name",
                "prefecture_total_job_count",
                "national_total_job_count",
                "national_occupation_job_count",
                "national_occupation_share",
                "estimated_prefecture_occupation_job_count",
                "approximation_method",
            ],
        )
        writer.writeheader()
        writer.writerows(estimated_rows)
    return output_csv


def estimate_prefecture_occupation_jobs_with_coverage(
    prefecture_total_csv: Path,
    national_occupation_estimate_csv: Path,
    output_csv: Path,
    start: Tuple[int, int] = (2022, 4),
) -> Path:
    national_estimated_rows_by_month: Dict[Tuple[int, int], List[Dict[str, str]]] = {}
    national_estimated_total_by_month: Dict[Tuple[int, int], int] = {}

    with national_occupation_estimate_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            year = int(row["year"])
            month = int(row["month"])
            if (year, month) < start:
                continue
            estimated_text = row.get("estimated_national_job_count", "").strip()
            if not estimated_text:
                continue
            estimated_value = int(estimated_text)
            month_key = (year, month)
            national_estimated_rows_by_month.setdefault(month_key, []).append(row)
            national_estimated_total_by_month[month_key] = national_estimated_total_by_month.get(month_key, 0) + estimated_value

    estimated_rows: List[Dict[str, str]] = []
    with prefecture_total_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            year = int(row["year"])
            month = int(row["month"])
            month_key = (year, month)
            if month_key not in national_estimated_rows_by_month:
                continue
            national_estimated_total = national_estimated_total_by_month.get(month_key)
            if not national_estimated_total:
                continue

            prefecture_total = int(row["prefecture_total_job_count"])
            for occupation_row in national_estimated_rows_by_month[month_key]:
                estimated_national_job_count = int(occupation_row["estimated_national_job_count"])
                share = estimated_national_job_count / national_estimated_total
                estimated_prefecture_job_count = round(prefecture_total * share)
                estimated_rows.append(
                    {
                        "year": str(year),
                        "month": str(month),
                        "prefecture": row["prefecture"],
                        "major_category": occupation_row.get("major_category", ""),
                        "occupation_name": occupation_row["occupation_name"],
                        "prefecture_total_job_count": str(prefecture_total),
                        "national_estimated_total_job_count": str(national_estimated_total),
                        "national_estimated_occupation_job_count": str(estimated_national_job_count),
                        "national_estimated_occupation_share": f"{share:.8f}",
                        "estimated_prefecture_occupation_job_count": str(estimated_prefecture_job_count),
                        "approximation_method": "prefecture_total_x_national_estimated_occupation_share",
                    }
                )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "prefecture",
                "major_category",
                "occupation_name",
                "prefecture_total_job_count",
                "national_estimated_total_job_count",
                "national_estimated_occupation_job_count",
                "national_estimated_occupation_share",
                "estimated_prefecture_occupation_job_count",
                "approximation_method",
            ],
        )
        writer.writeheader()
        writer.writerows(estimated_rows)
    return output_csv


def build_prefecture_major_occupation_scenarios(
    prefecture_total_csv: Path,
    national_occupation_csv: Path,
    major_template_csv: Path,
    occupation_master_csv: Path,
    output_csv: Path,
    start: Tuple[int, int] = (2022, 4),
    low_multiplier: float = 0.70,
    high_multiplier: float = 1.30,
) -> Path:
    prefecture_totals_valid: Dict[Tuple[int, int], List[Dict[str, str]]] = {}
    with prefecture_total_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = (int(row["year"]), int(row["month"]))
            if key < start:
                continue
            prefecture_totals_valid.setdefault(key, []).append(row)

    major_rates: Dict[Tuple[int, int, str], float] = {}
    with major_template_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            coverage_rate_text = row.get("coverage_rate", "").strip()
            if not coverage_rate_text:
                continue
            key = (int(row["year"]), int(row["month"]), row["major_category"])
            major_rates[key] = float(coverage_rate_text)

    occupation_factors: Dict[str, float] = {}
    with occupation_master_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            factor_text = row.get("occupation_relative_factor", "").strip()
            if factor_text:
                occupation_factors[row["occupation_name"]] = float(factor_text)

    national_totals: Dict[Tuple[int, int, str], int] = {}
    raw_rows_by_key: Dict[Tuple[int, int, str], List[Dict[str, str]]] = {}
    base_rows_by_key: Dict[Tuple[int, int, str], List[Dict[str, str]]] = {}
    base_totals: Dict[Tuple[int, int, str], int] = {}

    with national_occupation_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            year = int(row["year"])
            month = int(row["month"])
            point = (year, month)
            if point < start:
                continue
            job_metric = row.get("job_metric", "").strip() or "有効求人数"
            key = (year, month, job_metric)
            occupation_name = row["occupation_name"]
            major_category = row.get("major_category", "").strip()
            job_count = int(row["job_count"])

            if occupation_name == "職業計":
                national_totals[key] = job_count
                continue
            if major_category in {"", "総計", "集計区分", "分類不能"}:
                continue
            if occupation_name in {"介護関係職種（注２）カ", "分類不能の職業"}:
                continue

            raw_rows_by_key.setdefault(key, []).append(row)

            major_rate = major_rates.get((year, month, major_category))
            factor = occupation_factors.get(occupation_name)
            if major_rate is None or factor is None:
                continue
            coverage_rate = major_rate * factor
            if coverage_rate <= 0:
                continue
            estimated = round(job_count / coverage_rate)
            base_rows_by_key.setdefault(key, []).append(
                {
                    "major_category": major_category,
                    "occupation_name": occupation_name,
                    "job_count": str(estimated),
                }
            )
            base_totals[key] = base_totals.get(key, 0) + estimated

    rows: List[Dict[str, str]] = []
    for key, raw_rows in sorted(raw_rows_by_key.items()):
        year, month, job_metric = key
        national_total = national_totals.get(key)
        national_base_total = base_totals.get(key)
        prefecture_rows = prefecture_totals_valid.get((year, month), [])
        if not national_total or not national_base_total or not prefecture_rows:
            continue

        national_rows_base = {
            (row["major_category"], row["occupation_name"]): int(row["job_count"])
            for row in base_rows_by_key.get(key, [])
        }

        national_low_total = round(national_base_total * low_multiplier)
        national_high_total = round(national_base_total * high_multiplier)

        for prefecture_row in prefecture_rows:
            prefecture = prefecture_row["prefecture"]
            valid_prefecture_total = int(prefecture_row["prefecture_total_job_count"])
            valid_national_total = int(prefecture_row["national_total_job_count"])
            prefecture_share = valid_prefecture_total / valid_national_total if valid_national_total else 0.0

            if job_metric == "有効求人数":
                prefecture_metric_total = valid_prefecture_total
                prefecture_total_method = "e_stat_prefecture_total"
            else:
                prefecture_metric_total = round(national_total * prefecture_share)
                prefecture_total_method = "approx_new_total_from_valid_prefecture_share"

            prefecture_base_total = round(national_base_total * prefecture_share)
            prefecture_low_total = round(national_low_total * prefecture_share)
            prefecture_high_total = round(national_high_total * prefecture_share)

            for raw_row in raw_rows:
                major_category = raw_row["major_category"]
                occupation_name = raw_row["occupation_name"]
                raw_job_count = int(raw_row["job_count"])
                raw_share = raw_job_count / national_total if national_total else 0.0
                base_national_job_count = national_rows_base.get((major_category, occupation_name))
                if base_national_job_count is None:
                    continue
                base_share = base_national_job_count / national_base_total if national_base_total else 0.0

                rows.append(
                    {
                        "year": str(year),
                        "month": str(month),
                        "job_metric": job_metric,
                        "prefecture": prefecture,
                        "major_category": major_category,
                        "occupation_name": occupation_name,
                        "prefecture_hellowork_job_count": str(round(prefecture_metric_total * raw_share)),
                        "prefecture_base_job_count": str(round(prefecture_base_total * base_share)),
                        "prefecture_low_job_count": str(round(prefecture_low_total * base_share)),
                        "prefecture_high_job_count": str(round(prefecture_high_total * base_share)),
                        "prefecture_share_of_hellowork_total": f"{prefecture_share:.8f}",
                        "national_hellowork_total_job_count": str(national_total),
                        "national_base_total_job_count": str(national_base_total),
                        "national_low_total_job_count": str(national_low_total),
                        "national_high_total_job_count": str(national_high_total),
                    }
                )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "job_metric",
                "prefecture",
                "major_category",
                "occupation_name",
                "prefecture_hellowork_job_count",
                "prefecture_base_job_count",
                "prefecture_low_job_count",
                "prefecture_high_job_count",
                "prefecture_share_of_hellowork_total",
                "national_hellowork_total_job_count",
                "national_base_total_job_count",
                "national_low_total_job_count",
                "national_high_total_job_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_csv


def _find_prefecture_columns(sheet: Dict[str, str]) -> List[Tuple[str, str]]:
    prefecture_columns: List[Tuple[str, str]] = []
    for cell_ref, value in sheet.items():
        match = re.fullmatch(r"([A-Z]+)2", cell_ref)
        if not match:
            continue
        column = match.group(1)
        if column in {"A", "B", "C", "D"}:
            continue
        prefecture_name = _clean_prefecture_name(value)
        if prefecture_name:
            prefecture_columns.append((prefecture_name, column))
    return prefecture_columns


def _clean_prefecture_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = re.sub(r"(都|道|府|県)[ァ-ヶー]+$", r"\1", cleaned)
    return cleaned
