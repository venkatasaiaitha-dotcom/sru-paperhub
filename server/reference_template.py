"""
SR University Question Paper Reference Template & Validation Profile
Based on authentic SR University examination papers (e.g. B.Tech End Term / Mid Term).
"""

import re

REFERENCE_TEMPLATE = {
    "institution": {
        "name": "SR UNIVERSITY",
        "aliases": [
            "SR UNIVERSITY",
            "SRU",
            "SR UNIVERSITY WARANGAL",
            "SR UNIVERSITY, WARANGAL"
        ],
        "header_pattern": r"\b(SR\s+UNIVERSITY|SRU)\b",
        "schools": [
            "SCHOOL OF CS&AI",
            "SCHOOL OF COMPUTER SCIENCE & AI",
            "SCHOOL OF ENGINEERING",
            "SCHOOL OF BUSINESS",
            "SCHOOL OF SCIENCES"
        ],
        "departments": [
            "DEPARTMENT OF CSE",
            "DEPARTMENT OF COMPUTER SCIENCE",
            "DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING",
            "DEPARTMENT OF AIML",
            "DEPARTMENT OF AI & DATA SCIENCE",
            "DEPARTMENT OF ECE",
            "DEPARTMENT OF EEE",
            "DEPARTMENT OF MECH",
            "DEPARTMENT OF CIVIL"
        ]
    },
    
    # Mandatory Header Fields expected in SR University Question Papers
    "mandatory_fields": {
        "university_name": {
            "label": "University Name",
            "pattern": r"\bSR\s+UNIVERSITY\b",
            "required": True
        },
        "course_coordinator_label": {
            "label": "Course Coordinator Label",
            "pattern": r"\bCOURSE\s+COORDINATOR(\s+NAME)?\b",
            "required": True
        },
        "course_coordinator_name": {
            "label": "Course Coordinator Name",
            "pattern": r"(?:COURSE\s+COORDINATOR(?:\s+NAME)?[:\s\.\-\|]+)([A-Z\.\s]{3,35})(?=\s+(?:Course|Code|Regulation|Year|Date|Time|Max|$|\n))",
            "required": True
        },
        "course_code": {
            "label": "Course Code",
            "pattern": r"\b([0-9]{2}[A-Z]{2,4}[0-9]{2,4}[A-Z0-9]{2,6})\b",
            "required": True
        },
        "subject_name": {
            "label": "Subject Name / Course Title",
            "pattern": r"(?:Course\s+Title|Subject\s+Name)[:\s\.\-\|]+([A-Za-z0-9\s\&\-\/]{3,60})",
            "required": True
        },
        "regulation": {
            "label": "Regulation",
            "pattern": r"\b(R[1-2][0-9])\b",
            "required": True
        },
        "academic_year": {
            "label": "Academic Year",
            "pattern": r"\b(20[2-3][0-9]\s*[-–\/]\s*(?:20)?[2-3][0-9])\b",
            "required": True
        },
        "branch": {
            "label": "Branch / Department",
            "pattern": r"\b(CSE|AIML|AIDS|ECE|EEE|MECH|CIVIL|CS&AI|COMPUTER\s+SCIENCE)\b",
            "required": True
        },
        "year_of_study": {
            "label": "Year of Study / Semester",
            "pattern": r"\b(I{1,3}|IV|\b1st|\b2nd|\b3rd|\b4th|\b[1-4])\s*(?:Year|\/|\-|\s+Sem)",
            "required": True
        }
    },
    
    # Examination Structural Indicators
    "structure_indicators": {
        "instructions": [
            r"\bANSWER\s+ALL\s+QUESTIONS\b",
            r"\bANSWER\s+(?:ANY\s+)?[A-Z0-9]+\s+QUESTIONS\b",
            r"\bNOTE[:\s]",
            r"\bDURATION[:\s]",
            r"\bMAX(?:IMUM)?\.?\s+MARKS[:\s]"
        ],
        "question_numbering": [
            r"\bQ\.?\s*No\.?\b",
            r"^\s*([1-9]|10)\s*[\.\)]\s+",
            r"\b[1-9]\s*\.\s*[A-D]\s*[\.\)]",
            r"\b(?:Part|Section)\s*[-–\s]*[A-D]\b"
        ],
        "marks_allocation": [
            r"\b(?:Marks|Max\.?\s*Marks)\b",
            r"\[\s*[0-9]{1,2}\s*M\s*\]",
            r"\(\s*[0-9]{1,2}\s*Marks?\s*\)",
            r"\b[0-9]{1,2}\s*\+\s*[0-9]{1,2}\b"
        ]
    },

    # Indicators that signify non-question-paper documents (auto-reject)
    "disallowed_document_indicators": [
        (r"\b(Class\s+Notes|Lecture\s+Notes|Handwritten\s+Notes|Study\s+Material)\b", "Class Notes"),
        (r"\b(Assignment\s+[0-9]+|Assignment\s+No|Home\s+Assignment|Submitted\s+by)\b", "Assignment / Homework"),
        (r"\b(Lab\s+Manual|Lab\s+Record|Observation\s+Book|Practical\s+Record)\b", "Lab Record / Manual"),
        (r"\b(Project\s+Report|Mini\s+Project\s+Report|Major\s+Project|Abstract)\b", "Project Report"),
        (r"\b(Certificate\s+of\s+Participation|Certificate\s+of\s+Appreciation)\b", "Certificate"),
        (r"\b(Textbook|Chapter\s+[0-9]+|Table\s+of\s+Contents|ISBN\s+[0-9\-]+)\b", "Textbook"),
        (r"\b(Jawaharlal\s+Nehru\s+Technological\s+University|JNTUH|Osmania\s+University|Anna\s+University|VTU|IIT\s+[A-Za-z]+|NIT\s+[A-Za-z]+|Anurag\s+University|Vardhaman)\b", "Other University Paper")
    ],

    # Layout Parameters
    "layout": {
        "expected_page_size_mm": (210, 297), # A4
        "aspect_ratio_standard": 1.414,
        "aspect_ratio_tolerance_min": 1.20,
        "aspect_ratio_tolerance_max": 1.85,
        "header_region_max_pct": 0.40 # Header must reside in top 40% of document
    }
}
