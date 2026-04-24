from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

@pytest.fixture
def sample_qrp_path() -> Path:
    """範例 QRP 檔（單頁）。"""
    return PROJECT_ROOT / "範例" / "1-1.QRP"

@pytest.fixture
def sample_qrp_path_2() -> Path:
    return PROJECT_ROOT / "範例" / "2-1.QRP"
