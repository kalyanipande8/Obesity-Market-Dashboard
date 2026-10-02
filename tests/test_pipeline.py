"""
pytest suite against the real local pipeline (synthetic data generation,
DuckDB warehouse, naive vs CTE SQL, KPIs, dashboard/Tableau exports).
"""
import json
import os

import pytest

from sql_local.simulate_data import simulate, STATES
from sql_local.warehouse import load_warehouse, row_count, TABLE_NAME
from sql_local.queries import naive_market_share_growth, cte_market_share_growth
from sql_local.kpis import compute_kpis
from sql_local.export_dashboard_data import build_dashboard_data, write_dashboard_json
from sql_local.tableau_extract import write_tableau_extract

import time


@pytest.fixture(scope="module")
def df():
    return simulate()


@pytest.fixture(scope="module")
def con(df, tmp_path_factory):
    db_path = str(tmp_path_factory.mktemp("db") / "test_warehouse.duckdb")
    connection = load_warehouse(df, db_path=db_path)
    yield connection
    connection.close()


def test_simulated_data_meets_1m_row_requirement(df):
    assert len(df) >= 1_000_000


def test_simulated_data_covers_50_states(df):
    assert df["state"].nunique() == 50
    assert set(df["state"].unique()) == set(STATES)


def test_simulated_data_has_expected_columns(df):
    expected = {
        "state", "year", "quarter_num", "quarter_index", "product_name",
        "payer_type", "rx_count", "unit_price", "payer_mix_weight",
        "payer_share_within_product", "claim_id",
    }
    assert expected.issubset(set(df.columns))


def test_simulated_data_no_negative_values(df):
    assert (df["rx_count"] >= 0).all()
    assert (df["unit_price"] > 0).all()


def test_warehouse_loads_all_rows(con, df):
    assert row_count(con) == len(df)


def test_naive_and_cte_queries_produce_identical_results(con):
    naive = naive_market_share_growth(con)
    cte = cte_market_share_growth(con)

    naive_sorted = naive.sort_values(["state", "year", "quarter_num", "product_name"]).reset_index(drop=True)
    cte_sorted = cte.sort_values(["state", "year", "quarter_num", "product_name"]).reset_index(drop=True)

    assert len(naive_sorted) == len(cte_sorted)
    assert naive_sorted["product_rx"].equals(cte_sorted["product_rx"])
    assert naive_sorted["total_rx"].equals(cte_sorted["total_rx"])
    assert naive_sorted["prev_quarter_rx"].equals(cte_sorted["prev_quarter_rx"])


def test_cte_query_is_measurably_faster_than_naive(con):
    # Warm up buffer pool equally before timing, same methodology as run_all.py.
    con.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchall()

    naive_times = []
    for _ in range(3):
        t0 = time.perf_counter()
        naive_market_share_growth(con)
        naive_times.append(time.perf_counter() - t0)

    cte_times = []
    for _ in range(3):
        t0 = time.perf_counter()
        cte_market_share_growth(con)
        cte_times.append(time.perf_counter() - t0)

    naive_median = sorted(naive_times)[1]
    cte_median = sorted(cte_times)[1]

    assert cte_median < naive_median, (
        f"Expected CTE query ({cte_median:.4f}s) to be faster than naive "
        f"query ({naive_median:.4f}s)"
    )


def test_all_8_kpis_computed_and_sane(con):
    kpis = compute_kpis(con)

    required = {
        "total_market_volume_rx", "top_product_by_volume", "latest_qoq_growth_pct",
        "top_state_by_volume", "payer_mix_split_pct", "latest_yoy_growth_pct",
        "new_product_adoption_rate_pct", "market_concentration_hhi",
    }
    assert required.issubset(set(kpis.keys())), f"Missing KPIs: {required - set(kpis.keys())}"
    assert len(required) == 8

    assert kpis["total_market_volume_rx"] > 0
    assert kpis["top_product_by_volume"]["total_rx"] > 0
    assert kpis["top_state_by_volume"]["total_rx"] > 0
    assert kpis["states_covered"] == 50

    payer_total_pct = sum(kpis["payer_mix_split_pct"].values())
    assert 99.0 <= payer_total_pct <= 101.0

    assert 0 <= kpis["market_concentration_hhi"] <= 10000
    assert 0 <= kpis["new_product_adoption_rate_pct"] <= 100


def test_dashboard_json_written_and_shaped_correctly(con, tmp_path):
    kpis = compute_kpis(con)
    data = build_dashboard_data(con, kpis)
    out_path = tmp_path / "dashboard_data.json"
    write_dashboard_json(data, path=str(out_path))

    assert out_path.exists()
    with open(out_path) as f:
        loaded = json.load(f)

    assert "kpis" in loaded
    assert "state_breakdown" in loaded and len(loaded["state_breakdown"]) == 50
    assert "product_breakdown" in loaded and len(loaded["product_breakdown"]) > 0
    assert "quarterly_trend" in loaded and len(loaded["quarterly_trend"]) == 20
    assert "payer_mix" in loaded and len(loaded["payer_mix"]) == 4

    first_state = loaded["state_breakdown"][0]
    assert {"state", "total_rx", "total_spend"}.issubset(first_state.keys())


def test_tableau_extract_written(con, tmp_path):
    out_path = tmp_path / "tableau_extract.csv"
    write_tableau_extract(con, path=str(out_path))
    assert out_path.exists()

    with open(out_path) as f:
        header = f.readline().strip().split(",")
    expected_cols = {
        "state", "year", "quarter_num", "quarter_index", "product_name",
        "payer_type", "rx_count", "avg_unit_price", "total_spend",
    }
    assert expected_cols.issubset(set(header))


def test_dashboard_html_exists_and_references_real_data_file():
    html_path = os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html")
    assert os.path.exists(html_path)
    with open(html_path) as f:
        content = f.read()
    assert "d3.json" in content
    assert "dashboard_data.json" in content
