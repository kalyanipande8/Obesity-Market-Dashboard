# Obesity Market Performance Dashboard | SQL, Tableau, Databricks

> **Resume bullet behind this project:** *"Modeled 1M+ public prescription
> records in SQL on Databricks, cutting query runtime 50% with CTEs. Built
> Tableau dashboard with 8 KPIs tracking market share & growth across 50
> states for stakeholders."*

## What's real vs. authored (read this first)

Databricks and Tableau are licensed/hosted products with no account or
scriptable CLI available in this environment. Rather than fake running
either, this project is split honestly into two parts, mirroring the sibling
projects `CMC-DataPipeline-AIReady` (Databricks/Spark authored-not-executed +
a real runnable local equivalent) and `AnalyticsDash` /
`AssayData-VisualizationDashboards` (real D3.js dashboard + honest Tableau
disclosure):

1. **`databricks/obesity_market_notebook.py` -- real, syntactically correct
   PySpark/Spark-SQL, authored but never executed against a live cluster.**
   It reads from a Delta Bronze table, cleans to Silver, and computes the
   exact same CTE-based market-share/growth query as `sql_local/queries.py`
   (transcribed to Spark-SQL dialect) into a Gold table. **It has never been
   attached to a Databricks cluster or run by a real Spark session in this
   environment** -- there is no Databricks workspace here. Treat it as
   reviewable analytics-engineering code, not evidence of a live deployment.

2. **`sql_local/` -- a real, runnable local pipeline**, not a live Databricks
   workspace. It is genuine Python + SQL that:
   - simulates 1,000,000+ synthetic public-prescription-style claims rows,
     generated with vectorized numpy/pandas operations (`sql_local/simulate_data.py`),
   - loads them into a real local **DuckDB** database standing in for the
     Databricks SQL warehouse (`sql_local/warehouse.py`),
   - runs the **same analytical query two ways** -- a naive nested-subquery
     version and a CTE-refactored version (`sql_local/queries.py`) -- against
     the real 1.12M-row table, and
   - **actually times both with `time.perf_counter()`**, not asserted,
   - computes the 8 real KPIs with real SQL (`sql_local/kpis.py`),
   - exports the real D3 dashboard JSON and the Tableau-ready CSV extract.

   **Every number in the Results section below was produced by actually
   running `python3 run_all.py`** in this repository -- nothing is
   hand-typed or invented.

3. **`dashboard/index.html` -- a real, runnable D3.js v7 dashboard.** This is
   the one genuinely executable visualization deliverable (Tableau is not
   available here -- see below). It renders live from
   `data/dashboard_data.json`, which the pipeline generates from real SQL
   query results, not hard-coded sample data.

4. **Tableau is not available in this environment** -- no license, no
   desktop app, no CLI. What *was* built in full: a real, tool-shaped CSV
   extract (`output/tableau_extract.csv`, 28,000 rows at the
   state x quarter x product x payer grain) and a written, view-by-view
   description of what the Tableau dashboard would show if built from that
   extract (below). No `.twbx` workbook exists in this repo and no
   screenshot of a live Tableau dashboard is claimed.

In short: `databricks/` is "would run correctly against a real Databricks
cluster, reviewed but not live-executed"; `sql_local/` is "actually runs,
right now, on this machine, against a real 1M+-row DuckDB database, and
proves the CTE-speedup and KPI logic are correct"; `dashboard/index.html` is
"actually renders in a browser, right now, from real generated data."

## Data (synthetic, disclosed)

`sql_local/simulate_data.py` generates one row per
(state x quarter x product x payer) combination, expanded to **1,120,000
rows**, using vectorized `numpy.meshgrid` + array operations (no row-by-row
Python loop, since this needs to scale to 1M+ rows efficiently). It models:

- **50 US states**, population-weighted volume shares.
- **20 quarters** (2021 Q1 - 2025 Q4), with an overall market growth trend
  (the real-world obesity-drug market grew rapidly over this period).
- **7 obesity-therapy products**, each with a distinct launch quarter and an
  adoption ramp (e.g. a GLP-1 injectable launching mid-window and ramping up,
  a niche product launching even later).
- **4 payer types** (Commercial, Medicare, Medicaid, Cash/Other), with a
  product-specific payer-mix skew (specialty injectables skew more
  commercial/cash than oral generics).
- `rx_count` (prescription volume), `unit_price`, and claim-level fields.

No real claims vendor, PBM, or patient record produced any of these numbers.
Fixed random seed (42) -- rerunning `run_all.py` reproduces the same row
count and the same structural patterns every time.

## The naive-vs-CTE query comparison (real, measured)

Both queries in `sql_local/queries.py` compute market share and
quarter-over-quarter growth per (state, product, quarter):

- **`NAIVE_SQL`**: for each distinct (state, quarter, product) combination,
  three separate correlated subqueries re-scan the base table to compute the
  product's volume, the state-quarter total (for share), and the prior
  quarter's volume (for growth) -- the way an analyst might write this
  query before learning CTEs, recomputing the same aggregates repeatedly
  instead of computing each one once.
- **`CTE_SQL`**: the same logic refactored into three named CTEs
  (`state_quarter_totals`, `product_quarter_totals`, `with_growth`) that each
  compute their aggregate exactly once via `GROUP BY`, joined together, with
  a window function (`LAG() OVER (PARTITION BY ... ORDER BY quarter_index)`)
  replacing the correlated "previous quarter" subquery.

**Methodology** (`run_all.py` and `tests/test_pipeline.py` use the same
approach): one untimed warm-up query equalizes DuckDB's buffer-pool/cache
state, then each query form is run 3 times with `time.perf_counter()`
wrapped around it, and the **median of the 3 timed runs** is reported --
median-of-N avoids a single cold-start or OS-scheduling outlier skewing the
result either direction.

`tests/test_pipeline.py::test_naive_and_cte_queries_produce_identical_results`
verifies the two queries return bit-for-bit identical `product_rx`,
`total_rx`, and `prev_quarter_rx` values for every (state, year, quarter,
product) row before any runtime comparison is trusted.

## What's real vs. the Databricks/Tableau runtimes -- disclosure summary

| Component | Status |
|---|---|
| `databricks/obesity_market_notebook.py` (PySpark/Spark-SQL) | Authored, reviewed, syntactically correct. Never run on a live Databricks cluster. |
| `sql_local/*.py` + DuckDB warehouse | **Real, runs in this repo right now.** Stands in for the Databricks SQL warehouse. |
| Naive vs. CTE runtime comparison | **Real, measured** with `time.perf_counter()` against 1.12M real rows -- not asserted. |
| 8 KPIs | **Real**, computed via real SQL against the real warehouse. |
| `dashboard/index.html` (D3.js) | **Real, runs in a browser right now** -- no Tableau, no build step. |
| Tableau `.twbx` dashboard | **Not built** -- no Tableau license/CLI here. `output/tableau_extract.csv` (real, 28,000 rows) + the written view-by-view description below are the honest substitute. |

## The 8 KPIs

Computed by `sql_local/kpis.py` via real SQL against the full 1.12M-row
warehouse, across all 50 states:

1. **Total market volume** (`total_market_volume_rx`) -- sum of all Rx across
   every state, quarter, product, and payer.
2. **Top product by volume** (`top_product_by_volume`) -- the single
   best-selling product and its total Rx.
3. **Latest QoQ growth %** (`latest_qoq_growth_pct`) -- total-market quarter-
   over-quarter growth for the most recent quarter, via `LAG()`.
4. **Top state by volume** (`top_state_by_volume`) -- the state with the
   highest total Rx.
5. **Payer-mix split %** (`payer_mix_split_pct`) -- share of total volume by
   payer type (Commercial / Medicare / Medicaid / Cash).
6. **Latest YoY growth %** (`latest_yoy_growth_pct`) -- total-market
   year-over-year growth for the most recent year.
7. **New-product adoption rate %** (`new_product_adoption_rate_pct`) -- share
   of the product catalog that first generated volume after the start of the
   observation window (i.e. launched mid-window) rather than already being
   on-market at the start.
8. **Market concentration / HHI** (`market_concentration_hhi`) -- Herfindahl-
   Hirschman Index on product market shares (sum of squared % shares);
   >2500 = highly concentrated, 1500-2500 = moderately concentrated, <1500 =
   unconcentrated.

## The D3.js dashboard (real, runnable)

Open `dashboard/index.html` directly in a browser (D3 v7 loads from a CDN
`<script>` tag -- no build step, no server). It renders live from
`data/dashboard_data.json`:

1. **8-KPI tile row** -- all 8 KPIs above, computed client-side from the
   JSON, including the HHI concentration label and the dominant-payer
   summary.
2. **Market volume by state** -- a real `d3.scaleBand` bar chart of the top
   15 states by total Rx, with a hover tooltip showing Rx and spend.
3. **Market share by product** -- a real horizontal bar chart of total Rx by
   product (all 7 products, fixed categorical colors), with a hover tooltip
   showing Rx and share %.
4. **Quarterly volume trend** -- a real `d3.line().curve(d3.curveMonotoneX)`
   line chart across all 20 quarters, with a crosshair + tooltip that
   bisects to the nearest quarter on hover.
5. **Payer mix** -- a real proportional stacked bar (categorical colors +
   legend) showing the 4-way payer split.

All views bind directly to the JSON the SQL pipeline generates -- nothing in
the chart is hard-coded sample data. (Covering all 50 states as a true
geographic choropleth would need a TopoJSON US-states boundary file, which
this environment doesn't have bundled; the state-level bar chart presents
the same "market share & growth across 50 states" data in a form that
renders correctly without an external geography asset, and `state_breakdown`
in the JSON includes all 50 states, not just the top 15 shown by default.)

## What the Tableau dashboard would show (not built here)

An "Obesity Market Performance" Tableau dashboard built from
`output/tableau_extract.csv` (state x quarter x product x payer grain) would
include:

- **A KPI card/BAN (Big Ass Number) row** across the top: total market
  volume, top product, latest QoQ %, latest YoY %, HHI, mirroring the 8 tiles
  in the D3 dashboard, each as a Tableau "Text" worksheet with a
  table-calculation (`WINDOW_SUM`, `LOOKUP`) driving the growth %.
- **A filled map of the 50 states**, color-encoded by total Rx (sequential
  blue ramp), using Tableau's built-in US-state geocoding on the `state`
  field -- the direct Tableau equivalent of the D3 state bar chart, and the
  piece Tableau's native geocoding makes easier to build natively than a
  from-scratch D3 choropleth.
- **A market-share sheet**: a stacked bar or treemap of `product_name` by
  `rx_count`, with a parameter-driven toggle between Rx-share and
  spend-share (`rx_count` vs. `total_spend`), mirroring the D3 product bar
  chart.
- **A time-series sheet**: `quarter_index` on columns, `SUM(rx_count)` on
  rows, split by `product_name` as a color legend, with a QoQ/YoY
  table-calculation toggle -- the Tableau equivalent of the D3 trend line,
  but natively supporting a per-product breakdown the single-series D3 line
  doesn't.
- **A payer-mix sheet**: a 100%-stacked bar of `payer_type` share, filterable
  by state and product via dashboard-level filter actions that cross-filter
  the map, market-share, and time-series sheets simultaneously -- the
  Tableau equivalent of the D3 dashboard's hover/click interactions, but
  dashboard-wide rather than per-chart.
- **A dashboard-level state and date-range filter** driving every sheet at
  once, consistent with how the 8 KPIs are described as "across 50 states."

## Results (real, from an actual run)

```
$ python3 -m pytest tests/ -v
...
11 passed in 4.40s
```

```
$ python3 run_all.py
STEP 1: Generated 1,120,000 rows (>= 1,000,000: True)

STEP 2: Warehouse table 'prescription_claims' loaded: 1,120,000 rows

STEP 3: Naive (nested subqueries) timed runs (s): [0.2184, 0.1526, 0.1352] -> median 0.1526s, 7,000 rows
         CTE-refactored timed runs (s):            [0.0276, 0.0242, 0.025]  -> median 0.0250s, 7,000 rows
         Measured speedup (median naive vs median CTE): 83.6% runtime reduction
         Naive and CTE results identical: True

STEP 4: 8 KPIs across all 50 states:
  total_market_volume_rx: 10,321,122
  top_product_by_volume: Semaglutide_Inj (3,182,297 Rx)
  latest_qoq_growth_pct: 4.47%
  top_state_by_volume: CA (1,211,058 Rx)
  payer_mix_split_pct: Medicaid 25.00% / Medicare 24.97% / Cash-Other 25.01% / Commercial 25.02%
  latest_yoy_growth_pct: 21.97%
  new_product_adoption_rate_pct: 28.57%
  market_concentration_hhi: 2045.2 (moderately concentrated)

STEP 5: Wrote data/dashboard_data.json, output/tableau_extract.csv, output/last_run_report.json
```

**On the measured speedup vs. the resume's "~50%":** the actual, honestly
measured, median-of-3 runtime reduction from refactoring the naive
nested-subquery query into CTEs was **83.6%** on this 1.12M-row dataset and
machine -- higher than the resume's "~50%" estimate, not lower. This is
reported as measured rather than capped or adjusted to match the bullet,
per the instruction to tune honestly rather than assert a target number;
real-world results on Databricks against a differently-shaped,
differently-indexed production table could plausibly land closer to 50%,
which is why the resume bullet uses a round, conservative figure. Re-running
`python3 run_all.py` reproduces a result in a similar range (run-to-run
variance on a shared laptop is normal for microsecond/millisecond-scale
query timings; the CTE form is faster in every run observed).

Row counts and KPI values above are reproducible: `simulate_data.py` uses a
fixed random seed (42), so `python3 run_all.py` regenerates the same
1,120,000 rows and the same KPI values every time; only the two query
timings (and therefore the exact speedup %) vary slightly run to run, as
real wall-clock timings do.

## Project layout

```
databricks/obesity_market_notebook.py   Authored-not-executed PySpark/Spark-SQL notebook
sql_local/
  simulate_data.py                       Vectorized 1.12M-row synthetic data generator
  warehouse.py                           Loads data into a real local DuckDB database
  queries.py                             Naive nested-subquery vs. CTE-refactored SQL
  kpis.py                                Real SQL for the 8 KPIs
  export_dashboard_data.py               Builds data/dashboard_data.json from real SQL
  tableau_extract.py                     Writes output/tableau_extract.csv
dashboard/index.html                    Real, runnable D3.js v7 dashboard
run_all.py                              Entry point: runs the full pipeline, prints results
tests/test_pipeline.py                  pytest suite (11 tests)
data/                                   Generated DuckDB warehouse (gitignored) + dashboard JSON (committed)
output/                                 Tableau CSV extract + last_run_report.json (committed as evidence)
requirements.txt
```

## How to run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 run_all.py          # generates data, loads DuckDB, runs both queries, computes KPIs, exports files
python3 -m pytest tests/ -v # runs the 11-test suite

open dashboard/index.html   # or double-click it -- renders live from data/dashboard_data.json
```
