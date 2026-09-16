# Complete Metadata for All Files

This document provides comprehensive metadata extracted from all files in the 'loaders' package. Metadata includes module docstrings, class and method docstrings, function signatures, imports, and key features.

## Package Overview
From __init__.py:
Module docstring: "Document loading components"
Exports: BaseLoader, DocumentLoader, Document, TextLoader, PDFLoader, URLLoader, DOCXLoader, PPTXLoader, XLSXLoader, HTMLLoader, MarkdownLoader, OCRLoader, AdvancedDocumentLoader

## base.py

### Module Docstring
Base loader interface for document loading.

This module defines the base interface that all document loaders must implement,
providing a consistent API for loading different types of documents.

Notes:
- Downstream chunkers/optimizers rely on precise spans (start/end) and page-level
  information when available. Loaders should, at minimum, populate these in the
  `metadata` dictionary with conventional keys:
  - metadata['source_type']: str (e.g., 'pdf', 'html', 'docx', 'text')
  - metadata['page']: Optional[int]
  - metadata['span']: Optional[dict] with keys {'start': int, 'end': int}
  - metadata['language']: Optional[str]
  - metadata['mime_type']: Optional[str]
- Keep the `Document` dataclass minimal to avoid breaking existing call sites.
  Prefer enriching `metadata` with the standardized keys above.

### Imports
- from abc import ABC, abstractmethod
- from dataclasses import dataclass
- from typing import Any, Dict, Optional

### Classes

#### Document (dataclass)
Docstring: Represents a loaded document with metadata.

Attributes:
- text: The text content of the document
- metadata: Additional metadata about the document
- source: Source identifier (file path, URL, etc.)
- document_type: Type of document (pdf, url, text, etc.)

Methods:
- __post_init__(): Post-initialization validation.
- content (property): Backward-compatible alias for text.

Notes: For better interoperability, loaders should standardize important fields via `metadata`, such as page numbers and text spans.

#### BaseLoader (ABC)
Docstring: Abstract base class for document loaders. All document loaders must inherit from this class and implement the load method to provide consistent document loading interface.

Methods:
- __init__(**kwargs: Any): Initialize the loader with configuration options.
- load(source: str, **kwargs: Any) -> Document (abstractmethod): Load a document from the given source.
- validate_source(source: str) -> bool (abstractmethod): Validate if the source can be handled by this loader.
- _preprocess_text(text: str) -> str: Optional preprocessing hook for text normalization. Default returns input unchanged.
- _postprocess_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]: Optional postprocessing hook for metadata normalization. Default returns input.
- get_supported_extensions() -> list[str]: Get list of supported file extensions. Default returns [].
- get_loader_info() -> Dict[str, Any]: Get information about this loader (name, supported extensions, config, schema_hint).

#### DocumentLoader (inherits BaseLoader)
Docstring: Document loader interface for Multi-Format support. This class provides a simplified interface for document loading that's compatible with the new Multi-Format loaders.

Methods:
- load(source: str, **kwargs: Any) -> Document: Load a document from the given file path. Raises NotImplementedError.
- validate_source(source: str) -> bool: Validate if the source can be handled by this loader. Returns True.

## advanced_loaders.py

### Module Docstring
مدیر بارگذاری پیشرفته (Advanced Loading Manager)

### Imports
- from pathlib import Path
- from typing import Any, Dict
- from ragbot.configs.settings import settings
- from .base import Document
- from .docx import DOCXLoader
- from .html_loader import HTMLLoader
- from .markdown_loader import MarkdownLoader
- from .ocr_loader import OCRLoader
- from .pdf import PDFLoader
- from .pptx_loader import PPTXLoader
- from .text import TextLoader
- from .url import URLLoader
- from .xlsx_loader import XLSXLoader

### Classes

#### AdvancedDocumentLoader
Docstring: مدیر بارگذاری پیشرفته اسناد (Advanced Document Loading Manager)

Methods:
- __init__(): Initialize advanced document loader. Initializes loaders for allowed file types from settings (pdf, docx, txt, pptx, xlsx, html, htm, md, and image formats for OCR).
- load_document(file_path: str) -> Document (async): Load document by auto-detecting format. Handles URLs with URLLoader, files with appropriate loader based on extension.
- get_supported_formats() -> Dict[str, str] (async): Get supported formats, filtered by security settings.
- validate_file(file_path: str) -> Dict[str, Any] (async): Validate file - checks existence, size, format validity. Returns dict with is_valid, format, size, error.

## pdf.py

### Module Docstring
PDF document loader using PyMuPDF.

This module provides functionality to extract text content from PDF files
with proper error handling and metadata extraction.

### Imports
- import io
- from pathlib import Path
- from typing import Any, Callable, Dict, List, Optional
- try: import fitz (PyMuPDF), PYMUPDF_AVAILABLE = True
- except: PYMUPDF_AVAILABLE = False, dummy fitz class
- from ragbot.configs.settings import settings
- from ragbot.outputs.logger import logger
- from ragbot.rag.exceptions import DocumentProcessingError
- from ragbot.rag.loaders.base import BaseLoader, Document
- try: import pytesseract, from PIL import Image, PYOCR_AVAILABLE = True
- except: PYOCR_AVAILABLE = False

### Classes

#### PDFLoader (inherits BaseLoader)
Docstring: PDF document loader using PyMuPDF. This loader extracts text content from PDF files and provides metadata about the document structure and properties. Supports OCR fallback for scanned pages using pytesseract (default), easyocr, Google Cloud Vision, or custom function. Includes structural extraction for headings and markers if enabled.

Methods:
- __init__(**kwargs: Any): Initialize loader with config: max_pages (default 1000 from settings.pdf.max_pages), extract_images (bool, default False), password (for encrypted PDFs), OCR: lang='eng+fas' (default), engine='pytesseract' (options: 'pytesseract', 'easyocr', 'google', 'custom'), custom_ocr_func, google_token_path (for Google OCR), structural_extraction (bool for headings/markers), inject_heading_markers (bool).
- validate_source(source: str) -> bool: Validates PDF: file existence, is_file(), extension='.pdf', header starts with b'%PDF-', file size < settings.security.max_file_size_mb.
- get_supported_extensions() -> list[str]: Returns [".pdf"]
- load(source: str, **kwargs: Any) -> Document (async): Validates source, opens with fitz.open (handles password/stream), extracts text per page (fitz.get_text()), falls back to OCR if page text empty and extract_images=True (converts page to PNG, runs _perform_ocr), builds full text with page breaks, extracts metadata, applies preprocessing/normalization, structural extraction (find headings via font size/layout), injects markers if enabled. Handles errors with DocumentProcessingError.
- _extract_metadata(doc: fitz.Document, source: str) -> Dict[str, Any]: Extracts from doc.metadata: title, author, subject, keywords, creator, producer, creation_date, mod_date; adds page_count=doc.page_count, file_size, mtime, source_type='pdf', mime_type='application/pdf'.
- _extract_fallback_metadata(source: str, text_length: int) -> Dict[str, Any]: Minimal metadata if fitz unavailable: source, type='pdf', estimated_pages=text_length//500, mime_type.
- _perform_ocr(img_bytes: bytes) -> str: Dispatches to engine: 'pytesseract' (with lang, config '--oem 3 --psm 6'), 'easyocr' (reader.readtext), 'google' (_ocr_google), 'custom' (func call). Returns concatenated text or '' on error.
- _ocr_google(img_bytes: bytes) -> str: Uses Google Cloud Vision API: uploads to GCS bucket (from settings.ocr.google_bucket), detects text via vision_client.document_text_detection, returns full_text_annotation.text. Handles auth via google_token_path/service account.

### Functions

#### extract_pdf_text(file_path: str) -> str (async)
Legacy function for backward compatibility. Creates loader and extracts text.

## docx.py

### Module Docstring
DOCX (Microsoft Word) document loader.

Extracts text from .docx files into a normalized Document object.

### Imports
- from __future__ import annotations
- import asyncio, re, unicodedata, zipfile
- from collections import Counter
- from pathlib import Path
- from statistics import median
- from typing import Any, Dict, Optional
- try: import docx as _docx, DocxDocument = _docx.Document, DOCX_AVAILABLE = True except: dummies, DOCX_AVAILABLE = False
- from ragbot.configs.settings import settings
- from ragbot.outputs.logger import logger
- from ragbot.rag.exceptions import DocumentProcessingError
- from ragbot.rag.loaders.base import BaseLoader, Document

### Functions
- _style_id_heading_level(para) -> Optional[int]: Infers heading level from para.style.style_id if 'HeadingN' (N=1-9).
- _outline_level_from_ooxml(para) -> Optional[int]: Parses para._p.pPr.outlineLvl.val +1 (1-9).
- _para_max_font_pt(para) -> float: Max run.font.size.pt across runs, 0.0 if none.
- _estimate_body_font_size(font_pts: list[float]) -> float: Median of non-zero font_pts, fallback mode or 12.0.
- _layout_signals(para) -> Dict[str, bool]: Extracts signals: keep_next, page_break_before, spacing_before_large (>=200pt or autosp), bold_any (any run bold), short_text (<=120 chars).
- _score_heading_like(delta_pt: float, sig: Dict[str, bool]) -> tuple[bool, int]: Heuristic: hard (>=8pt delta) lvl1, medium (6-8) lvl2, soft (3-6) lvl3/4 if boosters (>=1/2 signals), False/0 else.
- _auto_infer_heading_levels(doc) -> list[Optional[int]]: For all paras: style/OOXML first, if <20% covered then font delta + signals for remaining (lvl 1-6).

### Classes

#### DOCXLoader (inherits BaseLoader)
Docstring: Load text content from a .docx file. Extracts paragraphs and table cell texts, applies basic normalization, and returns a unified `Document` with enriched metadata. Notes: Processing synchronous in thread executor (run_in_executor); lightweight structural extraction (paragraphs, tables up to docx_tables_max, no headers/footers). Supports heading inference (style/OOXML/dynamic font if docx_enable_structural_extraction), numbering preservation if docx_preserve_numbering, hyperlink extraction/injection if docx_extract_hyperlinks/inject_inline (up to docx_hyperlinks_max), image/footnote detection (has_*, lists capped), core properties, language voting if docx_detect_language. Zip bomb protection: checks ZIP entries < docx_max_zip_entries, uncompressed sum < docx_max_uncompressed_mb.

Methods:
- validate_source(source: str) -> bool: Path.is_file() and suffix.lower() == '.docx' (best-effort, no raise on errors).
- get_supported_extensions() -> list[str]: Returns [".docx"].
- load(source: str, **kwargs: Any) -> Document (async): Raises if !DOCX_AVAILABLE. Validates existence/suffix (best-effort stat), size < security.max_file_size_mb (warn if stat fails), zip bomb (is_zipfile, infolist len/sum file_size), _extract_sync in executor: doc = Document(str(path)); parts = [] for paras.text (strip, add numbering f"{counter}. {text}" if numPr/ilvl, heading # injection if level and inject_heading_markers, hyperlinks: xpath //w:hyperlink resolve rels target if /hyperlink/http add to set/list/inline [text](url)), tables: up to docx_tables_max rows.cells text \t join, images: len(inline_shapes)>0 for has_images, rels image/ for list if extract_images (up to docx_images_max), footnotes: rels /footnotes for has_footnotes; raw_content = \n.join(parts); normalize: NFC, remove [\x00-\x1F except \t\n], [ ]{2,} -> ' ', \s*\n\s* -> \n * breaks (default 1 from docx_paragraph_breaks), strip; counters: paragraphs/tables/cells, headings/has_headings/hyperlinks_count/list (sorted unique up to max)/links_list, images_list/has_images, has_footnotes, tables_max_cols, core_title/author/subject/created/modified; estimated_tokens = tiktoken cl100k_base or split; language = langdetect Counter.most_common on 3 chunks if detect_language; metadata = file_name/ext/path/absolute, loader/type='docx'/source_type='file'/mime='application/vnd...wordprocessingml.document', approx_chars, estimated_tokens, **counters, has_tables, title/author etc.; if !content warn; Document(text, metadata, source, document_type='docx'). Errors: DocumentProcessingError logged, from e.
- _extract_sync(p: Path) -> tuple[str, Dict[str, Any]]: Internal sync extractor for thread: implements above extraction/logic, returns normalized, counters.

## pptx_loader.py

### Module Docstring
PPTX (PowerPoint) document loader - Advanced.

Features:
- Auto heading detection: H1 (slide title) + H2/H3 via dynamic font delta & signals
- Bullet/numbered lists, tables (tab-separated), speaker notes
- Hyperlink extraction (inline + metadata), image/chart metadata
- Language detection (multi-chunk voting), token estimation (tiktoken)
- Zip bomb protection (since PPTX is a ZIP container)

### Imports
- from __future__ import annotations
- import zipfile
- from pathlib import Path
- from statistics import median
- from typing import Any, Dict, List, Optional, Tuple
- try: from pptx import Presentation, from pptx.enum.shapes import MSO_SHAPE_TYPE, PPTX_AVAILABLE = True except: PPTX_AVAILABLE = False
- from ragbot.configs.settings import settings
- from ragbot.outputs.logger import logger
- from ragbot.rag.exceptions import DocumentProcessingError
- from ragbot.rag.loaders.base import BaseLoader, Document

### Classes

#### PPTXLoader (inherits BaseLoader)
Docstring: Advanced PPTX loader with headings, lists, tables, notes, and rich metadata.

Methods:
- validate_source(source: str) -> bool: Checks if file exists with .pptx extension.
- get_supported_extensions() -> list[str]: Returns [".pptx"]
- load(source: str, **kwargs: Any) -> Document (async): Validates file, zip bomb protection, processes slides to extract text/headings/tables/notes/hyperlinks/images, builds metadata with language detection and token estimation.
- _collect_slide_font_stats(prs) -> List[float]: Collects font sizes from slides for body font estimation.
- _estimate_body_font_size(font_pts: List[float]) -> float: Estimates body font size using median.
- _extract_slide(slide, slide_number: int, ...) -> Tuple[...]: Extracts text metadata headings hyperlinks images from single slide, including title, shapes, lists, notes.
- _extract_slide_title(slide) -> str: Extracts first text shape as slide title.
- _extract_table(table_shape) -> str: Extracts table cells as tab-separated rows.
- _get_shape_hyperlink(shape) -> Optional[str]: Gets shape-level hyperlink address.
- _get_paragraph_hyperlink(para) -> Optional[str]: Gets first run hyperlink in paragraph.
- _paragraph_font_delta(para, body_pt: float) -> Tuple[float, bool]: Computes font delta from body font and checks for bold.
- _detect_language_voted(text: str) -> Optional[str]: Detects language via voting over text chunks.
- _estimate_tokens(text: str) -> int: Estimates token count using tiktoken or fallback.

## text.py

### Module Docstring
Plain text document loader.

This module provides functionality to load and process plain text content
with proper validation and metadata extraction.

### Imports
- from pathlib import Path
- from typing import Any, Dict, Optional
- from ragbot.configs.settings import settings
- from ragbot.outputs.logger import logger
- from ragbot.rag.exceptions import DocumentProcessingError, ValidationError
- from ragbot.rag.loaders.base import BaseLoader, Document

### Classes

#### TextLoader (inherits BaseLoader)
Docstring: Plain text document loader. Handles plain text content from strings, files, or other text sources with validation and metadata extraction.

Methods:
- __init__(**kwargs: Any): Initialize: max_length=1_000_000 (chars), encoding='utf-8', validate_encoding=True, extract_stats=True, detect_language=True (from kwargs or defaults).
- validate_source(source: str) -> bool: isinstance str, len <= max_length (warn >), if _is_file_path and exists is_file stat.st_size < security.max_file_size_mb (pass if stat fails).
- _is_file_path(source: str) -> bool: ( / or \\ ) or ( . near end with 1-10 alnum ext no space in source) and len<500.
- get_supported_extensions() -> list[str]: Returns [".txt", ".md", ".rst", ".log"].
- load(source: str, **kwargs: Any) -> Document (async): validate_source raise ValidationError invalid/empty (non-file no strip()), kwargs source_type force 'file'/'string' or _is_file_path -> _load_from_file (encoding override) else text=source; if file but empty no raise; normalize replace \r\n/\r to \n, re.sub \n{3,} \n\n; metadata=_extract_metadata update type='text'/source_type/mime ('text/markdown' .md, 'text/x-rst' .rst, else 'text/plain'), approx_chars=len, estimated_tokens=_estimate_tokens, if detect_language _detect_language_voted 3 chunks langdetect Counter.most_common or None, update kwargs.metadata; log; Document text/metadata/source/document_type='text'; raise ValidationError/DocumentProcessingError logged from e.
- _load_from_file(file_path: str, encoding: str) -> tuple[str, Dict[str, Any]] (async): path.exists/is_file raise not, stat, open r encoding read, UnicodeDecodeError fallbacks ['utf-8','latin-1','cp1252'] warn used, raise all fail; file_metadata name/absolute/size/st_mtime/suffix/encoding; raise DocumentProcessingError.
- _extract_metadata(text_content: str, file_metadata: Dict[str, Any], source_identifier: str) -> Dict[str, Any]: loader='TextLoader'/version='1.0.0', source_identifier/source, content_length=len, update file_metadata, if extract_stats _extract_text_stats.
- _extract_text_stats(text: str) -> Dict[str, Any]: char_count=len, word_count=split len, line_count=count\n +1, alpha/digit/space sums isalpha/isdigit/isspace, persian_chars sum \u0600-\u06ff /ratio round3, avg_word_length=alpha/word round2 or 0; warn error return {"stats_error":str(e)}.
- _detect_language_voted(text: str) -> Optional[str]: langdetect on 3 chunks ([:2000], [n//2-1000:n//2+1000], [-2000:]) Counter.most_common[0] if votes else None; None if import fail.

### Functions

#### load_text_content(content: str, **kwargs: Any) -> Document
Convenience function to load text content directly using TextLoader.

## html_loader.py

### Module Docstring
HTML document loader

This module provides an asynchronous loader for HTML documents with:
- Non-blocking IO (HTTP/file)
- Structural extraction (headings h1–h6) and optional heading markers injection
- Standardized metadata (title, description, canonical, OpenGraph/Twitter, language, mime)
- Optional link/image extraction with absolute URLs and limits
- Text normalization and safe cleaning

Docstring style follows Google Python style. All docstrings are in English.

### Imports
- import asyncio
- from typing import Any, Dict, List, Optional
- from urllib.parse import urljoin, urlparse
- import aiohttp
- from bs4 import BeautifulSoup
- try: from fake_useragent import UserAgent, HAS_FAKE_USERAGENT = True except: dummies
- from ragbot.configs.settings import settings
- from ragbot.rag.exceptions import DocumentProcessingError
- from .base import Document, DocumentLoader

### Classes

#### HTMLLoader (inherits DocumentLoader)
Docstring: Asynchronous loader for HTML documents. Supports non-blocking fetch/read, decompose unwanted tags, structural extraction (headings, markers if html_enable_structural_extraction), metadata (title/desc/keywords/canonical/og/twitter/lang/mime, headings summary, links/images capped if extract, langdetect if detect), text normalize (collapse blanks, \r to \n). Settings: html_timeout/retries (10s/2), html_max_links/images (50/20), html_user_agent_mode (fixed/random/chrome/firefox/auto), html_custom_headers json, html_cookies string, html_inject_heading_markers/detect_language/extract_links/images.

Methods:
- load(file_path: str) -> Document (async): if startswith http/s _fetch_url else _read_file for html_content/source_type; soup=BeautifulSoup html 'html.parser'; main_text=_extract_main_content source=file_path; metadata=_extract_metadata soup source source_type; Document text= main_text metadata; raise DocumentProcessingError from e.
- _fetch_url(url: str) -> str (async): timeout= max(1, html_timeout) default 10s; retries=max(0, html_retries) 2; headers=_build_headers url; for attempt 0-retries async session.get url timeout raise_for_status text=await resp.text; sleep min(1*(attempt+1),3) on except; raise DocumentProcessingError last_exc if all fail.
- _read_file(file_path: str) -> str (async): await to_thread _read_file_sync raise DocumentProcessingError from e.
- _read_file_sync(file_path: str) -> str: open r 'utf-8' read raise from e.
- _extract_main_content(soup: BeautifulSoup, source: str) -> str (async): for tag in ['script','style','nav','footer','header','noscript','iframe','object'] decompose; if html_enable_structural_extraction _inject_heading_markers_if_enabled; if structural soup.get_text \n strip else (soup.main or article or section or div class='content').get_text \n strip or soup.get_text; return _normalize_text text.
- _extract_metadata(soup: BeautifulSoup, source: str, source_type: str) -> Dict[str, Any] (async): metadata={'source':source, 'type':'html', 'source_type':source_type, 'mime_type':'text/html'}; title=soup.title get_text strip if title_tag; desc=meta name='description' content.strip; keywords=meta name='keywords' content.strip; canonical=link rel~ 'canonical' href _make_absolute base=source if url; og_title/desc/url = _get_meta 'og:title/desc/url' or _get_meta 'twitter:title/desc' name='twitter:*', url abs base if url; lang=None html_tag=soup.html lang.strip if html lang_attr; if html_detect_language metadata['language']=lang_attr or _detect_language_fallback soup; if structural headings=_extract_headings, 'headings':headings, structure_summary={'num_headings':len(headings), 'levels':sorted set h.level}; if html_extract_links base=source if url links=_extract_links, 'link_count':len(links), 'links':links if links; else 'link_count':0; similar for images if html_extract_images, image_count/len 'images':images; return metadata.
- _normalize_text(text: str) -> str: replace \r\n/\r \n; lines=[ln.strip for ln in split \n]; out=[], prev_blank=False, for ln if is_blank=len(ln)==0 and prev_blank continue else append, prev_blank=is_blank; \n.join(out).strip
- _extract_headings(soup: BeautifulSoup) -> List[Dict[str, Any]]: result=[]; for level 1-6 for h{level} find_all, orig=tag.data-original-text or get_text strip, if # lstrip # .strip, if txt {'level':level, 'text':txt}; return result.
- _inject_heading_markers_if_enabled(soup: BeautifulSoup) -> None: if not html_inject_heading_markers return; for level 1-6 for h{level} find_all txt=get_text strip if empty continue; try tag['data-original-text']=txt; tag.string = # * min(max(level,1),6) space txt.
- _extract_links(soup: BeautifulSoup, base_url: Optional[str]) -> List[Dict[str, str]]: max_links=max(0, html_max_links) 50; seen=set(); out=[]; for a href=True href.strip if empty continue; abs_href=_make_absolute href base if not urlparse scheme=="" urljoin; if not abs_href or abs_href in seen continue; seen.add; text=a.get_text strip or ''; out.append({'href':abs_href, 'text':text}); if len>=max break; return out (dedup abs_href).
- _extract_images(soup: BeautifulSoup, base_url: Optional[str]) -> List[Dict[str, str]]: max_images=max(0, html_max_images) 20; out=[]; for img src=src.strip if empty or startswith 'data:' continue; abs_src=_make_absolute src base; if not abs_src continue; alt=alt.strip or ''; out.append({'src':abs_src, 'alt':alt}); if len>=max break; return out.
- _make_absolute_url(url_value: str, base_url: Optional[str]) -> Optional[str]: if not url_value None; if base_url and urlparse scheme=="" try return urljoin except return url_value; return url_value.
- _detect_language_fallback(soup: BeautifulSoup) -> Optional[str]: import langdetect detect if fail None; text=soup.get_text \n strip [:5000] if >5000; if not strip return None; votes=[]; for seg in [:2000, [len//2:len//2+2000], [-2000:]] if seg.strip votes.append(detect seg); if votes Counter most_common[0][0] else None; except None.
- _build_headers(url: str) -> Dict[str, str]: ua_mode=html_user_agent_mode, fixed=settings.html_user_agent; if fixed ua=fixed; if random/chrome/firefox/auto and HAS_FAKE_USERAGENT ua=UserAgent random/chrome/firefox; headers={'User-Agent':ua}; extra_json=html_custom_headers if try json.loads extra dict k v str headers[k]=v; if html_cookies headers['Cookie']=cookie_hdr; headers.setdefault 'Accept' default, 'Accept-Language' 'en-US,en;q=0.9,fa;q=0.8', 'Accept-Encoding' 'gzip, deflate, br'; return headers.

## markdown_loader.py

### Module Docstring
Markdown document loader - Advanced.

Features:
- Front matter parsing (YAML/JSON-like)
- Heading extraction with levels (H1-H6)
- Lists, blockquotes, code blocks, tables
- Links and images metadata
- Language detection (multi-chunk voting)
- Token estimation (tiktoken)

### Imports
- import re, unicodedata
- from pathlib import Path
- from typing import Any, Dict, Optional
- import markdown
- from bs4 import BeautifulSoup
- from ragbot.configs.settings import settings
- from ragbot.outputs.logger import logger
- from ragbot.rag.exceptions import DocumentProcessingError
- from ragbot.rag.loaders.base import Document, DocumentLoader

### Classes

#### MarkdownLoader (inherits DocumentLoader)
Docstring: Load and parse Markdown documents with advanced metadata. Parses with markdown extensions (toc/codehilite/tables/fenced_code/nl2br), frontmatter --- yaml --- simple key:val lines, headings via splitlines lstrip # level/text, links/images re.findall \[ \]\( \), counts bullets/numbers/blockquotes/code ```lang body``` /tables |.*|, normalized text from html soup.get_text, langdetect if markdown_detect_language default False.

Methods:
- __init__(**kwargs: Any): md=markdown.Markdown extensions=['toc','codehilite','tables','fenced_code','nl2br']; detect_language=bool settings.multi_format.markdown_detect_language (default False).
- load(file_path: str) -> Document (async): path=Path file, !exists or suffix not in ['.md','.markdown'] raise DocumentProcessingError; raw=path.read_text 'utf-8' errors='ignore'; metadata=_extract_metadata raw str(path) set file_name=path.name, file_ext=suffix.lower(), loader='MarkdownLoader', type='markdown', source_type='file', mime_type='text/markdown'; html=md.convert(raw); soup=BS html 'html.parser'; text_content=soup.get_text sep='\n' strip=True; normalized=_normalize_text text_content; metadata['approx_chars']=len(normalized), ['estimated_tokens']=_estimate_tokens normalized; if detect_language lang=_detect_language_voted normalized if lang ['language']=lang; Document text=normalized metadata=metadata source=str(path) document_type='markdown'; error log raise DocumentProcessingError from e.
- _extract_metadata(content: str, file_path: str) -> Dict[str, Any] (async): metadata={'source':file_path, 'type':'markdown'}; if content startswith '---' try fm_end=find '---' 3, if !=-1 fm_block= [3:fm_end] for line split ':' key val strip metadata[key]=val; except warn 'Front matter parse failed'; headings=[]; for line splitlines if strip startswith '#' level=len lstrip #, title=lstrip # strip if title append {'level':level, 'title':title}; 'headers':headings, 'header_count':len(headings), 'has_headings':bool(headings); try 'headings': [{'level':h['level'],'text':h['title']} for h in headings]; links=re.findall r"\[([^\]]+)\]\(([^)]+)\)" content, 'links'=[{'text':t,'url':u} for t u], 'link_count':len, 'has_links':bool; images=re.findall r"!\[([^\]]*)\]\(([^)]+)\)", 'images'=[{'alt':alt,'url':url} for alt url], 'images_count':len, 'has_images':bool; bullets=re.findall r"^\s*[-*+] .+" MULTILINE content len 'bullet_list_count'; numbers=r"^\s*\d+\. ." len 'numbered_list_count'; blockquotes=r"^\s*> .+" len 'blockquote_count'; code_blocks=re.findall r"```(\w+)?([\s\S]*?)```" DOTALL, [{'lang':lang.strip() or None, 'length':len(body.strip())} for lang body], 'code_blocks_count':len; tables=re.findall r"\|.*\|" len 'tables_count'; return metadata.
- _normalize_text(text: str) -> str: unicodedata NFC, re.sub [\x00-\x08\x0B-\x0C\x0E-\x1F] '', [ \t]+ ' ', \s*\n\s* '\n' strip.
- _estimate_tokens(text: str) -> int: try tiktoken get_encoding 'cl100k_base' len encode except len split.
- _detect_language_voted(text: str) -> Optional[str]: try langdetect detect except None; n=len text; chunks=[[:min(2000,n)], [max(0,n//2-1000):min(n,n//2+1000)], [max(0,n-2000):]]; votes=[]; for ch if strip votes.append(detect ch); if not votes None else from collections Counter votes most_common[0][0]; except None.

## ocr_loader.py

### Module Docstring
بارگذاری اسناد با OCR با متادیتای استاندارد و نرمال‌سازی متن. (Loading documents with OCR with standard metadata and text normalization.)

### Imports
- from typing import Any, Dict, Optional
- import pytesseract
- from PIL import Image
- from ragbot.configs.settings import settings
- from ragbot.rag.exceptions import DocumentProcessingError
- from .base import Document, DocumentLoader

### Classes

#### OCRLoader (inherits DocumentLoader)
Docstring: بارگذاری اسناد با OCR (Document loading with OCR)

Methods:
- __init__(language: str = None): Initialize with OCR language (Persian + English from settings if None), sets supported_formats {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}.
- load(file_path: str) -> Document (async): Validates image file (extension, size), opens with PIL, extracts text with pytesseract, normalizes, extracts metadata (source, type, dimensions, format, exif), guesses mime, estimates tokens, detects language.
- _extract_text_with_ocr(image: Image.Image) -> str (async): Extracts text using pytesseract with config --oem 3 --psm 6 -l {language}.
- _clean_ocr_text(text: str) -> str: Cleans OCR output - strips lines, removes short lines (<3 chars), joins cleaned lines.
- _normalize_text(text: str) -> str: Normalizes Unicode NFC, removes control chars, collapses spaces/tabs, normalizes excessive newlines.
- _extract_image_metadata(image: Image.Image, file_path: str) -> Dict[str, Any] (async): Extracts image metadata: source, type, ocr_language, width, height, mode, format, exif_data if available.
- _guess_mime(ext: str, image: Optional[Image.Image]) -> str: Maps file extension to MIME type (e.g. .png -> image/png), falls back to image.format.
- _estimate_tokens(text: str) -> int: Estimates tokens using tiktoken cl100k_base or fallback to split().
- _detect_language_voted(text: str) -> Optional[str]: Detects language via majority vote over three chunks using langdetect.

## url.py

### Module Docstring
URL content loader with web scraping capabilities.

This module provides functionality to fetch and extract clean text content
from web URLs with proper error handling and content sanitization.

### Imports
- import asyncio, import re
- from typing import Any, Dict
- from urllib.parse import urljoin, urlparse
- try: import aiohttp, AIOHTTP_AVAILABLE = True except: False
- try: from bs4 import BeautifulSoup, Comment, BS4_AVAILABLE = True except: False
- from ragbot.configs.settings import settings
- from ragbot.outputs.logger import logger
- from ragbot.rag.exceptions import DocumentProcessingError
- from ragbot.rag.loaders.base import BaseLoader, Document

### Classes

#### URLLoader (inherits BaseLoader)
Docstring: URL content loader with web scraping capabilities. This loader fetches content from web URLs, extracts clean text, and provides metadata about the web page.

Methods:
- __init__(**kwargs: Any): Initialize with timeout, max_content_length, user_agent, follow_redirects, extract_links, max_retries. Sets remove_tags, content_tags.
- validate_source(source: str) -> bool: Validates URL scheme (http/https), netloc, domain regex.
- get_supported_extensions() -> list[str]: Returns ["http://", "https://"]
- load(source: str, **kwargs: Any) -> Document (async): Validates URL, fetches with aiohttp (retries, headers, cookies), parses with BS4, extracts metadata, text, headings, builds document.
- _extract_metadata(soup: BeautifulSoup, response: Any, source: str) -> Dict[str, Any]: Extracts title, meta (desc/keywords/author/robogs/og/twitter), lang, canonical, links, images.
- _extract_text_content(soup: BeautifulSoup) -> str: Removes unwanted tags, finds main content (semantic tags or class selectors), extracts/clean text.
- _clean_text(text: str) -> str: Normalizes newlines, removes excessive blank lines.
- _detect_language_fallback(soup: BeautifulSoup) -> str | None: Detects language via vote on text chunks.
- _inject_heading_markers_if_enabled(soup: BeautifulSoup) -> None: Injects Markdown markers into h1-h6.
- _extract_headings(soup: BeautifulSoup) -> list[dict[str, Any]]: Extracts levels and text from h1-h6.
- _build_headers() -> Dict[str, str]: Builds headers with User-Agent, custom, cookies, accept fields.
- _cookies_from_settings() -> Dict[str, str] | None: Parses settings cookies into dict.

### Functions

#### extract_url_content(url: str) -> str (async)
Legacy function for backward compatibility. Uses URLLoader to extract text.

## xlsx_loader.py

### Module Docstring
بارگذاری اسناد Excel (XLSX) با همگام‌سازی متادیتا و رفتار با سایر لودرها۔ (Loading Excel (XLSX) documents with metadata synchronization and behavior alignment with other loaders.)

### Imports
- import re
- import unicodedata
- from pathlib import Path
- from typing import Any, Dict, Optional
- import pandas as pd
- from ragbot.configs.settings import settings
- from ragbot.outputs.logger import logger
- from ragbot.rag.exceptions import DocumentProcessingError
- from .base import Document, DocumentLoader

### Classes

#### XLSXLoader (inherits DocumentLoader)
Docstring: بارگذاری اسناد Excel (Excel document loader)

Methods:
- load(file_path: str, **kwargs: Any) -> Document (async): Loads Excel file, validates path and size, reads all sheets (with limits on rows/sheets via settings.multi_format), converts DataFrames to text (sheet name, columns if include_headers, row data as col=value pairs), normalizes content (Unicode NFC, remove controls, collapse spaces, normalize newlines), builds metadata (file info, sheet_count, sheets dict with rows/columns/columns_list, total_rows, total_cells, approx_chars, estimated_tokens).
  - Args: file_path (str): Path to XLSX file
  - Returns: Document object with extracted text and metadata
- _dataframe_to_text(self, df: pd.DataFrame, sheet_name: str, include_headers: bool = True) -> str (async): Converts DataFrame to readable text, adds "Sheet: {name}", "ستون‌ها: {columns}" if headers, then rows as "ردیف {i}: col1=value1, col2=value2" (handles NaN, dates.isoformat(), str fallback).
- _detect_language_voted(self, text: str) -> Optional[str]: Detects language using langdetect on three chunks (start, middle, end) with Counter for majority vote.

### Functions

#### _estimate_tokens(text: str) -> int
Estimates token count using tiktoken (cl100k_base or first available encoding) or fallback to len(text.split()).

Notes: Supports optional kwargs (usecols, dtype, engine) for read_excel. Limits: max_rows (default 1000), max_sheets (optional). Safety: file size cap from settings.security.max_file_size_mb. Logs warnings for read errors. Metadata includes MIME type "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" and source_type "file".
