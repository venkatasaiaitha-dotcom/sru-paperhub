"""
Simple, Robust SR University Question Paper Verification & Duplicate Engine
"""

import os
import re
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


class VerificationEngine:
    def __init__(self):
        pass

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
        # Filter out common filler stop-words
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
        if ("pdf" in mime_type.lower()) and fitz:
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if len(doc) > 0:
                    page = doc[0]
                    rect = page.rect
                    w, h = rect.width, rect.height
                    if w > 0 and h > 0:
                        aspect_ratio = max(w, h) / min(w, h)
                        is_portrait = h >= w
                        conforms = 1.15 <= aspect_ratio <= 1.85
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
                conforms = 1.15 <= aspect_ratio <= 1.85
            return conforms, aspect_ratio, is_portrait
        except Exception:
            pass

        return True, aspect_ratio, is_portrait

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

    def check_course_code(self, text, expected_code=None):
        """
        Checks if Course Code is present in the paper text.
        """
        if not text:
            return False, "UNVERIFIED"

        text_upper = self.normalize_text(text)

        # 1. If student specified a code, check if it matches in the paper
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

        # 2. Extract course code directly from document header
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

        # 1. Extract vector text if PDF, otherwise use client_ocr_text
        doc_text = client_ocr_text or ""
        if ("pdf" in mime_type.lower()) and file_bytes and fitz:
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

        # 2. Duplicate Detection across past papers (OCR content matching)
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
                "extracted_text": doc_text
            }

        # 3. Check A4 Paper Layout
        conforms_a4, aspect_ratio, is_portrait = self.check_a4_layout(file_bytes, mime_type)

        # 4. Check 'SR UNIVERSITY' in upper box
        has_sru, uni_name = self.check_upperbox_sr_university(doc_text)

        # 5. Check Course Code
        has_code, extracted_code = self.check_course_code(doc_text, expected_code)

        # 6. Blank / empty document guard
        if len(doc_text) < 15:
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
                "extracted_text": doc_text
            }

        # Check for disallowed documents like class notes, assignment, other universities
        disallowed = [
            (r"\b(?:class\s*notes|lecture\s*notes|my\s*notes)\b", "Class Notes"),
            (r"\b(?:assignment(?:\\s*no|\s*number|\s*\d)?|homework)\b", "Student Assignment"),
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
                    "extracted_text": doc_text
                }

        # Decision Evaluation:
        # If upperbox has SR UNIVERSITY AND Course Code is present AND A4 layout
        if has_sru and has_code and conforms_a4:
            reasons.append("SR University institutional header verified in upper box.")
            reasons.append(f"Course code '{extracted_code}' verified in document.")
            reasons.append("Standard A4 examination paper layout verified.")
            return {
                "decision": "APPROVED",
                "is_duplicate": False,
                "confidence": max(int(ocr_confidence) if ocr_confidence else 95, 90),
                "reasons": reasons,
                "extracted_fields": {
                    "university_name": "SR UNIVERSITY",
                    "course_code": extracted_code,
                    "academic_regulation": student_selection.get("regulation", "R22"),
                    "academic_year": student_selection.get("academicYear", "2025-2026")
                },
                "extracted_text": doc_text
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
                "extracted_text": doc_text
            }


verifier = VerificationEngine()
