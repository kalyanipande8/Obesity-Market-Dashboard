"""
End-to-end pipeline runner:
  1. Simulate 1M+ synthetic prescription-claims rows (vectorized).
  2. Load them into a real local DuckDB warehouse.
  3. Run the naive nested-subquery market-share/growth query, timed.
  4. Run the CTE-refactored equivalent query, timed.
  5. Verify both produce identical results and report the real % speedup.
  6. Compute the 8 KPIs via real SQL.
  7. Export dashboard JSON (for the D3 dashboard) and the Tableau CSV extract.
"""
import json
import time

from sql_local.simulate_data import simulate
from sql_local.warehouse import load_warehouse, row_count, TABLE_NAME
from sql_local.queries import naive_market_share_growth, cte_market_share_growth
from sql_local.kpis import compute_kpis
from sql_local.export_dashboard_data import build_dashboard_data, write_dashboard_json
from sql_local.tableau_extract import write_tableau_extract

import os

os.makedirs("data", exist_ok=True)
os.makedirs("output", exist_ok=True)


def main():
    print("=" * 70)
    print("STEP 1: Simulating synthetic obesity-therapy prescription data")
    print("=" * 70)
    df = simulate()
    print(f"Generated {len(df):,} rows (>= 1,000,000: {len(df) >= 1_000_000})")

    print("\n" + "=" * 70)
    print("STEP 2: Loading into local DuckDB warehouse (Databricks stand-in)")
    print("=" * 70)
    con = load_warehouse(df)
    n_rows = row_count(con)
    print(f"Warehouse table '{TABLE_NAME}' loaded: {n_rows:,} rows")

    print("\n" + "=" * 70)
    print("STEP 3: Timing naive nested-subquery vs CTE-refactored SQL")
    print("=" * 70)
    print("Methodology: 1 cold warm-up query (not timed) to normalize buffer-pool")
    print("state, then 3 timed repetitions each with time.perf_counter(); the")
    print("median of the 3 timed runs is reported for each query form.")

    # Warm up the buffer pool/cache equally before timing either query form.
    con.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchall()

    naive_times = []
    naive_result = None
    for _ in range(3):
        t0 = time.perf_counter()
        naive_result = naive_market_share_growth(con)
        naive_times.append(time.perf_counter() - t0)

    cte_times = []
    cte_result = None
    for _ in range(3):
        t0 = time.perf_counter()
        cte_result = cte_market_share_growth(con)
        cte_times.append(time.perf_counter() - t0)

    naive_time = sorted(naive_times)[1]  # median of 3
    cte_time = sorted(cte_times)[1]

    print(f"Naive (nested subqueries) timed runs (s): {[round(t, 4) for t in naive_times]} -> median {naive_time:.4f}s, {len(naive_result):,} rows")
    print(f"CTE-refactored timed runs (s):            {[round(t, 4) for t in cte_times]} -> median {cte_time:.4f}s, {len(cte_result):,} rows")

    speedup_pct = (naive_time - cte_time) / naive_time * 100
    print(f"\nMeasured speedup (median naive vs median CTE): {speedup_pct:.1f}% runtime reduction")

    # Correctness check: same (state, year, quarter, product) keys map to identical
    # product_rx, total_rx, and prev_quarter_rx values in both query forms.
    naive_sorted = naive_result.sort_values(["state", "year", "quarter_num", "product_name"]).reset_index(drop=True)
    cte_sorted = cte_result.sort_values(["state", "year", "quarter_num", "product_name"]).reset_index(drop=True)
    rows_match = (
        len(naive_sorted) == len(cte_sorted)
        and naive_sorted["product_rx"].equals(cte_sorted["product_rx"])
        and naive_sorted["total_rx"].equals(cte_sorted["total_rx"])
        and naive_sorted["prev_quarter_rx"].equals(cte_sorted["prev_quarter_rx"])
    )
    print(f"Naive and CTE results identical on (state, year, quarter, product) -> (product_rx, total_rx, prev_quarter_rx): {rows_match}")

    print("\n" + "=" * 70)
    print("STEP 4: Computing 8 KPIs across all 50 states")
    print("=" * 70)
    kpis = compute_kpis(con)
    for k, v in kpis.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 70)
    print("STEP 5: Exporting dashboard JSON + Tableau CSV extract")
    print("=" * 70)
    dash_data = build_dashboard_data(con, kpis)
    write_dashboard_json(dash_data, "data/dashboard_data.json")
    print("Wrote data/dashboard_data.json")

    write_tableau_extract(con, "output/tableau_extract.csv")
    print("Wrote output/tableau_extract.csv")

    report = {
        "rows_generated": int(len(df)),
        "warehouse_rows": int(n_rows),
        "naive_query_seconds": naive_time,
        "cte_query_seconds": cte_time,
        "speedup_pct": speedup_pct,
        "results_identical": bool(rows_match),
        "kpis": kpis,
    }
    with open("output/last_run_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    print("\nWrote output/last_run_report.json")

    con.close()


if __name__ == "__main__":
    main()
