import sys
from . import (
    docx,
    html_loader,
    markdown_loader,
    ocr_loader,
    pdf,
    pptx_loader,
    text,
    xlsx_loader,
)
from .advanced_loaders import AdvancedDocumentLoader
from .base import BaseLoader, Document, DocumentLoader
from .docx import DOCXLoader
from .html_loader import HTMLLoader
from .markdown_loader import MDLoader, MarkdownLoader
from .ocr_loader import OCRLoader
from .pdf import PDFLoader
from .pptx_loader import PPTXLoader
from .text import TextLoader, TXTLoader
from .url import URLLoader
from .xlsx_loader import XLSXLoader

# Module-level aliases for dynamic resolution
pdfloader = pdf
docxloader = docx
txtloader = text
htmlloader = html_loader
mdloader = markdown_loader
ocrloader = ocr_loader
pptxloader = pptx_loader
xlsxloader = xlsx_loader

sys.modules.setdefault("ragbot.rag.loaders.pdfloader", pdf)
sys.modules.setdefault("ragbot.rag.loaders.docxloader", docx)
sys.modules.setdefault("ragbot.rag.loaders.txtloader", text)
sys.modules.setdefault("ragbot.rag.loaders.htmlloader", html_loader)
sys.modules.setdefault("ragbot.rag.loaders.mdloader", markdown_loader)
sys.modules.setdefault("ragbot.rag.loaders.ocrloader", ocr_loader)
sys.modules.setdefault("ragbot.rag.loaders.pptxloader", pptx_loader)
sys.modules.setdefault("ragbot.rag.loaders.xlsxloader", xlsx_loader)

__all__ = [
    "BaseLoader",
    "DocumentLoader",
    "Document",
    "TextLoader",
    "TXTLoader",
    "PDFLoader",
    "URLLoader",
    "DOCXLoader",
    "PPTXLoader",
    "XLSXLoader",
    "HTMLLoader",
    "MarkdownLoader",
    "MDLoader",
    "OCRLoader",
    "AdvancedDocumentLoader",
    "pdfloader",
    "docxloader",
    "txtloader",
    "htmlloader",
    "mdloader",
    "ocrloader",
    "pptxloader",
    "xlsxloader",
]
