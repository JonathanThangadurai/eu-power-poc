import json
import os
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    return json.loads((FIXTURES / filename).read_text())


@pytest.fixture(autouse=True, scope="session")
def _test_env():
    os.environ.setdefault("DISABLE_SCHEDULER", "true")
