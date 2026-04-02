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
