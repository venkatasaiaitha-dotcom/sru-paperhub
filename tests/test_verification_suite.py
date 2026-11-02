import unittest
from server.verifier import verifier

class TestVerificationSuite(unittest.TestCase):
    def setUp(self):
        # Base authentic text from SR University question paper
        self.genuine_ocr_text = """
SR UNIVERSITY
SCHOOL OF CS&AI DEPARTMENT OF CSE
Program Name: B.TECH Exam Type: End Term Academic Year: 2025-2026
Course Coordinator Name: DR. P. PRAVEEN
Course Code: 24CS301PC211 Course Title: Information Management System
Year/Sem: II/I Regulation: R24
Date of Exam: 04-12-2025 Time: 10:00 A.M to 12:00 P.M
Duration: 2 Hours Max. Marks: 40
ANSWER ALL QUESTIONS
Q.No. Question Marks
1 A. The national bank uses MongoDB to store customer information...
B. The following ER Diagram represents entities and their relationships... 5+5
Note: Do not write SQL CREATE commands or insert statements
"""
        self.student_selection = {
            "branch": "CSE",
            "semester": 3,
            "regulation": "R24",
            "academicYear": "2025-2026",
            "subjectCode": "24CS301PC211",
            "subjectName": "Information Management System",
            "examType": "SEM_END"
        }
        self.dummy_bytes = b"DUMMY_IMAGE_BYTES_FOR_TESTING_DATA"

    # TEST 1: Genuine SR University question paper. Expected: APPROVED
    def test_1_genuine_sru_paper(self):
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="paper.webp",
            mime_type="image/webp",
            student_selection=self.student_selection,
            client_ocr_text=self.genuine_ocr_text,
            ocr_confidence=90
        )
        self.assertEqual(rep["decision"], "APPROVED")
        self.assertEqual(rep["layers"]["layer_3_identity"]["status"], "PASSED")
        self.assertEqual(rep["layers"]["layer_4_coordinator"]["status"], "PASSED")

    # TEST 2: Class notes with SR University heading. Expected: REJECTED
    def test_2_class_notes(self):
        notes_text = """
SR UNIVERSITY - DEPARTMENT OF CSE
Lecture Notes: Database Management Systems
Chapter 1: Relational Data Model.
These are handwritten lecture notes explaining B+ Trees and indexing mechanisms.
        """
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="notes.pdf",
            mime_type="application/pdf",
            student_selection=self.student_selection,
            client_ocr_text=notes_text,
            ocr_confidence=92
        )
        self.assertEqual(rep["decision"], "REJECTED")
        self.assertEqual(rep["layers"]["layer_2_classification"]["status"], "FAILED")

    # TEST 3: Assignment renamed as question paper. Expected: REJECTED
    def test_3_assignment(self):
        assignment_text = """
SR UNIVERSITY
Department of Computer Science and Engineering
Home Assignment 2
Submitted by: Rahul Sharma, 22SR1A0501
Subject: Database Management Systems
        """
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="assignment.pdf",
            mime_type="application/pdf",
            student_selection=self.student_selection,
            client_ocr_text=assignment_text,
            ocr_confidence=88
        )
        self.assertEqual(rep["decision"], "REJECTED")
        self.assertEqual(rep["layers"]["layer_2_classification"]["status"], "FAILED")

    # TEST 4: Question paper from another university. Expected: REJECTED
    def test_4_other_university_paper(self):
        other_uni_text = """
Jawaharlal Nehru Technological University Hyderabad (JNTUH)
B.Tech III Year I Semester Examinations
Database Management Systems
Q.No. Question Marks
1 Explain Relational Algebra with examples. [10M]
        """
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="jntu_paper.pdf",
            mime_type="application/pdf",
            student_selection=self.student_selection,
            client_ocr_text=other_uni_text,
            ocr_confidence=90
        )
        self.assertEqual(rep["decision"], "REJECTED")
        self.assertIn("disallowed non-exam material: Other University Paper", rep["reasons"][0])

    # TEST 5: Genuine SR University question paper with wrong selected branch. Expected: REJECTED
    def test_5_branch_mismatch(self):
        wrong_selection = dict(self.student_selection)
        wrong_selection["branch"] = "CIVIL"  # Paper is CSE
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="paper.webp",
            mime_type="image/webp",
            student_selection=wrong_selection,
            client_ocr_text=self.genuine_ocr_text,
            ocr_confidence=90
        )
        self.assertEqual(rep["decision"], "REJECTED")
        self.assertTrue(any("Branch mismatch" in r for r in rep["reasons"]))

    # TEST 6: Genuine question paper missing Course Coordinator name. Expected: REJECTED / MANUAL REVIEW
    def test_6_missing_coordinator_name(self):
        missing_coord_text = self.genuine_ocr_text.replace("DR. P. PRAVEEN", "")
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="paper.webp",
            mime_type="image/webp",
            student_selection=self.student_selection,
            client_ocr_text=missing_coord_text,
            ocr_confidence=85
        )
        self.assertIn(rep["decision"], ["MANUAL_REVIEW", "REJECTED"])
        self.assertTrue(any("Course Coordinator name" in r for r in rep["reasons"]))

    # TEST 7: Genuine question paper missing the words "Course Coordinator". Expected: REJECTED
    def test_7_missing_coordinator_label(self):
        no_label_text = self.genuine_ocr_text.replace("Course Coordinator Name:", "")
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="paper.webp",
            mime_type="image/webp",
            student_selection=self.student_selection,
            client_ocr_text=no_label_text,
            ocr_confidence=85
        )
        self.assertEqual(rep["decision"], "REJECTED")
        self.assertTrue(any("Course Coordinator" in r for r in rep["reasons"]))

    # TEST 8: Genuine question paper with missing subject code / mismatch. Expected: REJECTED
    def test_8_subject_code_mismatch(self):
        wrong_code_selection = dict(self.student_selection)
        wrong_code_selection["subjectCode"] = "22ME101" # Mismatched Mechanical code
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="paper.webp",
            mime_type="image/webp",
            student_selection=wrong_code_selection,
            client_ocr_text=self.genuine_ocr_text,
            ocr_confidence=90
        )
        self.assertEqual(rep["decision"], "REJECTED")
        self.assertTrue(any("Course Code mismatch" in r for r in rep["reasons"]))

    # TEST 9: Blurry scanned question paper (low confidence). Expected: MANUAL REVIEW
    def test_9_blurry_scan(self):
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="paper.webp",
            mime_type="image/webp",
            student_selection=self.student_selection,
            client_ocr_text=self.genuine_ocr_text,
            ocr_confidence=42  # Low confidence below threshold
        )
        self.assertEqual(rep["decision"], "MANUAL_REVIEW")

    # TEST 10: Blank or corrupted PDF. Expected: REJECTED
    def test_10_blank_or_empty(self):
        rep = verifier.verify(
            file_bytes=b"",
            filename="empty.pdf",
            mime_type="application/pdf",
            student_selection=self.student_selection,
            client_ocr_text="",
            ocr_confidence=0
        )
        self.assertEqual(rep["decision"], "REJECTED")
        self.assertEqual(rep["layers"]["layer_1_file"]["status"], "FAILED")

    # TEST 11: Minor scanning/margin variations with genuine paper. Expected: APPROVED
    def test_11_minor_variations_approved(self):
        variation_text = self.genuine_ocr_text.replace("2025-2026", "2025-26")
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="paper_scan.webp",
            mime_type="image/webp",
            student_selection=self.student_selection,
            client_ocr_text=variation_text,
            ocr_confidence=88
        )
        self.assertEqual(rep["decision"], "APPROVED")

    # TEST 12: Document containing forged university details. Expected: REJECTED
    def test_12_forged_details(self):
        forged_text = """
FAKE UNIVERSITY WARANGAL
Department of CS
Course Coordinator: John Doe
Question 1: Explain forgery [10M]
        """
        rep = verifier.verify(
            file_bytes=self.dummy_bytes,
            filename="fake.pdf",
            mime_type="application/pdf",
            student_selection=self.student_selection,
            client_ocr_text=forged_text,
            ocr_confidence=75
        )
        self.assertEqual(rep["decision"], "REJECTED")
        self.assertEqual(rep["layers"]["layer_3_identity"]["status"], "FAILED")

if __name__ == '__main__':
    unittest.main()
