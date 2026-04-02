# job_count_by_occupation

e-Stat の「一般職業紹介状況（職業安定業務統計）」をもとに、まず全国全体の求人規模をハローワーク実数から推計し、そのあと必要に応じて JobMedley 対象職種へ絞り込めるようにした小さな Python CLI です。

今の流れは次の順番です。

1. `fetch` で職業別の `有効求人数` / `新規求人数` を取得する
2. `major_category_coverage_template_since_2022-04.csv` で大分類ごとの補正の強さを調整する
3. `occupation_coverage_master_since_2022-04.csv` で職種ごとの補正の強さを調整する
4. `occupation-coverage-estimate` で occupation 単位の全国推計を作る
5. `national-scenarios` で全国全体の `low / base / high` を月次で出す
6. そのあとに必要なら `jobmedley_related` を使って JobMedley 対象職種だけを切り出す

## セットアップ

```bash
cd /Volumes/SSD_DEV/repos/job_count_by_occupation
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 主要コマンド

2010年以降の職業別求人件数をまとめて取得:

```bash
job-count-by-occupation fetch --start-year 2010 --job-metric both
```

occupation ごとの補正係数マスタを再生成:

```bash
job-count-by-occupation occupation-coverage-master
```

occupation 単位の全国求人推計を再生成:

```bash
job-count-by-occupation occupation-coverage-estimate
```

大分類ごとの `ハローワーク実数 vs base推計` の比較HTMLを作成:

```bash
job-count-by-occupation major-chart
```

年月 × 都道府県 × 大分類 × 職種で、`ハローワーク / base / low / high` のシナリオCSVを作成:

```bash
job-count-by-occupation prefecture-scenarios
```

全国全体の月次市場規模シナリオを作成:

```bash
job-count-by-occupation national-scenarios
```

倍率を変えてシナリオ幅を再生成:

```bash
job-count-by-occupation national-scenarios --low-multiplier 0.8 --high-multiplier 1.2
```

## 残している主なファイル

### 入力・中間資材

- `outputs/job_counts_2010-01_to_2026-02.csv`
- `outputs/job_counts_2010-01_to_2026-02.json`
- `outputs/job_type_mapping_master.csv`
- `outputs/occupation_master_since_2022-04.csv`
- `outputs/major_category_coverage_template_since_2022-04.csv`
- `outputs/major_category_hellowork_vs_base_since_2022-04.csv`
- `outputs/major_category_hellowork_vs_base_since_2022-04.html`
- `outputs/prefecture_major_occupation_scenarios_since_2022-04.csv`
- `outputs/occupation_coverage_master_since_2022-04.csv`
- `outputs/occupation_national_estimate_since_2022-04.csv`

### 最終出力

- `outputs/national_market_scenarios_since_2022-04.csv`

### 退避先

不要になった派生ファイルは `archive/outputs/` に移しています。

## 補正方法

この repo では、ハローワークの求人数をそのまま全国求人の実数とはみなしていません。  
ハローワークに出やすい職種もあれば、民間サイトや紹介会社の方が使われやすい職種もあるので、職種ごとに補正の強さを変えています。

考え方は次のとおりです。

1. まず、e-Stat から取れるハローワークの有効求人数を土台にする
2. そのうえで、「この大分類はハローワークにどれくらい出やすいか」を大まかに決める
3. さらに、「同じ大分類の中でも、この職種は特にハローワークに出やすいか、出にくいか」を職種ごとに少し調整する
4. その結果を使って、ハローワークの件数を全国の件数らしく見えるように広げる

たとえば、

- 介護や看護のようにハローワークにも比較的出やすそうな職種は、補正をやや小さめにする
- IT やクリエイティブのように民間サービスに出やすそうな職種は、補正をやや大きめにする

という考え方です。

もう少し具体的にいうと、2段階で補正しています。

- 1段階目
  `major_category_coverage_template_since_2022-04.csv` で、大分類ごとの補正の強さを月ごとに持つ
- 2段階目
  `occupation_coverage_master_since_2022-04.csv` で、職種ごとの補正の強さを持つ

この2つを組み合わせて、「その職種のハローワーク件数を全国の件数として見るなら何倍くらいに広げるか」を決めています。

現在レビュー用に置いている大分類の初期カバー率は次です。

| 大分類 | 初期カバー率 |
|---|---:|
| サービス | 0.45 |
| 事務 | 0.35 |
| 保安 | 0.45 |
| 専門・技術 | 0.34 |
| 建設・採掘 | 0.55 |
| 生産工程 | 0.50 |
| 管理 | 0.20 |
| 販売 | 0.35 |
| 輸送・機械運転 | 0.50 |
| 農林漁業 | 0.65 |
| 運搬・清掃・包装等 | 0.48 |

職種ごとの見直しは、上の大分類カバー率に対して相対係数を掛ける形です。  
たとえば `専門・技術` が `0.34` で、`情報処理・通信技術者` の相対係数が `0.55` なら、その職種の実効カバー率は `0.34 × 0.55 = 0.187` です。

現在レビュー用に明示的に入れている職種別の相対係数は次です。  
ここに書いていない職種は原則 `1.00` です。

| occupation_name | 相対係数 |
|---|---:|
| 管理的職業従事者 | 0.60 |
| 一般事務従事者 | 0.85 |
| 事務従事者 | 0.85 |
| 会計事務従事者 | 0.90 |
| 営業・販売事務従事者 | 0.85 |
| 情報処理・通信技術者 | 0.55 |
| 美術家，デザイナー，写真家，映像撮影者 | 0.45 |
| 営業職業従事者 | 0.85 |
| 販売従事者 | 0.80 |
| 商品販売従事者 | 0.75 |
| 販売類似職業従事者 | 0.85 |
| サービス職業従事者 | 0.95 |
| 接客・給仕職業従事者 | 0.95 |
| 生活衛生サービス職業従事者 | 0.95 |
| 保健師，助産師，看護師 | 1.25 |
| 医師，歯科医師，獣医師，薬剤師 | 1.15 |
| 医療技術者 | 1.10 |
| 社会福祉専門職業従事者 | 1.20 |
| 介護サービス職業従事者 | 1.25 |
| 建築・土木・測量技術者 | 1.05 |
| 建設従事者（建設躯体工事従事者を除く） | 1.10 |
| 建設躯体工事従事者 | 1.10 |
| 電気工事従事者 | 1.10 |
| 自動車運転従事者 | 1.10 |
| 輸送・機械運転従事者 | 1.05 |
| 運搬・清掃・包装等従事者 | 1.05 |
| 清掃従事者 | 1.05 |
| 生産工程従事者 | 1.10 |
| 製造技術者（開発） | 0.75 |
| 製造技術者（開発を除く） | 0.90 |

## `base / low / high` の意味

今のフェーズでは、`base / low / high` は `JobMedley 対象職種` の数ではなく、まず `全国全体` の求人数シナリオです。

- `base`
  occupation ごとに補正した全国推計求人を、全国全職種ぶん合計したもの
- `low`
  `base` より小さめに見積もった保守ケース
- `high`
  `base` より大きめに見積もった上振れケース

つまり、今は

`全国全体の分母を先に作る段階`

で、そのあとに必要なら `jobmedley_related = true` の職種だけを束ねて JobMedley 比較用の分母にします。

## 都道府県レベルへの按分方法

都道府県別 × 大分類別 × 職種別のシナリオは、e-Stat に同じ粒度の公開表がないため、近似で作っています。

### 有効求人数

`有効求人数` については、e-Stat に都道府県別総量があるので、まず各月の都道府県シェアを作ります。

考え方は次のとおりです。

1. 各月のハローワーク有効求人数の全国合計を使う
2. 同じ月の都道府県別ハローワーク有効求人数を使う
3. `都道府県シェア = 都道府県のハローワーク有効求人数 / 全国のハローワーク有効求人数`
4. その都道府県シェアを、全国の職種別 `ハローワーク / base / low / high` に掛けて、都道府県別へ配る

つまり、

- 東京都がその月のハローワーク有効求人数の 14% を持っていれば
- 全国の `情報処理・通信技術者` の `base` 推計の 14% を東京都分として置く

という考え方です。

### 新規求人数

`新規求人数` については、今この repo で使っている都道府県別総量表が `有効求人数` ベースなので、同じ粒度の都道府県別 `新規求人数` 総量は直接使っていません。

そのため、新規求人数の都道府県配分は次の近似です。

1. その月の `有効求人数` で作った都道府県シェアを使う
2. その都道府県シェアを、その月の全国 `新規求人数` に掛けて、都道府県別の新規求人数総量を近似する
3. その近似総量を、全国の職種別 `新規求人数 / base / low / high` の構成比で配る

つまり新規求人数の都道府県別値は、

`その月の有効求人数の地域構成が、新規求人数にもおおむね当てはまる`

という仮定で作っています。

### 大分類・職種への配り方

都道府県総量を作ったあとは、各シナリオごとに全国側の構成比で配っています。

- `prefecture_hellowork_job_count`
  全国のハローワーク職種構成比で按分
- `prefecture_base_job_count`
  全国の `base` 職種構成比で按分
- `prefecture_low_job_count`
  全国の `low` 職種構成比で按分
- `prefecture_high_job_count`
  全国の `high` 職種構成比で按分

`low` と `high` は `base` に倍率を掛けたシナリオなので、職種構成比は `base` と同じで、総量だけが変わる形です。

### 注意点

- これは `実測の都道府県別職種別求人` ではなく近似です
- 特に `新規求人数` の都道府県別配分は、`有効求人数` の地域シェアを流用しています
- したがって、県ごとの実際の職種偏りや新規求人偏りを完全には反映していません
- ただし、`全国の職種構成` と `都道府県の総量差` を同時に持たせたい用途では、かなり使いやすい近似です

## 主要カラム

### `job_counts_2010-01_to_2026-02.csv`

- `year`
- `month`
- `job_metric`
- `major_category`
- `occupation_name`
- `job_count`

### `occupation_master_since_2022-04.csv`

- `occupation_name`
- `major_category`
- `description`
- `examples_or_scope`
- `jobmedley_related`

### `job_type_mapping_master.csv`

- `source_job_type`
- `mapped_major_category`
- `mapped_occupation_name`
- `mapping_confidence`
- `notes`

### `occupation_national_estimate_since_2022-04.csv`

- `year`
- `month`
- `major_category`
- `occupation_name`
- `jobmedley_related`
- `estat_job_count`
- `major_category_coverage_rate`
- `occupation_relative_factor`
- `coverage_rate`
- `estimated_national_job_count`

### `national_market_scenarios_since_2022-04.csv`

- `year`
- `month`
- `estimated_occupation_count`
- `hellowork_active_job_count`
- `estimated_national_active_job_count_low`
- `estimated_national_active_job_count_base`
- `estimated_national_active_job_count_high`
- `low_multiplier`
- `high_multiplier`

シナリオ定義:

- `hellowork_active_job_count`
  その月のハローワーク有効求人数の全国合計
- `estimated_national_active_job_count_base`
  職種ごとの仮説で全国向けに補正した全国求人の合計
- `estimated_national_active_job_count_low`
  `base × low_multiplier` で作る保守ケース
- `estimated_national_active_job_count_high`
  `base × high_multiplier` で作る上振れケース

初期値では次を使っています。

- `low_multiplier = 0.70`
- `high_multiplier = 1.30`

つまり初期設定では、

- `low = base × 0.70`
- `high = base × 1.30`

です。

### `prefecture_major_occupation_scenarios_since_2022-04.csv`

- `year`
- `month`
- `job_metric`
- `prefecture`
- `major_category`
- `occupation_name`
- `prefecture_hellowork_job_count`
- `prefecture_base_job_count`
- `prefecture_low_job_count`
- `prefecture_high_job_count`
- `prefecture_share_of_hellowork_total`
- `national_hellowork_total_job_count`
- `national_base_total_job_count`
- `national_low_total_job_count`
- `national_high_total_job_count`

## テスト

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```
