from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from job_count_by_occupation.estat import is_target_job_metric


@dataclass
class MonthlyCategoryAggregate:
    year: int
    month: int
    major_category: str
    estat_job_count: int


DEFAULT_OCCUPATION_RELATIVE_FACTORS = {
    "管理的職業従事者": 0.60,
    "一般事務従事者": 0.85,
    "事務従事者": 0.85,
    "会計事務従事者": 0.90,
    "営業・販売事務従事者": 0.85,
    "情報処理・通信技術者": 0.55,
    "美術家，デザイナー，写真家，映像撮影者": 0.45,
    "営業職業従事者": 0.85,
    "販売従事者": 0.80,
    "商品販売従事者": 0.75,
    "販売類似職業従事者": 0.85,
    "サービス職業従事者": 0.95,
    "接客・給仕職業従事者": 0.95,
    "生活衛生サービス職業従事者": 0.95,
    "保健師，助産師，看護師": 1.25,
    "医師，歯科医師，獣医師，薬剤師": 1.15,
    "医療技術者": 1.10,
    "社会福祉専門職業従事者": 1.20,
    "介護サービス職業従事者": 1.25,
    "建築・土木・測量技術者": 1.05,
    "建設従事者（建設躯体工事従事者を除く）": 1.10,
    "建設躯体工事従事者": 1.10,
    "電気工事従事者": 1.10,
    "自動車運転従事者": 1.10,
    "輸送・機械運転従事者": 1.05,
    "運搬・清掃・包装等従事者": 1.05,
    "清掃従事者": 1.05,
    "生産工程従事者": 1.10,
    "製造技術者（開発）": 0.75,
    "製造技術者（開発を除く）": 0.90,
}

DEFAULT_MAJOR_CATEGORY_COVERAGE_RATES = {
    "サービス": 0.45,
    "事務": 0.35,
    "保安": 0.45,
    "専門・技術": 0.34,
    "建設・採掘": 0.55,
    "生産工程": 0.50,
    "管理": 0.20,
    "販売": 0.35,
    "輸送・機械運転": 0.50,
    "農林漁業": 0.65,
    "運搬・清掃・包装等": 0.48,
}


def aggregate_major_category_monthly(
    input_csv: Path,
    output_csv: Path,
    start: Optional[Tuple[int, int]] = None,
    end: Optional[Tuple[int, int]] = None,
    exclude_total: bool = True,
) -> Path:
    grouped: Dict[Tuple[int, int, str], int] = {}

    with input_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not is_target_job_metric(row):
                continue
            year = int(row["year"])
            month = int(row["month"])
            point = (year, month)
            if start and point < start:
                continue
            if end and point > end:
                continue

            major_category = row.get("major_category", "").strip()
            if not major_category:
                continue
            if exclude_total and major_category == "総計":
                continue

            key = (year, month, major_category)
            grouped[key] = grouped.get(key, 0) + int(row["job_count"])

    rows = [
        MonthlyCategoryAggregate(year=year, month=month, major_category=major_category, estat_job_count=value)
        for (year, month, major_category), value in sorted(grouped.items())
    ]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["year", "month", "major_category", "estat_job_count"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "year": row.year,
                    "month": row.month,
                    "major_category": row.major_category,
                    "estat_job_count": row.estat_job_count,
                }
            )
    return output_csv


def create_major_category_coverage_template(
    aggregate_csv: Path,
    output_csv: Path,
    seed_defaults: bool = False,
) -> Path:
    rows: List[Dict[str, str]] = []
    with aggregate_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            major_category = row["major_category"]
            coverage_rate = ""
            coverage_source = ""
            notes = ""
            if seed_defaults and major_category in DEFAULT_MAJOR_CATEGORY_COVERAGE_RATES:
                coverage_rate = f"{DEFAULT_MAJOR_CATEGORY_COVERAGE_RATES[major_category]:.2f}"
                coverage_source = "default_heuristic"
                notes = "仮説値。occupation 補正係数と合わせて後続で調整"
            rows.append(
                {
                    "year": row["year"],
                    "month": row["month"],
                    "major_category": major_category,
                    "estat_job_count": row["estat_job_count"],
                    "coverage_rate": coverage_rate,
                    "estimated_national_job_count": "",
                    "coverage_source": coverage_source,
                    "notes": notes,
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "major_category",
                "estat_job_count",
                "coverage_rate",
                "estimated_national_job_count",
                "coverage_source",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_csv


def estimate_national_jobs_from_coverage_template(
    template_csv: Path,
    output_csv: Path,
) -> Path:
    estimated_rows: List[Dict[str, str]] = []
    with template_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            coverage_rate_text = row.get("coverage_rate", "").strip()
            estimated = ""
            if coverage_rate_text:
                coverage_rate = float(coverage_rate_text)
                if coverage_rate <= 0:
                    raise ValueError(f"coverage_rate must be > 0: year={row['year']} month={row['month']} category={row['major_category']}")
                estimated = str(round(int(row["estat_job_count"]) / coverage_rate))

            estimated_rows.append(
                {
                    "year": row["year"],
                    "month": row["month"],
                    "major_category": row["major_category"],
                    "estat_job_count": row["estat_job_count"],
                    "coverage_rate": coverage_rate_text,
                    "estimated_national_job_count": estimated,
                    "coverage_source": row.get("coverage_source", ""),
                    "notes": row.get("notes", ""),
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "major_category",
                "estat_job_count",
                "coverage_rate",
                "estimated_national_job_count",
                "coverage_source",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(estimated_rows)
    return output_csv


def create_occupation_coverage_master(
    occupation_master_csv: Path,
    output_csv: Path,
) -> Path:
    rows: List[Dict[str, str]] = []
    with occupation_master_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            occupation_name = row["occupation_name"]
            major_category = row.get("major_category", "")
            if occupation_name in {"職業計", "介護関係職種（注２）カ", "分類不能の職業"} or major_category in {"総計", "集計区分", "分類不能"}:
                default_factor = ""
                factor_source = "not_estimated"
                confidence = "n/a"
                notes = "総計・集計区分・分類不能は occupation 推計対象外"
            else:
                default_factor = f"{DEFAULT_OCCUPATION_RELATIVE_FACTORS.get(occupation_name, 1.0):.2f}"
                factor_source = (
                    "default_heuristic"
                    if occupation_name in DEFAULT_OCCUPATION_RELATIVE_FACTORS
                    else "default_neutral"
                )
                confidence = "low"
                notes = ""
            rows.append(
                {
                    "occupation_name": occupation_name,
                    "major_category": major_category,
                    "description": row.get("description", ""),
                    "examples_or_scope": row.get("examples_or_scope", ""),
                    "jobmedley_related": row.get("jobmedley_related", "false"),
                    "occupation_relative_factor": default_factor,
                    "factor_source": factor_source,
                    "confidence": confidence,
                    "notes": notes,
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "occupation_name",
                "major_category",
                "description",
                "examples_or_scope",
                "jobmedley_related",
                "occupation_relative_factor",
                "factor_source",
                "confidence",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_csv


def estimate_occupation_national_jobs(
    occupation_csv: Path,
    major_template_csv: Path,
    occupation_master_csv: Path,
    output_csv: Path,
    start: Optional[Tuple[int, int]] = None,
    end: Optional[Tuple[int, int]] = None,
) -> Path:
    major_rates: Dict[Tuple[int, int, str], float] = {}
    with major_template_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            coverage_rate_text = row.get("coverage_rate", "").strip()
            if not coverage_rate_text:
                continue
            major_rates[(int(row["year"]), int(row["month"]), row["major_category"])] = float(coverage_rate_text)

    occupation_factors: Dict[str, Dict[str, str]] = {}
    with occupation_master_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            occupation_factors[row["occupation_name"]] = row

    estimated_rows: List[Dict[str, str]] = []
    with occupation_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not is_target_job_metric(row):
                continue
            year = int(row["year"])
            month = int(row["month"])
            point = (year, month)
            if start and point < start:
                continue
            if end and point > end:
                continue

            occupation_name = row["occupation_name"]
            major_category = row.get("major_category", "")
            key = (year, month, major_category)
            major_rate = major_rates.get(key)
            master = occupation_factors.get(occupation_name)
            relative_factor = ""
            coverage_rate = ""
            estimated_national_job_count = ""
            factor_source = ""
            confidence = ""
            notes = ""
            jobmedley_related = "false"

            if master:
                jobmedley_related = master.get("jobmedley_related", "false")
                relative_factor = master.get("occupation_relative_factor", "").strip()
                factor_source = master.get("factor_source", "")
                confidence = master.get("confidence", "")
                notes = master.get("notes", "")

            if major_rate is not None and relative_factor:
                occupation_rate = major_rate * float(relative_factor)
                if occupation_rate > 0:
                    coverage_rate = f"{occupation_rate:.6f}"
                    estimated_national_job_count = str(round(int(row["job_count"]) / occupation_rate))

            estimated_rows.append(
                {
                    "year": row["year"],
                    "month": row["month"],
                    "major_category": major_category,
                    "occupation_name": occupation_name,
                    "jobmedley_related": jobmedley_related,
                    "estat_job_count": row["job_count"],
                    "major_category_coverage_rate": f"{major_rate:.6f}" if major_rate is not None else "",
                    "occupation_relative_factor": relative_factor,
                    "coverage_rate": coverage_rate,
                    "estimated_national_job_count": estimated_national_job_count,
                    "factor_source": factor_source,
                    "confidence": confidence,
                    "notes": notes,
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "major_category",
                "occupation_name",
                "jobmedley_related",
                "estat_job_count",
                "major_category_coverage_rate",
                "occupation_relative_factor",
                "coverage_rate",
                "estimated_national_job_count",
                "factor_source",
                "confidence",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(estimated_rows)
    return output_csv


def build_national_market_scenarios(
    occupation_estimate_csv: Path,
    output_csv: Path,
    low_multiplier: float = 0.7,
    high_multiplier: float = 1.3,
) -> Path:
    monthly: Dict[Tuple[int, int], Dict[str, int]] = {}

    with occupation_estimate_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = (int(row["year"]), int(row["month"]))
            bucket = monthly.setdefault(
                key,
                {
                    "estimated_occupation_count": 0,
                    "hellowork_active_job_count": 0,
                    "estimated_national_active_job_count_base": 0,
                },
            )
            if row.get("occupation_name", "") == "職業計":
                bucket["hellowork_active_job_count"] = int(row["estat_job_count"])

            estimated_text = row.get("estimated_national_job_count", "").strip()
            if estimated_text:
                bucket["estimated_occupation_count"] += 1
                bucket["estimated_national_active_job_count_base"] += int(estimated_text)

    rows: List[Dict[str, str]] = []
    for (year, month), values in sorted(monthly.items()):
        base = values["estimated_national_active_job_count_base"]
        low = round(base * low_multiplier)
        high = round(base * high_multiplier)
        rows.append(
            {
                "year": str(year),
                "month": str(month),
                "estimated_occupation_count": str(values["estimated_occupation_count"]),
                "hellowork_active_job_count": str(values["hellowork_active_job_count"]),
                "estimated_national_active_job_count_low": str(low),
                "estimated_national_active_job_count_base": str(base),
                "estimated_national_active_job_count_high": str(high),
                "low_multiplier": f"{low_multiplier:.2f}",
                "high_multiplier": f"{high_multiplier:.2f}",
                "scenario_method": "national_sum_with_base_estimate_band",
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "estimated_occupation_count",
                "hellowork_active_job_count",
                "estimated_national_active_job_count_low",
                "estimated_national_active_job_count_base",
                "estimated_national_active_job_count_high",
                "low_multiplier",
                "high_multiplier",
                "scenario_method",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_csv


def build_jobmedley_market_scenarios(
    occupation_estimate_csv: Path,
    output_csv: Path,
    low_multiplier: float = 0.7,
    high_multiplier: float = 1.3,
) -> Path:
    monthly: Dict[Tuple[int, int], Dict[str, int]] = {}

    with occupation_estimate_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("jobmedley_related", "").strip().lower() != "true":
                continue

            key = (int(row["year"]), int(row["month"]))
            bucket = monthly.setdefault(
                key,
                {
                    "jobmedley_related_occupation_count": 0,
                    "hellowork_active_job_count": 0,
                    "estimated_national_active_job_count_base": 0,
                },
            )
            bucket["jobmedley_related_occupation_count"] += 1
            bucket["hellowork_active_job_count"] += int(row["estat_job_count"])

            estimated_text = row.get("estimated_national_job_count", "").strip()
            if estimated_text:
                bucket["estimated_national_active_job_count_base"] += int(estimated_text)

    rows: List[Dict[str, str]] = []
    for (year, month), values in sorted(monthly.items()):
        base = values["estimated_national_active_job_count_base"]
        low = round(base * low_multiplier)
        high = round(base * high_multiplier)
        rows.append(
            {
                "year": str(year),
                "month": str(month),
                "jobmedley_related_occupation_count": str(values["jobmedley_related_occupation_count"]),
                "hellowork_active_job_count": str(values["hellowork_active_job_count"]),
                "estimated_national_active_job_count_low": str(low),
                "estimated_national_active_job_count_base": str(base),
                "estimated_national_active_job_count_high": str(high),
                "low_multiplier": f"{low_multiplier:.2f}",
                "high_multiplier": f"{high_multiplier:.2f}",
                "scenario_method": "jobmedley_related_sum_with_base_estimate_band",
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "year",
                "month",
                "jobmedley_related_occupation_count",
                "hellowork_active_job_count",
                "estimated_national_active_job_count_low",
                "estimated_national_active_job_count_base",
                "estimated_national_active_job_count_high",
                "low_multiplier",
                "high_multiplier",
                "scenario_method",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return output_csv
