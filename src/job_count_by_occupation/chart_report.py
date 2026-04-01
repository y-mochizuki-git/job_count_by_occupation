from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


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


def _load_top_series(csv_path: Path, start_year: int, start_month: int, top_n: int) -> List[OccupationSeries]:
    records: Dict[str, List[Tuple[str, int]]] = {}
    latest_label = ""
    latest_bucket: Dict[str, int] = {}

    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
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
