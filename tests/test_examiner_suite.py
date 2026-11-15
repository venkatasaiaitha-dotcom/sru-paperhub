"""Comprehensive 10-category + security/HTTP test suite for SRU PaperHub Human-Like AI Examiner."""

import hashlib
from io import BytesIO
import json
import os
import socketserver
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from PIL import Image, ImageDraw
import pymupdf

from server.ai_examiner import (
    AI_UNAVAILABLE_MESSAGE,
    AIExaminerService,
    GeminiServiceUnavailableError,
    POOR_QUALITY_MESSAGE,
    _parse_and_normalize_ai_json,
)
from server.document_processor import DocumentValidationError, process_uploaded_document, sanitize_filename
from server.server import PaperHubHandler
from server.sru_rules import SRUValidationConfig
from server.verify_paper_handler import _RATE_LIMIT_LOCK, _VERIFY_PAPER_RATE_LIMITS


def _make_pdf_bytes(pages_text):
    """Create a real multi-page PDF document in memory via PyMuPDF."""
    doc = pymupdf.open()
    for text in pages_text:
        page = doc.new_page(width=595, height=842)
        page.insert_text((50, 60), text, fontsize=11)
    raw = doc.tobytes()
    doc.close()
    return raw


def _make_crisp_exam_image_bytes(lines, fmt="JPEG", size=(800, 1130), exif_orientation=None):
    """Create a realistic high-contrast grayscale/white exam image sheet."""
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 30, size[0] - 30, 200], outline="black", width=2)
    y = 48
    for line in lines:
        draw.text((48, y), line, fill="black")
        y += 32
    buf = BytesIO()
    if exif_orientation is not None and fmt.upper() == "JPEG":
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        img.save(buf, format=fmt, quality=92, exif=exif.tobytes())
    else:
        img.save(buf, format=fmt)
    return buf.getvalue()


def _valid_ai_payload(overrides=None):
    base = {
        "document_type": "question_paper",
        "is_exam_paper": True,
        "institution": {"name": "SR University", "status": "PRESENT"},
        "metadata": {
            "course_code": "24CS301PC211",
            "subject_code": "24CS301PC211",
            "subject_name": "Information Management System",
            "regulation": "R24",
            "academic_year": "2025-2026",
            "branch": "CSE",
            "year": "II",
            "semester": "I",
            "exam_type": "End Term",
            "course_coordinator": "DR. P. PRAVEEN",
            "date": "04-12-2025",
            "duration": "2 Hours",
            "max_marks": "40",
        },
        "structural_analysis": {
            "header": "VALID",
            "instructions": "VALID",
            "question_numbering": "VALID",
            "marks_distribution": "VALID",
            "sections": "VALID",
            "footer": "VALID",
            "overall_layout": "VALID",
        },
        "quality_assessment": {"is_readable": True, "quality_level": "GOOD", "issues": []},
        "evidence": [
            {"category": "institution", "status": "PRESENT", "observation": "SR University header present."},
            {"category": "questions", "status": "PRESENT", "observation": "Consistent numbered questions and marks."},
        ],
        "issues": [],
        "suspicious_signals": [],
        "decision": "APPROVE",
        "confidence": 0.96,
        "reason": "Consistent with expected SRU End Term question-paper characteristics.",
    }
    if overrides:
        for k, v in overrides.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v
    return base


def _encode_multipart(field_name, filename, content_type, data_bytes, metadata_dict=None):
    boundary = "----SRUExaminerTestBoundary98765"
    chunks = []
    if metadata_dict is not None:
        chunks.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="metadata"\r\n\r\n'
            f"{json.dumps(metadata_dict)}\r\n".encode("utf-8")
        )
    chunks.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        + data_bytes
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )
    body = b"".join(chunks)
    return f"multipart/form-data; boundary={boundary}", body


class _FakeGeminiClient:
    """Deterministic controllable stand-in for GeminiExaminerClient."""

    def __init__(self, handler_fn):
        self.handler_fn = handler_fn
        self.calls = 0

    def get_model_name(self):
        return "gemini-3.8-flash"

    def analyze_document(self, doc, user_metadata=None):
        self.calls += 1
        return self.handler_fn(doc, user_metadata), "gemini-3.8-flash"


class TestHumanLikeAIExaminerSuite(unittest.TestCase):
    def setUp(self):
        with _RATE_LIMIT_LOCK:
            _VERIFY_PAPER_RATE_LIMITS.clear()

    def test_1_valid_sru_question_paper_pdf(self):
        """TEST 1: Valid SRU PDF question paper is verified as APPROVE."""
        pdf_bytes = _make_pdf_bytes(
            [
                "SR UNIVERSITY\nSCHOOL OF CS&AI - DEPARTMENT OF CSE\n"
                "Course Code: 24CS301PC211  Course Title: Information Management System\n"
                "Regulation: R24  Academic Year: 2025-2026  Max Marks: 40\n"
                "ANSWER ALL QUESTIONS\n1. A) Design an ER diagram for a bank system. [5M]\nB) Normalize to 3NF. [5M]"
            ]
        )
        fake = _FakeGeminiClient(lambda doc, meta: _valid_ai_payload())
        svc = AIExaminerService(gemini_client=fake)
        status, payload = svc.examine_upload(pdf_bytes, "sru_dbms.pdf", "application/pdf")

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["verification"]["decision"], "APPROVE")
        self.assertGreaterEqual(payload["verification"]["score"], 0.75)
        self.assertEqual(payload["verification"]["institution"]["status"], "PRESENT")
        self.assertEqual(payload["verification"]["metadata"]["course_code"], "24CS301PC211")
        self.assertEqual(fake.calls, 1)

    def test_2_random_university_question_paper_rejected(self):
        """TEST 2: Question paper from another university (e.g. JNTUH) is REJECTED."""
        pdf_bytes = _make_pdf_bytes(
            [
                "JAWAHARLAL NEHRU TECHNOLOGICAL UNIVERSITY HYDERABAD\n"
                "III B.Tech II Sem Examinations\nSubject: Compiler Design\nPart A (25 Marks)"
            ]
        )
        ai_res = _valid_ai_payload(
            {
                "document_type": "other_university_paper",
                "is_exam_paper": True,
                "institution": {"name": "JNTUH", "status": "CONTRADICTORY"},
                "evidence": [
                    {
                        "category": "institution",
                        "status": "CONTRADICTORY",
                        "observation": "Paper explicitly carries JNTUH header.",
                    }
                ],
                "issues": [{"severity": "HIGH", "issue": "Issued by JNTUH, not SR University."}],
                "decision": "REJECT",
                "confidence": 0.97,
                "reason": "Document belongs to JNTUH rather than SR University.",
            }
        )
        svc = AIExaminerService(gemini_client=_FakeGeminiClient(lambda doc, meta: ai_res))
        status, payload = svc.examine_upload(pdf_bytes, "jntuh_paper.pdf", "application/pdf")

        self.assertEqual(status, 200)
        self.assertEqual(payload["verification"]["decision"], "REJECT")

    def test_3_completely_unrelated_pdf_rejected(self):
        """TEST 3: Completely unrelated PDF (event poster/brochure/invoice) is REJECTED."""
        pdf_bytes = _make_pdf_bytes(
            [
                "The Students Collective presents Podcast Session\n"
                "Guest: CEO @ Revithalize\nVenue: 9th Block Auditorium\nSCAN ME TO REGISTER"
            ]
        )
        ai_res = _valid_ai_payload(
            {
                "document_type": "poster_flyer",
                "is_exam_paper": False,
                "institution": {"name": "", "status": "MISSING"},
                "structural_analysis": {
                    "header": "INVALID",
                    "instructions": "MISSING",
                    "question_numbering": "MISSING",
                    "marks_distribution": "MISSING",
                    "sections": "MISSING",
                    "footer": "MISSING",
                    "overall_layout": "INVALID",
                },
                "issues": [{"severity": "HIGH", "issue": "Document is a promotional event poster, not an exam paper."}],
                "decision": "REJECT",
                "confidence": 0.98,
                "reason": "Promotional podcast session flyer, not an examination question paper.",
            }
        )
        svc = AIExaminerService(gemini_client=_FakeGeminiClient(lambda doc, meta: ai_res))
        status, payload = svc.examine_upload(pdf_bytes, "podcast.pdf", "application/pdf")

        self.assertEqual(status, 200)
        self.assertEqual(payload["verification"]["decision"], "REJECT")

    def test_4_image_of_valid_sru_paper_with_exif_rotation(self):
        """TEST 4: Valid SRU exam scan image (with EXIF orientation correction) is APPROVED."""
        img_bytes = _make_crisp_exam_image_bytes(
            [
                "SR UNIVERSITY - SCHOOL OF CS&AI",
                "Course Code: 24CS301PC211 | Regulation: R24 | B.Tech CSE",
                "Information Management System - End Term Exam (40 Marks)",
                "ANSWER ALL QUESTIONS",
                "1. Explain B+ Tree indexing and ACID properties. (10 Marks)",
                "2. Compare MongoDB document model vs Relational DBMS. (10 Marks)",
                "3. Design normalized tables up to BCNF with FDs. (10 Marks)",
                "4. Discuss two-phase locking and deadlock recovery. (10 Marks)",
            ],
            fmt="JPEG",
            exif_orientation=6,
        )
        fake = _FakeGeminiClient(lambda doc, meta: _valid_ai_payload())
        svc = AIExaminerService(gemini_client=fake)
        status, payload = svc.examine_upload(img_bytes, "scan.jpg", "image/jpeg")

        self.assertEqual(status, 200)
        self.assertEqual(payload["verification"]["decision"], "APPROVE")
        self.assertEqual(fake.calls, 1)

    def test_5_blurry_or_low_res_paper_routes_to_human_review(self):
        """TEST 5: Blurry or unreadable low-res image returns HUMAN_REVIEW instead of auto-rejecting."""
        from PIL import ImageFilter

        crisp_bytes = _make_crisp_exam_image_bytes(
            [
                "SR UNIVERSITY",
                "Course Code: 24CS301PC211",
                "1. Explain operating systems process scheduling. (10M)",
                "2. Explain paging and segmentation. (10M)",
            ],
            fmt="PNG",
        )
        with Image.open(BytesIO(crisp_bytes)) as img:
            blurred = img.filter(ImageFilter.GaussianBlur(radius=5.0))
            out = BytesIO()
            blurred.save(out, format="JPEG")
            blurry_bytes = out.getvalue()

        fake = _FakeGeminiClient(lambda doc, meta: _valid_ai_payload())
        svc = AIExaminerService(gemini_client=fake)
        status, payload = svc.examine_upload(blurry_bytes, "blurry_photo.jpg", "image/jpeg")

        self.assertEqual(status, 200)
        self.assertEqual(payload["verification"]["decision"], "HUMAN_REVIEW")
        self.assertIn(POOR_QUALITY_MESSAGE, payload["verification"]["reason"])
        self.assertEqual(fake.calls, 0)  # Saved API call on unreadable quality

    def test_6_genuine_paper_with_missing_optional_fields_not_false_rejected(self):
        """TEST 6: Genuine SRU paper omitting coordinator/year/date/footer is still APPROVED cleanly."""
        pdf_bytes = _make_pdf_bytes(
            [
                "SR UNIVERSITY\nCourse Code: 22CS204\nSubject: Operating Systems\n"
                "End Term Examination\n1. Explain deadlock prevention. [10M]\n2. Explain virtual memory. [10M]"
            ]
        )
        ai_res = _valid_ai_payload(
            {
                "metadata": {
                    "course_code": "22CS204",
                    "subject_code": "22CS204",
                    "subject_name": "Operating Systems",
                    "regulation": "",
                    "academic_year": "",
                    "branch": "CSE",
                    "year": "",
                    "semester": "",
                    "exam_type": "End Term",
                    "course_coordinator": "",
                    "date": "",
                    "duration": "2 Hours",
                    "max_marks": "40",
                },
                "structural_analysis": {
                    "header": "VALID",
                    "instructions": "NOT_APPLICABLE",
                    "question_numbering": "VALID",
                    "marks_distribution": "VALID",
                    "sections": "PARTIAL",
                    "footer": "MISSING",
                    "overall_layout": "VALID",
                },
                "evidence": [
                    {"category": "institution", "status": "PRESENT", "observation": "SR University header present."},
                    {"category": "coordinator", "status": "MISSING", "observation": "Coordinator name not printed."},
                ],
                "decision": "APPROVE",
                "confidence": 0.88,
                "reason": "Genuine SRU exam structure despite missing optional fields.",
            }
        )
        svc = AIExaminerService(gemini_client=_FakeGeminiClient(lambda doc, meta: ai_res))
        status, payload = svc.examine_upload(pdf_bytes, "partial_fields.pdf", "application/pdf")

        self.assertEqual(status, 200)
        self.assertEqual(payload["verification"]["decision"], "APPROVE")

    def test_7_inconsistent_course_information_blocked(self):
        """TEST 7: Uploaded paper contradicts submitted/internal course metadata -> never APPROVED."""
        pdf_bytes = _make_pdf_bytes(
            [
                "SR UNIVERSITY\nCourse Code: 24CS301PC211 Information Management System\n"
                "1. Write SQL queries for relational schema. [10M]"
            ]
        )
        ai_res = _valid_ai_payload(
            {
                "evidence": [
                    {
                        "category": "course_consistency",
                        "status": "CONTRADICTORY",
                        "observation": "Questions cover Thermodynamics while subject title states DBMS.",
                    }
                ],
                "issues": [
                    {
                        "severity": "HIGH",
                        "issue": "Course title and questions belong to incompatible subjects.",
                    }
                ],
                "decision": "HUMAN_REVIEW",
                "confidence": 0.52,
                "reason": "Inconsistent course code/subject between metadata and questions.",
            }
        )
        svc = AIExaminerService(gemini_client=_FakeGeminiClient(lambda doc, meta: ai_res))
        status, payload = svc.examine_upload(
            pdf_bytes,
            "mismatch.pdf",
            "application/pdf",
            user_metadata={"subjectCode": "22ME405", "regulation": "R20"},
        )

        self.assertEqual(status, 200)
        self.assertNotEqual(payload["verification"]["decision"], "APPROVE")
        self.assertIn(payload["verification"]["decision"], ("REJECT", "HUMAN_REVIEW"))

    def test_8_fake_keyword_stuffed_sru_paper_anti_bypass_rejected(self):
        """TEST 8: Malicious keyword-stuffed fake document containing 'SR University' is REJECTED even if AI hints approve."""
        pdf_bytes = _make_pdf_bytes(
            [
                "SR University\nCourse Coordinator Name: Prof X\nCourse Code: FAKE999\n"
                "This is a cheat sheet / notes dump disguised with SRU labels."
            ]
        )
        # Simulate adversarial case where Gemini flagged suspicious_signals and non-exam nature
        ai_res = _valid_ai_payload(
            {
                "document_type": "class_notes",
                "is_exam_paper": False,
                "suspicious_signals": [
                    "Contains 'SR University' and 'Course Coordinator' labels pasted above non-examination notes."
                ],
                "issues": [{"severity": "HIGH", "issue": "Keyword-stuffed non-exam material."}],
                "decision": "APPROVE",  # Even if model hallucinated APPROVE, deterministic engine blocks!
                "confidence": 0.90,
                "reason": "Labels appear copied without real examination questions.",
            }
        )
        svc = AIExaminerService(gemini_client=_FakeGeminiClient(lambda doc, meta: ai_res))
        status, payload = svc.examine_upload(pdf_bytes, "fake_sru.pdf", "application/pdf")

        self.assertEqual(status, 200)
        self.assertEqual(payload["verification"]["decision"], "REJECT")

    def test_9_multipage_pdf_inspects_all_pages_and_caps_safely(self):
        """TEST 9: Multi-page PDF inspects all pages (Page 1..4) and safely samples very long PDFs."""
        pages = [
            "Page 1: SR UNIVERSITY\nB.TECH END TERM\nInstructions: Answer All Questions.",
            "Page 2: SECTION A\n1. Define relational algebra operators. [5M]",
            "Page 3: SECTION B\n2. Explain B+ tree deletion algorithm. [10M]",
            "Page 4: SECTION C\n3. Distributed transactions & 2PC protocol. [15M]\n--- END OF PAPER ---",
        ]
        pdf_bytes = _make_pdf_bytes(pages)
        observed = {}

        def _capture(doc, meta):
            observed["page_count"] = doc.page_count
            observed["visual_pages"] = len(doc.visual_pages)
            observed["sampled"] = doc.sampled_page_numbers
            observed["text_pages"] = len(doc.pdf_page_texts)
            return _valid_ai_payload()

        svc = AIExaminerService(gemini_client=_FakeGeminiClient(_capture))
        status, payload = svc.examine_upload(pdf_bytes, "multipage.pdf", "application/pdf")

        self.assertEqual(status, 200)
        self.assertEqual(payload["verification"]["decision"], "APPROVE")
        self.assertEqual(observed["page_count"], 4)
        self.assertEqual(observed["visual_pages"], 4)
        self.assertEqual(observed["sampled"], [1, 2, 3, 4])
        self.assertEqual(observed["text_pages"], 4)

        # Also verify 12-page PDF extracts ALL 12 page texts while capping visual renders safely to <= 6
        doc_12 = process_uploaded_document(
            _make_pdf_bytes([f"Page {i} SR UNIVERSITY Question {i}" for i in range(1, 13)]),
            "long_12_pages.pdf",
            max_pdf_pages=6,
        )
        self.assertEqual(doc_12.page_count, 12)
        self.assertEqual(len(doc_12.pdf_page_texts), 12)
        self.assertEqual(len(doc_12.visual_pages), 6)
        self.assertIn(1, doc_12.sampled_page_numbers)
        self.assertIn(12, doc_12.sampled_page_numbers)

    def test_10_corrupted_and_unsupported_uploads_rejected_safely(self):
        """TEST 10: Corrupted PDFs, fake extensions, SVGs, executables, and empty files are rejected."""
        svc = AIExaminerService(gemini_client=_FakeGeminiClient(lambda doc, meta: _valid_ai_payload()))

        # 1. Corrupted PDF bytes
        s1, p1 = svc.examine_upload(b"%PDF-1.7\ngarbage-corrupted-body", "broken.pdf", "application/pdf")
        self.assertEqual(s1, 400)
        self.assertFalse(p1["success"])
        self.assertEqual(p1["verification"]["decision"], "REJECT")

        # 2. SVG XSS vector disguised or direct
        s2, p2 = svc.examine_upload(b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "bad.svg", "image/svg+xml")
        self.assertEqual(s2, 400)
        self.assertEqual(p2["verification"]["decision"], "REJECT")

        # 3. Executable spoofed as .png
        s3, p3 = svc.examine_upload(b"MZ\x90\x00\x03\x00\x00\x00fake_exe", "virus.png", "image/png")
        self.assertEqual(s3, 400)
        self.assertFalse(p3["success"])

        # 4. Empty upload
        s4, p4 = svc.examine_upload(b"", "empty.pdf", "application/pdf")
        self.assertEqual(s4, 400)

        # 5. Filename path traversal sanitization
        self.assertEqual(sanitize_filename("../../../../etc/passwd\x00.pdf"), "passwd_.pdf")

    def test_gemini_api_failure_never_approves_and_returns_503(self):
        """When Gemini is unavailable/times out/key missing, NEVER approve and return friendly error."""
        pdf_bytes = _make_pdf_bytes(["SR UNIVERSITY\nCourse Code: 24CS301PC211\n1. Explain DBMS."])

        class _FailingClient:
            def get_model_name(self):
                return "gemini-3.8-flash"

            def analyze_document(self, doc, user_metadata=None):
                raise GeminiServiceUnavailableError(AI_UNAVAILABLE_MESSAGE, error_category="TIMEOUT")

        svc = AIExaminerService(gemini_client=_FailingClient())
        status, payload = svc.examine_upload(pdf_bytes, "paper.pdf", "application/pdf")

        self.assertEqual(status, 503)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"], AI_UNAVAILABLE_MESSAGE)
        self.assertNotEqual(payload["verification"]["decision"], "APPROVE")

    def test_malformed_gemini_json_handled_without_crash(self):
        """Malformed JSON from Gemini raises cleanly and strips fences when valid."""
        with self.assertRaises(ValueError):
            _parse_and_normalize_ai_json("not valid json {{{")

        fenced = "```json\n" + json.dumps(_valid_ai_payload()) + "\n```"
        parsed = _parse_and_normalize_ai_json(fenced)
        self.assertEqual(parsed["decision"], "APPROVE")

    def test_real_workspace_assets_preprocess_cleanly(self):
        """Validate preprocessing works cleanly on real sample files in local Downloads/artifacts if present."""
        sample_pdf = r"C:\Users\AITHA VENKATA SAI\Downloads\25CAI102PC205_CSE_MID_1.pdf"
        sample_png = r"C:\Users\AITHA VENKATA SAI\.gemini\antigravity\brain\58a2024d-fc87-4f3c-b8fb-a8118ba1854f\.user_uploaded\media_1793691355935_afc0cf1c.png"
        if os.path.exists(sample_pdf):
            with open(sample_pdf, "rb") as handle:
                doc = process_uploaded_document(handle.read(), "real.pdf", "application/pdf")
            self.assertTrue(doc.is_pdf)
            self.assertGreaterEqual(doc.page_count, 1)
            self.assertFalse(doc.quality_insufficient)
        if os.path.exists(sample_png):
            with open(sample_png, "rb") as handle:
                doc = process_uploaded_document(handle.read(), "real.png", "image/png")
            self.assertFalse(doc.is_pdf)
            self.assertFalse(doc.quality_insufficient)

    def test_http_endpoint_verify_paper_multipart_and_cache_and_cleanup(self):
        """End-to-end HTTP POST /api/verify-paper over live local TCP socket with mocked Gemini."""
        class _QuietHandler(PaperHubHandler):
            def log_message(self, format, *args):
                pass

        class _TCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True

        httpd = _TCPServer(("127.0.0.1", 0), _QuietHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        try:
            pdf_bytes = _make_pdf_bytes(
                [
                    "SR UNIVERSITY\nCourse Code: 24CS301PC211\nInformation Management System\n"
                    "End Term Regulation R24 Academic Year 2025-2026\n1. Explain normalization. [10M]"
                ]
            )
            fake = _FakeGeminiClient(lambda doc, meta: _valid_ai_payload())

            with patch("server.verify_paper_handler.examiner_service.gemini_client", fake):
                ct, body = _encode_multipart(
                    "file",
                    "valid_sru.pdf",
                    "application/pdf",
                    pdf_bytes,
                    metadata_dict={"subjectCode": "24CS301PC211", "regulation": "R24"},
                )
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/verify-paper",
                    data=body,
                    method="POST",
                    headers={"Content-Type": ct, "Content-Length": str(len(body))},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    self.assertEqual(resp.status, 200)
                    res_json = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(res_json["success"])
                self.assertEqual(res_json["verification"]["decision"], "APPROVE")
                self.assertFalse(res_json["verification"]["cached"])
                self.assertEqual(fake.calls, 1)

                # Identical re-upload hits short-lived TTL cache (cost optimization!)
                req2 = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/verify-paper",
                    data=body,
                    method="POST",
                    headers={"Content-Type": ct, "Content-Length": str(len(body))},
                )
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    res2 = json.loads(resp2.read().decode("utf-8"))
                self.assertTrue(res2["verification"]["cached"])
                self.assertEqual(fake.calls, 1)

                # Invalid .exe upload gets 400 JSON without crashing server
                ct_bad, body_bad = _encode_multipart("file", "malware.exe", "application/octet-stream", b"MZ\x90\x00test")
                req_bad = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/verify-paper",
                    data=body_bad,
                    method="POST",
                    headers={"Content-Type": ct_bad, "Content-Length": str(len(body_bad))},
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(req_bad, timeout=10)
                self.assertEqual(ctx.exception.code, 400)
                err_body = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertFalse(err_body["success"])

            # Verify no temp files leaked from sru_examiner_*
            leftover = [
                name for name in os.listdir(tempfile.gettempdir()) if name.startswith("sru_examiner_")
            ]
            self.assertEqual(leftover, [])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_no_gemini_api_key_or_internal_prompt_exposed_in_frontend(self):
        """Ensure built HTML contains no GEMINI_API_KEY and no backend prompt template text."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "public", "index.html"), encoding="utf-8") as handle:
            html = handle.read()
        self.assertNotIn("GEMINI_API_KEY", html)
        self.assertNotIn("AIza", html)
        self.assertNotIn("DOCUMENT ANALYSIS:", html)

    def test_gemini_client_interactions_wire_retry_and_privacy_store_false(self):
        """Verify GeminiExaminerClient calls Interactions API with store=False, handles 503 retries, and uses env key securely."""
        import httpx
        from google import genai
        from server.ai_examiner import GeminiExaminerClient

        attempts = {"count": 0, "bodies": []}

        def transport_handler(request):
            attempts["count"] += 1
            attempts["bodies"].append(json.loads(request.content.decode("utf-8")))
            if attempts["count"] == 1:
                return httpx.Response(503, json={"error": {"message": "Temporary overload"}})
            return httpx.Response(
                200,
                json={
                    "id": "int_123",
                    "status": "completed",
                    "object": "interaction",
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [{"type": "text", "text": json.dumps(_valid_ai_payload())}],
                        }
                    ],
                },
            )

        cfg = SRUValidationConfig()
        cfg.max_retries = 2
        gm_client = GeminiExaminerClient(cfg)
        mock_sdk = genai.Client(
            api_key="unit-test-secret",
            http_options={"httpx_client": httpx.Client(transport=httpx.MockTransport(transport_handler))},
        )
        gm_client._client = mock_sdk
        gm_client._cached_api_key = "unit-test-secret"

        doc = process_uploaded_document(
            _make_pdf_bytes(["SR UNIVERSITY\nCourse Code: 24CS301PC211\n1. Explain DBMS."]),
            "wire_test.pdf",
            "application/pdf",
        )
        with patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-secret", "GEMINI_MODEL": "gemini-3.8-flash"}):
            with patch("server.ai_examiner.time.sleep", return_value=None):
                parsed, model_name = gm_client.analyze_document(doc)

        self.assertEqual(attempts["count"], 2)
        self.assertEqual(model_name, "gemini-3.8-flash")
        self.assertEqual(parsed["decision"], "APPROVE")
        self.assertFalse(attempts["bodies"][1]["store"])
        self.assertEqual(attempts["bodies"][1]["response_format"]["mime_type"], "application/json")
        self.assertGreaterEqual(len(attempts["bodies"][1]["input"]), 1)

        # Also verify missing GEMINI_API_KEY fails safely without approving
        gm_missing = GeminiExaminerClient(cfg)
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(GeminiServiceUnavailableError) as err_ctx:
                gm_missing.analyze_document(doc)
            self.assertEqual(err_ctx.exception.error_category, "MISSING_API_KEY")


if __name__ == "__main__":
    unittest.main()
