"""
Writes a real, tidy CSV extract (output/tableau_extract.csv) shaped the way
Tableau wants it: one row per state x quarter x product x payer with the
measures Tableau would pivot via Measure Names/Values. Tableau itself is not
available in this environment (see README), so this extract -- plus the
written view-by-view dashboard description in the README -- is the honest
deliverable for that half of the resume bullet.
"""
from sql_local.warehouse import TABLE_NAME


def write_tableau_extract(con, path: str = "output/tableau_extract.csv"):
    # Aggregated to the state x quarter x product x payer grain (one row per
    # reporting cell, not one row per raw claim line) -- this is the grain a
    # Tableau extract would actually be built at for this dashboard, and it
    # keeps the extract a reasonable, reviewable, committable size instead of
    # the full 1M+ raw claim-line table.
    con.execute(f"""
        COPY (
            SELECT state, year, quarter_num, quarter_index, product_name, payer_type,
                   SUM(rx_count) AS rx_count,
                   ROUND(AVG(unit_price), 2) AS avg_unit_price,
                   ROUND(SUM(rx_count * unit_price), 2) AS total_spend
            FROM {TABLE_NAME}
            GROUP BY state, year, quarter_num, quarter_index, product_name, payer_type
            ORDER BY state, quarter_index, product_name, payer_type
        ) TO '{path}' (HEADER, DELIMITER ',')
    """)
