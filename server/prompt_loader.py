"""Maintainable prompt template loader for the Human-Like AI Examiner."""

import os
from typing import Any, Dict, List, Optional

try:
    from .sru_rules import SRUValidationConfig, load_reference_profiles, summarize_reference_context
except (ImportError, ValueError):
    from sru_rules import SRUValidationConfig, load_reference_profiles, summarize_reference_context


DEFAULT_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "prompts", "examiner_prompt.txt"
)


def load_examiner_prompt_template(prompt_path: str = DEFAULT_PROMPT_PATH) -> str:
    """Load the backend examiner prompt template from disk."""
    with open(prompt_path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def build_examiner_system_instruction(
    config: SRUValidationConfig,
    user_metadata: Optional[Dict[str, Any]] = None,
    profiles: Optional[List[Dict[str, Any]]] = None,
    prompt_path: str = DEFAULT_PROMPT_PATH,
) -> str:
    """Render the complete system instruction with configurable SRU reference guidelines."""
    template = load_examiner_prompt_template(prompt_path)
    loaded_profiles = profiles if profiles is not None else load_reference_profiles(
        config.reference_profiles_dir
    )
    ref_context = summarize_reference_context(config, loaded_profiles)

    cleaned_meta = {
        k: str(v).strip()
        for k, v in (user_metadata or {}).items()
        if v is not None and str(v).strip()
    }
    if cleaned_meta:
        meta_lines = [
            "OPTIONAL STUDENT-ENTERED FORM DETAILS (Use only as contextual hints; prioritize actual document visual and textual evidence. If the document itself is a genuine SR University question paper, do NOT reject it merely because user-selected form values differ from the printed text — extract the true metadata directly from the document):"
        ]
        for key, value in sorted(cleaned_meta.items()):
            meta_lines.append(f"- {key}: {value}")
        user_context = "\n".join(meta_lines)
    else:
        user_context = (
            "SUBMITTED UPLOAD METADATA: None provided; evaluate strictly from the document itself."
        )

    return template.format(
        SRU_REFERENCE_CONTEXT=ref_context,
        USER_METADATA_CONTEXT=user_context,
    )
