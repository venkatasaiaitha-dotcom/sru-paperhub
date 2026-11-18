"""Human-Like AI Examiner powered by Google Gemini Interactions API and deterministic SRU scoring."""

import base64
import hashlib
import json
import logging
import os
import random
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from google import genai

try:
    from .document_processor import (
        DocumentValidationError,
        ProcessedDocument,
        process_uploaded_document,
    )
    from .prompt_loader import build_examiner_system_instruction
    from .sru_rules import (
        DECISIONS,
        EVIDENCE_STATUSES,
        NON_EXAM_DOCUMENT_TYPES,
        STRUCTURAL_STATUSES,
        SRUValidationConfig,
        load_reference_profiles,
        matches_sru_institution,
    )
except (ImportError, ValueError):
    from document_processor import (
        DocumentValidationError,
        ProcessedDocument,
        process_uploaded_document,
    )
    from prompt_loader import build_examiner_system_instruction
    from sru_rules import (
        DECISIONS,
        EVIDENCE_STATUSES,
        NON_EXAM_DOCUMENT_TYPES,
        STRUCTURAL_STATUSES,
        SRUValidationConfig,
        load_reference_profiles,
        matches_sru_institution,
    )


logger = logging.getLogger("sru.examiner")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"
ASSESSMENT_APPROVED_TEXT = (
    "The document is consistent with expected SRU question-paper characteristics."
)
ASSESSMENT_REJECTED_TEXT = (
    "The document is not consistent with expected SRU question-paper characteristics."
)
ASSESSMENT_REVIEW_TEXT = (
    "Automated verification could not conclusively determine whether this paper is consistent with expected SRU question-paper characteristics; human review is recommended."
)
AI_UNAVAILABLE_MESSAGE = "AI verification is temporarily unavailable. Please try again."
POOR_QUALITY_MESSAGE = "Document quality is insufficient for reliable automated verification."


EXAMINER_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "enum": [
                "question_paper",
                "other_university_paper",
                "class_notes",
                "assignment",
                "lab_record",
                "syllabus",
                "answer_key",
                "poster_flyer",
                "non_academic_image",
                "corrupted_unreadable",
                "unknown",
            ],
        },
        "is_exam_paper": {"type": "boolean"},
        "institution": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "status": {"type": "string", "enum": list(EVIDENCE_STATUSES)},
            },
            "required": ["name", "status"],
        },
        "metadata": {
            "type": "object",
            "properties": {
                "course_code": {"type": "string"},
                "subject_code": {"type": "string"},
                "subject_name": {"type": "string"},
                "regulation": {"type": "string"},
                "academic_year": {"type": "string"},
                "branch": {"type": "string"},
                "year": {"type": "string"},
                "semester": {"type": "string"},
                "exam_type": {"type": "string"},
                "course_coordinator": {"type": "string"},
                "date": {"type": "string"},
                "duration": {"type": "string"},
                "max_marks": {"type": "string"},
            },
            "required": [
                "course_code",
                "subject_code",
                "subject_name",
                "regulation",
                "academic_year",
                "branch",
                "year",
                "semester",
                "exam_type",
            ],
        },
        "structural_analysis": {
            "type": "object",
            "properties": {
                "header": {"type": "string", "enum": list(STRUCTURAL_STATUSES)},
                "instructions": {"type": "string", "enum": list(STRUCTURAL_STATUSES)},
                "question_numbering": {"type": "string", "enum": list(STRUCTURAL_STATUSES)},
                "marks_distribution": {"type": "string", "enum": list(STRUCTURAL_STATUSES)},
                "sections": {"type": "string", "enum": list(STRUCTURAL_STATUSES)},
                "footer": {"type": "string", "enum": list(STRUCTURAL_STATUSES)},
                "overall_layout": {"type": "string", "enum": list(STRUCTURAL_STATUSES)},
            },
            "required": [
                "header",
                "instructions",
                "question_numbering",
                "marks_distribution",
                "sections",
                "footer",
                "overall_layout",
            ],
        },
        "quality_assessment": {
            "type": "object",
            "properties": {
                "is_readable": {"type": "boolean"},
                "quality_level": {"type": "string", "enum": ["GOOD", "FAIR", "POOR"]},
                "issues": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["is_readable", "quality_level", "issues"],
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "status": {"type": "string", "enum": list(EVIDENCE_STATUSES)},
                    "observation": {"type": "string"},
                },
                "required": ["category", "status", "observation"],
            },
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
                    "issue": {"type": "string"},
                },
                "required": ["severity", "issue"],
            },
        },
        "suspicious_signals": {
            "type": "array",
            "items": {"type": "string"},
        },
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": [
        "document_type",
        "is_exam_paper",
        "institution",
        "metadata",
        "structural_analysis",
        "evidence",
        "issues",
        "decision",
        "confidence",
        "reason",
    ],
}


class GeminiServiceUnavailableError(Exception):
    """Raised when Gemini API is missing configuration, unreachable, timed out, or malformed."""

    def __init__(self, message: str = AI_UNAVAILABLE_MESSAGE, error_category: str = "AI_UNAVAILABLE"):
        super().__init__(message)
        self.message = message
        self.error_category = error_category


def _extract_interaction_text(interaction: Any) -> str:
    """Safely extract response text from a Gemini Interaction object."""
    text = getattr(interaction, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    steps = getattr(interaction, "steps", None) or []
    parts: List[str] = []
    for step in reversed(steps):
        if getattr(step, "type", None) == "model_output":
            for block in getattr(step, "content", None) or []:
                block_text = getattr(block, "text", None)
                if isinstance(block_text, str) and block_text.strip():
                    parts.append(block_text.strip())
            if parts:
                break
    return "\n".join(parts).strip()


def _parse_and_normalize_ai_json(raw_text: str) -> Dict[str, Any]:
    """Parse strict JSON from Gemini output and normalize all fields against schema defaults."""
    if not raw_text or not isinstance(raw_text, str):
        raise ValueError("Empty AI response")

    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("AI response JSON must be an object")

    doc_type = str(parsed.get("document_type") or "unknown").strip().lower()
    is_exam_paper = bool(parsed.get("is_exam_paper", False))

    raw_inst = parsed.get("institution") if isinstance(parsed.get("institution"), dict) else {}
    inst_status = str(raw_inst.get("status") or "UNCERTAIN").strip().upper()
    if inst_status not in EVIDENCE_STATUSES:
        inst_status = "UNCERTAIN"
    institution = {
        "name": str(raw_inst.get("name") or "").strip(),
        "status": inst_status,
    }

    raw_meta = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
    meta_keys = (
        "course_code",
        "subject_code",
        "subject_name",
        "regulation",
        "academic_year",
        "branch",
        "year",
        "semester",
        "exam_type",
        "course_coordinator",
        "date",
        "duration",
        "max_marks",
    )
    metadata = {k: str(raw_meta.get(k) or "").strip() for k in meta_keys}

    raw_struct = (
        parsed.get("structural_analysis")
        if isinstance(parsed.get("structural_analysis"), dict)
        else {}
    )
    struct_keys = (
        "header",
        "instructions",
        "question_numbering",
        "marks_distribution",
        "sections",
        "footer",
        "overall_layout",
    )
    structural_analysis: Dict[str, str] = {}
    for key in struct_keys:
        val = str(raw_struct.get(key) or "UNCERTAIN").strip().upper()
        structural_analysis[key] = val if val in STRUCTURAL_STATUSES else "UNCERTAIN"

    raw_qual = (
        parsed.get("quality_assessment")
        if isinstance(parsed.get("quality_assessment"), dict)
        else {}
    )
    quality_level = str(raw_qual.get("quality_level") or "GOOD").strip().upper()
    if quality_level not in ("GOOD", "FAIR", "POOR"):
        quality_level = "GOOD"
    quality_assessment = {
        "is_readable": bool(raw_qual.get("is_readable", True)),
        "quality_level": quality_level,
        "issues": [str(x).strip() for x in (raw_qual.get("issues") or []) if str(x).strip()][:10],
    }

    evidence: List[Dict[str, str]] = []
    for item in parsed.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "UNCERTAIN").strip().upper()
        if status not in EVIDENCE_STATUSES:
            status = "UNCERTAIN"
        obs = str(item.get("observation") or "").strip()
        cat = str(item.get("category") or "general").strip()
        if obs:
            evidence.append({"category": cat, "status": status, "observation": obs})

    issues: List[Dict[str, str]] = []
    for item in parsed.get("issues") or []:
        if isinstance(item, dict):
            sev = str(item.get("severity") or "MEDIUM").strip().upper()
            if sev not in ("LOW", "MEDIUM", "HIGH"):
                sev = "MEDIUM"
            msg = str(item.get("issue") or "").strip()
            if msg:
                issues.append({"severity": sev, "issue": msg})
        elif isinstance(item, str) and item.strip():
            issues.append({"severity": "MEDIUM", "issue": item.strip()})

    suspicious_signals = [
        str(x).strip() for x in (parsed.get("suspicious_signals") or []) if str(x).strip()
    ]

    ai_decision = str(parsed.get("decision") or "HUMAN_REVIEW").strip().upper()
    if ai_decision == "APPROVED":
        ai_decision = "APPROVE"
    elif ai_decision == "REJECTED":
        ai_decision = "REJECT"
    elif ai_decision not in DECISIONS:
        ai_decision = "HUMAN_REVIEW"

    try:
        ai_conf = float(parsed.get("confidence", 0.5))
        if ai_conf > 1.0:
            ai_conf = ai_conf / 100.0
        ai_conf = round(max(0.0, min(1.0, ai_conf)), 4)
    except (TypeError, ValueError):
        ai_conf = 0.5

    reason = str(parsed.get("reason") or "").strip()

    return {
        "document_type": doc_type,
        "is_exam_paper": is_exam_paper,
        "institution": institution,
        "metadata": metadata,
        "structural_analysis": structural_analysis,
        "quality_assessment": quality_assessment,
        "evidence": evidence,
        "issues": issues,
        "suspicious_signals": suspicious_signals,
        "decision": ai_decision,
        "confidence": ai_conf,
        "reason": reason,
    }


def _build_document_context_prompt(doc: ProcessedDocument) -> str:
    """Build concise multi-page context describing the preprocessed document for Gemini."""
    lines = [
        f"Document Summary: format={'PDF' if doc.is_pdf else 'Image'}, "
        f"total_pages={doc.page_count}, visually_attached_pages={doc.sampled_page_numbers}, "
        f"image_quality_signal={doc.quality_summary}, aspect_ratio={doc.aspect_ratio}.",
        "Inspect all visually attached page images carefully as your primary source of truth. "
        "Do not assume text alone tells the whole story.",
    ]
    if doc.is_pdf:
        lines.append(
            f"PDF extraction metadata: is_scanned={doc.is_scanned_pdf}, total_extracted_chars={doc.total_extracted_chars}."
        )
        text_pages = [p for p in doc.pdf_page_texts if p.get("text")]
        if text_pages:
            lines.append("Extracted PDF text by page (for cross-page verification across all pages):")
            for page_info in text_pages:
                snippet = page_info["text"]
                if len(text_pages) > 5 and page_info["page"] not in (1, 2, doc.page_count):
                    snippet = snippet[:2200]
                lines.append(f"--- Page {page_info['page']} of {doc.page_count} ---\n{snippet}")
        else:
            lines.append("No selectable PDF text layer was found; rely directly on visual page inspection.")
    elif doc.visual_pages:
        vp = doc.visual_pages[0]
        lines.append(
            f"Image diagnostics: width={vp.width}px, height={vp.height}px, sharpness={vp.sharpness}, brightness={vp.brightness}."
        )
    return "\n\n".join(lines)


class GeminiExaminerClient:
    """Thread-safe Gemini Interactions API wrapper with retries, backoff, timeouts, and strict JSON parsing."""

    def __init__(self, config: SRUValidationConfig):
        self.config = config
        self._client_lock = threading.Lock()
        self._cached_api_key: Optional[str] = None
        self._client: Optional[genai.Client] = None

    def get_model_name(self) -> str:
        return os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL

    def _get_client(self) -> genai.Client:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise GeminiServiceUnavailableError(
                AI_UNAVAILABLE_MESSAGE, error_category="MISSING_API_KEY"
            )
        with self._client_lock:
            if self._client is None or self._cached_api_key != api_key:
                self._client = genai.Client(api_key=api_key)
                self._cached_api_key = api_key
            return self._client

    def _classify_exception(self, exc: Exception) -> Tuple[bool, str]:
        """Classify exception as (is_retryable, category_code) without exposing secret details."""
        msg = str(exc).lower()
        name = type(exc).__name__.lower()
        if "timeout" in name or "timed out" in msg:
            return True, "TIMEOUT"
        if "429" in msg or "rate" in msg or "quota" in msg or "resource_exhausted" in msg:
            return True, "RATE_LIMIT_OR_QUOTA"
        if any(code in msg for code in ("500", "502", "503", "504", "unavailable", "internal")):
            return True, "UPSTREAM_5XX"
        if any(code in msg for code in ("connection", "network", "dns", "reset", "broken pipe")):
            return True, "NETWORK_ERROR"
        if any(code in msg for code in ("401", "403", "api_key", "permission", "unauthorized")):
            return False, "AUTH_ERROR"
        if "400" in msg or "invalid_argument" in msg:
            return False, "INVALID_REQUEST"
        if isinstance(exc, (json.JSONDecodeError, ValueError)):
            return True, "MALFORMED_AI_OUTPUT"
        return False, "AI_CLIENT_ERROR"

    def analyze_document(
        self,
        doc: ProcessedDocument,
        user_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """Send preprocessed visual pages and context to Gemini Interactions API with retries and fallback."""
        client = self._get_client()
        primary_model = self.get_model_name()
        candidates: List[str] = [primary_model]
        for fallback in ("gemini-3.5-flash-lite", "gemini-3.8-flash"):
            if fallback not in candidates:
                candidates.append(fallback)

        profiles = load_reference_profiles(self.config.reference_profiles_dir)
        system_instruction = build_examiner_system_instruction(
            config=self.config,
            user_metadata=user_metadata,
            profiles=profiles,
        )

        input_blocks: List[Dict[str, Any]] = [
            {"type": "text", "text": _build_document_context_prompt(doc)}
        ]
        resolution = "high" if len(doc.visual_pages) <= 3 else "medium"
        for page in doc.visual_pages:
            input_blocks.append(
                {
                    "type": "image",
                    "data": base64.b64encode(page.image_bytes).decode("ascii"),
                    "mime_type": page.mime_type,
                    "resolution": resolution,
                }
            )

        last_category = "AI_UNAVAILABLE"
        attempts = self.config.max_retries + 1

        for model_idx, candidate_model in enumerate(candidates):
            for attempt in range(attempts):
                try:
                    interaction = client.interactions.create(
                        model=candidate_model,
                        system_instruction=system_instruction,
                        input=input_blocks,
                        response_format={
                            "type": "text",
                            "mime_type": "application/json",
                            "schema": EXAMINER_JSON_SCHEMA,
                        },
                        generation_config={
                            "temperature": 0.1,
                            "max_output_tokens": 2500,
                        },
                        store=False,
                        timeout=float(self.config.timeout_seconds),
                    )
                    raw_text = _extract_interaction_text(interaction)
                    normalized = _parse_and_normalize_ai_json(raw_text)
                    return normalized, candidate_model
                except GeminiServiceUnavailableError:
                    raise
                except Exception as exc:
                    retryable, category = self._classify_exception(exc)
                    last_category = category
                    logger.warning(
                        "Gemini interaction attempt %d/%d on '%s' failed: %s (%s)",
                        attempt + 1,
                        attempts,
                        candidate_model,
                        category,
                        type(exc).__name__,
                    )
                    if not retryable:
                        raise GeminiServiceUnavailableError(
                            AI_UNAVAILABLE_MESSAGE, error_category=last_category
                        )
                    if attempt < attempts - 1:
                        delay = min(4.0, 0.6 * (2 ** attempt) + random.uniform(0.05, 0.25))
                        time.sleep(delay)
                    else:
                        if model_idx < len(candidates) - 1:
                            logger.info(
                                "Switching to fallback model '%s'...",
                                candidates[model_idx + 1],
                            )

        raise GeminiServiceUnavailableError(
            AI_UNAVAILABLE_MESSAGE, error_category=last_category
        )


def _norm_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _is_clean_metadata_mismatch(submitted: str, extracted: str, field_name: str) -> Optional[str]:
    """Compare optional student-entered metadata against paper metadata without overly brittle rules."""
    sub_clean = (submitted or "").strip()
    ext_clean = (extracted or "").strip()
    if not sub_clean or not ext_clean:
        return None

    sub_tok = _norm_token(sub_clean)
    ext_tok = _norm_token(ext_clean)
    if not sub_tok or not ext_tok:
        return None

    if field_name in ("course_code", "subject_code"):
        if sub_tok == ext_tok:
            return None
        # Allow prefix/substring when one is shorthand unless both are distinct full course codes
        if len(sub_tok) >= 4 and len(ext_tok) >= 4 and (sub_tok in ext_tok or ext_tok in sub_tok):
            return f"Partial {field_name.replace('_', ' ')} variation ('{sub_clean}' vs '{ext_clean}')."
        return f"Submitted {field_name.replace('_', ' ')} '{sub_clean}' does not match document '{ext_clean}'."

    if field_name == "regulation":
        sub_r = re.search(r"R\d{2}", sub_tok)
        ext_r = re.search(r"R\d{2}", ext_tok)
        if sub_r and ext_r and sub_r.group(0) != ext_r.group(0):
            return f"Submitted regulation '{sub_r.group(0)}' contradicts document '{ext_r.group(0)}'."
    return None


def score_and_decide(
    ai_result: Dict[str, Any],
    doc: ProcessedDocument,
    config: SRUValidationConfig,
    user_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Combine AI examiner findings, local visual diagnostics, and SRU rules into a final verdict."""
    evidence = list(ai_result.get("evidence") or [])
    issues = list(ai_result.get("issues") or [])
    suspicious_signals = list(ai_result.get("suspicious_signals") or [])
    struct = ai_result.get("structural_analysis") or {}
    meta = ai_result.get("metadata") or {}
    inst = ai_result.get("institution") or {}
    quality = ai_result.get("quality_assessment") or {}

    doc_type = str(ai_result.get("document_type") or "unknown").lower()
    is_exam = bool(ai_result.get("is_exam_paper", False))
    inst_name = str(inst.get("name") or "").strip()
    inst_status = str(inst.get("status") or "UNCERTAIN").upper()

    # Cross-check submitted form metadata against extracted document metadata cleanly
    meta_contradictions = 0
    if user_metadata:
        form_code = user_metadata.get("subjectCode") or user_metadata.get("course_code") or ""
        doc_code = meta.get("course_code") or meta.get("subject_code") or ""
        code_mismatch = _is_clean_metadata_mismatch(str(form_code), doc_code, "course_code")
        if code_mismatch:
            # Informational only: student dropdown defaults or shorthand must not reject genuine papers
            issues.append({"severity": "LOW", "issue": code_mismatch})
            evidence.append(
                {"category": "metadata_alignment", "status": "PRESENT", "observation": f"Paper course code '{doc_code}' is prioritized over form input '{form_code}'."}
            )

        form_reg = user_metadata.get("regulation") or ""
        reg_mismatch = _is_clean_metadata_mismatch(str(form_reg), meta.get("regulation", ""), "regulation")
        if reg_mismatch:
            issues.append({"severity": "LOW", "issue": reg_mismatch})
            evidence.append(
                {"category": "regulation_alignment", "status": "PRESENT", "observation": f"Paper regulation '{meta.get('regulation')}' is prioritized over form input '{form_reg}'."}
            )

    # 1. Document Identity Score
    if is_exam and doc_type == "question_paper":
        identity_score = 1.0
    elif is_exam and doc_type == "unknown":
        identity_score = 0.65
    elif doc_type in NON_EXAM_DOCUMENT_TYPES or not is_exam:
        identity_score = 0.0
    else:
        identity_score = 0.35

    # 2. SRU Institution & Metadata Evidence Score (tolerant of missing optional fields)
    is_sru_name = matches_sru_institution(inst_name, config)
    if inst_status == "CONTRADICTORY":
        inst_score = 0.0
    elif inst_status == "PRESENT" and (is_sru_name or not inst_name):
        inst_score = 1.0
    elif inst_status == "PRESENT" and not is_sru_name:
        inst_score = 0.0
        inst_status = "CONTRADICTORY"
        issues.append(
            {"severity": "HIGH", "issue": f"Institution '{inst_name}' is not SR University."}
        )
    elif inst_status == "UNCERTAIN":
        inst_score = 0.45
    else:
        inst_score = 0.25

    core_present = sum(1 for k in config.expected_core_fields if str(meta.get(k) or "").strip())
    ctx_present = sum(1 for k in config.expected_contextual_fields if str(meta.get(k) or "").strip())
    core_ratio = core_present / max(1, len(config.expected_core_fields))
    ctx_ratio = ctx_present / max(1, len(config.expected_contextual_fields))
    metadata_fields_score = min(1.0, (0.70 * core_ratio) + (0.30 * min(1.0, ctx_ratio * 1.4)))
    sru_metadata_score = (0.52 * inst_score) + (0.48 * metadata_fields_score)

    # 3. Structural Score
    struct_map = {
        "VALID": 1.0,
        "PARTIAL": 0.68,
        "NOT_APPLICABLE": 0.72,
        "UNCERTAIN": 0.42,
        "MISSING": 0.25,
        "INVALID": 0.0,
    }
    struct_weights = {
        "header": 0.20,
        "instructions": 0.12,
        "question_numbering": 0.20,
        "marks_distribution": 0.16,
        "sections": 0.12,
        "footer": 0.05,
        "overall_layout": 0.15,
    }
    structural_score = sum(
        struct_weights[k] * struct_map.get(struct.get(k, "UNCERTAIN"), 0.4)
        for k in struct_weights
    )

    # 4. Visual / Layout & Quality Score
    layout_val = struct_map.get(struct.get("overall_layout", "UNCERTAIN"), 0.5)
    local_quality_factor = 0.25 if doc.quality_insufficient else 1.0
    ai_quality_factor = 0.30 if (not quality.get("is_readable", True) or quality.get("quality_level") == "POOR") else (
        0.75 if quality.get("quality_level") == "FAIR" else 1.0
    )
    visual_layout_score = layout_val * min(local_quality_factor, ai_quality_factor)

    # 5. Question Paper Evidence Score
    qp_val = (
        0.45 * struct_map.get(struct.get("question_numbering", "UNCERTAIN"), 0.4)
        + 0.35 * struct_map.get(struct.get("marks_distribution", "UNCERTAIN"), 0.4)
        + 0.20 * struct_map.get(struct.get("sections", "UNCERTAIN"), 0.4)
    )
    question_paper_score = qp_val if is_exam else 0.0

    # 6. Consistency Score
    contradictory_evidence_count = sum(1 for e in evidence if e.get("status") == "CONTRADICTORY")
    uncertain_evidence_count = sum(1 for e in evidence if e.get("status") == "UNCERTAIN")
    high_issues = sum(1 for i in issues if i.get("severity") == "HIGH")
    medium_issues = sum(1 for i in issues if i.get("severity") == "MEDIUM")

    consistency_score = max(
        0.0,
        1.0
        - (0.35 * contradictory_evidence_count)
        - (0.25 * meta_contradictions)
        - (0.12 * high_issues)
        - (0.06 * uncertain_evidence_count),
    )

    # Compute Weighted Raw Score and Penalties
    weights = config.scoring_weights
    positive_score = (
        weights["document_identity"] * identity_score
        + weights["sru_metadata"] * sru_metadata_score
        + weights["structural"] * structural_score
        + weights["visual_layout"] * visual_layout_score
        + weights["question_paper_evidence"] * question_paper_score
        + weights["consistency"] * consistency_score
    )

    penalties_cfg = config.penalties
    total_penalty = (
        high_issues * penalties_cfg["high_issue"] * 0.6
        + medium_issues * penalties_cfg["medium_issue"]
        + contradictory_evidence_count * penalties_cfg["contradiction"] * 0.7
        + len(suspicious_signals) * penalties_cfg["suspicious_signal"]
    )
    if quality.get("quality_level") == "POOR" or doc.quality_insufficient:
        total_penalty += penalties_cfg["poor_quality"]

    # Blend carefully with calibrated backend score (AI confidence never overrides hard evidence)
    ai_conf = float(ai_result.get("confidence", 0.5))
    final_score = round(max(0.0, min(1.0, positive_score - total_penalty)), 4)

    # Hard Backend Decision Guardrails (Section 7, 10, 19, 24, 26)
    poor_quality_flag = (
        doc.quality_insufficient
        or not quality.get("is_readable", True)
        or quality.get("quality_level") == "POOR"
        or doc_type == "corrupted_unreadable"
    )
    clear_non_paper = (
        doc_type in NON_EXAM_DOCUMENT_TYPES
        or (not is_exam and doc_type != "corrupted_unreadable" and not poor_quality_flag)
    )
    has_other_university = doc_type == "other_university_paper" or (
        inst_status == "CONTRADICTORY" and bool(inst_name) and not is_sru_name
    )
    has_anti_bypass = len(suspicious_signals) > 0 and (
        not is_exam or high_issues > 0 or contradictory_evidence_count > 0
    )

    final_decision: str
    final_reason = ai_result.get("reason") or ""

    is_genuine_sru_exam = (
        is_exam
        and doc_type == "question_paper"
        and inst_status in ("PRESENT", "UNCERTAIN")
        and (is_sru_name or inst_status == "PRESENT")
        and not has_other_university
        and not clear_non_paper
        and not poor_quality_flag
        and len(suspicious_signals) == 0
        and high_issues == 0
    )

    if has_other_university or (clear_non_paper and not poor_quality_flag):
        final_decision = "REJECT"
    elif has_anti_bypass and (final_score < config.approve_threshold or contradictory_evidence_count >= 1):
        final_decision = "REJECT"
    elif poor_quality_flag:
        final_decision = "HUMAN_REVIEW"
        if POOR_QUALITY_MESSAGE.lower() not in final_reason.lower():
            extra = "; ".join(doc.quality_issues or quality.get("issues") or [])
            final_reason = (
                f"{POOR_QUALITY_MESSAGE} ({extra})" if extra else POOR_QUALITY_MESSAGE
            )
    elif high_issues > 0 or contradictory_evidence_count > 0:
        if final_score < config.reject_threshold:
            final_decision = "REJECT"
        else:
            final_decision = "HUMAN_REVIEW"
    elif is_genuine_sru_exam and (
        final_score >= config.approve_threshold
        or ai_result.get("decision") == "APPROVE"
        or final_score >= 0.58
    ):
        final_decision = "APPROVE"
    elif final_score >= config.approve_threshold and is_exam and inst_status in ("PRESENT", "UNCERTAIN") and (is_sru_name or inst_status == "PRESENT"):
        # Require at least SR University institution evidence and zero suspicious bypass flags
        if inst_status == "PRESENT" and len(suspicious_signals) == 0 and high_issues == 0 and contradictory_evidence_count == 0:
            final_decision = "APPROVE"
        else:
            final_decision = "HUMAN_REVIEW"
    elif ai_result.get("decision") == "REJECT" and final_score < config.approve_threshold:
        final_decision = "REJECT"
    elif ai_result.get("decision") == "HUMAN_REVIEW":
        final_decision = "HUMAN_REVIEW" if final_score >= config.reject_threshold else "REJECT"
    elif final_score < config.reject_threshold:
        final_decision = "REJECT"
    else:
        final_decision = "HUMAN_REVIEW"

    # Build explainable checkmarks & concerns without internal CoT
    highlights: List[str] = []
    concerns: List[str] = []

    if inst_status == "PRESENT" and (is_sru_name or not inst_name):
        highlights.append("SR University identification")
    elif inst_status == "CONTRADICTORY":
        concerns.append(f"Institution mismatch ({inst_name or 'Non-SRU institution'})")
    else:
        concerns.append("SR University header identification is unclear")

    if is_exam and struct.get("header") in ("VALID", "PARTIAL"):
        highlights.append("Valid examination header & structure")
    elif not is_exam:
        concerns.append(f"Document appears to be '{doc_type.replace('_', ' ')}' rather than a question paper")

    if meta.get("course_code") or meta.get("subject_code"):
        highlights.append(f"Course code ({meta.get('course_code') or meta.get('subject_code')})")
    if meta.get("subject_name"):
        highlights.append(f"Subject information ({meta['subject_name']})")
    if struct.get("question_numbering") == "VALID":
        highlights.append("Consistent question numbering")
    if struct.get("marks_distribution") in ("VALID", "PARTIAL"):
        highlights.append("Consistent marks distribution")

    for iss in issues:
        msg = iss.get("issue", "").strip()
        if msg and msg not in concerns:
            concerns.append(msg)
    for sig in suspicious_signals:
        if sig not in concerns:
            concerns.append(sig)
    for q_iss in doc.quality_issues:
        if q_iss not in concerns:
            concerns.append(q_iss)

    if final_decision == "APPROVE":
        assessment = ASSESSMENT_APPROVED_TEXT
        if not final_reason:
            final_reason = ASSESSMENT_APPROVED_TEXT
        calibrated_conf = round(max(final_score, min(0.99, (final_score + ai_conf) / 2.0)), 4)
    elif final_decision == "REJECT":
        assessment = ASSESSMENT_REJECTED_TEXT
        if not final_reason:
            final_reason = concerns[0] if concerns else ASSESSMENT_REJECTED_TEXT
        calibrated_conf = round(min(0.99, max(ai_conf, 1.0 - final_score)), 4)
    else:
        assessment = ASSESSMENT_REVIEW_TEXT
        if not final_reason:
            final_reason = concerns[0] if concerns else ASSESSMENT_REVIEW_TEXT
        calibrated_conf = round(max(0.25, min(0.85, final_score)), 4)

    return {
        "decision": final_decision,
        "confidence": calibrated_conf,
        "score": final_score,
        "score_breakdown": {
            "document_identity": round(identity_score, 3),
            "sru_metadata": round(sru_metadata_score, 3),
            "structural": round(structural_score, 3),
            "visual_layout": round(visual_layout_score, 3),
            "question_paper_evidence": round(question_paper_score, 3),
            "consistency": round(consistency_score, 3),
            "penalties": round(total_penalty, 3),
        },
        "reason": final_reason,
        "assessment_statement": assessment,
        "document_type": doc_type,
        "is_exam_paper": is_exam,
        "institution": {
            "name": inst_name or ("SR University" if inst_status == "PRESENT" else ""),
            "status": inst_status,
        },
        "metadata": meta,
        "structural_analysis": struct,
        "evidence": evidence[:20],
        "issues": issues[:15],
        "highlights": highlights[:8],
        "concerns": concerns[:8],
        "document_info": {
            "page_count": doc.page_count,
            "sampled_pages": doc.sampled_page_numbers,
            "is_pdf": doc.is_pdf,
            "is_scanned": doc.is_scanned_pdf if doc.is_pdf else False,
            "quality": doc.quality_summary,
            "sha256": doc.sha256,
        },
    }


class AIExaminerService:
    """Orchestrates validation, preprocessing, Gemini AI reasoning, scoring, caching, and privacy logging."""

    def __init__(self, base_dir: str = "", gemini_client: Optional[GeminiExaminerClient] = None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config = SRUValidationConfig.from_env(self.base_dir)
        self.gemini_client = gemini_client or GeminiExaminerClient(self.config)
        self._cache_lock = threading.Lock()
        self._verdict_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._cache_ttl_seconds = 900

    def _reload_runtime_config(self) -> None:
        self.config = SRUValidationConfig.from_env(self.base_dir)
        self.gemini_client.config = self.config

    def _cache_key(self, sha256_hex: str, user_metadata: Optional[Dict[str, Any]]) -> str:
        meta_json = json.dumps(user_metadata or {}, sort_keys=True, ensure_ascii=True)
        meta_hash = hashlib.sha256(meta_json.encode("utf-8")).hexdigest()[:16]
        return f"{sha256_hex}:{meta_hash}:{self.gemini_client.get_model_name()}"

    def _get_cached_verdict(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._cache_lock:
            entry = self._verdict_cache.get(key)
            if not entry:
                return None
            expires_at, verdict = entry
            if now >= expires_at:
                self._verdict_cache.pop(key, None)
                return None
            copied = json.loads(json.dumps(verdict))
            copied["cached"] = True
            return copied

    def _set_cached_verdict(self, key: str, verdict: Dict[str, Any]) -> None:
        with self._cache_lock:
            if len(self._verdict_cache) >= 128:
                oldest_key = min(self._verdict_cache.items(), key=lambda item: item[1][0])[0]
                self._verdict_cache.pop(oldest_key, None)
            self._verdict_cache[key] = (
                time.time() + self._cache_ttl_seconds,
                json.loads(json.dumps(verdict)),
            )

    def _log_audit(
        self,
        request_id: str,
        doc: Optional[ProcessedDocument],
        duration_ms: int,
        decision: str = "ERROR",
        score: float = 0.0,
        cached: bool = False,
        error_category: str = "NONE",
    ) -> None:
        """Emit metadata-only audit logs with zero document contents or secrets."""
        ext = doc.extension if doc else "unknown"
        size_bytes = doc.file_size_bytes if doc else 0
        pages = doc.page_count if doc else 0
        quality = doc.quality_summary if doc else "N/A"
        logger.info(
            "request_id=%s ext=%s size_bytes=%d pages=%d quality=%s decision=%s score=%.3f cached=%s duration_ms=%d error_category=%s",
            request_id,
            ext,
            size_bytes,
            pages,
            quality,
            decision,
            score,
            cached,
            duration_ms,
            error_category,
        )

    def examine_upload(
        self,
        file_bytes: bytes,
        filename: Optional[str],
        declared_mime: Optional[str] = None,
        user_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        """Execute full verification pipeline and return (http_status, api_payload)."""
        started = time.perf_counter()
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        self._reload_runtime_config()
        doc: Optional[ProcessedDocument] = None

        try:
            doc = process_uploaded_document(
                file_bytes=file_bytes,
                filename=filename,
                declared_mime=declared_mime,
                request_id=request_id,
                max_upload_mb=self.config.max_upload_mb,
                max_pdf_pages=self.config.max_pdf_pages,
            )
        except DocumentValidationError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            self._log_audit(request_id, None, elapsed, decision="REJECT", error_category=exc.error_code)
            return exc.status_code, {
                "success": False,
                "request_id": request_id,
                "error": exc.message,
                "error_code": exc.error_code,
                "verification": {
                    "decision": "REJECT",
                    "confidence": 0.0,
                    "score": 0.0,
                    "reason": exc.message,
                    "assessment_statement": ASSESSMENT_REJECTED_TEXT,
                    "document_type": "corrupted_unreadable",
                    "is_exam_paper": False,
                    "metadata": {},
                    "evidence": [],
                    "issues": [{"severity": "HIGH", "issue": exc.message}],
                    "concerns": [exc.message],
                    "highlights": [],
                },
            }

        # Cost & quality guard: unreadable raster scans/thumbnails go directly to HUMAN_REVIEW
        if doc.quality_insufficient:
            elapsed = int((time.perf_counter() - started) * 1000)
            reason = (
                f"{POOR_QUALITY_MESSAGE} ({'; '.join(doc.quality_issues)})"
                if doc.quality_issues
                else POOR_QUALITY_MESSAGE
            )
            verification = {
                "decision": "HUMAN_REVIEW",
                "confidence": 0.35,
                "score": 0.35,
                "score_breakdown": {
                    "document_identity": 0.0,
                    "sru_metadata": 0.0,
                    "structural": 0.0,
                    "visual_layout": 0.2,
                    "question_paper_evidence": 0.0,
                    "consistency": 0.0,
                    "penalties": 0.2,
                },
                "reason": reason,
                "assessment_statement": ASSESSMENT_REVIEW_TEXT,
                "document_type": "corrupted_unreadable",
                "is_exam_paper": False,
                "institution": {"name": "", "status": "UNCERTAIN"},
                "metadata": {},
                "structural_analysis": {
                    "header": "UNCERTAIN",
                    "instructions": "UNCERTAIN",
                    "question_numbering": "UNCERTAIN",
                    "marks_distribution": "UNCERTAIN",
                    "sections": "UNCERTAIN",
                    "footer": "UNCERTAIN",
                    "overall_layout": "UNCERTAIN",
                },
                "evidence": [
                    {
                        "category": "image_quality",
                        "status": "UNCERTAIN",
                        "observation": reason,
                    }
                ],
                "issues": [{"severity": "HIGH", "issue": msg} for msg in (doc.quality_issues or [POOR_QUALITY_MESSAGE])],
                "highlights": [],
                "concerns": doc.quality_issues or [POOR_QUALITY_MESSAGE],
                "document_info": {
                    "page_count": doc.page_count,
                    "sampled_pages": doc.sampled_page_numbers,
                    "is_pdf": doc.is_pdf,
                    "is_scanned": doc.is_scanned_pdf if doc.is_pdf else False,
                    "quality": doc.quality_summary,
                    "sha256": doc.sha256,
                },
                "model": self.gemini_client.get_model_name(),
                "cached": False,
                "duration_ms": elapsed,
            }
            self._log_audit(request_id, doc, elapsed, decision="HUMAN_REVIEW", score=0.35)
            return 200, {
                "success": True,
                "request_id": request_id,
                "verification": verification,
            }

        # Deduplicate repeated identical uploads in short TTL cache
        cache_key = self._cache_key(doc.sha256, user_metadata)
        cached_verdict = self._get_cached_verdict(cache_key)
        if cached_verdict is not None:
            elapsed = int((time.perf_counter() - started) * 1000)
            cached_verdict["duration_ms"] = elapsed
            self._log_audit(
                request_id,
                doc,
                elapsed,
                decision=cached_verdict["decision"],
                score=float(cached_verdict.get("score", 0.0)),
                cached=True,
            )
            return 200, {
                "success": True,
                "request_id": request_id,
                "verification": cached_verdict,
            }

        # Call Gemini Multimodal Examiner (never approves on failure!)
        try:
            ai_result, model_used = self.gemini_client.analyze_document(
                doc=doc,
                user_metadata=user_metadata,
            )
        except GeminiServiceUnavailableError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            self._log_audit(
                request_id, doc, elapsed, decision="UNAVAILABLE", error_category=exc.error_category
            )
            return 503, {
                "success": False,
                "request_id": request_id,
                "error": AI_UNAVAILABLE_MESSAGE,
                "error_code": exc.error_category,
                "verification": {
                    "decision": "HUMAN_REVIEW",
                    "confidence": 0.0,
                    "score": 0.0,
                    "reason": AI_UNAVAILABLE_MESSAGE,
                    "assessment_statement": AI_UNAVAILABLE_MESSAGE,
                    "document_type": "unknown",
                    "is_exam_paper": False,
                    "metadata": {},
                    "evidence": [],
                    "issues": [{"severity": "HIGH", "issue": AI_UNAVAILABLE_MESSAGE}],
                    "concerns": [AI_UNAVAILABLE_MESSAGE],
                    "highlights": [],
                },
            }

        verification = score_and_decide(
            ai_result=ai_result,
            doc=doc,
            config=self.config,
            user_metadata=user_metadata,
        )
        elapsed = int((time.perf_counter() - started) * 1000)
        verification["model"] = model_used
        verification["cached"] = False
        verification["duration_ms"] = elapsed

        logger.info(
            "VERIFY RESULT [%s]: decision=%s score=%.3f model=%s reason='%s' issues=%s",
            request_id,
            verification["decision"],
            verification["score"],
            model_used,
            verification.get("reason", "")[:120],
            [i.get("issue") for i in verification.get("issues", [])][:3],
        )

        self._set_cached_verdict(cache_key, verification)
        self._log_audit(
            request_id,
            doc,
            elapsed,
            decision=verification["decision"],
            score=verification["score"],
        )
        return 200, {
            "success": True,
            "request_id": request_id,
            "verification": verification,
        }


examiner_service = AIExaminerService()
