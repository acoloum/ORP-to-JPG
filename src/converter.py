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
