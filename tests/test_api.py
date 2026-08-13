"""API uçtan uca testleri (FastAPI TestClient)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from api.index import _hit_log, app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_serve_index():
    r = client.get("/")
    assert r.status_code == 200
    assert "Convrt" in r.text


def test_convert_txt_to_docx():
    r = client.post(
        "/api/convert",
        files={"file": ("ornek.txt", "merhaba dunya\nikinci satir".encode(), "text/plain")},
        data={"target_format": "docx"},
    )
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # ZIP (docx) imzası
    assert "docx" in r.headers.get("content-disposition", "").lower()


def test_convert_unsupported_extension():
    r = client.post(
        "/api/convert",
        files={"file": ("virus.exe", b"MZ...", "application/octet-stream")},
        data={"target_format": "pdf"},
    )
    assert r.status_code == 400


def test_convert_unsupported_target():
    r = client.post(
        "/api/convert",
        files={"file": ("metin.txt", b"selam", "text/plain")},
        data={"target_format": "pdf"},
    )
    assert r.status_code == 400


def test_convert_oversize():
    r = client.post(
        "/api/convert",
        files={"file": ("buyuk.txt", b"a" * (5 * 1024 * 1024), "text/plain")},
        data={"target_format": "docx"},
    )
    assert r.status_code == 413


def test_convert_invalid_image():
    r = client.post(
        "/api/convert",
        files={"file": ("sahte.png", b"not really an image", "image/png")},
        data={"target_format": "jpg"},
    )
    assert r.status_code == 400


def test_convert_gif_to_png():
    # GIF girişi backend'de artık destekleniyor (frontend ile uyumlu)
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buf, format="GIF")
    r = client.post(
        "/api/convert",
        files={"file": ("anim.gif", buf.getvalue(), "image/gif")},
        data={"target_format": "png"},
    )
    assert r.status_code == 200
    assert r.content[:4] == b"\x89PNG"


def test_convert_html_to_pdf():
    r = client.post(
        "/api/convert",
        files={"file": ("sayfa.html", b"<html><body><h1>Merhaba</h1></body></html>", "text/html")},
        data={"target_format": "pdf"},
    )
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_convert_pdf_single_page_to_png():
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Tek sayfa")
    payload = doc.tobytes()
    doc.close()

    r = client.post(
        "/api/convert",
        files={"file": ("tek.pdf", payload, "application/pdf")},
        data={"target_format": "png"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/png")
    assert r.content[:4] == b"\x89PNG"


def test_convert_pdf_multipage_to_zip():
    import fitz

    doc = fitz.open()
    for _ in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), "Cok sayfa")
    payload = doc.tobytes()
    doc.close()

    r = client.post(
        "/api/convert",
        files={"file": ("cok.pdf", payload, "application/pdf")},
        data={"target_format": "png"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/zip")
    assert r.content[:2] == b"PK"  # ZIP imzası
    assert "converted-images.zip" in r.headers.get("content-disposition", "")


def test_rate_limit(monkeypatch):
    _hit_log.clear()
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "3")
    for _ in range(3):
        r = client.post(
            "/api/convert",
            files={"file": ("a.txt", b"x", "text/plain")},
            data={"target_format": "docx"},
        )
        assert r.status_code == 200
    r = client.post(
        "/api/convert",
        files={"file": ("a.txt", b"x", "text/plain")},
        data={"target_format": "docx"},
    )
    assert r.status_code == 429
