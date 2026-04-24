"""批次轉檔協調層。"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Literal
import threading


class OutputMode(Enum):
    SAME_FOLDER = "same"
    SUBFOLDER = "subfolder"
    CUSTOM = "custom"


class ConflictPolicy(Enum):
    ASK = "ask"
    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"


class ConflictAction(Enum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"
    CANCEL = "cancel"


@dataclass
class ConflictDecision:
    action: ConflictAction
    apply_to_all: bool = False


@dataclass
class FileResult:
    source: Path
    output: Path | None
    status: Literal["success", "skipped", "failed"]
    error: str | None = None


@dataclass
class BatchSummary:
    results: list[FileResult] = field(default_factory=list)
    cancelled: bool = False

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.status == "success")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")


ConflictCallback = Callable[[Path], ConflictDecision]
ProgressCallback = Callable[["ProgressEvent"], None]


@dataclass
class ProgressEvent:
    kind: Literal["batch_start", "file_start", "file_done", "batch_end"]
    index: int = 0
    total: int = 0
    source: Path | None = None
    result: FileResult | None = None
    summary: BatchSummary | None = None


def resolve_output_path(
    source: Path,
    mode: OutputMode,
    custom_dir: Path | None,
) -> Path:
    """依模式決定 PDF 輸出路徑（不做衝突檢查，不建資料夾）。"""
    stem = source.stem + ".pdf"
    if mode == OutputMode.SAME_FOLDER:
        return source.with_name(stem)
    if mode == OutputMode.SUBFOLDER:
        return source.parent / "PDF" / stem
    if mode == OutputMode.CUSTOM:
        if custom_dir is None:
            raise ValueError("自訂輸出模式必須提供 custom_dir")
        return Path(custom_dir) / stem
    raise ValueError(f"未知的 OutputMode: {mode}")


def _next_available_rename(path: Path) -> Path:
    """找到下一個 `<stem> (N)<suffix>` 可用檔名。"""
    n = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def resolve_conflict(
    target: Path,
    policy: ConflictPolicy,
    callback: ConflictCallback | None,
) -> tuple[Path, ConflictAction]:
    """根據策略決定最終輸出路徑與動作。

    回傳 (最終路徑, 動作)；若動作為 SKIP 或 CANCEL，呼叫端應跳過寫入。
    """
    if not target.exists():
        return target, ConflictAction.OVERWRITE
    if policy == ConflictPolicy.OVERWRITE:
        return target, ConflictAction.OVERWRITE
    if policy == ConflictPolicy.SKIP:
        return target, ConflictAction.SKIP
    if policy == ConflictPolicy.RENAME:
        return _next_available_rename(target), ConflictAction.RENAME
    # ASK
    if callback is None:
        raise ValueError("ConflictPolicy.ASK 需要提供 callback")
    decision = callback(target)
    if decision.action == ConflictAction.RENAME:
        return _next_available_rename(target), ConflictAction.RENAME
    return target, decision.action
