"""pytest ortamı — api.index import edilmeden önce çalışır."""

import os
import tempfile

# Gerçek /tmp'yi kirletmemek için testler ayrı bir geçici dizin kullanır.
os.environ.setdefault("CONVERT_TMP_DIR", tempfile.mkdtemp(prefix="convrt-tests-"))

# Testler sırasında rate limit'in araya girmemesi için yüksek tutulur.
os.environ["RATE_LIMIT_REQUESTS"] = "10000"
os.environ["RATE_LIMIT_WINDOW"] = "60"

# API'nin import sırasında okuduğu diğer varsayılanlar
os.environ.setdefault("MAX_FILE_SIZE_MB", "4.5")
