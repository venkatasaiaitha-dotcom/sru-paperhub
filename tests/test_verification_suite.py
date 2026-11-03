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
1 A. The national bank uses MongoDB to store customer information and their transaction records.
The database contains two collections: accounts and transactions. 5+5
B. The following ER Diagram represents entities and their relationships in a system.
Convert this ER Model into its Relational Model by listing all relations with their attributes.
"""
        self.genuine_selection = {
            "branch": "CSE",
            "semester": "3",
            "regulation": "R24",
            "academicYear": "2025-2026",
            "subjectCode": "24CS301PC211",
            "subjectName": "Information Management System",
            "examType": "SEM_END"
        }

    def test_1_genuine_sru_paper_approved(self):
        """Genuine SR University paper with upperbox header & course code is APPROVED."""
        report = verifier.verify(
            file_bytes=b"",
            filename="genuine_paper.jpg",
            mime_type="image/jpeg",
            student_selection=self.genuine_selection,
            client_ocr_text=self.genuine_ocr_text,
            ocr_confidence=92
        )
        self.assertEqual(report["decision"], "APPROVED")
        self.assertFalse(report.get("is_duplicate"))
        self.assertEqual(report["extracted_fields"]["university_name"], "SR UNIVERSITY")
        self.assertEqual(report["extracted_fields"]["course_code"], "24CS301PC211")

    def test_2_missing_sr_university_header(self):
        """Missing 'SR UNIVERSITY' in upper box is rejected as not a valid paper."""
        text = self.genuine_ocr_text.replace("SR UNIVERSITY", "ABC INSTITUTE")
        text = text.replace("SCHOOL OF CS&AI", "")
        report = verifier.verify(
            file_bytes=b"",
            filename="no_sru.jpg",
            mime_type="image/jpeg",
            student_selection=self.genuine_selection,
            client_ocr_text=text,
            ocr_confidence=85
        )
        self.assertEqual(report["decision"], "REJECTED")
        self.assertTrue(any("SR UNIVERSITY" in r for r in report["reasons"]))

    def test_3_course_code_mismatch(self):
        """Course code mismatch is rejected as not a valid paper for that code."""
        wrong_selection = dict(self.genuine_selection)
        wrong_selection["subjectCode"] = "22EC401"
        report = verifier.verify(
            file_bytes=b"",
            filename="wrong_code.jpg",
            mime_type="image/jpeg",
            student_selection=wrong_selection,
            client_ocr_text=self.genuine_ocr_text,
            ocr_confidence=90
        )
        self.assertEqual(report["decision"], "REJECTED")
        self.assertTrue(any("Course code" in r for r in report["reasons"]))

    def test_4_class_notes_rejected(self):
        """Class notes uploaded as question paper is rejected."""
        notes_text = """
SR UNIVERSITY
Class Notes - Module 2 Database Indexing
Course Code: 24CS301PC211
Here are my handwritten lecture notes explaining B+ Trees and MongoDB.
"""
        report = verifier.verify(
            file_bytes=b"",
            filename="notes.jpg",
            mime_type="image/jpeg",
            student_selection=self.genuine_selection,
            client_ocr_text=notes_text,
            ocr_confidence=88
        )
        self.assertEqual(report["decision"], "REJECTED")
        self.assertTrue(any("prohibited" in r.lower() or "notes" in r.lower() for r in report["reasons"]))

    def test_5_student_assignment_rejected(self):
        """Assignment uploaded as question paper is rejected."""
        assignment_text = """
SR UNIVERSITY
DEPARTMENT OF CSE
Assignment No 3 - Information Management System
Course Code: 24CS301PC211
Student Name: Rahul Sharma
Question 1: Explain relational normalization with examples.
"""
        report = verifier.verify(
            file_bytes=b"",
            filename="assignment.jpg",
            mime_type="image/jpeg",
            student_selection=self.genuine_selection,
            client_ocr_text=assignment_text,
            ocr_confidence=90
        )
        self.assertEqual(report["decision"], "REJECTED")

    def test_6_blank_or_empty_rejected(self):
        """Blank document is rejected."""
        report = verifier.verify(
            file_bytes=b"",
            filename="blank.jpg",
            mime_type="image/jpeg",
            student_selection=self.genuine_selection,
            client_ocr_text="",
            ocr_confidence=0
        )
        self.assertEqual(report["decision"], "REJECTED")

    def test_7_duplicate_detection_same_code(self):
        """Uploading the exact same paper already in past data is detected as DUPLICATE."""
        existing_papers = [
            {
                "id": "sru_cse_24cs301pc211_past",
                "subject_code": "24CS301PC211",
                "subject_name": "Information Management System",
                "extracted_text": self.genuine_ocr_text
            }
        ]
        report = verifier.verify(
            file_bytes=b"",
            filename="duplicate_paper.jpg",
            mime_type="image/jpeg",
            student_selection=self.genuine_selection,
            client_ocr_text=self.genuine_ocr_text,
            ocr_confidence=95,
            existing_papers=existing_papers
        )
        self.assertEqual(report["decision"], "REJECTED")
        self.assertTrue(report.get("is_duplicate"))
        self.assertTrue(any("already exists" in r.lower() for r in report["reasons"]))

    def test_8_duplicate_detection_mistaken_typo_code(self):
        """If user enters mistaken course code (e.g. 24CS301 instead of 24CS301PC211) but uploads same paper, AI detects duplicate from past data."""
        existing_papers = [
            {
                "id": "sru_cse_24cs301pc211_original",
                "subject_code": "24CS301PC211",
                "subject_name": "Information Management System",
                "extracted_text": self.genuine_ocr_text
            }
        ]
        # User mistakenly writes code as "24CS301" or "CS301"
        mistaken_selection = dict(self.genuine_selection)
        mistaken_selection["subjectCode"] = "24CS301"

        report = verifier.verify(
            file_bytes=b"",
            filename="reupload_same_paper.jpg",
            mime_type="image/jpeg",
            student_selection=mistaken_selection,
            client_ocr_text=self.genuine_ocr_text,
            ocr_confidence=92,
            existing_papers=existing_papers
        )
        self.assertEqual(report["decision"], "REJECTED")
        self.assertTrue(report.get("is_duplicate"))
        self.assertTrue(any("already exists" in r.lower() for r in report["reasons"]))


if __name__ == "__main__":
    unittest.main()
