"""
SR University Question Paper Verification & Duplicate Engine
Multi-Engine Validation: Google Gemini API (Multimodal) + PyMuPDF + Geometry + Heuristic OCR Fallback
"""

import os
import re
import json
import time
from io import BytesIO
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

# Official Google GenAI SDK integration
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    APIError = Exception
    GENAI_AVAILABLE = False


class VerificationEngine:
    def __init__(self):
        self.default_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()

    def get_gemini_client(self):
        """
        Safely instantiates Google GenAI client if API key is present in environment.
        """
        if not GENAI_AVAILABLE:
            return None
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None
        try:
            return genai.Client(api_key=api_key)
        except Exception as e:
            print(f"[VERIFIER] Gemini client initialization notice: {e}")
            return None

    def gemini_verify(self, file_bytes, mime_type, expected_code=None):
        """
        Multimodal analysis using Google Gemini API.
        Extracts institutional header, classifies document, and extracts question paper text.
        """
        client = self.get_gemini_client()
        if not client or not file_bytes:
            return None

        norm_mime = (mime_type or "image/jpeg").lower()
        if "pdf" in norm_mime:
            clean_mime = "application/pdf"
        elif "png" in norm_mime:
            clean_mime = "image/png"
        elif "webp" in norm_mime:
            clean_mime = "image/webp"
        else:
            clean_mime = "image/jpeg"

        prompt = (
            "You are the senior document intelligence verification engine for SR UNIVERSITY (Warangal, Telangana).\n"
            "Analyze the attached academic examination paper document.\n\n"
            "Evaluate strictly:\n"
            "1. Header Check: Is 'SR UNIVERSITY' or 'SR University Warangal' present in the upper box/header?\n"
            "2. Document Classification: Classify into strictly one category:\n"
            "   - 'QUESTION_PAPER': Authentic university examination paper (End Term, Mid Term / Re-Mid, Supplementary).\n"
            "   - 'CLASS_NOTES': Lecture notes, study summaries, student notebook pages.\n"
            "   - 'ASSIGNMENT': Student homework, tutorial sheets, solved assignments.\n"
            "   - 'LAB_RECORD': Laboratory manuals, observation notebooks, or experiment records.\n"
            "   - 'OTHER_UNIVERSITY': Question papers belonging to other universities (e.g., JNTUH, JNTUK, Osmania, Kakatiya).\n"
            "   - 'OTHER': Blank pages, textbooks, project reports, certificates, or unrelated non-examination images.\n"
            "3. Course Code: Extract the Course Code (e.g. 24CS301PC211, 22CS301, 20CS101, etc.).\n"
            "4. Subject Title: Extract the Subject Name / Course Title.\n"
            "5. Academic Regulation: Extract regulation (e.g. R24, R22, R20).\n"
            "6. Academic Year: Extract academic year (e.g. 2025-2026).\n"
            "7. Course Coordinator: Extract coordinator name if present.\n"
            "8. Questions & Content: Extract all questions, problem statements, and technical text.\n\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "is_sr_university": true/false,\n'
            '  "has_upperbox_sr_header": true/false,\n'
            '  "document_type": "QUESTION_PAPER"|"CLASS_NOTES"|"ASSIGNMENT"|"LAB_RECORD"|"OTHER_UNIVERSITY"|"OTHER",\n'
            '  "course_code": "extracted code or UNVERIFIED",\n'
            '  "subject_name": "extracted name or UNVERIFIED",\n'
            '  "regulation": "extracted regulation or UNVERIFIED",\n'
            '  "academic_year": "extracted year or UNVERIFIED",\n'
            '  "course_coordinator": "coordinator name or UNVERIFIED",\n'
            '  "confidence": integer 0-100,\n'
            '  "extracted_text_summary": "questions and text extracted from document",\n'
            '  "reason": "concise technical verification note"\n'
            "}"
        )

        try:
            part = types.Part.from_bytes(data=file_bytes, mime_type=clean_mime)
            model_to_use = self.default_model
            response = client.models.generate_content(
                model=model_to_use,
                contents=[part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            if response and response.text:
                clean_json_str = response.text.strip()
                if clean_json_str.startswith("```json"):
                    clean_json_str = clean_json_str[7:]
                if clean_json_str.endswith("```"):
                    clean_json_str = clean_json_str[:-3]
                parsed = json.loads(clean_json_str.strip())
                return parsed
        except Exception as e:
            print(f"[VERIFIER] Gemini multimodal call warning (falling back to local engine): {e}")
            return None

        return None

    def normalize_text(self, text):
        if not text:
            return ""
        t = re.sub(r"\s+", " ", str(text)).strip().upper()
        t = t.replace("–", "-").replace("—", "-")
        return t

    def normalize_code(self, code):
        if not code:
            return ""
        return re.sub(r"[^A-Z0-9]", "", self.normalize_text(code))

    def fuzzy_code_match(self, val1, val2):
        if not val1 or not val2:
            return False
        n1 = self.normalize_code(val1)
        n2 = self.normalize_code(val2)
        if n1 == n2 or n1 in n2 or n2 in n1:
            return True
        subs = {'O': '0', 'I': '1', 'L': '1', 'S': '5', 'B': '8', 'Z': '2'}
        c1 = "".join(subs.get(c, c) for c in n1)
        c2 = "".join(subs.get(c, c) for c in n2)
        return c1 == c2 or c1 in c2 or c2 in c1

    def clean_tokens(self, text):
        if not text:
            return []
        stop_words = {
            "the", "and", "for", "with", "from", "that", "this", "each", "following",
            "which", "have", "been", "were", "what", "when", "where", "write", "explain",
            "discuss", "describe", "define", "question", "questions", "answer", "marks",
            "university", "school", "department", "exam", "term", "academic", "year",
            "program", "date", "time", "hours", "duration", "maximum", "total", "paper"
        }
        words = re.findall(r"[a-z0-9]{4,}", text.lower())
        return [w for w in words if w not in stop_words]

    def calculate_text_similarity(self, text1, text2):
        """
        Calculates content similarity between two question papers using token overlap and phrases.
        """
        if not text1 or not text2:
            return 0.0, 0
        tokens1 = self.clean_tokens(text1)
        tokens2 = self.clean_tokens(text2)
        if not tokens1 or not tokens2:
            return 0.0, 0

        set2 = set(tokens2)
        matches = [t for t in tokens1 if t in set2]
        match_count = len(matches)
        min_len = min(len(tokens1), len(tokens2))
        similarity = match_count / max(min_len, 1)

        # Check for 4-word consecutive phrase matches
        words1 = text1.lower().split()
        words2_text = " " + " ".join(text2.lower().split()) + " "
        phrase_matches = 0
        if len(words1) >= 4:
            step = 3
            for i in range(0, min(len(words1) - 3, 40), step):
                phrase = " " + " ".join(words1[i:i+4]) + " "
                if phrase in words2_text:
                    phrase_matches += 1

        if phrase_matches >= 2:
            similarity = max(similarity, 0.75)

        return similarity, match_count

    def check_duplicate_past_papers(self, text, existing_papers=None):
        """
        Scans full OCR extracted text against all past papers.
        Detects if this paper is already present in past data even if course code has a typo.
        """
        if not existing_papers or not text or len(text.strip()) < 30:
            return False, None, 0.0

        for p in existing_papers:
            past_text = p.get("extracted_text") or p.get("extractedText") or ""
            if not past_text and isinstance(p.get("verification_report"), dict):
                past_text = p.get("verification_report", {}).get("extracted_text", "")

            if not past_text or len(past_text.strip()) < 30:
                continue

            similarity, match_count = self.calculate_text_similarity(text, past_text)
            if similarity >= 0.35 and match_count >= 12:
                return True, p, similarity

        return False, None, 0.0

    def check_a4_layout(self, file_bytes, mime_type):
        """
        Validates physical page dimensions conform to standard A4 layout.
        Standard A4: 210 x 297 mm, aspect ratio = 1.414 (tolerance 1.15 to 1.85).
        """
        aspect_ratio = 1.414
        conforms = True
        is_portrait = True

        if not file_bytes:
            return True, aspect_ratio, is_portrait

        # PDF geometry via PyMuPDF
        if ("pdf" in (mime_type or "").lower()) and fitz:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if len(doc) > 0:
                    page = doc[0]
                    rect = page.rect
                    w, h = rect.width, rect.height
                    if w > 0 and h > 0:
                        aspect_ratio = max(w, h) / min(w, h)
                        is_portrait = h >= w
                        conforms = 1.20 <= aspect_ratio <= 2.25
                doc.close()
                return conforms, aspect_ratio, is_portrait
            except Exception:
                pass

        # Image geometry via Pillow
        try:
            img = Image.open(BytesIO(file_bytes))
            w, h = img.size
            if w > 0 and h > 0:
                aspect_ratio = max(w, h) / min(w, h)
                is_portrait = h >= w
                conforms = 1.20 <= aspect_ratio <= 2.25
            return conforms, aspect_ratio, is_portrait
        except Exception:
            pass

        return True, aspect_ratio, is_portrait

    def check_image_color_saturation(self, file_bytes, mime_type):
        """
        Calculates color saturation percentage for image uploads.
        Exam papers are monochrome (< 10% color). Flower/scenery/photo uploads have > 30% colorful pixels.
        """
        if not file_bytes or len(file_bytes) < 100 or ("image" not in (mime_type or "").lower()):
            return False, 0.0
        try:
            img = Image.open(BytesIO(file_bytes)).convert("RGB")
            # Downsample for fast check
            sample = img.resize((120, max(int(120 * img.height / img.width), 10)))
            pixels = [sample.getpixel((x, y)) for y in range(sample.height) for x in range(sample.width)]
            total = len(pixels)
            colorful = sum(1 for r, g, b in pixels if max(r, g, b) - min(r, g, b) > 30)
            ratio = (colorful / total) * 100
            return ratio > 18.0, ratio
        except Exception:
            return False, 0.0

    def check_upperbox_sr_university(self, text):
        """
        Checks for 'SR UNIVERSITY' in upperbox / institutional header.
        """
        if not text:
            return False, "UNVERIFIED"

        text_upper = self.normalize_text(text)
        upper_box_text = text_upper[:800]

        patterns = [
            r"\bSR\s+UNIVERSITY\b",
            r"\bSRU\b",
            r"\bSR\s+UNIVERSITY\s+WARANGAL\b",
            r"\bSR\s+ENGINEERING\s+COLLEGE\b"
        ]

        for p in patterns:
            m = re.search(p, upper_box_text)
            if m:
                return True, "SR UNIVERSITY"

        for p in patterns:
            m = re.search(p, text_upper)
            if m:
                return True, "SR UNIVERSITY"

        return False, "UNVERIFIED"

    def check_course_code(self, text, expected_code=None, gemini_code=None):
        """
        Checks if Course Code is present in the paper text or detected by Gemini.
        """
        text_upper = self.normalize_text(text) if text else ""

        # 1. If student specified a code, check if it matches in the paper or Gemini
        if expected_code:
            norm_expected = self.normalize_code(expected_code)
            if norm_expected:
                clean_doc_alphanum = re.sub(r"[^A-Z0-9]", "", text_upper)
                if norm_expected in clean_doc_alphanum:
                    return True, expected_code.upper()
                if self.fuzzy_code_match(norm_expected, clean_doc_alphanum):
                    return True, expected_code.upper()
                root_match = re.search(r"[0-9]{2}[A-Z]{2,4}[0-9]{3}", norm_expected)
                if root_match and root_match.group(0) in clean_doc_alphanum:
                    return True, expected_code.upper()
                if gemini_code and self.fuzzy_code_match(norm_expected, gemini_code):
                    return True, expected_code.upper()

        # 2. Check if Gemini already extracted a valid course code
        if gemini_code and gemini_code != "UNVERIFIED" and len(gemini_code) >= 3:
            if not expected_code or self.fuzzy_code_match(expected_code, gemini_code):
                return True, gemini_code.upper()

        # 3. Extract course code directly from document header regex
        patterns = [
            r"COURSE\s+CODE[:\s\.\-\|]*([0-9]{2}[A-Z]{2,4}[0-9]{3}[A-Z0-9]{0,6})",
            r"SUBJECT\s+CODE[:\s\.\-\|]*([0-9]{2}[A-Z]{2,4}[0-9]{3}[A-Z0-9]{0,6})",
            r"\b([0-9]{2}[A-Z]{2,4}[0-9]{3}PC[0-9]{3})\b",
            r"\b([0-9]{2}[A-Z]{2,4}[0-9]{3})\b",
            r"\b([A-Z]{2,4}[0-9]{3})\b"
        ]

        for p in patterns:
            m = re.search(p, text_upper)
            if m:
                found_code = m.group(1).strip()
                if expected_code:
                    if self.fuzzy_code_match(expected_code, found_code):
                        return True, found_code
                    return False, found_code
                return True, found_code

        return False, "UNVERIFIED"

    def verify(self, file_bytes, filename, mime_type, student_selection=None, client_ocr_text="", ocr_confidence=0, existing_papers=None):
        student_selection = student_selection or {}
        reasons = []
        engine_mode = "local-multi-engine"

        # 0. Check excessive color saturation (rejects flower photos, scenery, nature, selfies)
        is_colorful, color_ratio = self.check_image_color_saturation(file_bytes, mime_type)
        if is_colorful:
            return {
                "decision": "REJECTED",
                "is_duplicate": False,
                "confidence": 0,
                "reasons": [
                    "This document is not a valid SR University question paper.",
                    "Document contains excessive vibrant color. Non-examination photos (flowers, scenery, selfies, nature) are strictly rejected."
                ],
                "extracted_fields": {
                    "university_name": "UNVERIFIED",
                    "course_code": "UNVERIFIED"
                },
                "extracted_text": "",
                "engine": engine_mode
            }

        # 1. Extract vector text if PDF, otherwise use client_ocr_text
        doc_text = client_ocr_text or ""
        if ("pdf" in (mime_type or "").lower()) and file_bytes and fitz:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                pages_text = []
                for p in doc:
                    pages_text.append(p.get_text())
                pdf_extracted = "\n".join(pages_text).strip()
                if len(pdf_extracted) > len(doc_text):
                    doc_text = pdf_extracted
                doc.close()
            except Exception:
                pass

        doc_text = doc_text.strip()
        expected_code = student_selection.get("subjectCode") or student_selection.get("course_code") or ""

        # 2. Call Google Gemini API for Multimodal Document Understanding (if key configured & bytes available)
        gemini_result = None
        if file_bytes and len(file_bytes) > 0:
            gemini_result = self.gemini_verify(file_bytes, mime_type, expected_code)
            if gemini_result:
                engine_mode = "gemini-api+local"

        # If Gemini returned extracted text / questions, enrich doc_text for duplicate scanning
        if gemini_result:
            g_summary = gemini_result.get("extracted_text_summary") or ""
            if g_summary and g_summary not in doc_text:
                doc_text = f"{doc_text}\n{g_summary}".strip()

        # 3. Duplicate Detection across past papers (OCR & token overlap matching)
        is_duplicate, matched_paper, sim_score = self.check_duplicate_past_papers(doc_text, existing_papers)
        if is_duplicate and matched_paper:
            matched_code = matched_paper.get("subject_code") or matched_paper.get("subjectCode") or "Existing Paper"
            matched_name = matched_paper.get("subject_name") or matched_paper.get("subjectName") or ""
            return {
                "decision": "REJECTED",
                "is_duplicate": True,
                "matched_duplicate": {
                    "id": matched_paper.get("id"),
                    "subject_code": matched_code,
                    "subject_name": matched_name
                },
                "confidence": 100,
                "reasons": [
                    f"This question paper already exists in the archive! Matched with {matched_code} - {matched_name} ({int(sim_score*100)}% content match)."
                ],
                "extracted_fields": {
                    "university_name": "SR UNIVERSITY",
                    "course_code": matched_code
                },
                "extracted_text": doc_text,
                "engine": engine_mode
            }

        # 4. Check A4 Paper Layout
        conforms_a4, aspect_ratio, is_portrait = self.check_a4_layout(file_bytes, mime_type)

        # 5. Check 'SR UNIVERSITY' in upper box (via Gemini and local pattern match)
        has_sru_local, uni_name_local = self.check_upperbox_sr_university(doc_text)
        has_sru_gemini = bool(gemini_result and (gemini_result.get("has_upperbox_sr_header") or gemini_result.get("is_sr_university")))
        has_sru = has_sru_local or has_sru_gemini
        uni_name = "SR UNIVERSITY" if has_sru else uni_name_local

        # 6. Check Course Code
        gemini_code = gemini_result.get("course_code") if gemini_result else None
        has_code, extracted_code = self.check_course_code(doc_text, expected_code, gemini_code)

        # 7. Blank / empty document guard
        if len(doc_text) < 15 and not gemini_result:
            return {
                "decision": "REJECTED",
                "is_duplicate": False,
                "confidence": 0,
                "reasons": [
                    "This document is not a valid SR University question paper (Document appears to be blank or unreadable)."
                ],
                "extracted_fields": {
                    "university_name": "UNVERIFIED",
                    "course_code": "UNVERIFIED"
                },
                "extracted_text": doc_text,
                "engine": engine_mode
            }

        # 8. Check for disallowed documents (Class notes, assignments, lab records, other universities)
        # 8A. Gemini classification check
        if gemini_result:
            doc_type = gemini_result.get("document_type", "QUESTION_PAPER").upper()
            if doc_type in ["CLASS_NOTES", "ASSIGNMENT", "LAB_RECORD", "TEXTBOOK", "OTHER_UNIVERSITY", "OTHER"]:
                type_labels = {
                    "CLASS_NOTES": "Class Notes / Lecture Summary",
                    "ASSIGNMENT": "Student Assignment / Homework",
                    "LAB_RECORD": "Laboratory Manual / Record",
                    "TEXTBOOK": "Textbook Material / Syllabus",
                    "OTHER_UNIVERSITY": "Other University Question Paper",
                    "OTHER": "Unrelated Non-Examination Document"
                }
                label = type_labels.get(doc_type, doc_type)
                return {
                    "decision": "REJECTED",
                    "is_duplicate": False,
                    "confidence": gemini_result.get("confidence", 85),
                    "reasons": [
                        "This document is not a valid SR University question paper.",
                        f"Document classified by AI as prohibited non-examination material: '{label}'."
                    ],
                    "extracted_fields": {
                        "university_name": uni_name,
                        "course_code": extracted_code
                    },
                    "extracted_text": doc_text,
                    "engine": engine_mode
                }

        # 8B. Local Regex disallowed documents check
        disallowed = [
            (r"\b(?:podcast|scan\s*me|auditorium|workshop|webinar|hackathon|chief\s*guest|invitation|certificate\s*of|college\s*fest|annual\s*fest|register\s*now|registration\s*link|registration\s*fee)\b|\bpresents\s+(?:a\s+|the\s+)?(?:podcast|session|event|workshop)\b", "Event / Promotional Poster or Flyer"),
            (r"\b(?:class\s*notes|lecture\s*notes|my\s*notes)\b", "Class Notes"),
            (r"\b(?:assignment(?:\s*no|\s*number|\s*\d)?|homework)\b", "Student Assignment"),
            (r"\b(?:lab\s*manual|lab\s*record|record\s*book|experiment\s*no)\b", "Laboratory Record"),
            (r"\b(?:jntuh|jntuk|osmania\s*university|anna\s*university|kakatiya\s*university)\b", "Other University Paper")
        ]
        for pattern, cat in disallowed:
            if re.search(pattern, doc_text, re.IGNORECASE):
                return {
                    "decision": "REJECTED",
                    "is_duplicate": False,
                    "confidence": 10,
                    "reasons": [
                        "This document is not a valid SR University question paper.",
                        f"Document classified as prohibited non-examination material: '{cat}'."
                    ],
                    "extracted_fields": {
                        "university_name": uni_name,
                        "course_code": extracted_code
                    },
                    "extracted_text": doc_text,
                    "engine": engine_mode
                }

        # 9. Decision Evaluation:
        # If upperbox has SR UNIVERSITY AND Course Code is present AND A4 layout
        if has_sru and has_code and conforms_a4:
            reasons.append("SR University institutional header verified in upper box.")
            reasons.append(f"Course code '{extracted_code}' verified in document.")
            reasons.append("Standard A4 examination paper layout verified.")

            calc_confidence = 95
            if gemini_result and gemini_result.get("confidence"):
                calc_confidence = int(gemini_result.get("confidence"))
            elif ocr_confidence:
                calc_confidence = max(int(ocr_confidence), 90)

            return {
                "decision": "APPROVED",
                "is_duplicate": False,
                "confidence": calc_confidence,
                "reasons": reasons,
                "extracted_fields": {
                    "university_name": "SR UNIVERSITY",
                    "course_code": extracted_code,
                    "subject_name": (gemini_result.get("subject_name") if gemini_result and gemini_result.get("subject_name") != "UNVERIFIED" else student_selection.get("subjectName", "")),
                    "academic_regulation": (gemini_result.get("regulation") if gemini_result and gemini_result.get("regulation") != "UNVERIFIED" else student_selection.get("regulation", "R22")),
                    "academic_year": (gemini_result.get("academic_year") if gemini_result and gemini_result.get("academic_year") != "UNVERIFIED" else student_selection.get("academicYear", "2025-2026")),
                    "course_coordinator": (gemini_result.get("course_coordinator") if gemini_result else "UNVERIFIED")
                },
                "extracted_text": doc_text,
                "engine": engine_mode
            }
        else:
            failure_points = []
            if not has_sru:
                failure_points.append("The upper header box must clearly state 'SR UNIVERSITY'.")
            if not has_code:
                failure_points.append(f"Course code '{expected_code or 'Code'}' was not found in the paper.")
            if not conforms_a4:
                failure_points.append(f"Document geometry ({aspect_ratio:.2f}) does not match standard A4 paper layout.")

            reasons.append("This document is not a valid SR University question paper.")
            reasons.extend(failure_points)

            return {
                "decision": "REJECTED",
                "is_duplicate": False,
                "confidence": 15,
                "reasons": reasons,
                "extracted_fields": {
                    "university_name": uni_name,
                    "course_code": extracted_code
                },
                "extracted_text": doc_text,
                "engine": engine_mode
            }


verifier = VerificationEngine()
