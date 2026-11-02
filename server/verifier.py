"""
AI-Powered Question Paper Verification & Validation Engine
SR University PaperHub
"""

import os
import re
import time
import json
from io import BytesIO
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

from .reference_template import REFERENCE_TEMPLATE

class VerificationEngine:
    def __init__(self, template=None):
        self.template = template or REFERENCE_TEMPLATE

    def normalize_text(self, text):
        if not text:
            return ""
        t = re.sub(r"\s+", " ", str(text)).strip().upper()
        t = t.replace("–", "-").replace("—", "-")
        return t

    def fuzzy_code_match(self, val1, val2):
        if not val1 or not val2:
            return False
        n1 = re.sub(r"[^A-Z0-9]", "", self.normalize_text(val1))
        n2 = re.sub(r"[^A-Z0-9]", "", self.normalize_text(val2))
        if n1 == n2:
            return True
        subs = {'O': '0', 'I': '1', 'L': '1', 'S': '5', 'B': '8', 'Z': '2'}
        c1 = "".join(subs.get(c, c) for c in n1)
        c2 = "".join(subs.get(c, c) for c in n2)
        return c1 == c2

    def normalize_academic_year(self, year_str):
        if not year_str:
            return ""
        m = re.search(r"(20[2-3][0-9])\s*[-–\/]\s*(?:20)?([2-3][0-9])", str(year_str))
        if m:
            start_yr = m.group(1)
            end_yr = m.group(2)
            if len(end_yr) == 2:
                end_yr = "20" + end_yr
            return f"{start_yr}-{end_yr}"
        return self.normalize_text(year_str)

    def normalize_regulation(self, reg_str):
        if not reg_str:
            return ""
        m = re.search(r"R\s*([0-9]{2})", str(reg_str).upper())
        if m:
            return f"R{m.group(1)}"
        return self.normalize_text(reg_str)

    def normalize_branch(self, branch_str):
        if not branch_str:
            return ""
        b = self.normalize_text(branch_str)
        if "CSE" in b or "COMPUTER SCIENCE" in b or "CS&AI" in b:
            return "CSE"
        if "AIML" in b or "AI&ML" in b or "ARTIFICIAL INTELLIGENCE" in b:
            return "AIML"
        if "AIDS" in b or "DATA SCIENCE" in b:
            return "AIDS"
        if "ECE" in b or "ELECTRONICS" in b:
            return "ECE"
        if "EEE" in b or "ELECTRICAL" in b:
            return "EEE"
        if "MECH" in b or "MECHANICAL" in b:
            return "MECH"
        if "CIVIL" in b:
            return "CIVIL"
        return b

    def normalize_year_sem(self, year_sem_str):
        if not year_sem_str:
            return ""
        s = self.normalize_text(year_sem_str)
        if re.search(r"\b(II\/I|2[\-\/]1|SEM\s*3|2ND\s*YEAR|II\s*YEAR)\b", s):
            return "2ND YEAR / SEM 3"
        if re.search(r"\b(II\/II|2[\-\/]2|SEM\s*4)\b", s):
            return "2ND YEAR / SEM 4"
        if re.search(r"\b(I\/I|1[\-\/]1|SEM\s*1|1ST\s*YEAR|I\s*YEAR)\b", s):
            return "1ST YEAR / SEM 1"
        if re.search(r"\b(I\/II|1[\-\/]2|SEM\s*2)\b", s):
            return "1ST YEAR / SEM 2"
        if re.search(r"\b(III\/I|3[\-\/]1|SEM\s*5|3RD\s*YEAR|III\s*YEAR)\b", s):
            return "3RD YEAR / SEM 5"
        if re.search(r"\b(III\/II|3[\-\/]2|SEM\s*6)\b", s):
            return "3RD YEAR / SEM 6"
        if re.search(r"\b(IV\/I|4[\-\/]1|SEM\s*7|4TH\s*YEAR|IV\s*YEAR)\b", s):
            return "4TH YEAR / SEM 7"
        if re.search(r"\b(IV\/II|4[\-\/]2|SEM\s*8)\b", s):
            return "4TH YEAR / SEM 8"
        return s

    def extract_document_text_and_layout(self, file_bytes, mime_type):
        """Extracts text and page layout metrics from PDF or Image."""
        layout_info = {
            "is_pdf": False,
            "page_count": 1,
            "width_pt": 0,
            "height_pt": 0,
            "aspect_ratio": 1.414,
            "is_a4": True,
            "layout_details": ""
        }
        text = ""

        if mime_type == "application/pdf":
            layout_info["is_pdf"] = True
            if fitz:
                try:
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    layout_info["page_count"] = len(doc)
                    if len(doc) > 0:
                        first_page = doc[0]
                        rect = first_page.rect
                        layout_info["width_pt"] = rect.width
                        layout_info["height_pt"] = rect.height
                        if rect.width > 0:
                            layout_info["aspect_ratio"] = round(rect.height / rect.width, 3)
                        
                        min_ratio = self.template["layout"]["aspect_ratio_tolerance_min"]
                        max_ratio = self.template["layout"]["aspect_ratio_tolerance_max"]
                        layout_info["is_a4"] = (min_ratio <= layout_info["aspect_ratio"] <= max_ratio)
                        layout_info["layout_details"] = f"A4 PDF: {round(rect.width, 1)} x {round(rect.height, 1)} pt, Aspect Ratio: {layout_info['aspect_ratio']}"

                        page_texts = []
                        for i in range(min(len(doc), 3)):
                            page_texts.append(doc[i].get_text("text"))
                        text = "\n".join(page_texts)
                    doc.close()
                except Exception as e:
                    layout_info["layout_details"] = f"PDF Read Warning: {str(e)}"
        else:
            try:
                img = Image.open(BytesIO(file_bytes))
                w, h = img.size
                layout_info["width_pt"] = w
                layout_info["height_pt"] = h
                if w > 0:
                    layout_info["aspect_ratio"] = round(h / w, 3)
                
                min_ratio = self.template["layout"]["aspect_ratio_tolerance_min"]
                max_ratio = self.template["layout"]["aspect_ratio_tolerance_max"]
                layout_info["is_a4"] = (min_ratio <= layout_info["aspect_ratio"] <= max_ratio)
                layout_info["layout_details"] = f"Image Scan: {w}x{h} px, Aspect Ratio: {layout_info['aspect_ratio']}"
            except Exception as e:
                layout_info["layout_details"] = f"Image Process Warning: {str(e)}"

        return text, layout_info

    def verify(self, file_bytes, filename, mime_type, student_selection, client_ocr_text="", ocr_confidence=0):
        """
        Executes the 8-Layer Multi-Tier Verification Engine.
        Returns a comprehensive Document Verification Report.
        """
        reasons = []
        warnings = []
        is_approved = True
        is_rejected = False
        requires_manual_review = False

        # LAYER 1: FILE VALIDATION
        file_valid = True
        file_error = ""
        file_size_bytes = len(file_bytes) if file_bytes else 0
        file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

        allowed_mimes = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
        if not file_bytes or file_size_bytes == 0:
            file_valid = False
            file_error = "File is empty (0 bytes)."
        elif file_size_bytes > 15 * 1024 * 1024:
            file_valid = False
            file_error = f"File size ({file_size_mb} MB) exceeds maximum allowed 15 MB."
        elif mime_type not in allowed_mimes:
            file_valid = False
            file_error = f"File MIME type '{mime_type}' is disallowed. Only JPG, PNG, WEBP, and PDF are accepted."

        if not file_valid:
            return self._build_report(
                decision="REJECTED",
                summary=f"Layer 1 File Validation Failed: {file_error}",
                confidence=0,
                layers={"layer_1_file": {"name": "File Format & Readability", "status": "FAILED", "error": file_error, "size_mb": file_size_mb}},
                reasons=[file_error]
            )

        extracted_doc_text, layout_info = self.extract_document_text_and_layout(file_bytes, mime_type)
        
        combined_text = ""
        if extracted_doc_text and len(extracted_doc_text.strip()) > 30:
            combined_text = extracted_doc_text + "\n" + (client_ocr_text or "")
        else:
            combined_text = client_ocr_text or extracted_doc_text or ""

        clean_text_upper = self.normalize_text(combined_text)

        if layout_info.get("is_pdf") and layout_info.get("page_count", 1) > 15:
            reasons.append(f"Document has {layout_info.get('page_count')} pages. Examination question papers must not exceed 15 pages (rejected as book/manual).")
            is_rejected = True

        # LAYER 2: DOCUMENT CLASSIFICATION
        doc_classification = "Examination Question Paper"
        classification_failed = False
        disallowed_match_found = None

        for pattern, label in self.template["disallowed_document_indicators"]:
            if re.search(pattern, clean_text_upper, re.IGNORECASE):
                disallowed_match_found = label
                classification_failed = True
                break

        if classification_failed:
            reasons.append(f"Document classified as disallowed non-exam material: {disallowed_match_found}.")
            is_rejected = True
            doc_classification = disallowed_match_found

        if len(clean_text_upper) < 25:
            reasons.append("Document has insufficient readable text or is blank/unreadable.")
            requires_manual_review = True

        # LAYER 3 & 4: UNIVERSITY IDENTITY VALIDATION
        uni_verified = False
        uni_pattern = self.template["institution"]["header_pattern"]
        if re.search(uni_pattern, clean_text_upper):
            uni_verified = True
        elif "SR UNIVERSITY" in clean_text_upper or "SRU" in clean_text_upper:
            uni_verified = True
        else:
            for sch in self.template["institution"]["schools"]:
                if sch in clean_text_upper:
                    uni_verified = True
                    break
            for dpt in self.template["institution"]["departments"]:
                if dpt in clean_text_upper:
                    uni_verified = True
                    break

        if not uni_verified:
            reasons.append("SR University identification ('SR UNIVERSITY' or official school header) was not detected.")
            is_rejected = True

        # LAYER 3 & 5: MANDATORY FIELD EXTRACTION & COMPARISON
        extracted_fields = {}
        field_comparisons = []

        # 1. University Name
        extracted_fields["university_name"] = "SR UNIVERSITY" if uni_verified else "UNVERIFIED"

        # 2. Regulation
        reg_match = re.search(r"\bREGULATION[:\s\.\-\|]*\s*(R\s*[0-9]{2})\b", clean_text_upper)
        if not reg_match:
            reg_match = re.search(r"\b(R[1-2][0-9])\b", clean_text_upper)
        extracted_reg = self.normalize_regulation(reg_match.group(1)) if reg_match else "UNVERIFIED"
        extracted_fields["regulation"] = extracted_reg

        # 3. Academic Year
        ay_match = re.search(r"\bACADEMIC\s+YEAR[:\s\.\-\|]*\s*(20[2-3][0-9]\s*[-–\/]\s*(?:20)?[2-3][0-9])\b", clean_text_upper)
        if not ay_match:
            ay_match = re.search(r"\b(20[2-3][0-9]\s*[-–\/]\s*(?:20)?[2-3][0-9])\b", clean_text_upper)
        extracted_ay = self.normalize_academic_year(ay_match.group(1)) if ay_match else "UNVERIFIED"
        extracted_fields["academic_year"] = extracted_ay

        # 4. Course Code
        cc_match = re.search(r"\bCOURSE\s+CODE[:\s\.\-\|]*\s*([0-9]{2}[A-Z]{2,4}[0-9]{2,4}[A-Z0-9]{2,6})\b", clean_text_upper)
        if not cc_match:
            cc_match = re.search(r"\b([0-9]{2}[A-Z]{2,4}[0-9]{2,4}[A-Z0-9]{0,6})\b", clean_text_upper)
        extracted_cc = cc_match.group(1) if cc_match else "UNVERIFIED"
        extracted_fields["course_code"] = extracted_cc

        # 5. Subject Name / Course Title
        sn_match = re.search(r"(?:COURSE\s+TITLE|SUBJECT\s+NAME|SUBJECT)[:\s\.\-\|]+([A-Z0-9\s\&\-\/]{3,50}?)(?=\s+(?:YEAR|SEM|REGULATION|DATE|TIME|ANSWER|MAX|DURATION|$|\n))", clean_text_upper)
        extracted_sn = sn_match.group(1).strip() if sn_match else "UNVERIFIED"
        extracted_fields["subject_name"] = extracted_sn

        # 6. Subject Code (Evaluated independently)
        sc_match = re.search(r"\bSUBJECT\s+CODE[:\s\.\-\|]*\s*([0-9A-Z]{5,15})\b", clean_text_upper)
        extracted_sc = sc_match.group(1) if sc_match else extracted_cc
        extracted_fields["subject_code"] = extracted_sc

        # 7. Branch / Department
        br_match = re.search(r"\b(CSE|AIML|AIDS|ECE|EEE|MECH|CIVIL|CS&AI)\b", clean_text_upper)
        extracted_branch = self.normalize_branch(br_match.group(1)) if br_match else "UNVERIFIED"
        extracted_fields["branch"] = extracted_branch

        # 8. Year of Study / Semester
        ys_match = re.search(r"\b(?:YEAR\s*\/\s*SEM|YEAR|SEMESTER)[:\s\.\-\|]*\s*([IV0-9\/\-\s]+?)(?=\s+(?:REGULATION|DATE|TIME|DURATION|ANSWER|$|\n))", clean_text_upper)
        extracted_ys = self.normalize_year_sem(ys_match.group(1)) if ys_match else "UNVERIFIED"
        extracted_fields["year_of_study"] = extracted_ys

        # 9 & 10. Course Coordinator Label and Name
        coord_label_found = False
        coord_name = "UNVERIFIED"

        if re.search(r"\bCOURSE\s+COORDINATOR\b", clean_text_upper):
            coord_label_found = True

        coord_match = re.search(r"COURSE\s+COORDINATOR(?:\s+NAME)?[:\s\.\-\|]+([A-Z\.\s]{3,35}?)(?=\s+(?:COURSE|CODE|REGULATION|YEAR|DATE|TIME|MAX|ANSWER|B\.TECH|$|\n))", clean_text_upper)
        if coord_match:
            candidate_name = coord_match.group(1).strip()
            candidate_name = re.sub(r"[^A-Z\.\s]", "", candidate_name).strip()
            for kw in ["COURSE", "CODE", "TITLE", "NAME", "TE"]:
                if candidate_name.endswith(kw):
                    candidate_name = candidate_name[:-len(kw)].strip()
            if len(candidate_name) >= 3 and candidate_name not in ["NAME", "TE", "NULL"]:
                coord_name = candidate_name
                coord_label_found = True

        extracted_fields["course_coordinator_label"] = "FOUND" if coord_label_found else "UNVERIFIED"
        extracted_fields["course_coordinator_name"] = coord_name

        if not coord_label_found:
            reasons.append("Mandatory field 'Course Coordinator' label was not found in document.")
            is_rejected = True
        elif coord_name == "UNVERIFIED":
            reasons.append("Identifiable Course Coordinator name could not be extracted.")
            requires_manual_review = True

        # COMPARISON WITH STUDENT SELECTIONS
        sel_reg = student_selection.get("regulation", "")
        sel_year = student_selection.get("academicYear", "")
        sel_code = student_selection.get("subjectCode", "")
        sel_branch = student_selection.get("branch", "")
        sel_sem = str(student_selection.get("semester", ""))

        # 1. Compare Regulation
        if sel_reg:
            norm_sel_reg = self.normalize_regulation(sel_reg)
            if extracted_reg != "UNVERIFIED":
                if norm_sel_reg == extracted_reg:
                    field_comparisons.append({"field": "Regulation", "selected": norm_sel_reg, "extracted": extracted_reg, "match": "MATCH"})
                else:
                    field_comparisons.append({"field": "Regulation", "selected": norm_sel_reg, "extracted": extracted_reg, "match": "MISMATCH"})
                    reasons.append(f"Regulation mismatch: Selected '{norm_sel_reg}' but document specifies '{extracted_reg}'.")
                    is_rejected = True
            else:
                field_comparisons.append({"field": "Regulation", "selected": norm_sel_reg, "extracted": "UNVERIFIED", "match": "UNVERIFIED"})
                warnings.append("Regulation could not be verified with 100% confidence from OCR.")

        # 2. Compare Academic Year
        if sel_year:
            norm_sel_year = self.normalize_academic_year(sel_year)
            if extracted_ay != "UNVERIFIED":
                if norm_sel_year == extracted_ay:
                    field_comparisons.append({"field": "Academic Year", "selected": norm_sel_year, "extracted": extracted_ay, "match": "MATCH"})
                else:
                    field_comparisons.append({"field": "Academic Year", "selected": norm_sel_year, "extracted": extracted_ay, "match": "MISMATCH"})
                    reasons.append(f"Academic Year mismatch: Selected '{norm_sel_year}' but document specifies '{extracted_ay}'.")
                    is_rejected = True
            else:
                field_comparisons.append({"field": "Academic Year", "selected": norm_sel_year, "extracted": "UNVERIFIED", "match": "UNVERIFIED"})
                warnings.append("Academic Year could not be verified from OCR.")

        # 3. Compare Course / Subject Code
        if sel_code:
            norm_sel_code = self.normalize_text(sel_code)
            if extracted_cc != "UNVERIFIED":
                if self.fuzzy_code_match(norm_sel_code, extracted_cc):
                    field_comparisons.append({"field": "Course Code", "selected": norm_sel_code, "extracted": extracted_cc, "match": "MATCH"})
                else:
                    field_comparisons.append({"field": "Course Code", "selected": norm_sel_code, "extracted": extracted_cc, "match": "MISMATCH"})
                    reasons.append(f"Course Code mismatch: Selected '{norm_sel_code}' but document specifies '{extracted_cc}'.")
                    is_rejected = True
            else:
                field_comparisons.append({"field": "Course Code", "selected": norm_sel_code, "extracted": "UNVERIFIED", "match": "UNVERIFIED"})
                warnings.append("Course Code was unverified from OCR scan.")

        # 4. Compare Branch
        if sel_branch:
            norm_sel_branch = self.normalize_branch(sel_branch)
            if extracted_branch != "UNVERIFIED":
                if norm_sel_branch == extracted_branch or (norm_sel_branch == "CSE" and extracted_branch == "CS&AI"):
                    field_comparisons.append({"field": "Branch", "selected": norm_sel_branch, "extracted": extracted_branch, "match": "MATCH"})
                else:
                    field_comparisons.append({"field": "Branch", "selected": norm_sel_branch, "extracted": extracted_branch, "match": "MISMATCH"})
                    reasons.append(f"Branch mismatch: Selected '{norm_sel_branch}' but document belongs to '{extracted_branch}'.")
                    is_rejected = True
            else:
                field_comparisons.append({"field": "Branch", "selected": norm_sel_branch, "extracted": "UNVERIFIED", "match": "UNVERIFIED"})
                warnings.append("Branch could not be verified from OCR.")

        # 5. Compare Semester / Year of Study
        if sel_sem:
            sem_map = {"1": "1ST YEAR / SEM 1", "2": "1ST YEAR / SEM 2", "3": "2ND YEAR / SEM 3", "4": "2ND YEAR / SEM 4", "5": "3RD YEAR / SEM 5", "6": "3RD YEAR / SEM 6", "7": "4TH YEAR / SEM 7", "8": "4TH YEAR / SEM 8"}
            norm_sel_sem = sem_map.get(sel_sem, f"SEM {sel_sem}")
            if extracted_ys != "UNVERIFIED":
                if norm_sel_sem in extracted_ys or (sel_sem == "3" and ("II/I" in extracted_ys or "2ND YEAR" in extracted_ys)):
                    field_comparisons.append({"field": "Year / Semester", "selected": norm_sel_sem, "extracted": extracted_ys, "match": "MATCH"})
                else:
                    field_comparisons.append({"field": "Year / Semester", "selected": norm_sel_sem, "extracted": extracted_ys, "match": "MISMATCH"})
                    warnings.append(f"Semester flag: Selected Semester {sel_sem} while document indicates '{extracted_ys}'.")
                    requires_manual_review = True
            else:
                field_comparisons.append({"field": "Year / Semester", "selected": norm_sel_sem, "extracted": "UNVERIFIED", "match": "UNVERIFIED"})

        # LAYER 6: A4 LAYOUT VERIFICATION
        layout_status = "PASSED"
        if not layout_info.get("is_a4", True):
            layout_status = "WARNING"
            warnings.append(f"Aspect ratio ({layout_info.get('aspect_ratio')}) deviates from standard A4 (1.414). Tolerated for mobile phone photo.")

        # LAYER 7: QUESTION PAPER STRUCTURE VALIDATION
        has_instructions = False
        has_questions = False
        has_marks = False

        if re.search(r"\b(ANSWER\s+ALL\s+QUESTIONS|ANSWER\s+ANY|DURATION|MAX(?:IMUM)?\.?\s*MARKS|NOTE[:\s])\b", clean_text_upper):
            has_instructions = True

        if re.search(r"(\bQ\.?\s*NO\.?|\bQUESTION\b|\b[1-9]\s*[\.\)]|\b[A-D]\s*[\.\)]\s+[A-Z])", clean_text_upper):
            has_questions = True

        if re.search(r"(\bMARKS\b|\bMAX\.?\s*MARKS\b|\b[0-9]{1,2}\s*\+\s*[0-9]{1,2}\b|\[\s*[0-9]{1,2}\s*M\s*\]|\(\s*[0-9]{1,2}\s*MARKS?\s*\))", clean_text_upper):
            has_marks = True

        structure_status = "PASSED"
        if not has_questions and not has_marks and not has_instructions:
            structure_status = "FAILED"
            reasons.append("Examination structure not detected: Missing question numbering, marks allocation, and exam instructions.")
            is_rejected = True
        elif not has_questions or not has_marks:
            structure_status = "PARTIAL"
            warnings.append("Some question structure elements were not clearly identified.")
            requires_manual_review = True

        # LAYER 8: FINAL DECISION ENGINE
        final_decision = "APPROVED"
        final_summary = "Your question paper has passed all multi-layer verification checks and is approved for publishing."

        if is_rejected or len(reasons) > 0:
            final_decision = "REJECTED"
            final_summary = "Your document could not be verified as a genuine SR University examination question paper."
        elif requires_manual_review or (ocr_confidence > 0 and ocr_confidence < 50) or any(c["match"] == "UNVERIFIED" for c in field_comparisons):
            final_decision = "MANUAL_REVIEW"
            final_summary = "Your document requires faculty review before publishing due to scanning ambiguity or partial OCR verification."

        score = 94.0
        if ocr_confidence and ocr_confidence > 0:
            score = round((score + ocr_confidence) / 2, 1)
        if final_decision == "REJECTED":
            score = min(score, 35.0)
        elif final_decision == "MANUAL_REVIEW":
            score = min(score, 68.0)

        report = {
            "decision": final_decision,
            "summary": final_summary,
            "confidence": score,
            "document_type": doc_classification,
            "university_identity": "VERIFIED" if uni_verified else "UNVERIFIED",
            "course_coordinator_status": "FOUND" if coord_label_found and coord_name != "UNVERIFIED" else ("PARTIAL" if coord_label_found else "MISSING"),
            "course_coordinator_name": coord_name,
            "layers": {
                "layer_1_file": {
                    "name": "File Format & Readability",
                    "status": "PASSED" if file_valid else "FAILED",
                    "details": f"Size: {file_size_mb} MB, MIME: {mime_type}"
                },
                "layer_2_classification": {
                    "name": "Question Paper Classification",
                    "status": "PASSED" if not classification_failed else "FAILED",
                    "doc_type": doc_classification
                },
                "layer_3_identity": {
                    "name": "SR University Identification",
                    "status": "PASSED" if uni_verified else "FAILED",
                    "institution": "SR UNIVERSITY" if uni_verified else "NOT_FOUND"
                },
                "layer_4_coordinator": {
                    "name": "Course Coordinator Verification",
                    "status": "PASSED" if coord_label_found and coord_name != "UNVERIFIED" else "FAILED",
                    "label": "FOUND" if coord_label_found else "MISSING",
                    "name_extracted": coord_name
                },
                "layer_5_metadata": {
                    "name": "Academic Metadata Matching",
                    "status": "PASSED" if all(c.get("match") in ["MATCH", "UNVERIFIED"] for c in field_comparisons) and not any(c.get("match") == "MISMATCH" for c in field_comparisons) else "FAILED",
                    "comparisons": field_comparisons
                },
                "layer_6_layout": {
                    "name": "A4 Page Layout Verification",
                    "status": layout_status,
                    "details": layout_info.get("layout_details", "")
                },
                "layer_7_structure": {
                    "name": "Question Structure & Marks Validation",
                    "status": structure_status,
                    "details": f"Instructions: {'YES' if has_instructions else 'NO'}, Questions: {'YES' if has_questions else 'NO'}, Marks: {'YES' if has_marks else 'NO'}"
                },
                "layer_8_decision": {
                    "name": "Final Verification Decision",
                    "status": final_decision
                }
            },
            "extracted_fields": extracted_fields,
            "reasons": reasons,
            "warnings": warnings,
            "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        return report

    def _build_report(self, decision, summary, confidence, layers, reasons):
        return {
            "decision": decision,
            "summary": summary,
            "confidence": confidence,
            "document_type": "Unknown",
            "university_identity": "UNVERIFIED",
            "course_coordinator_status": "MISSING",
            "course_coordinator_name": "UNVERIFIED",
            "layers": layers,
            "extracted_fields": {},
            "reasons": reasons,
            "warnings": [],
            "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

verifier = VerificationEngine()
