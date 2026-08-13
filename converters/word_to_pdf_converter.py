import mammoth
from xhtml2pdf import pisa
import io

def convert_docx_to_pdf(input_path: str, output_path: str):
    """DOCX dosyasını önce HTML'e, ardından PDF'e dönüştürür."""
    
    # 1. DOCX -> HTML
    with open(input_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)
        html_content = result.value

    # 2. HTML'i PDF için daha şık hale getirecek CSS enjeksiyonu
    styled_html = f"""
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
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # 3. HTML -> PDF (xhtml2pdf ile render et)
    with open(output_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(styled_html, dest=pdf_file, encoding='utf-8')
        
    if pisa_status.err:
        raise Exception("DOCX'ten PDF'e dönüştürme sırasında render hatası oluştu.")