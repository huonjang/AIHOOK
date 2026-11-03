
import sqlite3
from app.database import BACKEND_DIR

db_path = BACKEND_DIR / "aihook.db"

print("Database path:", db_path.resolve())
print("File exists:", db_path.exists())

with sqlite3.connect(str(db_path)) as conn:
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    print("\nTables:", tables)

    for table in ("invoices", "businesses", "invoice_analyses"):
        print(f"\n{table.upper()}:")
        print(conn.execute(f"PRAGMA table_info({table})").fetchall())
