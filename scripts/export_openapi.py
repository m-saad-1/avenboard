"""Run from repository root: python scripts/export_openapi.py."""

import json, sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "app"))
from boards.main import app

(root / "docs/openapi.json").write_text(
    json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8"
)
