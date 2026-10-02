"""
Computes the 8 real KPIs for the obesity-therapy market dashboard, all via
real SQL against the local DuckDB warehouse (1M+ rows), across all 50 states.
"""
from sql_local.warehouse import TABLE_NAME


def compute_kpis(con) -> dict:
    kpis = {}

    kpis["total_market_volume_rx"] = con.execute(
        f"SELECT SUM(rx_count) FROM {TABLE_NAME}"
    ).fetchone()[0]

    top_product = con.execute(f"""
        SELECT product_name, SUM(rx_count) AS total_rx
        FROM {TABLE_NAME}
        GROUP BY product_name
        ORDER BY total_rx DESC
        LIMIT 1
    """).fetchone()
    kpis["top_product_by_volume"] = {"product": top_product[0], "total_rx": int(top_product[1])}

    qoq = con.execute(f"""
        WITH q AS (
            SELECT quarter_index, SUM(rx_count) AS total_rx
            FROM {TABLE_NAME}
            GROUP BY quarter_index
        ),
        g AS (
            SELECT quarter_index, total_rx,
                   LAG(total_rx) OVER (ORDER BY quarter_index) AS prev_rx
            FROM q
        )
        SELECT quarter_index, total_rx, prev_rx,
               (total_rx - prev_rx) / prev_rx AS qoq_pct
        FROM g
        ORDER BY quarter_index DESC
        LIMIT 1
    """).fetchone()
    kpis["latest_qoq_growth_pct"] = round(float(qoq[3]) * 100, 2) if qoq[3] is not None else None

    state_leader = con.execute(f"""
        SELECT state, SUM(rx_count) AS total_rx
        FROM {TABLE_NAME}
        GROUP BY state
        ORDER BY total_rx DESC
        LIMIT 1
    """).fetchone()
    kpis["top_state_by_volume"] = {"state": state_leader[0], "total_rx": int(state_leader[1])}

    payer_mix = con.execute(f"""
        SELECT payer_type, SUM(rx_count) AS total_rx
        FROM {TABLE_NAME}
        GROUP BY payer_type
    """).fetchdf()
    total_payer_rx = payer_mix["total_rx"].sum()
    kpis["payer_mix_split_pct"] = {
        row["payer_type"]: round(float(row["total_rx"]) / total_payer_rx * 100, 2)
        for _, row in payer_mix.iterrows()
    }

    yoy = con.execute(f"""
        WITH y AS (
            SELECT year, SUM(rx_count) AS total_rx
            FROM {TABLE_NAME}
            GROUP BY year
        ),
        g AS (
            SELECT year, total_rx,
                   LAG(total_rx) OVER (ORDER BY year) AS prev_rx
            FROM y
        )
        SELECT year, total_rx, prev_rx,
               (total_rx - prev_rx) / prev_rx AS yoy_pct
        FROM g
        ORDER BY year DESC
        LIMIT 1
    """).fetchone()
    kpis["latest_yoy_growth_pct"] = round(float(yoy[3]) * 100, 2) if yoy[3] is not None else None

    # "New-product adoption rate": share of products in the catalog that first
    # generated real prescription volume after the start of the observation
    # window (i.e. launched mid-window rather than already on-market at the
    # start), as a fraction of all products ever observed with volume > 0.
    adoption = con.execute(f"""
        WITH launch AS (
            SELECT product_name, MIN(quarter_index) AS first_active_quarter
            FROM {TABLE_NAME}
            WHERE rx_count > 0
            GROUP BY product_name
        )
        SELECT
            SUM(CASE WHEN first_active_quarter > 0 THEN 1 ELSE 0 END) AS new_products,
            COUNT(*) AS total_products
        FROM launch
    """).fetchone()
    kpis["new_product_adoption_rate_pct"] = round(adoption[0] / adoption[1] * 100, 2)

    hhi = con.execute(f"""
        WITH product_totals AS (
            SELECT product_name, SUM(rx_count) AS total_rx
            FROM {TABLE_NAME}
            GROUP BY product_name
        ),
        shares AS (
            SELECT total_rx / (SELECT SUM(total_rx) FROM product_totals) AS share
            FROM product_totals
        )
        SELECT SUM(POWER(share * 100, 2)) FROM shares
    """).fetchone()[0]
    kpis["market_concentration_hhi"] = round(float(hhi), 1)

    states_covered = con.execute(f"SELECT COUNT(DISTINCT state) FROM {TABLE_NAME}").fetchone()[0]
    kpis["states_covered"] = states_covered

    return kpis
