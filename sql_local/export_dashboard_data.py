"""
Builds data/dashboard_data.json -- the real data file the D3.js dashboard
(dashboard/index.html) binds to. Every number comes from a real SQL query
against the DuckDB warehouse; nothing here is hand-written sample data.
"""
import json
from sql_local.warehouse import TABLE_NAME


def build_dashboard_data(con, kpis: dict) -> dict:
    state_breakdown = con.execute(f"""
        SELECT state, SUM(rx_count) AS total_rx, SUM(rx_count * unit_price) AS total_spend
        FROM {TABLE_NAME}
        GROUP BY state
        ORDER BY total_rx DESC
    """).fetchdf()

    product_breakdown = con.execute(f"""
        SELECT product_name, SUM(rx_count) AS total_rx
        FROM {TABLE_NAME}
        GROUP BY product_name
        ORDER BY total_rx DESC
    """).fetchdf()

    quarterly_trend = con.execute(f"""
        SELECT year, quarter_num, quarter_index, SUM(rx_count) AS total_rx
        FROM {TABLE_NAME}
        GROUP BY year, quarter_num, quarter_index
        ORDER BY quarter_index
    """).fetchdf()

    payer_mix = con.execute(f"""
        SELECT payer_type, SUM(rx_count) AS total_rx
        FROM {TABLE_NAME}
        GROUP BY payer_type
        ORDER BY total_rx DESC
    """).fetchdf()

    data = {
        "kpis": kpis,
        "state_breakdown": state_breakdown.to_dict(orient="records"),
        "product_breakdown": product_breakdown.to_dict(orient="records"),
        "quarterly_trend": [
            {
                "label": f"{int(r.year)}Q{int(r.quarter_num)}",
                "quarter_index": int(r.quarter_index),
                "total_rx": int(r.total_rx),
            }
            for r in quarterly_trend.itertuples()
        ],
        "payer_mix": payer_mix.to_dict(orient="records"),
    }
    return data


def write_dashboard_json(data: dict, path: str = "data/dashboard_data.json"):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
