from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import xlrd


E_STAT_BASE_URL = "https://www.e-stat.go.jp"
E_STAT_SEARCH_URL = (
    "https://www.e-stat.go.jp/stat-search/files?"
    "data=1&layout=dataset&metadata=1&page=1&query=%E8%81%B7%E6%A5%AD%E5%88%A5"
    "&toukei=00450222&tstat=000001020327"
)
TARGET_TABLE_NUMBER = "21"
TARGET_TABLE_TITLE = "職業別労働市場関係指標"
USER_AGENT = "job-count-by-occupation/0.1"
XML_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

JOB_METRICS = {
    "both": None,
    "valid": {
        "label": "有効求人数",
        "xlsx_sheet": "第２１表ー２　有効求人（パート含む常用）",
        "xls_pattern": "有効求人",
    },
    "new": {
        "label": "新規求人数",
        "xlsx_sheet": "第２１表ー１　新規求人（パート含む常用）",
        "xls_pattern": "新規求人",
    },
}
TARGET_SHEET_NAME = JOB_METRICS["valid"]["xlsx_sheet"]
TARGET_XLS_SHEET_PATTERN = JOB_METRICS["valid"]["xls_pattern"]

HISTORY_SOURCES = [
    {
        "name": "長期時系列表 11-2",
        "kind": "xls",
        "url": "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000031942507&fileKind=0",
        "start": (2010, 1),
        "end": (2012, 2),
    },
    {
        "name": "長期時系列表 21（旧様式）",
        "kind": "xlsx",
        "url": "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040050660&fileKind=0",
        "start": (2012, 3),
        "end": (2022, 3),
    },
    {
        "name": "長期時系列表 21（現行）",
        "kind": "xlsx",
        "url": "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040428409&fileKind=0",
        "start": (2022, 4),
        "end": None,
    },
]


@dataclass
class DatasetInfo:
    title: str
    dataset_period: str
    surveyed_at: str
    published_at: str
    detail_url: str
    download_url: str


@dataclass
class JobCountRecord:
    job_metric: str
    occupation_name: str
    job_count: int
    year: int
    month: int
    source_table: str
    source_sheet: str
    source_url: str


MAJOR_CATEGORY_MAP = {
    "その他のサービス職業従事者": "サービス",
    "その他の保健医療従事者": "専門・技術",
    "その他の専門的職業": "専門・技術",
    "その他の技術者": "専門・技術",
    "その他の輸送従事者": "輸送・機械運転",
    "その他の運搬・清掃・包装等従事者": "運搬・清掃・包装等",
    "サービス職業従事者": "サービス",
    "一般事務従事者": "事務",
    "事務従事者": "事務",
    "事務用機器操作員": "事務",
    "介護サービス職業従事者": "サービス",
    "介護関係職種（注２）カ": "集計区分",
    "会計事務従事者": "事務",
    "保健医療サービス職業従事者": "専門・技術",
    "保健師，助産師，看護師": "専門・技術",
    "保安職業従事者": "保安",
    "分類不能の職業": "分類不能",
    "包装従事者": "運搬・清掃・包装等",
    "医師，歯科医師，獣医師，薬剤師": "専門・技術",
    "医療技術者": "専門・技術",
    "商品販売従事者": "販売",
    "営業・販売事務従事者": "事務",
    "営業職業従事者": "販売",
    "土木作業従事者": "建設・採掘",
    "外勤事務従事者": "事務",
    "定置・建設機械運転従事者": "輸送・機械運転",
    "家庭生活支援サービス職業従事者": "サービス",
    "専門的・技術的職業従事者": "専門・技術",
    "居住施設・ビル等管理人": "サービス",
    "建築・土木・測量技術者": "専門・技術",
    "建設・採掘従事者": "建設・採掘",
    "建設従事者（建設躯体工事従事者を除く）": "建設・採掘",
    "建設躯体工事従事者": "建設・採掘",
    "情報処理・通信技術者": "専門・技術",
    "採掘従事者": "建設・採掘",
    "接客・給仕職業従事者": "サービス",
    "機械整備・修理従事者": "生産工程",
    "機械検査従事者": "生産工程",
    "機械組立従事者": "生産工程",
    "機械組立設備制御・監視従事者": "生産工程",
    "清掃従事者": "運搬・清掃・包装等",
    "生活衛生サービス職業従事者": "サービス",
    "生産工程従事者": "生産工程",
    "生産設備制御・監視従事者（金属製品を除く）セ": "生産工程",
    "生産設備制御・監視従事者（金属製品）セ": "生産工程",
    "生産関連・生産類似作業従事者": "生産工程",
    "生産関連事務従事者": "事務",
    "社会福祉専門職業従事者": "専門・技術",
    "管理的職業従事者": "管理",
    "美術家，デザイナー，写真家，映像撮影者": "専門・技術",
    "職業計": "総計",
    "自動車運転従事者": "輸送・機械運転",
    "船舶・航空機運転従事者": "輸送・機械運転",
    "製品検査従事者（金属製品を除く）": "生産工程",
    "製品検査従事者（金属製品）": "生産工程",
    "製品製造・加工処理従事者（金属製品を除く）": "生産工程",
    "製品製造・加工処理従事者（金属製品）セ": "生産工程",
    "製造技術者（開発を除く）": "専門・技術",
    "製造技術者（開発）": "専門・技術",
    "販売従事者": "販売",
    "販売類似職業従事者": "販売",
    "輸送・機械運転従事者": "輸送・機械運転",
    "農林漁業従事者": "農林漁業",
    "運搬・清掃・包装等従事者": "運搬・清掃・包装等",
    "運搬従事者": "運搬・清掃・包装等",
    "運輸・郵便事務従事者": "事務",
    "鉄道運転従事者": "輸送・機械運転",
    "電気工事従事者": "建設・採掘",
    "飲食物調理従事者": "サービス",
}


class _EStatSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.datasets: List[Dict[str, str]] = []
        self._current: Optional[Dict[str, str]] = None
        self._field: Optional[str] = None
        self._capture_anchor = False
        self._capture_title = False
        self._capture_detail_item = False
        self._detail_items: List[str] = []
        self._download_href: Optional[str] = None
        self._anchor_href: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_map = dict(attrs)
        classes = attr_map.get("class", "")
        if tag == "article" and "stat-resource_list-item-dataset" in classes:
            self._current = {}
            self._detail_items = []
            self._download_href = None
            self._anchor_href = None
        elif self._current is not None and tag == "li" and "stat-resource_list-detail-item" in classes:
            self._field = "detail_item"
            self._capture_detail_item = True
        elif self._current is not None and tag == "a":
            href = attr_map.get("href", "")
            if "stat-search/file-download" in href:
                self._download_href = href
            if "stat-item2_parent" in classes:
                self._anchor_href = href
                self._capture_anchor = True
                self._capture_title = True
        elif self._current is not None and tag == "span" and "stat-separator" in classes and self._capture_anchor:
            self._field = "title"

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self._current is not None:
            if self._detail_items:
                self._current["detail_items"] = "\n".join(self._detail_items)
            if self._download_href:
                self._current["download_href"] = self._download_href
            if self._anchor_href:
                self._current["detail_href"] = self._anchor_href
            self.datasets.append(self._current)
            self._current = None
            self._field = None
            self._capture_anchor = False
            self._capture_title = False
            self._capture_detail_item = False
        elif tag == "li" and self._capture_detail_item:
            self._field = None
            self._capture_detail_item = False
        elif tag == "a" and self._capture_anchor:
            self._capture_anchor = False
            self._capture_title = False
            self._field = None

    def handle_data(self, data: str) -> None:
        if self._current is None:
            return
        text = _normalize_whitespace(data)
        if not text:
            return
        if self._field == "detail_item":
            self._detail_items.append(text)
        elif self._field == "title" and self._capture_title:
            existing = self._current.get("title", "")
            self._current["title"] = f"{existing} {text}".strip()


def fetch_latest_job_counts(
    output_dir: Path,
    output_format: str = "both",
    job_metric: str = "both",
) -> Tuple[DatasetInfo, List[JobCountRecord], List[Path]]:
    dataset = fetch_latest_dataset_info()
    workbook_bytes = _fetch_bytes(dataset.download_url)
    records, year, month = parse_job_counts_from_workbook(workbook_bytes, dataset.download_url, job_metric=job_metric)

    output_dir.mkdir(parents=True, exist_ok=True)
    created_files = write_outputs(
        output_dir=output_dir,
        output_format=output_format,
        records=records,
        year=year,
        month=month,
    )
    return dataset, records, created_files


def fetch_job_counts_from_year(
    start_year: int,
    output_dir: Path,
    output_format: str = "both",
    job_metric: str = "both",
) -> Tuple[List[JobCountRecord], List[Path]]:
    all_records: List[JobCountRecord] = []
    for source in HISTORY_SOURCES:
        source_records = fetch_history_source_records(
            kind=source["kind"],
            source_url=source["url"],
            source_name=source["name"],
            requested_start_year=start_year,
            source_start=source["start"],
            source_end=source["end"],
            job_metric=job_metric,
        )
        all_records.extend(source_records)

    all_records.sort(key=lambda record: (record.year, record.month, record.occupation_name))
    output_dir.mkdir(parents=True, exist_ok=True)
    created_files = write_outputs(
        output_dir=output_dir,
        output_format=output_format,
        records=all_records,
        year=all_records[0].year,
        month=all_records[0].month,
        range_end=(all_records[-1].year, all_records[-1].month),
    )
    return all_records, created_files


def fetch_latest_dataset_info() -> DatasetInfo:
    html = _fetch_text(E_STAT_SEARCH_URL)
    parser = _EStatSearchParser()
    parser.feed(html)

    for item in parser.datasets:
        title = item.get("title", "")
        normalized_title = title.replace(" ", "")
        if TARGET_TABLE_TITLE in normalized_title and f"長期時系列表{TARGET_TABLE_NUMBER}" in normalized_title:
            detail_blob = item.get("detail_items", "")
            return DatasetInfo(
                title=title,
                dataset_period=_extract_detail_value(detail_blob, r"(～令和[^\n ]+)"),
                surveyed_at=_extract_detail_value(detail_blob, r"(\d{4}年\d{1,2}月)"),
                published_at=_extract_detail_value(detail_blob, r"(\d{4}-\d{2}-\d{2})"),
                detail_url=urljoin(E_STAT_BASE_URL, item["detail_href"]),
                download_url=urljoin(E_STAT_BASE_URL, item["download_href"]),
            )
    raise RuntimeError("対象の職業別統計表を e-Stat 上で見つけられませんでした。")


def parse_job_counts_from_workbook(
    workbook_bytes: bytes,
    source_url: str,
    job_metric: str = "both",
) -> Tuple[List[JobCountRecord], int, int]:
    reader = XlsxReader.from_bytes(workbook_bytes)
    records: List[JobCountRecord] = []
    latest_year: Optional[int] = None
    latest_month: Optional[int] = None
    for metric_key in _metric_keys(job_metric):
        metric = JOB_METRICS[metric_key]
        sheet = reader.read_sheet_by_name(metric["xlsx_sheet"])
        latest_col, year, month = _find_latest_month_column(sheet)
        latest_year = year if latest_year is None else max(latest_year, year)
        latest_month = month if latest_month is None else max(latest_month, month)

        row_number = 6
        while True:
            occupation_name = sheet.get(f"A{row_number}", "").strip()
            if not occupation_name:
                break
            raw_value = sheet.get(f"{latest_col}{row_number}", "").strip()
            if raw_value.isdigit():
                records.append(
                    JobCountRecord(
                        job_metric=metric["label"],
                        occupation_name=_clean_occupation_name(occupation_name),
                        job_count=int(raw_value),
                        year=year,
                        month=month,
                        source_table="長期時系列表 21 職業別労働市場関係指標（実数）（平成21年改定）（令和4年4月～）",
                        source_sheet=metric["xlsx_sheet"],
                        source_url=source_url,
                    )
                )
            row_number += 1

    if not records or latest_year is None or latest_month is None:
        raise RuntimeError("Excel から職種別求人数を抽出できませんでした。")
    return records, latest_year, latest_month


def fetch_history_source_records(
    kind: str,
    source_url: str,
    source_name: str,
    requested_start_year: int,
    source_start: Tuple[int, int],
    source_end: Optional[Tuple[int, int]],
    job_metric: str = "both",
) -> List[JobCountRecord]:
    workbook_bytes = _fetch_bytes(source_url)
    if kind == "xlsx":
        records = parse_all_months_from_xlsx(workbook_bytes, source_url, source_name, job_metric=job_metric)
    elif kind == "xls":
        records = parse_all_months_from_xls(workbook_bytes, source_url, source_name, job_metric=job_metric)
    else:
        raise ValueError(f"Unsupported source kind: {kind}")

    filtered: List[JobCountRecord] = []
    for record in records:
        if record.year < requested_start_year:
            continue
        if (record.year, record.month) < source_start:
            continue
        if source_end and (record.year, record.month) > source_end:
            continue
        filtered.append(record)
    return filtered


def parse_all_months_from_xlsx(
    workbook_bytes: bytes,
    source_url: str,
    source_name: str,
    job_metric: str = "both",
) -> List[JobCountRecord]:
    reader = XlsxReader.from_bytes(workbook_bytes)
    records: List[JobCountRecord] = []
    for metric_key in _metric_keys(job_metric):
        metric = JOB_METRICS[metric_key]
        sheet = reader.read_sheet_by_name(metric["xlsx_sheet"])
        month_columns = _find_all_xlsx_month_columns(sheet)
        records.extend(
            _build_records_from_xlsx_month_columns(
                sheet=sheet,
                month_columns=month_columns,
                source_url=source_url,
                source_name=source_name,
                job_metric_label=metric["label"],
                source_sheet=metric["xlsx_sheet"],
            )
        )
    return records


def parse_all_months_from_xls(
    workbook_bytes: bytes,
    source_url: str,
    source_name: str,
    job_metric: str = "both",
) -> List[JobCountRecord]:
    book = xlrd.open_workbook(file_contents=workbook_bytes)
    records: List[JobCountRecord] = []
    for metric_key in _metric_keys(job_metric):
        metric = JOB_METRICS[metric_key]
        sheet = _find_xls_target_sheet(book, metric["xls_pattern"])
        month_columns = _find_all_xls_month_columns(sheet)
        records.extend(
            _build_records_from_xls_month_columns(
                sheet=sheet,
                month_columns=month_columns,
                source_url=source_url,
                source_name=source_name,
                job_metric_label=metric["label"],
            )
        )
    return records


def write_outputs(
    output_dir: Path,
    output_format: str,
    records: List[JobCountRecord],
    year: int,
    month: int,
    range_end: Optional[Tuple[int, int]] = None,
) -> List[Path]:
    output_format = output_format.lower()
    created_files: List[Path] = []
    if range_end is None or range_end == (year, month):
        stem = f"job_counts_{year:04d}-{month:02d}"
    else:
        end_year, end_month = range_end
        stem = f"job_counts_{year:04d}-{month:02d}_to_{end_year:04d}-{end_month:02d}"

    if output_format in {"both", "csv"}:
        csv_path = output_dir / f"{stem}.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["year", "month", "job_metric", "major_category", "occupation_name", "job_count"],
            )
            writer.writeheader()
            for record in records:
                writer.writerow(
                    {
                        "year": record.year,
                        "month": record.month,
                        "job_metric": record.job_metric,
                        "major_category": get_major_category(record.occupation_name),
                        "occupation_name": record.occupation_name,
                        "job_count": record.job_count,
                    }
                )
        created_files.append(csv_path)

    if output_format in {"both", "json"}:
        json_path = output_dir / f"{stem}.json"
        with json_path.open("w", encoding="utf-8") as fh:
            json.dump([asdict(record) for record in records], fh, ensure_ascii=False, indent=2)
        created_files.append(json_path)

    return created_files


class XlsxReader:
    def __init__(self, archive: zipfile.ZipFile) -> None:
        self.archive = archive
        self.shared_strings = self._load_shared_strings()
        self.sheets = self._load_sheet_map()

    @classmethod
    def from_bytes(cls, workbook_bytes: bytes) -> "XlsxReader":
        return cls(zipfile.ZipFile(io.BytesIO(workbook_bytes)))

    def read_sheet_by_name(self, sheet_name: str) -> Dict[str, str]:
        sheet_path = self.sheets.get(sheet_name)
        if not sheet_path:
            available = ", ".join(self.sheets)
            raise KeyError(f"シート '{sheet_name}' が見つかりません。available={available}")

        root = ET.fromstring(self.archive.read(sheet_path))
        cells: Dict[str, str] = {}
        for cell in root.findall(".//a:sheetData/a:row/a:c", XML_NS):
            ref = cell.attrib["r"]
            value = self._cell_value(cell)
            if value != "":
                cells[ref] = value
        return cells

    def _load_shared_strings(self) -> List[str]:
        try:
            root = ET.fromstring(self.archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return []
        values: List[str] = []
        for item in root.findall("a:si", XML_NS):
            texts = [node.text or "" for node in item.iterfind(".//a:t", XML_NS)]
            values.append("".join(texts))
        return values

    def _load_sheet_map(self) -> Dict[str, str]:
        workbook_root = ET.fromstring(self.archive.read("xl/workbook.xml"))
        rel_root = ET.fromstring(self.archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: f"xl/{rel.attrib['Target']}"
            for rel in rel_root.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
            if rel.attrib.get("Type", "").endswith("/worksheet")
        }
        sheets: Dict[str, str] = {}
        for sheet in workbook_root.findall("a:sheets/a:sheet", XML_NS):
            name = sheet.attrib["name"].strip()
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            sheets[name] = rel_map[rel_id]
        return sheets

    def _cell_value(self, cell: ET.Element) -> str:
        inline = cell.find("a:is", XML_NS)
        if inline is not None:
            return "".join(node.text or "" for node in inline.iterfind(".//a:t", XML_NS)).strip()

        value = cell.find("a:v", XML_NS)
        if value is None or value.text is None:
            return ""

        text = value.text.strip()
        if cell.attrib.get("t") == "s":
            return self.shared_strings[int(text)].strip()
        return text


def _find_latest_month_column(sheet: Dict[str, str]) -> Tuple[str, int, int]:
    candidates = _find_all_xlsx_month_columns(sheet)
    if not candidates:
        raise RuntimeError("最新年月の列を特定できませんでした。")
    year, month, column = max(candidates, key=lambda item: (item[0], item[1]))
    return column, year, month


def _find_all_xlsx_month_columns(sheet: Dict[str, str]) -> List[Tuple[int, int, str]]:
    candidates: List[Tuple[int, int, str]] = []
    for cell_ref, year_value in sheet.items():
        match = re.fullmatch(r"([A-Z]+)2", cell_ref)
        if not match:
            continue
        column = match.group(1)
        month_label = sheet.get(f"{column}4", "")
        if not month_label:
            continue
        year_match = re.search(r"(\d{4})年", year_value)
        month_match = re.search(r"(\d{1,2})月", month_label)
        if not year_match or not month_match:
            continue
        candidates.append((int(year_match.group(1)), int(month_match.group(1)), column))
    return sorted(candidates)


def _find_xls_target_sheet(book: xlrd.book.Book, metric_pattern: str) -> xlrd.sheet.Sheet:
    for idx in range(book.nsheets):
        sheet = book.sheet_by_index(idx)
        if metric_pattern in sheet.name and "含パート" in sheet.name:
            return sheet
    raise RuntimeError(f"旧Excel内に対象シートが見つかりませんでした: {metric_pattern}")


def _find_all_xls_month_columns(sheet: xlrd.sheet.Sheet) -> List[Tuple[int, int, int]]:
    columns: List[Tuple[int, int, int]] = []
    current_year: Optional[int] = None
    for col_idx in range(sheet.ncols):
        label = _normalize_whitespace(str(sheet.cell_value(2, col_idx)))
        parsed = _parse_xls_month_label(label, current_year)
        if parsed is None:
            continue
        year, month = parsed
        current_year = year
        columns.append((year, month, col_idx))
    return columns


def _parse_xls_month_label(label: str, current_year: Optional[int]) -> Optional[Tuple[int, int]]:
    if not label or "計" in label:
        return None
    year_month = re.fullmatch(r"(\d{1,2})年(\d{1,2})月", label)
    if year_month:
        heisei_year = int(year_month.group(1))
        month = int(year_month.group(2))
        return 1988 + heisei_year, month
    month_only = re.fullmatch(r"(\d{1,2})月", label)
    if month_only and current_year is not None:
        return current_year, int(month_only.group(1))
    return None


def _build_records_from_xlsx_month_columns(
    sheet: Dict[str, str],
    month_columns: List[Tuple[int, int, str]],
    source_url: str,
    source_name: str,
    job_metric_label: str,
    source_sheet: str,
) -> List[JobCountRecord]:
    records: List[JobCountRecord] = []
    row_number = 6
    while True:
        occupation_name = sheet.get(f"A{row_number}", "").strip()
        if not occupation_name:
            break
        cleaned_name = _clean_occupation_name(occupation_name)
        for year, month, column in month_columns:
            raw_value = sheet.get(f"{column}{row_number}", "").strip()
            if raw_value.isdigit():
                records.append(
                    JobCountRecord(
                        job_metric=job_metric_label,
                        occupation_name=cleaned_name,
                        job_count=int(raw_value),
                        year=year,
                        month=month,
                        source_table=source_name,
                        source_sheet=source_sheet,
                        source_url=source_url,
                    )
                )
        row_number += 1
    return records


def _build_records_from_xls_month_columns(
    sheet: xlrd.sheet.Sheet,
    month_columns: List[Tuple[int, int, int]],
    source_url: str,
    source_name: str,
    job_metric_label: str,
) -> List[JobCountRecord]:
    records: List[JobCountRecord] = []
    for row_idx in range(3, sheet.nrows):
        occupation_name = _normalize_whitespace(str(sheet.cell_value(row_idx, 0)))
        if not occupation_name:
            continue
        cleaned_name = _clean_occupation_name(occupation_name)
        for year, month, col_idx in month_columns:
            cell_value = sheet.cell_value(row_idx, col_idx)
            if isinstance(cell_value, str) and not cell_value.strip():
                continue
            try:
                job_count = int(float(cell_value))
            except (TypeError, ValueError):
                continue
            records.append(
                JobCountRecord(
                    job_metric=job_metric_label,
                    occupation_name=cleaned_name,
                    job_count=job_count,
                    year=year,
                    month=month,
                    source_table=source_name,
                    source_sheet=sheet.name,
                    source_url=source_url,
                )
            )
    return records


def _clean_occupation_name(value: str) -> str:
    normalized = _normalize_whitespace(value)
    return re.sub(r"(?<=[一-龥々ぁ-んァ-ヶー、，・])([ァ-ヶー]{6,})$", "", normalized)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_after_label(text: str, label: str) -> str:
    cleaned = _normalize_whitespace(text)
    return cleaned.replace(label, "", 1).strip()


def _extract_detail_value(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    if not match:
        raise RuntimeError(f"e-Stat の詳細情報から必要な値を抽出できませんでした: pattern={pattern}")
    return match.group(1)


def get_major_category(occupation_name: str) -> str:
    return MAJOR_CATEGORY_MAP.get(occupation_name, "")


def normalize_job_metric(job_metric: str) -> str:
    metric = (job_metric or "both").strip().lower()
    if metric not in JOB_METRICS:
        raise ValueError(f"Unsupported job metric: {job_metric}")
    return metric


def is_target_job_metric(row: Dict[str, str], job_metric_label: str = "有効求人数") -> bool:
    row_metric = row.get("job_metric", "").strip()
    return row_metric in {"", job_metric_label}


def _metric_keys(job_metric: str) -> List[str]:
    metric = normalize_job_metric(job_metric)
    if metric == "both":
        return ["valid", "new"]
    return [metric]


def _fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def _fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read()
