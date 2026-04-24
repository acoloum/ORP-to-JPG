from pathlib import Path
from src.converter import (
    OutputMode, ConflictPolicy, ConflictAction,
    ConflictDecision, FileResult, BatchSummary,
    resolve_output_path,
)


def test_enums_have_expected_values():
    assert {m.value for m in OutputMode} == {"same", "subfolder", "custom"}
    assert {p.value for p in ConflictPolicy} == {"ask", "overwrite", "skip", "rename"}
    assert {a.value for a in ConflictAction} == {"overwrite", "skip", "rename", "cancel"}


def test_file_result_fields():
    r = FileResult(source=Path("a.QRP"), output=None, status="failed", error="x")
    assert r.source == Path("a.QRP")
    assert r.status == "failed"


def test_resolve_output_same_folder():
    src = Path("C:/data/report.QRP")
    out = resolve_output_path(src, OutputMode.SAME_FOLDER, None)
    assert out == Path("C:/data/report.pdf")


def test_resolve_output_subfolder():
    src = Path("C:/data/report.QRP")
    out = resolve_output_path(src, OutputMode.SUBFOLDER, None)
    assert out == Path("C:/data/PDF/report.pdf")


def test_resolve_output_custom():
    src = Path("C:/data/report.QRP")
    custom = Path("D:/outputs")
    out = resolve_output_path(src, OutputMode.CUSTOM, custom)
    assert out == Path("D:/outputs/report.pdf")


def test_resolve_output_custom_requires_dir():
    import pytest
    with pytest.raises(ValueError):
        resolve_output_path(Path("a.QRP"), OutputMode.CUSTOM, None)
