"""HTML → PDF dönüşüm modülü (xhtml2pdf)."""

import re

from xhtml2pdf import pisa


def convert_html_to_pdf(input_path: str, output_path: str) -> None:
    """HTML dosyasını şık bir PDF'e dönüştürür."""
    with open(input_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    # Kaynak tam bir HTML belgesiyse yalnızca <body> içeriğini kullan
    # (iç içe <html>/<body> oluşmasını engeller).
    match = re.search(r"<body[^>]*>(.*)</body>", content, flags=re.S | re.I)
    if match:
        content = match.group(1)

    styled_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{ size: a4 portrait; margin: 2cm; }}
    body {{ font-family: Helvetica, sans-serif; font-size: 11pt; line-height: 1.6; color: #333333; }}
    h1, h2, h3, h4 {{ color: #111111; margin-top: 1em; margin-bottom: 0.5em; }}
    p {{ margin-bottom: 1em; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 1em; }}
    th, td {{ border: 1px solid #dddddd; padding: 8px; text-align: left; }}
    img {{ max-width: 100%; }}
    pre {{ background: #f5f5f5; padding: 8px; border-radius: 4px; overflow-x: auto; }}
</style>
</head>
<body>
{content}
</body>
</html>"""

    with open(output_path, "wb") as pdf_file:
        status = pisa.CreatePDF(styled_html, dest=pdf_file, encoding="utf-8")
    if status.err:
        raise RuntimeError("HTML to PDF rendering failed.")
