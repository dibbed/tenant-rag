"""Document loading components"""

from .advanced_loaders import AdvancedDocumentLoader
from .base import BaseLoader, Document, DocumentLoader
from .docx import DOCXLoader
from .html_loader import HTMLLoader
from .markdown_loader import MarkdownLoader
from .ocr_loader import OCRLoader
from .pdf import PDFLoader
from .pptx_loader import PPTXLoader
from .text import TextLoader
from .url import URLLoader
from .xlsx_loader import XLSXLoader

__all__ = [
    "BaseLoader",
    "DocumentLoader",
    "Document",
    "TextLoader",
    "PDFLoader",
    "URLLoader",
    "DOCXLoader",
    "PPTXLoader",
    "XLSXLoader",
    "HTMLLoader",
    "MarkdownLoader",
    "OCRLoader",
    "AdvancedDocumentLoader",
]
