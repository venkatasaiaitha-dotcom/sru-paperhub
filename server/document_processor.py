"""Secure document validation, in-memory transient processing, image preprocessing, and multi-page PDF handling."""

from dataclasses import dataclass, field
import hashlib
from io import BytesIO
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError
import pymupdf


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}

_LAPLACIAN_KERNEL = ImageFilter.Kernel(
    (3, 3),
    [0, 1, 0, 1, -4, 1, 0, 1, 0],
    scale=1,
    offset=128,
)

PLACEHOLDER_REGEX = re.compile(
    r"\b("
    r"lorem\s+ipsum|"
    r"dolor\s+sit\s+amet|"
    r"consectetur\s+adipiscing|"
    r"adipiscing\s+elit|"
    r"pellentesque\s+sem|"
    r"pulvinar\s+vivamus|"
    r"iaculis\s+massa|"
    r"pretium\s+tellus|"
    r"taciti\s+sociosqu|"
    r"torquent\s+per\s+conubia|"
    r"insert\s+question\s+here|"
    r"sample\s+question\s+text|"
    r"dummy\s+question\s+text|"
    r"placeholder\s+text"
    r")\b",
    re.IGNORECASE,
)

HEALTH_BIOLOGY_REGEX = re.compile(
    r"\b("
    r"resting\s+heart\s+rate|heart\s+rate|blood\s+pressure|red\s+blood\s+cells?|white\s+blood\s+cells?|"
    r"bacterial\s+infection|viral\s+infection|antibiotics?|dehydration|diabetes|insulin|blood\s+sugar|"
    r"immune\s+system|cardiovascular|digestive\s+system|filtering\s+waste\s+from\s+the\s+blood|"
    r"health-related\s+questions?|scenario-based\s+health|vital\s+signs?|chest\s+pain|painkiller|"
    r"stethoscope|symptoms?|pathogen|hypertension|glucose|cholesterol|hemoglobin|kidneys?\s+filter|"
    r"human\s+anatomy|physiology|pharmacology"
    r")\b",
    re.IGNORECASE,
)

TECH_COURSE_HEADER_REGEX = re.compile(
    r"\b("
    r"cloud(?:\s+computing)?|computer\s+science|c\.?s\.?e|data\s+structures?|operating\s+systems?|"
    r"dbms|database|machine\s+learning|software\s+engineering|artificial\s+intelligence|"
    r"algorithms?|cryptography|cyber\s+security|web\s+technologies|compiler\s+design|computer\s+networks|"
    r"microprocessors?|embedded\s+systems?|information\s+management\s+systems?"
    r")\b",
    re.IGNORECASE,
)

TECH_QUESTION_CONTENT_REGEX = re.compile(
    r"\b("
    r"iaas|paas|saas|virtualization|hypervisor|docker|kubernetes|aws|azure|gcp|"
    r"datacenter|virtual\s+machine|load\s+balancing|scalability|multitenancy|database|sql|"
    r"algorithm|complexity|memory|cpu|network|packet|protocol|cache|thread|process|api|"
    r"compiler|operating\s+system|linux|storage|server|router|bandwidth|encryption"
    r")\b",
    re.IGNORECASE,
)


class DocumentValidationError(Exception):
    """Raised when an uploaded file fails security, type, size, or structural integrity validation."""

    def __init__(self, message: str, status_code: int = 400, error_code: str = "INVALID_DOCUMENT"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


@dataclass
class PreparedVisualPage:
    """Single preprocessed page or image payload ready for multimodal Gemini inspection."""

    page_number: int
    image_bytes: bytes
    mime_type: str
    width: int
    height: int
    sharpness: float
    brightness: float
    contrast: float


@dataclass
class ProcessedDocument:
    """Normalized document package extracted cleanly from a temporary file."""

    request_id: str
    safe_filename: str
    extension: str
    mime_type: str
    file_size_bytes: int
    sha256: str
    is_pdf: bool
    page_count: int = 1
    sampled_page_numbers: List[int] = field(default_factory=list)
    visual_pages: List[PreparedVisualPage] = field(default_factory=list)
    pdf_page_texts: List[Dict[str, Any]] = field(default_factory=list)
    total_extracted_chars: int = 0
    is_scanned_pdf: bool = False
    quality_insufficient: bool = False
    quality_issues: List[str] = field(default_factory=list)
    quality_summary: str = "GOOD"
    aspect_ratio: float = 1.414
    has_placeholder_text: bool = False
    placeholder_matches: List[str] = field(default_factory=list)
    has_domain_mismatch: bool = False
    domain_mismatch_reason: str = ""


def sanitize_filename(filename: Optional[str]) -> str:
    """Strip path traversal, control characters, and unsafe bytes from uploaded filenames."""
    base = os.path.basename((filename or "").replace("\\", "/")).strip()
    base = re.sub(r"[\x00-\x1f\x7f<>:\"/\\|?*]+", "_", base)
    base = re.sub(r"\s+", "_", base).strip("._")
    if not base:
        return "uploaded_document"
    return base[:120]


def sniff_magic_mime(data: bytes) -> Optional[str]:
    """Identify true file format using magic-byte signatures rather than trusting filename/headers."""
    if not data:
        return None
    head = data[:32]
    stripped = data[:1024].lstrip()
    if head.startswith(b"%PDF-") or stripped.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    # Explicitly classify dangerous formats so they are cleanly rejected
    lower_head = stripped[:256].lower()
    if b"<svg" in lower_head or b"<!doctype html" in lower_head or b"<html" in lower_head:
        return "image/svg+xml"
    if head.startswith(b"MZ") or head.startswith(b"\x7fELF") or head.startswith(b"#!"):
        return "application/x-executable"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    return None


def validate_upload_bytes(
    file_bytes: bytes,
    filename: Optional[str],
    declared_mime: Optional[str] = None,
    max_upload_mb: int = 15,
) -> Tuple[str, str, str]:
    """Validate file size, sanitized extension, declared MIME, and magic-byte signature."""
    if not file_bytes or len(file_bytes) == 0:
        raise DocumentValidationError("Uploaded file is empty.", status_code=400, error_code="EMPTY_FILE")

    max_bytes = max_upload_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise DocumentValidationError(
            f"File exceeds the maximum allowed upload limit of {max_upload_mb} MB.",
            status_code=413,
            error_code="FILE_TOO_LARGE",
        )

    safe_name = sanitize_filename(filename)
    _, ext = os.path.splitext(safe_name.lower())
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError(
            f"Unsupported file extension '{ext}'. Allowed formats: PDF, PNG, JPG, JPEG, WEBP.",
            status_code=400,
            error_code="UNSUPPORTED_FILE_TYPE",
        )

    sniffed_mime = sniff_magic_mime(file_bytes)
    if sniffed_mime in ("image/svg+xml", "application/x-executable", "application/zip"):
        raise DocumentValidationError(
            "Security policy blocked potentially unsafe file format. Only PDF, PNG, JPG, or WEBP question papers are accepted.",
            status_code=400,
            error_code="BLOCKED_FILE_TYPE",
        )

    if sniffed_mime is None or sniffed_mime not in ALLOWED_MIME_TYPES:
        raise DocumentValidationError(
            "Uploaded file signature is corrupted or not a valid PDF, PNG, JPG, or WEBP document.",
            status_code=400,
            error_code="INVALID_FILE_SIGNATURE",
        )

    cleaned_declared = (declared_mime or "").split(";")[0].strip().lower()
    if cleaned_declared and cleaned_declared not in ALLOWED_MIME_TYPES:
        if cleaned_declared != "application/octet-stream":
            raise DocumentValidationError(
                f"Unsupported MIME type '{cleaned_declared}'. Allowed formats: PDF, PNG, JPG, WEBP.",
                status_code=400,
                error_code="UNSUPPORTED_MIME_TYPE",
            )

    # Reject misleading extension mismatch (e.g. executable/PNG renamed to .pdf or PDF renamed to .png)
    ext_expected = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    if ext and ext in ext_expected and ext_expected[ext] != sniffed_mime:
        raise DocumentValidationError(
            "File content does not match its file extension.",
            status_code=400,
            error_code="EXTENSION_MIME_MISMATCH",
        )

    resolved_ext = ext or {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }[sniffed_mime]

    return safe_name, resolved_ext, sniffed_mime


def _normalize_image_rgb(img: Image.Image) -> Image.Image:
    """Correct EXIF orientation and flatten alpha/palette/CMYK to clean RGB."""
    transposed = ImageOps.exif_transpose(img)
    if getattr(transposed, "n_frames", 1) > 1:
        transposed.seek(0)
    if transposed.mode in ("RGBA", "LA") or (
        transposed.mode == "P" and "transparency" in transposed.info
    ):
        rgba = transposed.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[3])
        return background
    if transposed.mode != "RGB":
        return transposed.convert("RGB")
    return transposed.copy()


def _measure_image_quality(rgb_img: Image.Image) -> Dict[str, Any]:
    """Compute resolution, sharpness (Laplacian variance), brightness, and contrast diagnostics."""
    width, height = rgb_img.size
    thumb = rgb_img.copy()
    thumb.thumbnail((1000, 1400), Image.Resampling.LANCZOS)
    gray = thumb.convert("L")

    tw, th = gray.size
    crop_box = (4, 4, max(5, tw - 4), max(5, th - 4)) if tw > 12 and th > 12 else (0, 0, tw, th)
    gray_inner = gray.crop(crop_box)
    edges = gray.filter(_LAPLACIAN_KERNEL).crop(crop_box)

    g_stat = ImageStat.Stat(gray_inner)
    e_stat = ImageStat.Stat(edges)

    brightness = float(g_stat.mean[0])
    contrast = float(g_stat.stddev[0])
    sharpness = float(e_stat.var[0])

    issues: List[str] = []
    if min(width, height) < 320 or (width * height) < 150_000:
        issues.append("Image resolution is too low to read fine examination text reliably.")
    if contrast < 8.0 or brightness < 28.0:
        issues.append("Document is excessively dark, washed out, or blank.")
    elif sharpness < 95.0:
        issues.append("Image appears too blurry or out of focus for reliable text inspection.")

    return {
        "width": width,
        "height": height,
        "aspect_ratio": round(max(width, height) / max(1, min(width, height)), 3),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "sharpness": round(sharpness, 2),
        "issues": issues,
        "insufficient": len(issues) > 0,
    }


def _encode_normalized_jpeg(rgb_img: Image.Image, max_edge: int = 1800, quality: int = 88) -> Tuple[bytes, int, int]:
    """Resize oversized camera images cleanly while keeping small exam text sharp."""
    working = rgb_img.copy()
    if max(working.size) > max_edge:
        working.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buf = BytesIO()
    working.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue(), working.width, working.height


def _select_representative_page_indices(page_count: int, max_pages: int) -> List[int]:
    """Select all pages up to max_pages, or spread indices across first, middle, and final pages."""
    if page_count <= max_pages:
        return list(range(page_count))
    if max_pages <= 2:
        return [0, page_count - 1][:max_pages]

    selected = {0, 1, page_count - 1}
    remaining = max_pages - len(selected)
    if remaining > 0:
        span_start = 2
        span_end = page_count - 2
        if span_end >= span_start:
            step = (span_end - span_start + 1) / (remaining + 1)
            for i in range(1, remaining + 1):
                idx = min(span_end, max(span_start, int(round(span_start + i * step - 0.5))))
                selected.add(idx)
    return sorted(selected)[:max_pages]


def process_uploaded_document(
    file_bytes: bytes,
    filename: Optional[str],
    declared_mime: Optional[str] = None,
    request_id: str = "req_unknown",
    max_upload_mb: int = 15,
    max_pdf_pages: int = 8,
) -> ProcessedDocument:
    """Validate and transiently inspect an uploaded PDF or image without persistent storage."""
    safe_name, ext, mime_type = validate_upload_bytes(
        file_bytes=file_bytes,
        filename=filename,
        declared_mime=declared_mime,
        max_upload_mb=max_upload_mb,
    )
    sha256_hex = hashlib.sha256(file_bytes).hexdigest()

    if mime_type == "application/pdf":
        return _process_pdf_bytes(
            file_bytes=file_bytes,
            request_id=request_id,
            safe_filename=safe_name,
            ext=ext,
            mime_type=mime_type,
            file_size_bytes=len(file_bytes),
            sha256_hex=sha256_hex,
            max_pdf_pages=max_pdf_pages,
        )

    return _process_image_bytes(
        file_bytes=file_bytes,
        request_id=request_id,
        safe_filename=safe_name,
        ext=ext,
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        sha256_hex=sha256_hex,
    )


def _process_image_bytes(
    file_bytes: bytes,
    request_id: str,
    safe_filename: str,
    ext: str,
    mime_type: str,
    file_size_bytes: int,
    sha256_hex: str,
) -> ProcessedDocument:
    try:
        with Image.open(BytesIO(file_bytes)) as img:
            img.load()
            rgb_img = _normalize_image_rgb(img)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise DocumentValidationError(
            "Uploaded image file is corrupted or unreadable.",
            status_code=400,
            error_code="CORRUPTED_IMAGE",
        ) from exc

    diag = _measure_image_quality(rgb_img)
    jpeg_bytes, out_w, out_h = _encode_normalized_jpeg(rgb_img, max_edge=1800, quality=88)

    page = PreparedVisualPage(
        page_number=1,
        image_bytes=jpeg_bytes,
        mime_type="image/jpeg",
        width=out_w,
        height=out_h,
        sharpness=diag["sharpness"],
        brightness=diag["brightness"],
        contrast=diag["contrast"],
    )

    quality_summary = "POOR" if diag["insufficient"] else ("FAIR" if diag["sharpness"] < 240 else "GOOD")
    return ProcessedDocument(
        request_id=request_id,
        safe_filename=safe_filename,
        extension=ext,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        sha256=sha256_hex,
        is_pdf=False,
        page_count=1,
        sampled_page_numbers=[1],
        visual_pages=[page],
        quality_insufficient=diag["insufficient"],
        quality_issues=diag["issues"],
        quality_summary=quality_summary,
        aspect_ratio=diag["aspect_ratio"],
    )


def _process_pdf_bytes(
    file_bytes: bytes,
    request_id: str,
    safe_filename: str,
    ext: str,
    mime_type: str,
    file_size_bytes: int,
    sha256_hex: str,
    max_pdf_pages: int,
) -> ProcessedDocument:
    try:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise DocumentValidationError(
            "Uploaded PDF is corrupted or cannot be opened.",
            status_code=400,
            error_code="CORRUPTED_PDF",
        ) from exc

    try:
        if getattr(doc, "needs_pass", False):
            raise DocumentValidationError(
                "Password-protected or encrypted PDFs cannot be verified automatically.",
                status_code=400,
                error_code="ENCRYPTED_PDF",
            )

        page_count = len(doc)
        if page_count <= 0:
            raise DocumentValidationError(
                "Uploaded PDF contains zero pages.",
                status_code=400,
                error_code="EMPTY_PDF",
            )

        # Extract text from ALL pages so multi-page papers never lose Section B/C/last pages
        page_texts: List[Dict[str, Any]] = []
        total_chars = 0
        first_aspect = 1.414
        for idx in range(page_count):
            page = doc[idx]
            rect = page.rect
            if idx == 0 and rect.width > 0 and rect.height > 0:
                first_aspect = round(max(rect.width, rect.height) / max(1.0, min(rect.width, rect.height)), 3)
            txt = (page.get_text("text") or "").strip()
            total_chars += len(txt)
            # Cap per-page text defensively for huge non-exam PDFs
            page_texts.append(
                {
                    "page": idx + 1,
                    "char_count": len(txt),
                    "text": txt[:6000],
                }
            )

        is_scanned = total_chars < max(40, page_count * 25)
        sampled_indices = _select_representative_page_indices(page_count, max_pdf_pages)
        dpi = 140 if len(sampled_indices) <= 4 else 115
        max_edge = 1600 if len(sampled_indices) <= 4 else 1350

        visual_pages: List[PreparedVisualPage] = []
        poor_pages = 0
        quality_issues: List[str] = []

        for idx in sampled_indices:
            page = doc[idx]
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            diag = _measure_image_quality(pil_img)
            if diag["insufficient"]:
                poor_pages += 1
                for issue in diag["issues"]:
                    if issue not in quality_issues:
                        quality_issues.append(issue)
            jpeg_bytes, out_w, out_h = _encode_normalized_jpeg(pil_img, max_edge=max_edge, quality=85)
            visual_pages.append(
                PreparedVisualPage(
                    page_number=idx + 1,
                    image_bytes=jpeg_bytes,
                    mime_type="image/jpeg",
                    width=out_w,
                    height=out_h,
                    sharpness=diag["sharpness"],
                    brightness=diag["brightness"],
                    contrast=diag["contrast"],
                )
            )
    finally:
        doc.close()

    # Scanned PDFs where every rendered page fails visual readability/contrast are poor quality
    quality_insufficient = is_scanned and visual_pages and (poor_pages == len(visual_pages))
    if total_chars == 0 and visual_pages and all(p.contrast < 6.0 for p in visual_pages):
        quality_insufficient = True
        if "PDF pages appear completely blank." not in quality_issues:
            quality_issues.append("PDF pages appear completely blank.")

    # Check for placeholder filler text (e.g. Lorem Ipsum, dummy Latin template text)
    full_doc_text = " ".join(p.get("text", "") for p in page_texts)
    placeholder_hits = PLACEHOLDER_REGEX.findall(full_doc_text)
    has_placeholder = len(placeholder_hits) > 0
    cleaned_hits = list(dict.fromkeys(placeholder_hits))[:5]
    if has_placeholder:
        quality_issues.append("Document contains placeholder filler text ('Lorem Ipsum') instead of genuine examination questions.")

    # Check for course subject domain mismatch (e.g. Health questions in a Computer Science / Cloud Computing paper)
    has_domain_mismatch = False
    domain_mismatch_reason = ""
    if TECH_COURSE_HEADER_REGEX.search(full_doc_text):
        health_matches = HEALTH_BIOLOGY_REGEX.findall(full_doc_text)
        tech_matches = TECH_QUESTION_CONTENT_REGEX.findall(full_doc_text)
        if len(health_matches) >= 3 and len(tech_matches) <= 2:
            has_domain_mismatch = True
            domain_mismatch_reason = (
                "Severe content domain mismatch: Question content consists of health/biology questions "
                "instead of matching the stated Computer Science / Cloud Computing course."
            )
            quality_issues.append(domain_mismatch_reason)

    quality_summary = "POOR" if quality_insufficient else "GOOD"
    return ProcessedDocument(
        request_id=request_id,
        safe_filename=safe_filename,
        extension=ext,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        sha256=sha256_hex,
        is_pdf=True,
        page_count=page_count,
        sampled_page_numbers=[i + 1 for i in sampled_indices],
        visual_pages=visual_pages,
        pdf_page_texts=page_texts,
        total_extracted_chars=total_chars,
        is_scanned_pdf=is_scanned,
        quality_insufficient=quality_insufficient,
        quality_issues=quality_issues,
        quality_summary=quality_summary,
        aspect_ratio=first_aspect,
        has_placeholder_text=has_placeholder,
        placeholder_matches=cleaned_hits,
        has_domain_mismatch=has_domain_mismatch,
        domain_mismatch_reason=domain_mismatch_reason,
    )
