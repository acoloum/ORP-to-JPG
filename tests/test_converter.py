from pathlib import Path
from src.converter import (
    OutputMode, ConflictPolicy, ConflictAction,
    ConflictDecision, FileResult, BatchSummary,
)


def test_enums_have_expected_values():
    assert {m.value for m in OutputMode} == {"same", "subfolder", "custom"}
    assert {p.value for p in ConflictPolicy} == {"ask", "overwrite", "skip", "rename"}
    assert {a.value for a in ConflictAction} == {"overwrite", "skip", "rename", "cancel"}


def test_file_result_fields():
    r = FileResult(source=Path("a.QRP"), output=None, status="failed", error="x")
    assert r.source == Path("a.QRP")
    assert r.status == "failed"
