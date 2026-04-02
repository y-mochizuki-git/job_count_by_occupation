from __future__ import annotations

import csv
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from job_count_by_occupation.estat import is_target_job_metric


@dataclass
class SeriesPoint:
    label: str
    value: int


@dataclass
class OccupationSeries:
    occupation_name: str
    latest_value: int
    points: List[SeriesPoint]


COLORS = [
    "#0f766e",
    "#2563eb",
    "#dc2626",
    "#7c3aed",
    "#d97706",
    "#059669",
    "#db2777",
    "#4f46e5",
    "#0891b2",
    "#65a30d",
]


def generate_top20_report(
    csv_path: Path,
    output_path: Path,
    start_year: int = 2022,
    start_month: int = 4,
    top_n: int = 20,
) -> Path:
    series = _load_top_series(csv_path, start_year, start_month, top_n)
    first_half = series[:10]
    second_half = series[10:20]

    html_text = _build_html(
        title="2022年4月以降の職種別有効求人数トレンド",
        subtitle=f"対象: {start_year}年{start_month}月以降 / 最新月の求人数でTOP{top_n}を抽出 / 職業計は除外",
        sections=[
            ("TOP 1-10", first_half),
            ("TOP 11-20", second_half),
        ],
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def generate_major_category_comparison_report(
    csv_path: Path,
    output_path: Path,
    start_year: int = 2022,
    start_month: int = 4,
) -> Path:
    sections = _load_major_category_sections(csv_path, start_year, start_month)
    html_text = _build_html(
        title="大分類別 有効求人数トレンド",
        subtitle=f"対象: {start_year}年{start_month}月以降 / 各大分類について ハローワーク実数 と base推計 を比較 / 総計・集計区分・分類不能は除外",
        sections=sections,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def generate_scenario_explorer_report(
    csv_path: Path,
    output_path: Path,
    start_year: int = 2022,
    start_month: int = 4,
) -> Path:
    dataset = _load_scenario_explorer_dataset(csv_path, start_year, start_month)
    html_text = _build_scenario_explorer_html(dataset)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_text, encoding="utf-8")
    return output_path


def _load_top_series(csv_path: Path, start_year: int, start_month: int, top_n: int) -> List[OccupationSeries]:
    records: Dict[str, List[Tuple[str, int]]] = {}
    latest_label = ""
    latest_bucket: Dict[str, int] = {}

    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not is_target_job_metric(row):
                continue
            year = int(row["year"])
            month = int(row["month"])
            if (year, month) < (start_year, start_month):
                continue
            occupation_name = row["occupation_name"]
            if occupation_name == "職業計":
                continue
            label = f"{year}-{month:02d}"
            value = int(row["job_count"])
            records.setdefault(occupation_name, []).append((label, value))
            if label >= latest_label:
                if label > latest_label:
                    latest_label = label
                    latest_bucket = {}
                latest_bucket[occupation_name] = value

    top_names = [
        name
        for name, _ in sorted(latest_bucket.items(), key=lambda item: item[1], reverse=True)[:top_n]
    ]

    series_list: List[OccupationSeries] = []
    for name in top_names:
        points = [SeriesPoint(label=label, value=value) for label, value in records[name]]
        series_list.append(
            OccupationSeries(
                occupation_name=name,
                latest_value=latest_bucket[name],
                points=points,
            )
        )
    return series_list


def _load_major_category_sections(
    csv_path: Path,
    start_year: int,
    start_month: int,
) -> List[Tuple[str, List[OccupationSeries]]]:
    bucket: Dict[str, Dict[Tuple[int, int], Dict[str, int]]] = {}
    latest_values: Dict[str, int] = {}

    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            year = int(row["year"])
            month = int(row["month"])
            if (year, month) < (start_year, start_month):
                continue

            major_category = row.get("major_category", "").strip()
            if major_category in {"", "総計", "集計区分", "分類不能"}:
                continue

            estat_text = row.get("estat_job_count", "").strip()
            estimated_text = row.get("estimated_national_job_count", "").strip()
            if not estat_text or not estimated_text:
                continue

            category_bucket = bucket.setdefault(major_category, {})
            month_bucket = category_bucket.setdefault((year, month), {"ハローワーク": 0, "base推計": 0})
            month_bucket["ハローワーク"] += int(estat_text)
            month_bucket["base推計"] += int(estimated_text)
            latest_values[major_category] = month_bucket["ハローワーク"]

    sections: List[Tuple[str, List[OccupationSeries]]] = []
    for major_category, _ in sorted(latest_values.items(), key=lambda item: item[1], reverse=True):
        series_group = []
        for series_name in ["ハローワーク", "base推計"]:
            points_raw = [
                (f"{year}-{month:02d}", values[series_name])
                for (year, month), values in sorted(bucket[major_category].items())
            ]
            points = [SeriesPoint(label=label, value=value) for label, value in points_raw]
            series_group.append(
                OccupationSeries(
                    occupation_name=series_name,
                    latest_value=points[-1].value,
                    points=points,
                )
            )
        sections.append((major_category, series_group))
    return sections


def _build_html(title: str, subtitle: str, sections: Sequence[Tuple[str, Sequence[OccupationSeries]]]) -> str:
    section_html = "\n".join(_render_section(name, series_group) for name, series_group in sections if series_group)
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --paper: #fffdf8;
      --ink: #1c1917;
      --muted: #57534e;
      --grid: #d6d3d1;
      --frame: #e7e5e4;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #fcd9b6 0, transparent 28%),
        radial-gradient(circle at top right, #c7e7dd 0, transparent 30%),
        linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
    }}
    .wrap {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.15;
    }}
    .lead {{
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 15px;
    }}
    .section {{
      margin-top: 28px;
      background: rgba(255, 253, 248, 0.92);
      border: 1px solid var(--frame);
      border-radius: 24px;
      padding: 20px;
      box-shadow: 0 18px 45px rgba(28, 25, 23, 0.08);
    }}
    h2 {{
      margin: 0 0 16px;
      font-size: 22px;
    }}
    .chart-block {{
      overflow-x: auto;
    }}
    .legend {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px 16px;
      margin-top: 14px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 14px;
      color: var(--muted);
    }}
    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      flex: 0 0 auto;
    }}
    .legend strong {{
      color: var(--ink);
      font-weight: 700;
    }}
    .footer {{
      margin-top: 18px;
      font-size: 12px;
      color: var(--muted);
    }}
    svg text {{
      font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <h1>{html.escape(title)}</h1>
    <p class="lead">{html.escape(subtitle)}</p>
    {section_html}
  </main>
</body>
</html>
"""


def _load_scenario_explorer_dataset(
    csv_path: Path,
    start_year: int,
    start_month: int,
) -> Dict[str, object]:
    metric_codes: Dict[str, int] = {}
    prefecture_codes: Dict[str, int] = {}
    major_codes: Dict[str, int] = {}
    occupation_codes: Dict[str, int] = {}

    metric_values: List[str] = []
    prefecture_values: List[str] = []
    major_values: List[str] = []
    occupation_values: List[str] = []
    month_labels: List[str] = []
    month_codes: Dict[str, int] = {}
    rows: List[List[int]] = []

    def encode(value: str, code_map: Dict[str, int], values: List[str]) -> int:
        if value not in code_map:
            code_map[value] = len(values)
            values.append(value)
        return code_map[value]

    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            year = int(row["year"])
            month = int(row["month"])
            if (year, month) < (start_year, start_month):
                continue

            month_label = f"{year}-{month:02d}"
            month_id = encode(month_label, month_codes, month_labels)
            metric_id = encode(row["job_metric"], metric_codes, metric_values)
            prefecture_id = encode(row["prefecture"], prefecture_codes, prefecture_values)
            major_id = encode(row["major_category"], major_codes, major_values)
            occupation_id = encode(row["occupation_name"], occupation_codes, occupation_values)
            rows.append(
                [
                    month_id,
                    metric_id,
                    prefecture_id,
                    major_id,
                    occupation_id,
                    int(row["prefecture_hellowork_job_count"]),
                    int(row["prefecture_base_job_count"]),
                    int(row["prefecture_low_job_count"]),
                    int(row["prefecture_high_job_count"]),
                ]
            )

    return {
        "months": month_labels,
        "metrics": metric_values,
        "prefectures": prefecture_values,
        "majorCategories": major_values,
        "occupations": occupation_values,
        "rows": rows,
    }


def _build_scenario_explorer_html(dataset: Dict[str, object]) -> str:
    dataset_json = json.dumps(dataset, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>有効求人数・新規求人数 シナリオ探索</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --paper: rgba(255, 253, 248, 0.96);
      --ink: #1c1917;
      --muted: #57534e;
      --frame: #e7e5e4;
      --grid: #d6d3d1;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #fcd9b6 0, transparent 28%),
        radial-gradient(circle at top right, #c7e7dd 0, transparent 30%),
        linear-gradient(180deg, #f8f4ec 0%, var(--bg) 100%);
    }}
    .wrap {{
      max-width: 1480px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }}
    h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.15;
    }}
    .lead {{
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 15px;
      max-width: 980px;
    }}
    .panel {{
      margin-top: 24px;
      background: var(--paper);
      border: 1px solid var(--frame);
      border-radius: 24px;
      padding: 18px;
      box-shadow: 0 18px 45px rgba(28, 25, 23, 0.08);
    }}
    .controls {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px 16px;
      align-items: end;
    }}
    label {{
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: var(--muted);
    }}
    select {{
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid #d6d3d1;
      background: #fffdf8;
      color: var(--ink);
      font-size: 14px;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px 20px;
      margin-top: 16px;
      font-size: 14px;
      color: var(--muted);
    }}
    .summary strong {{
      color: var(--ink);
    }}
    .chart-wrap {{
      margin-top: 18px;
      overflow-x: auto;
    }}
    .legend {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 10px 16px;
      margin-top: 14px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 14px;
      color: var(--muted);
    }}
    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      flex: 0 0 auto;
    }}
    .hint {{
      margin-top: 14px;
      font-size: 13px;
      color: var(--muted);
      line-height: 1.6;
    }}
    .empty {{
      margin-top: 18px;
      padding: 24px;
      border: 1px dashed #d6d3d1;
      border-radius: 18px;
      color: var(--muted);
      background: rgba(255, 253, 248, 0.75);
    }}
    svg text {{
      font-family: "Hiragino Sans", "Yu Gothic", sans-serif;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <h1>都道府県・大分類・職種の時系列シナリオ探索</h1>
    <p class="lead">`prefecture_major_occupation_scenarios_since_2022-04.csv` を埋め込んだ探索HTMLです。表示単位を切り替えながら、ハローワーク実数と推計シナリオを月次折れ線で確認できます。比較モードでは最新月の値が大きい順に上位系列を表示します。</p>
    <section class="panel">
      <div class="controls">
        <label>表示モード
          <select id="viewMode">
            <option value="single">単一系列</option>
            <option value="prefecture">都道府県比較</option>
            <option value="major">大分類比較</option>
            <option value="occupation">職種比較</option>
          </select>
        </label>
        <label>指標
          <select id="metric"></select>
        </label>
        <label>シナリオ
          <select id="scenario">
            <option value="hellowork">ハローワーク</option>
            <option value="base">base</option>
            <option value="low">low</option>
            <option value="high">high</option>
          </select>
        </label>
        <label>都道府県
          <select id="prefecture"></select>
        </label>
        <label>大分類
          <select id="majorCategory"></select>
        </label>
        <label>職種
          <select id="occupation"></select>
        </label>
        <label>表示本数
          <select id="topN">
            <option value="5">5</option>
            <option value="10" selected>10</option>
            <option value="20">20</option>
            <option value="47">47</option>
            <option value="100">100</option>
          </select>
        </label>
      </div>
      <div class="summary" id="summary"></div>
      <div class="chart-wrap" id="chartWrap"></div>
      <div class="legend" id="legend"></div>
      <div class="hint">
        単一系列では、未選択の軸は合算されます。比較モードでは、比較しない軸をフィルタとして使います。
        例: 「職種比較」で `都道府県=北海道`、`大分類=サービス` を選ぶと、北海道のサービス職種だけを比較します。
      </div>
    </section>
  </main>
  <script id="scenario-data" type="application/json">{dataset_json}</script>
  <script>
    const DATA = JSON.parse(document.getElementById("scenario-data").textContent);
    const COLORS = {json.dumps(COLORS)};
    const ALL = "__all__";
    const metricEl = document.getElementById("metric");
    const scenarioEl = document.getElementById("scenario");
    const viewModeEl = document.getElementById("viewMode");
    const prefectureEl = document.getElementById("prefecture");
    const majorEl = document.getElementById("majorCategory");
    const occupationEl = document.getElementById("occupation");
    const topNEl = document.getElementById("topN");
    const summaryEl = document.getElementById("summary");
    const chartWrapEl = document.getElementById("chartWrap");
    const legendEl = document.getElementById("legend");

    function setOptions(select, options, includeAll = true, allLabel = "すべて") {{
      const current = select.value;
      select.innerHTML = "";
      if (includeAll) {{
        const option = document.createElement("option");
        option.value = ALL;
        option.textContent = allLabel;
        select.appendChild(option);
      }}
      for (const value of options) {{
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }}
      if ([...select.options].some((option) => option.value === current)) {{
        select.value = current;
      }}
    }}

    function init() {{
      setOptions(metricEl, DATA.metrics, false);
      setOptions(prefectureEl, DATA.prefectures, true, "全都道府県");
      setOptions(majorEl, DATA.majorCategories, true, "全大分類");
      setOptions(occupationEl, DATA.occupations, true, "全職種");
      metricEl.value = DATA.metrics.includes("有効求人数") ? "有効求人数" : DATA.metrics[0];
      scenarioEl.value = "base";
      prefectureEl.value = ALL;
      majorEl.value = ALL;
      occupationEl.value = ALL;
      for (const el of [metricEl, scenarioEl, viewModeEl, prefectureEl, majorEl, occupationEl, topNEl]) {{
        el.addEventListener("change", render);
      }}
      render();
    }}

    function render() {{
      const state = {{
        metric: metricEl.value,
        scenario: scenarioEl.value,
        view: viewModeEl.value,
        prefecture: prefectureEl.value,
        major: majorEl.value,
        occupation: occupationEl.value,
        topN: Number(topNEl.value),
      }};
      const rows = DATA.rows.filter((row) => DATA.metrics[row[1]] === state.metric);
      const series = buildSeries(rows, state);
      renderSummary(series, state);
      if (!series.length) {{
        chartWrapEl.innerHTML = '<div class="empty">条件に一致する系列がありません。フィルタを少し緩めてください。</div>';
        legendEl.innerHTML = "";
        return;
      }}
      chartWrapEl.innerHTML = renderSvg(series, DATA.months, 1260, 520);
      legendEl.innerHTML = series.map((seriesItem, index) => `
        <div class="legend-item">
          <span class="swatch" style="background:${{COLORS[index % COLORS.length]}}"></span>
          <span><strong>${{escapeHtml(seriesItem.name)}}</strong> 最新: ${{seriesItem.latest.toLocaleString("ja-JP")}}</span>
        </div>
      `).join("");
    }}

    function buildSeries(rows, state) {{
      const scenarioIndex = {{ hellowork: 5, base: 6, low: 7, high: 8 }}[state.scenario];
      const grouped = new Map();
      for (const row of rows) {{
        const monthLabel = DATA.months[row[0]];
        const prefecture = DATA.prefectures[row[2]];
        const major = DATA.majorCategories[row[3]];
        const occupation = DATA.occupations[row[4]];

        let groupKey = "";
        let groupLabel = "";
        if (state.view === "single") {{
          if (state.prefecture !== ALL && prefecture !== state.prefecture) continue;
          if (state.major !== ALL && major !== state.major) continue;
          if (state.occupation !== ALL && occupation !== state.occupation) continue;
          groupKey = "__single__";
          groupLabel = buildSingleLabel(state);
        }} else if (state.view === "prefecture") {{
          if (state.major !== ALL && major !== state.major) continue;
          if (state.occupation !== ALL && occupation !== state.occupation) continue;
          groupKey = prefecture;
          groupLabel = prefecture;
        }} else if (state.view === "major") {{
          if (state.prefecture !== ALL && prefecture !== state.prefecture) continue;
          if (state.occupation !== ALL && occupation !== state.occupation) continue;
          groupKey = major;
          groupLabel = major;
        }} else {{
          if (state.prefecture !== ALL && prefecture !== state.prefecture) continue;
          if (state.major !== ALL && major !== state.major) continue;
          groupKey = occupation;
          groupLabel = occupation;
        }}

        if (!grouped.has(groupKey)) {{
          grouped.set(groupKey, {{ name: groupLabel, values: new Map() }});
        }}
        const entry = grouped.get(groupKey);
        entry.values.set(monthLabel, (entry.values.get(monthLabel) || 0) + row[scenarioIndex]);
      }}

      const series = [...grouped.values()].map((entry) => {{
        const points = DATA.months.map((month) => entry.values.get(month) || 0);
        return {{
          name: entry.name,
          points,
          latest: points[points.length - 1] || 0,
        }};
      }});

      if (state.view !== "single") {{
        series.sort((a, b) => b.latest - a.latest);
        return series.slice(0, state.topN);
      }}
      return series;
    }}

    function buildSingleLabel(state) {{
      const parts = [];
      parts.push(state.prefecture === ALL ? "全都道府県" : state.prefecture);
      parts.push(state.major === ALL ? "全大分類" : state.major);
      parts.push(state.occupation === ALL ? "全職種" : state.occupation);
      return parts.join(" / ");
    }}

    function renderSummary(series, state) {{
      const latestMonth = DATA.months[DATA.months.length - 1];
      const totalLatest = series.reduce((sum, item) => sum + item.latest, 0);
      const modeLabels = {{
        single: "単一系列",
        prefecture: "都道府県比較",
        major: "大分類比較",
        occupation: "職種比較",
      }};
      summaryEl.innerHTML = `
        <span><strong>表示モード:</strong> ${{modeLabels[state.view]}}</span>
        <span><strong>指標:</strong> ${{state.metric}}</span>
        <span><strong>シナリオ:</strong> ${{state.scenario}}</span>
        <span><strong>最新月:</strong> ${{latestMonth}}</span>
        <span><strong>系列数:</strong> ${{series.length}}</span>
        <span><strong>最新月合計:</strong> ${{totalLatest.toLocaleString("ja-JP")}}</span>
      `;
    }}

    function renderSvg(series, labels, width, height) {{
      const left = 78;
      const right = 24;
      const top = 24;
      const bottom = 56;
      const innerW = width - left - right;
      const innerH = height - top - bottom;
      const allValues = series.flatMap((item) => item.points);
      const minValue = Math.min(...allValues);
      const maxValue = Math.max(...allValues);
      const pad = Math.max(1, Math.floor((maxValue - minValue) * 0.08));
      const yMin = Math.max(0, minValue - pad);
      const yMax = maxValue + pad;

      function xAt(index) {{
        if (labels.length === 1) return left + innerW / 2;
        return left + innerW * index / (labels.length - 1);
      }}
      function yAt(value) {{
        if (yMax === yMin) return top + innerH / 2;
        const ratio = (value - yMin) / (yMax - yMin);
        return top + innerH * (1 - ratio);
      }}

      const grid = [];
      for (let step = 0; step < 6; step += 1) {{
        const value = yMin + (yMax - yMin) * step / 5;
        const y = yAt(Math.round(value));
        grid.push(`<line x1="${{left}}" y1="${{y.toFixed(2)}}" x2="${{width-right}}" y2="${{y.toFixed(2)}}" stroke="#d6d3d1" stroke-width="1" />`);
        grid.push(`<text x="${{left-10}}" y="${{(y+4).toFixed(2)}}" text-anchor="end" font-size="12" fill="#57534e">${{Math.round(value).toLocaleString("ja-JP")}}</text>`);
      }}

      const xTicks = [];
      const tickIndices = [...new Set([0, Math.floor(labels.length / 4), Math.floor(labels.length / 2), Math.floor(labels.length * 3 / 4), labels.length - 1])];
      for (const idx of tickIndices) {{
        const x = xAt(idx);
        xTicks.push(`<line x1="${{x.toFixed(2)}}" y1="${{top}}" x2="${{x.toFixed(2)}}" y2="${{height-bottom}}" stroke="#eee7dc" stroke-width="1" />`);
        xTicks.push(`<text x="${{x.toFixed(2)}}" y="${{height-20}}" text-anchor="middle" font-size="12" fill="#57534e">${{labels[idx]}}</text>`);
      }}

      const lines = [];
      const endLabels = [];
      series.forEach((seriesItem, index) => {{
        const color = COLORS[index % COLORS.length];
        const path = seriesItem.points.map((value, pointIndex) => `${{xAt(pointIndex).toFixed(2)}},${{yAt(value).toFixed(2)}}`).join(" ");
        lines.push(`<polyline fill="none" stroke="${{color}}" stroke-width="2.5" points="${{path}}" />`);
        const endX = xAt(seriesItem.points.length - 1);
        const endY = yAt(seriesItem.points[seriesItem.points.length - 1]);
        lines.push(`<circle cx="${{endX.toFixed(2)}}" cy="${{endY.toFixed(2)}}" r="3.5" fill="${{color}}" />`);
        endLabels.push(`<text x="${{Math.min(width-right-2, endX + 8).toFixed(2)}}" y="${{(endY+4).toFixed(2)}}" font-size="11" fill="${{color}}">${{index + 1}}</text>`);
      }});

      return `
        <svg viewBox="0 0 ${{width}} ${{height}}" width="100%" height="auto" role="img" aria-label="折れ線グラフ">
          <rect x="0" y="0" width="${{width}}" height="${{height}}" rx="18" fill="#fffdf8" />
          ${{grid.join("")}}
          ${{xTicks.join("")}}
          <line x1="${{left}}" y1="${{height-bottom}}" x2="${{width-right}}" y2="${{height-bottom}}" stroke="#a8a29e" stroke-width="1.5" />
          <line x1="${{left}}" y1="${{top}}" x2="${{left}}" y2="${{height-bottom}}" stroke="#a8a29e" stroke-width="1.5" />
          ${{lines.join("")}}
          ${{endLabels.join("")}}
        </svg>
      `;
    }}

    function escapeHtml(value) {{
      return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    init();
  </script>
</body>
</html>
"""


def _render_section(section_name: str, series_group: Sequence[OccupationSeries]) -> str:
    chart = _render_svg_chart(series_group, width=1260, height=520)
    legends = []
    for idx, series in enumerate(series_group):
        color = COLORS[idx % len(COLORS)]
        legends.append(
            f"""<div class="legend-item">
<span class="swatch" style="background:{color}"></span>
<span><strong>{html.escape(series.occupation_name)}</strong> 最新: {series.latest_value:,}</span>
</div>"""
        )
    return f"""<section class="section">
  <h2>{html.escape(section_name)}</h2>
  <div class="chart-block">{chart}</div>
  <div class="legend">
    {''.join(legends)}
  </div>
  <div class="footer">縦軸は求人数、横軸は月次。各線は 2026年2月時点の上位職種です。</div>
</section>"""


def _render_svg_chart(series_group: Sequence[OccupationSeries], width: int, height: int) -> str:
    left = 78
    right = 24
    top = 24
    bottom = 56
    inner_w = width - left - right
    inner_h = height - top - bottom

    labels = [point.label for point in series_group[0].points]
    all_values = [point.value for series in series_group for point in series.points]
    min_value = min(all_values)
    max_value = max(all_values)
    pad = max(1, int((max_value - min_value) * 0.08))
    y_min = max(0, min_value - pad)
    y_max = max_value + pad

    def x_at(index: int) -> float:
        if len(labels) == 1:
            return left + inner_w / 2
        return left + inner_w * index / (len(labels) - 1)

    def y_at(value: int) -> float:
        if y_max == y_min:
            return top + inner_h / 2
        ratio = (value - y_min) / (y_max - y_min)
        return top + inner_h * (1 - ratio)

    grid_lines = []
    for step in range(6):
        value = y_min + (y_max - y_min) * step / 5
        y = y_at(int(value))
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" stroke="#d6d3d1" stroke-width="1" />'
        )
        grid_lines.append(
            f'<text x="{left-10}" y="{y+4:.2f}" text-anchor="end" font-size="12" fill="#57534e">{int(value):,}</text>'
        )

    x_ticks = []
    tick_indices = sorted(set([0, len(labels) // 4, len(labels) // 2, (len(labels) * 3) // 4, len(labels) - 1]))
    for idx in tick_indices:
        x = x_at(idx)
        x_ticks.append(
            f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height-bottom}" stroke="#eee7dc" stroke-width="1" />'
        )
        x_ticks.append(
            f'<text x="{x:.2f}" y="{height-20}" text-anchor="middle" font-size="12" fill="#57534e">{labels[idx]}</text>'
        )

    line_paths = []
    end_labels = []
    for idx, series in enumerate(series_group):
        color = COLORS[idx % len(COLORS)]
        path_points = [f"{x_at(i):.2f},{y_at(point.value):.2f}" for i, point in enumerate(series.points)]
        line_paths.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{" ".join(path_points)}" />'
        )
        x_end = x_at(len(series.points) - 1)
        y_end = y_at(series.points[-1].value)
        line_paths.append(f'<circle cx="{x_end:.2f}" cy="{y_end:.2f}" r="3.5" fill="{color}" />')
        end_labels.append(
            f'<text x="{min(width-right-2, x_end + 8):.2f}" y="{y_end+4:.2f}" font-size="11" fill="{color}">{idx+1}</text>'
        )

    return f"""<svg viewBox="0 0 {width} {height}" width="100%" height="auto" role="img" aria-label="折れ線グラフ">
  <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#fffdf8" />
  {''.join(grid_lines)}
  {''.join(x_ticks)}
  <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#a8a29e" stroke-width="1.5" />
  <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#a8a29e" stroke-width="1.5" />
  {''.join(line_paths)}
  {''.join(end_labels)}
</svg>"""
