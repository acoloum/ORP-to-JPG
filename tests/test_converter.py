from pathlib import Path
from src.converter import (
    OutputMode, ConflictPolicy, ConflictAction,
    ConflictDecision, FileResult, BatchSummary,
    resolve_output_path, resolve_conflict,
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


def test_conflict_overwrite_returns_same_path(tmp_path):
    existing = tmp_path / "a.pdf"
    existing.write_bytes(b"x")
    target, action = resolve_conflict(existing, ConflictPolicy.OVERWRITE, None)
    assert target == existing
    assert action == ConflictAction.OVERWRITE


def test_conflict_skip(tmp_path):
    existing = tmp_path / "a.pdf"
    existing.write_bytes(b"x")
    target, action = resolve_conflict(existing, ConflictPolicy.SKIP, None)
    assert action == ConflictAction.SKIP


def test_conflict_rename_picks_next_number(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"x")
    (tmp_path / "a (1).pdf").write_bytes(b"x")
    target, action = resolve_conflict(
        tmp_path / "a.pdf", ConflictPolicy.RENAME, None,
    )
    assert target == tmp_path / "a (2).pdf"
    assert action == ConflictAction.RENAME


def test_conflict_no_existing_file(tmp_path):
    target = tmp_path / "fresh.pdf"
    result, action = resolve_conflict(target, ConflictPolicy.ASK, None)
    # 檔案不存在時不觸發 callback，直接用原路徑
    assert result == target
    assert action == ConflictAction.OVERWRITE


def test_conflict_ask_invokes_callback(tmp_path):
    existing = tmp_path / "a.pdf"
    existing.write_bytes(b"x")
    calls = []

    def cb(path: Path) -> ConflictDecision:
        calls.append(path)
        return ConflictDecision(action=ConflictAction.SKIP)

    _target, action = resolve_conflict(existing, ConflictPolicy.ASK, cb)
    assert calls == [existing]
    assert action == ConflictAction.SKIP
