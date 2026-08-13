"""PDF dönüşüm modülü (PyMuPDF + pdf2docx)."""

import os
import re

import fitz  # PyMuPDF
from pdf2docx import Converter

from converters import ConversionError


def convert_pdf_to_images(input_path: str, output_dir: str, img_format: str) -> list:
    """PDF'in tüm sayfalarını görsele çevirir; üretilen dosya yollarını döndürür.

    Çok sayfalı PDF'lerde her sayfa ayrı bir görsel dosyası olarak kaydedilir
    (düzenleme çağırana aittir).
    """
    doc = fitz.open(input_path)
    try:
        if doc.page_count == 0:
            raise ConversionError("The PDF has no pages.")
        paths = []
        for index, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            page_path = os.path.join(output_dir, f"page-{index + 1}.{img_format}")
            pix.save(page_path)
            paths.append(page_path)
        return paths
    finally:
        doc.close()


def convert_pdf_to_txt(input_path: str, output_path: str) -> None:
    """PDF metnini düz metin olarak çıkarır (taranmış PDF'lerde boş kalabilir)."""
    doc = fitz.open(input_path)
    try:
        parts = [page.get_text() for page in doc]
    finally:
        doc.close()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


def convert_pdf_to_docx(input_path: str, output_path: str) -> None:
    """PDF'i DOCX'e dönüştürür (pdf2docx)."""
    cv = Converter(input_path)
    try:
        cv.convert(output_path, start=0, end=None)
    finally:
        cv.close()


def convert_pdf_to_html(input_path: str, output_path: str) -> None:
    """PDF metnini hafif bir HTML belgesine dönüştürür (yapı korunur, OCR yok)."""
    doc = fitz.open(input_path)
    try:
        bodies = []
        for page in doc:
            raw = page.get_text("html")
            match = re.search(r"<body[^>]*>(.*)</body>", raw, flags=re.S | re.I)
            bodies.append(match.group(1) if match else raw)
    finally:
        doc.close()

    html = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        '<head>\n<meta charset="utf-8">\n'
        "<title>Converted PDF</title>\n"
        "</head>\n<body>\n"
        + "\n".join(bodies)
        + "\n</body>\n</html>\n"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
