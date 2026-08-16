from __future__ import annotations

import os
from pathlib import Path

import uvicorn


backend_root = Path(__file__).resolve().parents[1]
database_path = (backend_root / "data" / "playwright-e2e.db").resolve()
expected_parent = (backend_root / "data").resolve()

if database_path.parent != expected_parent or database_path.name != "playwright-e2e.db":
    raise RuntimeError("Unexpected browser-test database path.")

database_path.unlink(missing_ok=True)
os.environ["MASTERY_DB_PATH"] = str(database_path)

try:
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
finally:
    database_path.unlink(missing_ok=True)
