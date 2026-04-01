import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from job_count_by_occupation.estat import (
    TARGET_SHEET_NAME,
    XlsxReader,
    _clean_occupation_name,
    _parse_xls_month_label,
    _find_latest_month_column,
    parse_job_counts_from_workbook,
    write_outputs,
)


class EstatTests(unittest.TestCase):
    def test_find_latest_month_column(self) -> None:
        sheet = {
            "B2": "2025年",
            "B4": "12月",
            "C2": "2026年",
            "C4": "1月",
            "D2": "2026年",
            "D4": "2月",
        }
        column, year, month = _find_latest_month_column(sheet)
        self.assertEqual(("D", 2026, 2), (column, year, month))

    def test_clean_occupation_name_strips_trailing_katakana_reading(self) -> None:
        self.assertEqual(
            "医師，歯科医師，獣医師，薬剤師",
            _clean_occupation_name("医師，歯科医師，獣医師，薬剤師イシシカイシジュウイシヤクザイシ"),
        )

    def test_parse_job_counts_from_workbook(self) -> None:
        workbook_bytes = _build_test_workbook()
        records, year, month = parse_job_counts_from_workbook(workbook_bytes, "https://example.com/source.xlsx")

        self.assertEqual((2026, 2), (year, month))
        self.assertEqual(3, len(records))
        self.assertEqual("職業計", records[0].occupation_name)
        self.assertEqual(101, records[0].job_count)
        self.assertEqual("管理的職業従事者", records[1].occupation_name)
        self.assertEqual(11, records[1].job_count)

    def test_write_outputs(self) -> None:
        workbook_bytes = _build_test_workbook()
        records, year, month = parse_job_counts_from_workbook(workbook_bytes, "https://example.com/source.xlsx")

        with tempfile.TemporaryDirectory() as tmp_dir:
            created = write_outputs(Path(tmp_dir), "both", records, year, month)
            self.assertEqual(2, len(created))
            self.assertTrue(any(path.suffix == ".csv" for path in created))
            json_path = next(path for path in created if path.suffix == ".json")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(3, len(payload))
            self.assertEqual(2026, payload[0]["year"])
            csv_path = next(path for path in created if path.suffix == ".csv")
            csv_text = csv_path.read_text(encoding="utf-8")
            self.assertTrue(csv_text.startswith("year,month,major_category,occupation_name,job_count"))

    def test_xlsx_reader_resolves_sheet_by_name(self) -> None:
        workbook_bytes = _build_test_workbook()
        reader = XlsxReader(zipfile.ZipFile(io.BytesIO(workbook_bytes)))
        sheet = reader.read_sheet_by_name(TARGET_SHEET_NAME)
        self.assertEqual("2026年", sheet["D2"])
        self.assertEqual("管理的職業従事者カンリテキショクギョウジュウジシャ", sheet["A7"])

    def test_parse_xls_month_label(self) -> None:
        self.assertEqual((2010, 1), _parse_xls_month_label("22年1月", None))
        self.assertEqual((2010, 2), _parse_xls_month_label("2月", 2010))
        self.assertIsNone(_parse_xls_month_label("22年計", None))


def _build_test_workbook() -> bytes:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{TARGET_SHEET_NAME}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>
</Relationships>
"""
    shared_strings = [
        "2025年",
        "2026年",
        "12月",
        "1月",
        "2月",
        "職業計",
        "管理的職業従事者カンリテキショクギョウジュウジシャ",
        "専門的・技術的職業従事者",
    ]
    shared_xml = [
        """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>""",
        """<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">""",
    ]
    for value in shared_strings:
        shared_xml.append(f"<si><t>{value}</t></si>")
    shared_xml.append("</sst>")
    worksheet = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="2">
      <c r="B2" t="s"><v>0</v></c>
      <c r="C2" t="s"><v>1</v></c>
      <c r="D2" t="s"><v>1</v></c>
    </row>
    <row r="4">
      <c r="B4" t="s"><v>2</v></c>
      <c r="C4" t="s"><v>3</v></c>
      <c r="D4" t="s"><v>4</v></c>
    </row>
    <row r="6">
      <c r="A6" t="s"><v>5</v></c>
      <c r="D6"><v>101</v></c>
    </row>
    <row r="7">
      <c r="A7" t="s"><v>6</v></c>
      <c r="D7"><v>11</v></c>
    </row>
    <row r="8">
      <c r="A8" t="s"><v>7</v></c>
      <c r="D8"><v>22</v></c>
    </row>
  </sheetData>
</worksheet>
"""

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/sharedStrings.xml", "".join(shared_xml))
        zf.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
