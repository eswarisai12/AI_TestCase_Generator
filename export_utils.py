from __future__ import annotations

from typing import Any

import pandas as pd

EXPORT_COLUMNS = [
    "id",
    "scenario_type",
    "title",
    "preconditions",
    "steps",
    "test_data",
    "expected_result",
    "priority",
    "assumptions",
]


def test_cases_to_csv(test_cases: list[dict[str, Any]]) -> str:
    dataframe = pd.DataFrame(test_cases, columns=EXPORT_COLUMNS)
    return dataframe.to_csv(index=False)