from PIL import Image

from converters import ConversionError

# Şeffaflığı desteklemeyen hedef formatlar — bu formatlar için RGBA → RGB yapılır.
_OPAQUE_TARGETS = {"JPEG", "BMP", "PDF", "GIF"}


def convert_image(input_path: str, output_path: str, target_format: str) -> None:
    """Görseli okur ve istenen formata çevirir.

    Girdi olarak png/jpg/jpeg/webp/gif/bmp/tiff/ico desteklenir.
    Hedef şeffaflık desteklemiyorsa görsel otomatik olarak RGB'ye çevrilir.
    """
    try:
        image = Image.open(input_path)
    except Image.UnidentifiedImageError:
        raise ConversionError("The uploaded file is not a valid image.")

    target_fmt = target_format.upper()
    if target_fmt == "JPG":
        target_fmt = "JPEG"

    if image.mode in ("RGBA", "LA", "P") and target_fmt in _OPAQUE_TARGETS:
        image = image.convert("RGB")

    image.save(output_path, format=target_fmt)
