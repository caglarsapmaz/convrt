"""Dönüştürme modülleri için ortak hata türü."""


class ConversionError(Exception):
    """Kullanıcı kaynaklı, geri bildirilebilir dönüştürme hataları (→ HTTP 400).

    İç hatalardan ayrıştırılır: yalnızca bu tür 400 olarak döner, diğer
    beklenmedik hatalar 500 olarak loglanır.
    """
