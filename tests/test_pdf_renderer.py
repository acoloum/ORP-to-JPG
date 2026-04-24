from src.pdf_renderer import is_pdf_printer_available, PDF_PRINTER_NAME


def test_pdf_printer_detection_returns_bool():
    result = is_pdf_printer_available()
    assert isinstance(result, bool)


def test_pdf_printer_name_constant():
    assert PDF_PRINTER_NAME == "Microsoft Print to PDF"
