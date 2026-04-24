import pytest

from src.qrp_parser import parse_qrp, QrpParseError


def test_parse_sample_qrp_returns_one_emf_page(sample_qrp_path):
    pages = parse_qrp(sample_qrp_path)
    assert len(pages) == 1
    emf = pages[0]
    # EMF 檔案必以 EMR_HEADER 開頭（Type=1，Little-endian DWORD）
    assert emf[:4] == b"\x01\x00\x00\x00"
    # 簽章 "EMF " (little-endian " EMF") 位於 offset 40
    assert emf[40:44] == b" EMF"


def test_parse_handles_signature_near_eof(tmp_path):
    """若 EMF 簽章出現在檔尾，但無法容納完整 header，應視為 false positive 略過。"""
    # 42 bytes 填充 + " EMF" 簽章（共 46 bytes），後面不足容納 nBytes 欄位
    fake = tmp_path / "near_eof.QRP"
    fake.write_bytes(b"\x00" * 42 + b" EMF")
    with pytest.raises(QrpParseError, match="不包含 EMF"):
        parse_qrp(fake)


def test_parse_raises_when_no_emf(tmp_path):
    fake = tmp_path / "bad.QRP"
    fake.write_bytes(b"not a qrp file" * 100)
    with pytest.raises(QrpParseError, match="不包含 EMF"):
        parse_qrp(fake)


def test_parse_raises_when_truncated(tmp_path, sample_qrp_path):
    # 讀入範例，找到 EMF 起點，把 nbytes 改到超出檔尾
    data = bytearray(sample_qrp_path.read_bytes())
    idx = data.find(b" EMF")
    start = idx - 40
    # 將 nbytes 改成超大值
    import struct
    struct.pack_into("<I", data, start + 48, 9_999_999)
    broken = tmp_path / "broken.QRP"
    broken.write_bytes(bytes(data))
    with pytest.raises(QrpParseError, match="損壞或截斷"):
        parse_qrp(broken)
