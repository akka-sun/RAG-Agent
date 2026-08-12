import base64

from app.evaluation.benchmark_runner import image_to_pdf


def test_image_to_pdf_wraps_png_as_single_page_pdf() -> None:
    # 1x1 RGB PNG, kept inline so this test never downloads a dataset.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )

    pdf = image_to_pdf(png)

    assert pdf.startswith(b"%PDF-1.4")
    assert b"/Subtype /Image" in pdf
    assert b"/MediaBox [0 0 1 1]" in pdf
    assert pdf.endswith(b"%%EOF\n")
