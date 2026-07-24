"""
History Tracker
----------------
Stores each quality-check run's score in a local SQLite database so you
can chart data quality drift over time (a core "monitoring tool" feature,
not just a one-shot checker).
"""

import sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = "quality_history.db"


def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            dataset_name TEXT,
            row_count INTEGER,
            completeness_score REAL,
            overall_score REAL,
            quality_label TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_run(dataset_name, row_count, completeness_score, overall_score, quality_label, db_path=DB_PATH):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO quality_runs
           (timestamp, dataset_name, row_count, completeness_score, overall_score, quality_label)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            dataset_name,
            row_count,
            completeness_score,
            overall_score,
            quality_label,
        ),
    )
    conn.commit()
    conn.close()


def get_history(db_path=DB_PATH, limit=100):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        f"SELECT * FROM quality_runs ORDER BY id DESC LIMIT {limit}", conn
    )
    conn.close()
    return df.iloc[::-1].reset_index(drop=True)  # chronological order


def clear_history(db_path=DB_PATH):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM quality_runs")
    conn.commit()
    conn.close()
