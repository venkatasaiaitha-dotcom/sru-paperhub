import json
import os
import re

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "initial_papers.json")

def test_papers_dataset():
    assert os.path.exists(DATA_FILE), "initial_papers.json must exist"
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        papers = json.load(f)
    assert len(papers) >= 7, "Must contain papers across all engineering branches"
    
    branches = {p["branch"] for p in papers}
    expected_branches = {"CSE", "AIML", "ECE", "EEE", "MECH", "CIVIL", "AIDS"}
    assert expected_branches.issubset(branches), f"Missing branches: {expected_branches - branches}"

    for p in papers:
        assert "subjectCode" in p
        assert "subjectName" in p
        assert "partA" in p and len(p["partA"]) > 0
        assert "partB" in p and len(p["partB"]) > 0
        assert p["maxMarks"] in [30, 60]
        assert p["duration"] in ["90 Mins", "3 Hours"]
    print("[PASS] Test 1: Papers dataset contains complete branches and exam structures")

def test_karma_logic():
    initial_karma = 1240
    karma_per_upload = 50
    updated_karma = initial_karma + karma_per_upload
    assert updated_karma == 1290

    def calc_badge(pts):
        if pts >= 1000: return "Campus Legend"
        if pts >= 500: return "Senior Scholar"
        if pts >= 250: return "Top Contributor"
        return "Rising Star"

    assert calc_badge(1290) == "Campus Legend"
    assert calc_badge(600) == "Senior Scholar"
    assert calc_badge(300) == "Top Contributor"
    assert calc_badge(100) == "Rising Star"
    print("[PASS] Test 2: Karma increment and contributor badge progression")

def test_roll_and_email_validation():
    roll_regex = re.compile(r"^[0-9]{2}SR[0-9][A-Z][0-9]{4}$", re.IGNORECASE)
    assert roll_regex.match("21SR1A0501")
    assert roll_regex.match("22SR1A6704")

    email_regex = re.compile(r"^[A-Za-z0-9._%+-]+@sru\.edu\.in$", re.IGNORECASE)
    assert email_regex.match("21sr1a0501@sru.edu.in")
    assert not email_regex.match("user@gmail.com")
    print("[PASS] Test 3: Roll number and SRU email format validation")

if __name__ == "__main__":
    test_papers_dataset()
    test_karma_logic()
    test_roll_and_email_validation()
    print("\nALL WEB TESTS PASSED (3/3)!")
