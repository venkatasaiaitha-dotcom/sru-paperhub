"""Configurable SR University validation rules, scoring weights, and reference profile loader."""

from dataclasses import dataclass, field
import json
import os
import re
from typing import Any, Dict, List


EVIDENCE_STATUSES = (
    "PRESENT",
    "MISSING",
    "UNCERTAIN",
    "CONTRADICTORY",
    "NOT_APPLICABLE",
)

STRUCTURAL_STATUSES = (
    "VALID",
    "PARTIAL",
    "MISSING",
    "INVALID",
    "UNCERTAIN",
    "NOT_APPLICABLE",
)

DECISIONS = ("APPROVE", "REJECT", "HUMAN_REVIEW")

DOCUMENT_TYPES = (
    "question_paper",
    "other_university_paper",
    "class_notes",
    "assignment",
    "lab_record",
    "syllabus",
    "answer_key",
    "poster_flyer",
    "non_academic_image",
    "dummy_placeholder_paper",
    "corrupted_unreadable",
    "unknown",
)

NON_EXAM_DOCUMENT_TYPES = {
    "other_university_paper",
    "class_notes",
    "assignment",
    "lab_record",
    "syllabus",
    "answer_key",
    "poster_flyer",
    "non_academic_image",
    "dummy_placeholder_paper",
    "domain_mismatched_paper",
}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class SRUValidationConfig:
    """Environment- and JSON-configurable SR University validation and scoring rules."""

    university_name: str = "SR University"
    university_aliases: List[str] = field(
        default_factory=lambda: [
            "SR University",
            "SR UNIVERSITY",
            "S R University",
            "S.R. University",
            "SRU",
            "SR University Warangal",
            "Ananthasagar",
            "SR Engineering College",
            "SREC",
            "SR Group",
            "School of Computer Science & AI",
            "School of Engineering",
        ]
    )
    expected_core_fields: List[str] = field(
        default_factory=lambda: [
            "course_code",
            "subject_name",
            "exam_type",
            "regulation",
            "academic_year",
        ]
    )
    expected_contextual_fields: List[str] = field(
        default_factory=lambda: [
            "subject_code",
            "branch",
            "year",
            "semester",
            "course_coordinator",
            "date",
            "duration",
            "max_marks",
        ]
    )
    known_regulations_regex: str = r"^R\d{2}$"
    course_code_regex: str = r"^[A-Z0-9]{4,16}$"
    approve_threshold: float = 0.65
    reject_threshold: float = 0.35
    timeout_seconds: int = 45
    max_retries: int = 2
    max_upload_mb: int = 15
    max_pdf_pages: int = 8
    rate_limit_per_min: int = 15
    reference_profiles_dir: str = ""
    scoring_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "document_identity": 0.24,
            "sru_metadata": 0.22,
            "structural": 0.18,
            "visual_layout": 0.12,
            "question_paper_evidence": 0.14,
            "consistency": 0.10,
        }
    )
    penalties: Dict[str, float] = field(
        default_factory=lambda: {
            "high_issue": 0.18,
            "medium_issue": 0.07,
            "contradiction": 0.16,
            "suspicious_signal": 0.22,
            "poor_quality": 0.20,
        }
    )

    @classmethod
    def from_env(cls, base_dir: str = "") -> "SRUValidationConfig":
        """Build configuration from defaults, optional JSON override file, and env vars."""
        cfg = cls()
        default_ref_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "references"
        )
        rules_override_path = os.environ.get("SRU_RULES_CONFIG_PATH", "").strip()
        if rules_override_path and os.path.isfile(rules_override_path):
            try:
                with open(rules_override_path, "r", encoding="utf-8") as handle:
                    override = json.load(handle)
                if isinstance(override, dict):
                    if isinstance(override.get("scoring_weights"), dict):
                        cfg.scoring_weights.update(override["scoring_weights"])
                    if isinstance(override.get("penalties"), dict):
                        cfg.penalties.update(override["penalties"])
                    for attr in (
                        "university_name",
                        "university_aliases",
                        "expected_core_fields",
                        "expected_contextual_fields",
                        "known_regulations_regex",
                        "course_code_regex",
                    ):
                        if attr in override:
                            setattr(cfg, attr, override[attr])
            except Exception:
                pass

        cfg.approve_threshold = max(
            0.50, min(0.95, _env_float("EXAMINER_APPROVE_THRESHOLD", cfg.approve_threshold))
        )
        cfg.reject_threshold = max(
            0.10, min(0.60, _env_float("EXAMINER_REJECT_THRESHOLD", cfg.reject_threshold))
        )
        cfg.timeout_seconds = max(10, _env_int("EXAMINER_TIMEOUT_SECONDS", cfg.timeout_seconds))
        cfg.max_retries = max(0, min(5, _env_int("EXAMINER_MAX_RETRIES", cfg.max_retries)))
        cfg.max_upload_mb = max(1, min(50, _env_int("EXAMINER_MAX_UPLOAD_MB", cfg.max_upload_mb)))
        cfg.max_pdf_pages = max(1, min(20, _env_int("EXAMINER_MAX_PDF_PAGES", cfg.max_pdf_pages)))
        cfg.rate_limit_per_min = max(
            1, min(120, _env_int("EXAMINER_RATE_LIMIT_PER_MIN", cfg.rate_limit_per_min))
        )

        ref_env = os.environ.get("SRU_REFERENCE_PROFILES_DIR", "").strip()
        if ref_env:
            if not os.path.isabs(ref_env) and base_dir:
                cfg.reference_profiles_dir = os.path.join(base_dir, ref_env)
            else:
                cfg.reference_profiles_dir = ref_env
        else:
            cfg.reference_profiles_dir = default_ref_dir
        return cfg


def load_reference_profiles(profiles_dir: str) -> List[Dict[str, Any]]:
    """Load configurable SRU characteristics & sample reference profiles from JSON files."""
    if not profiles_dir or not os.path.isdir(profiles_dir):
        return []
    profiles: List[Dict[str, Any]] = []
    for filename in sorted(os.listdir(profiles_dir)):
        if not filename.lower().endswith(".json"):
            continue
        full_path = os.path.join(profiles_dir, filename)
        try:
            with open(full_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                profiles.append(data)
        except Exception:
            continue
    return profiles


def summarize_reference_context(config: SRUValidationConfig, profiles: List[Dict[str, Any]]) -> str:
    """Produce concise SRU rule and reference profile guidance for the Gemini Examiner."""
    lines = [
        f"Institution: {config.university_name} (recognized aliases: {', '.join(config.university_aliases[:5])})",
        f"High-signal examination metadata fields (genuine papers may omit 1-2 contextual items): {', '.join(config.expected_core_fields)}",
        f"Additional contextual fields often present on SRU papers: {', '.join(config.expected_contextual_fields)}",
    ]
    for profile in profiles[:5]:
        name = profile.get("profile_name", "SRU Profile")
        notes = profile.get("characteristic_patterns", [])
        variations = profile.get("acceptable_variations", [])
        red_flags = profile.get("suspicious_red_flags", [])
        if notes:
            lines.append(f"[{name}] Structural expectations: " + "; ".join(str(x) for x in notes[:8]))
        if variations:
            lines.append(f"[{name}] Acceptable genuine variations: " + "; ".join(str(x) for x in variations[:6]))
        if red_flags:
            lines.append(f"[{name}] Red flags / bypass signs: " + "; ".join(str(x) for x in red_flags[:6]))
    return "\n".join(lines)


def matches_sru_institution(name: str, config: SRUValidationConfig) -> bool:
    """Check whether an identified institution name refers to SR University."""
    cleaned = re.sub(r"[^A-Z0-9\s]", " ", (name or "").upper()).strip()
    if not cleaned:
        return False
    if (
        "SR UNIVERSITY" in cleaned
        or "S R UNIVERSITY" in cleaned
        or cleaned == "SRU"
        or "SR ENGINEERING COLLEGE" in cleaned
        or "SREC" in cleaned
    ):
        return True
    for alias in config.university_aliases:
        alias_clean = re.sub(r"[^A-Z0-9\s]", " ", alias.upper()).strip()
        if alias_clean and alias_clean in cleaned and len(alias_clean) >= 3:
            return True
    return False
