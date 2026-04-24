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
