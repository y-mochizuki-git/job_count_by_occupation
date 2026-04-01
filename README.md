# job_count_by_occupation

e-Stat の「一般職業紹介状況（職業安定業務統計）」から、全国の職種別有効求人数を取得する小さな Python CLI です。

取得対象:

- 統計: 一般職業紹介状況（職業安定業務統計）
- 表: 長期時系列表 21
- シート: `第２１表ー２　有効求人（パート含む常用）`
- 指標: 職業別有効求人数（パートタイムを含む常用）

## セットアップ

```bash
cd /Volumes/SSD_DEV/repos/job_count_by_occupation
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 使い方

最新の職業別求人件数を取得して `outputs/` に保存します。

```bash
job-count-by-occupation fetch
```

インストールせずにそのまま試す場合:

```bash
PYTHONPATH=src python3 -m job_count_by_occupation fetch
```

2010年以降をまとめて取得:

```bash
job-count-by-occupation fetch --start-year 2010
```

任意の出力先を指定することもできます。

```bash
job-count-by-occupation fetch --output-dir ./outputs
```

JSON のみ保存:

```bash
job-count-by-occupation fetch --format json
```

CSV のみ保存:

```bash
job-count-by-occupation fetch --format csv
```

## 出力内容

- `job_counts_YYYY-MM.csv`
- `job_counts_YYYY-MM.json`
- `job_counts_YYYY-MM_to_YYYY-MM.csv`
- `job_counts_YYYY-MM_to_YYYY-MM.json`

各レコードには以下を含みます。

- `year`: 対象年
- `month`: 対象月
- `occupation_name`: 職種名
- `job_count`: 有効求人数
- `source_table`: 統計表名
- `source_sheet`: シート名
- `source_url`: Excel の取得元 URL

## テスト

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
