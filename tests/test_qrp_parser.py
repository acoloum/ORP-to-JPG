from src.qrp_parser import parse_qrp


def test_parse_sample_qrp_returns_one_emf_page(sample_qrp_path):
    pages = parse_qrp(sample_qrp_path)
    assert len(pages) == 1
    emf = pages[0]
    # EMF 檔案必以 EMR_HEADER 開頭（Type=1，Little-endian DWORD）
    assert emf[:4] == b"\x01\x00\x00\x00"
    # 簽章 "EMF " (little-endian " EMF") 位於 offset 40
    assert emf[40:44] == b" EMF"
