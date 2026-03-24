from __future__ import annotations

import pandas as pd

from agent_router.sandbox import execute_pandas_code, validate_pandas_code


def test_validate_pandas_code_allows_numpy_and_pandas_imports():
    valid, error = validate_pandas_code(
        "import pandas as pd\nimport numpy as np\nresult = pd.DataFrame({'x': np.array([1, 2])})"
    )

    assert valid is True
    assert error is None


def test_validate_pandas_code_blocks_non_allowlisted_imports():
    valid, error = validate_pandas_code(
        "import os\nresult = df"
    )

    assert valid is False
    assert error == "Forbidden import: os"


def test_execute_pandas_code_blocks_filesystem_escape_patterns():
    result = execute_pandas_code(
        "result = df\nopen('/tmp/escape.txt', 'w')",
        df=pd.DataFrame({"value": [1]}),
    )

    assert result["ok"] is False
    assert "open()" in result["error"]
