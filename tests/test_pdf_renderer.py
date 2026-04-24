import pytest
from src.pdf_renderer import is_pdf_printer_available, PDF_PRINTER_NAME
from src.pdf_renderer import render_pdf
from src.qrp_parser import parse_qrp


def test_pdf_printer_detection_returns_bool():
    result = is_pdf_printer_available()
    assert isinstance(result, bool)


def test_pdf_printer_name_constant():
    assert PDF_PRINTER_NAME == "Microsoft Print to PDF"


@pytest.mark.skipif(
    not is_pdf_printer_available(),
    reason="Microsoft Print to PDF 未安裝",
)
def test_render_sample_qrp_to_pdf(sample_qrp_path, tmp_path):
    pages = parse_qrp(sample_qrp_path)
    output = tmp_path / "out.pdf"
    render_pdf(pages, output)
    assert output.exists()
    assert output.stat().st_size > 0
    assert output.read_bytes()[:5] == b"%PDF-"
