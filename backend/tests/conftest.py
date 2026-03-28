from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from investigation_logger import logger  # noqa: E402


@pytest.fixture(autouse=True)
def isolate_app_db(tmp_path, monkeypatch):
    test_db = tmp_path / "simwork-test.db"
    monkeypatch.setenv("SIMWORK_DB_PATH", str(test_db))
    monkeypatch.setattr(logger, "DB_PATH", test_db)
    yield
