"""Convrt — FastAPI tabanlı, ücretsiz ve reklamsız dosya dönüştürme servisi.

Tasarım notları:
- Render (ücretsiz plan) üzerinde çalışacak şekilde tasarlanmıştır; dış servis yoktur.
- Hiçbir dosya kalıcı olarak saklanmaz: tüm geçici dosyalar işletim sisteminin
  geçici dizininde oluşturulur ve istek tamamlanınca silinir.
- Ağır bağımlılıklar (PyMuPDF, pdf2docx vb.) yalnızca ihtiyaç anında içe aktarılır
  (lazy import) — böylece soğuk başlatma süresi ve bellek kullanımı düşük tutulur.
"""

import logging
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
import zipfile
from collections import defaultdict, deque

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from converters import ConversionError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("convrt")

# --------------------------------------------------------------------------- #
# Yapılandırma (tümü ortam değişkenleriyle özelleştirilebilir)
# --------------------------------------------------------------------------- #
TMP_DIR = os.environ.get("CONVERT_TMP_DIR", tempfile.gettempdir())
PUBLIC_DIR = os.path.join(parent_dir, "public")

# Varsayılan 4.5 MB — Render dahil tüm ortamlarda güvenli bir değerdir.
MAX_FILE_SIZE_MB = float(os.environ.get("MAX_FILE_SIZE_MB", "4.5"))

# IP başına basit istek limiti (bellek içi, tek instance için yeterli).
DEFAULT_RATE_LIMIT = int(os.environ.get("RATE_LIMIT_REQUESTS", "30"))
DEFAULT_RATE_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))

app = FastAPI(
    title="Convrt API",
    version="1.0.0",
    description="Ücretsiz, reklamsız dosya dönüştürme servisi. Dosyalar saklanmaz.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Çerez kullanılmıyor → "*" ile güvenlidir.
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists(PUBLIC_DIR):
    app.mount("/static", StaticFiles(directory=PUBLIC_DIR), name="static")

MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "html": "text/html",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "ico": "image/x-icon",
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
}

# Desteklenen dönüşümler — frontend'deki conversionMap ile birebir uyumludur.
# Bu tablo, UI ile backend arasındaki tek doğruluk kaynağıdır.
IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "ico"}
IMAGE_TARGETS = {"pdf", "png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "ico"}

SUPPORTED_TARGETS = {
    "pdf": ["docx", "txt", "html", "png", "jpg"],
    "docx": ["pdf", "txt"],
    "txt": ["docx"],
    "html": ["pdf"],
    "htm": ["pdf"],
    "xlsx": ["csv"],
    "csv": ["xlsx"],
}
for _ext in IMAGE_EXTS:
    SUPPORTED_TARGETS[_ext] = sorted(IMAGE_TARGETS - {_ext})


# --------------------------------------------------------------------------- #
# Yardımcılar
# --------------------------------------------------------------------------- #
def cleanup_files(paths):
    """Geçici dosyaları güvenle siler (hata sessizce geçilir, loglanır)."""
    for path in paths or []:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                logger.warning("Temizlenemedi: %s", path)


def cleanup_dir(path):
    """Geçici klasörü siler."""
    if path and os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


_hit_log = defaultdict(deque)
_last_prune_at = 0.0


def enforce_rate_limit(request: Request) -> None:
    """IP başına basit kayar pencere (sliding window) istek limiti.

    Not: X-Forwarded-For yalnızca Render gibi güvenilir bir proxy arkasındayken
    kullanılır; proxy doğru değeri yazar. Bellek büyümesini önlemek için
    uzun süredir sessiz kalan IP kayıtları periyodik olarak temizlenir.
    """
    global _last_prune_at
    limit = int(os.environ.get("RATE_LIMIT_REQUESTS", str(DEFAULT_RATE_LIMIT)))
    window = int(os.environ.get("RATE_LIMIT_WINDOW", str(DEFAULT_RATE_WINDOW)))
    if limit <= 0:
        return
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    now = time.monotonic()
    bucket = _hit_log[ip]
    while bucket and now - bucket[0] > window:
        bucket.popleft()
    # Uzun süredir sessiz kalan IP kayıtlarını periyodik olarak düşür (bellek koruması)
    if now - _last_prune_at > max(window, 60):
        _last_prune_at = now
        for dead_ip in [
            k for k, v in _hit_log.items() if not v or now - v[-1] > window * 4
        ]:
            del _hit_log[dead_ip]
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429, detail="Too many requests. Please try again later."
        )
    bucket.append(now)


# --------------------------------------------------------------------------- #
# Sayfa rotaları
# --------------------------------------------------------------------------- #
@app.get("/")
def serve_index():
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))


@app.get("/styles.css")
def serve_css():
    return FileResponse(os.path.join(PUBLIC_DIR, "styles.css"))


@app.get("/app.js")
def serve_js():
    return FileResponse(os.path.join(PUBLIC_DIR, "app.js"))


@app.get("/api/health")
def health_check():
    return {"status": "success", "message": "API is ready", "version": app.version}


@app.get("/api/config")
def get_config():
    """İstemcinin güvenli varsayılanlarla senkron kalması için yapılandırma."""
    return {"max_file_size_mb": MAX_FILE_SIZE_MB}


# --------------------------------------------------------------------------- #
# Dönüştürme uç noktası
# --------------------------------------------------------------------------- #
@app.post("/api/convert")
async def convert_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_format: str = Form(...),
):
    enforce_rate_limit(request)

    # 1) Boyut kontrolü — önce Content-Length (dosyayı belleğe almadan reddeder)
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail=f"File is too large. Maximum size is {MAX_FILE_SIZE_MB:g} MB.",
                )
        except ValueError:
            pass

    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum size is {MAX_FILE_SIZE_MB:g} MB.",
        )

    # 2) Format doğrulama — desteklenmeyen girdi/hedef için 400 döndür (500 değil)
    original_ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    target_fmt = target_format.lower().lstrip(".")

    if original_ext not in SUPPORTED_TARGETS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{original_ext}")
    if target_fmt not in SUPPORTED_TARGETS[original_ext]:
        raise HTTPException(
            status_code=400,
            detail=f"Conversion from .{original_ext} to .{target_fmt} is not supported.",
        )

    # 3) Geçici dosyalar (asla kalıcı saklama yok)
    base = uuid.uuid4().hex
    input_path = os.path.join(TMP_DIR, f"{base}.{original_ext}")
    output_path = os.path.join(TMP_DIR, f"{base}.{target_fmt}")

    with open(input_path, "wb") as buffer:
        buffer.write(file_content)

    response_filename = f"converted.{target_fmt}"
    zip_mode = False
    work_dirs = []

    try:
        if original_ext in IMAGE_EXTS:
            from converters.image_converter import convert_image

            convert_image(input_path, output_path, target_fmt)

        elif original_ext == "pdf":
            if target_fmt in ("png", "jpg"):
                from converters.pdf_converter import convert_pdf_to_images

                pages_dir = os.path.join(TMP_DIR, f"{base}_pages")
                os.makedirs(pages_dir, exist_ok=True)
                work_dirs.append(pages_dir)
                pages = convert_pdf_to_images(input_path, pages_dir, target_fmt)
                if len(pages) == 1:
                    os.replace(pages[0], output_path)
                else:
                    zip_path = os.path.join(TMP_DIR, f"{base}.zip")
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for page in pages:
                            zf.write(page, arcname=os.path.basename(page))
                    output_path = zip_path
                    zip_mode = True
                    response_filename = "converted-images.zip"
            elif target_fmt == "docx":
                from converters.pdf_converter import convert_pdf_to_docx

                convert_pdf_to_docx(input_path, output_path)
            elif target_fmt == "txt":
                from converters.pdf_converter import convert_pdf_to_txt

                convert_pdf_to_txt(input_path, output_path)
            elif target_fmt == "html":
                from converters.pdf_converter import convert_pdf_to_html

                convert_pdf_to_html(input_path, output_path)

        elif original_ext in ("html", "htm"):
            from converters.html_converter import convert_html_to_pdf

            convert_html_to_pdf(input_path, output_path)

        elif original_ext == "docx":
            if target_fmt == "pdf":
                from converters.word_to_pdf_converter import convert_docx_to_pdf

                convert_docx_to_pdf(input_path, output_path)
            else:  # txt
                from converters.text_converter import convert_docx_to_txt

                convert_docx_to_txt(input_path, output_path)

        elif original_ext == "txt":
            from converters.text_converter import convert_txt_to_docx

            convert_txt_to_docx(input_path, output_path)

        elif original_ext == "xlsx":
            from converters.excel_converter import convert_xlsx_to_csv

            convert_xlsx_to_csv(input_path, output_path)

        elif original_ext == "csv":
            from converters.excel_converter import convert_csv_to_xlsx

            convert_csv_to_xlsx(input_path, output_path)

        # 4) Sonuç kontrolü
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            if target_fmt == "txt":
                raise HTTPException(
                    status_code=400,
                    detail="No text could be extracted from the file. It may be a scanned PDF.",
                )
            raise HTTPException(
                status_code=500, detail="Conversion produced an empty result."
            )

    except HTTPException:
        raise
    except ConversionError as exc:
        # Kullanıcı kaynaklı hatalar (geçersiz görsel, boş PDF vb.) → 400
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception(
            "Conversion failed (input=%s, target=%s)", original_ext, target_fmt
        )
        raise HTTPException(
            status_code=500,
            detail="Conversion failed. Please try again or choose a different file.",
        )
    finally:
        # Girdi ve ara klasörler her durumda temizlenir
        cleanup_files([input_path])
        for directory in work_dirs:
            cleanup_dir(directory)

    # Çıktı, yanıt gönderildikten SONRA silinir (background task).
    # Not: istemci indirme sırasında bağlantıyı koparırsa Starlette bu görevi
    # çalıştırmayabilir; kalan dosyalar yalnızca geçici (/tmp) alanda birikir ve
    # Render örneği yeniden başlatıldığında otomatik olarak temizlenir.
    background_tasks.add_task(cleanup_files, [output_path])

    return FileResponse(
        path=output_path,
        filename=response_filename,
        media_type=MIME_TYPES.get(target_fmt if not zip_mode else "zip", "application/octet-stream"),
    )
