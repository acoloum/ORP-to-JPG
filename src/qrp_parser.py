"""QRP 解析器：從 Delphi QuickReport 檔抽取內嵌的 EMF 頁面。"""
from __future__ import annotations
from pathlib import Path
import struct

EMF_SIGNATURE = b" EMF"  # 位於 EMR_HEADER 的 offset 40
SIG_OFFSET = 40
NBYTES_OFFSET = 48       # EMR_HEADER.nBytes 欄位（DWORD LE）
TYPE_OFFSET = 0          # EMR_HEADER.iType，應為 1


class QrpParseError(Exception):
    """QRP 檔案無法解析。"""


def parse_qrp(path: str | Path) -> list[bytes]:
    """解析 QRP 檔，回傳每頁 EMF 的 bytes 清單。

    作法：掃描所有 EMF 簽章，依 EMR_HEADER.nBytes 切出完整 EMF 區塊。
    """
    data = Path(path).read_bytes()
    pages: list[bytes] = []
    search_from = 0
    while True:
        idx = data.find(EMF_SIGNATURE, search_from)
        if idx < 0:
            break
        start = idx - SIG_OFFSET
        search_from = idx + len(EMF_SIGNATURE)
        if start < 0:
            continue
        (itype,) = struct.unpack_from("<I", data, start + TYPE_OFFSET)
        if itype != 1:
            continue
        (nbytes,) = struct.unpack_from("<I", data, start + NBYTES_OFFSET)
        if nbytes == 0 or start + nbytes > len(data):
            raise QrpParseError("EMF 頁面資料損壞或截斷")
        pages.append(data[start : start + nbytes])
    if not pages:
        raise QrpParseError("檔案不包含 EMF 頁面，可能不是有效的 QRP 檔")
    return pages
