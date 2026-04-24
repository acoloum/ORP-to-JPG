import threading
from pathlib import Path
from src.converter import (
    OutputMode, ConflictPolicy, ConflictAction,
    ConflictDecision, FileResult, BatchSummary,
    resolve_output_path, resolve_conflict,
    convert_batch,
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
    assert out == Path("C:/data/report.jpg")


def test_resolve_output_subfolder():
    src = Path("C:/data/report.QRP")
    out = resolve_output_path(src, OutputMode.SUBFOLDER, None)
    assert out == Path("C:/data/JPG/report.jpg")


def test_resolve_output_custom():
    src = Path("C:/data/report.QRP")
    custom = Path("D:/outputs")
    out = resolve_output_path(src, OutputMode.CUSTOM, custom)
    assert out == Path("D:/outputs/report.jpg")


def test_resolve_output_custom_requires_dir():
    import pytest
    with pytest.raises(ValueError):
        resolve_output_path(Path("a.QRP"), OutputMode.CUSTOM, None)


def test_conflict_overwrite_returns_same_path(tmp_path):
    existing = tmp_path / "a.jpg"
    existing.write_bytes(b"x")
    target, action = resolve_conflict(existing, ConflictPolicy.OVERWRITE, None)
    assert target == existing
    assert action == ConflictAction.OVERWRITE


def test_conflict_skip(tmp_path):
    existing = tmp_path / "a.jpg"
    existing.write_bytes(b"x")
    target, action = resolve_conflict(existing, ConflictPolicy.SKIP, None)
    assert action == ConflictAction.SKIP


def test_conflict_rename_picks_next_number(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "a (1).jpg").write_bytes(b"x")
    target, action = resolve_conflict(
        tmp_path / "a.jpg", ConflictPolicy.RENAME, None,
    )
    assert target == tmp_path / "a (2).jpg"
    assert action == ConflictAction.RENAME


def test_conflict_no_existing_file(tmp_path):
    target = tmp_path / "fresh.jpg"
    result, action = resolve_conflict(target, ConflictPolicy.ASK, None)
    # 檔案不存在時不觸發 callback，直接用原路徑
    assert result == target
    assert action == ConflictAction.OVERWRITE


def test_conflict_ask_invokes_callback(tmp_path):
    existing = tmp_path / "a.jpg"
    existing.write_bytes(b"x")
    calls = []

    def cb(path: Path) -> ConflictDecision:
        calls.append(path)
        return ConflictDecision(action=ConflictAction.SKIP)

    _target, action = resolve_conflict(existing, ConflictPolicy.ASK, cb)
    assert calls == [existing]
    assert action == ConflictAction.SKIP


def test_batch_continues_after_single_failure(tmp_path, monkeypatch):
    # 造 3 個 QRP 假檔：第 2 個會失敗
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    files = []
    for i in range(3):
        f = src_dir / f"{i}.QRP"
        f.write_bytes(b"stub")
        files.append(f)

    def fake_parse(path):
        if "1.QRP" in str(path):
            from src.qrp_parser import QrpParseError
            raise QrpParseError("壞檔")
        return [b"emf-stub"]

    def fake_render(pages, output_path, dpi=200, quality=95):
        p = Path(output_path).with_suffix(".jpg")
        p.write_bytes(b"\xff\xd8\xff\xe0fake")
        return [p]

    monkeypatch.setattr("src.converter.parse_qrp", fake_parse)
    monkeypatch.setattr("src.converter.render_jpg", fake_render)

    summary = convert_batch(
        sources=files,
        output_mode=OutputMode.SAME_FOLDER,
        custom_output_dir=None,
        conflict_policy=ConflictPolicy.OVERWRITE,
        conflict_callback=None,
        progress_callback=None,
        cancel_event=None,
    )
    assert summary.success_count == 2
    assert summary.failed_count == 1
    assert not summary.cancelled


def test_batch_honors_cancel_event(tmp_path, monkeypatch):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    files = [src_dir / f"{i}.QRP" for i in range(5)]
    for f in files:
        f.write_bytes(b"stub")

    cancel = threading.Event()
    processed = []

    def fake_parse(path):
        processed.append(path)
        if len(processed) == 2:
            cancel.set()  # 第 2 檔處理完後取消
        return [b"emf"]

    def fake_render(pages, output_path, dpi=200, quality=95):
        p = Path(output_path).with_suffix(".jpg")
        p.write_bytes(b"\xff\xd8\xff\xe0fake")
        return [p]

    monkeypatch.setattr("src.converter.parse_qrp", fake_parse)
    monkeypatch.setattr("src.converter.render_jpg", fake_render)

    summary = convert_batch(
        sources=files,
        output_mode=OutputMode.SAME_FOLDER,
        custom_output_dir=None,
        conflict_policy=ConflictPolicy.OVERWRITE,
        conflict_callback=None,
        progress_callback=None,
        cancel_event=cancel,
    )
    assert summary.cancelled
    assert len(processed) == 2
    assert summary.success_count == 2


def test_batch_emits_progress_events(tmp_path, monkeypatch):
    f = tmp_path / "only.QRP"
    f.write_bytes(b"stub")
    monkeypatch.setattr("src.converter.parse_qrp", lambda p: [b"emf"])

    def fake_render(pages, output_path, dpi=200, quality=95):
        p = Path(output_path).with_suffix(".jpg")
        p.write_bytes(b"\xff\xd8\xff\xe0fake")
        return [p]

    monkeypatch.setattr("src.converter.render_jpg", fake_render)

    events = []
    convert_batch(
        sources=[f],
        output_mode=OutputMode.SAME_FOLDER,
        custom_output_dir=None,
        conflict_policy=ConflictPolicy.OVERWRITE,
        conflict_callback=None,
        progress_callback=events.append,
        cancel_event=None,
    )
    kinds = [e.kind for e in events]
    assert kinds == ["batch_start", "file_start", "file_done", "batch_end"]
