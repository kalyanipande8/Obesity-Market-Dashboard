"""
Loads the simulated prescription-claims DataFrame into a real local DuckDB
database. DuckDB stands in for the Databricks/Spark SQL warehouse described
in databricks/obesity_market_notebook.py -- this is the genuinely executable
half of the project (see README).
"""
import duckdb
import pandas as pd

DB_PATH = "data/obesity_market.duckdb"
TABLE_NAME = "prescription_claims"


def load_warehouse(df: pd.DataFrame, db_path: str = DB_PATH) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(db_path)
    con.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    con.register("df_view", df)
    con.execute(f"CREATE TABLE {TABLE_NAME} AS SELECT * FROM df_view")
    con.unregister("df_view")
    con.execute(f"CREATE INDEX IF NOT EXISTS idx_state ON {TABLE_NAME}(state)")
    con.execute(f"CREATE INDEX IF NOT EXISTS idx_quarter ON {TABLE_NAME}(quarter_index)")
    return con


def row_count(con: duckdb.DuckDBPyConnection) -> int:
    return con.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
