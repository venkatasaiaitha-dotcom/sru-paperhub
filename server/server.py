import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import base64
import time

PORT = int(os.environ.get("PORT", 3000))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "initial_papers.json")
ANNOUNCEMENT_FILE = os.path.join(DATA_DIR, "announcement.json")
UPLOAD_DIR = os.path.join(PUBLIC_DIR, "uploads")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

def load_papers():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print("Error reading papers file:", e)
    return []

def save_papers(papers):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(papers, f, indent=2)
    except Exception as e:
        print("Error writing papers file:", e)

def load_announcement():
    try:
        if os.path.exists(ANNOUNCEMENT_FILE):
            with open(ANNOUNCEMENT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("text", "")
    except Exception:
        pass
    return "Welcome to SR University PaperHub! Browse past exam papers or upload new question papers to help your classmates."

def save_announcement(text):
    try:
        with open(ANNOUNCEMENT_FILE, "w", encoding="utf-8") as f:
            json.dump({"text": text, "updatedAt": int(time.time())}, f, indent=2)
    except Exception as e:
        print("Error writing announcement file:", e)

STUDENTS = []

class PaperHubHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def end_headers(self):
        # Universal CORS and tunnel headers for cross-device & proxy compatibility
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "*")
        if self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def _send_json(self, data, status=200):
        try:
            payload = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        # Handle CORS preflight cleanly
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_body_json(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len <= 0:
            return {}
        
        # Read exact content length in a loop to handle large payloads over tunnels
        body = b""
        remaining = content_len
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            body += chunk
            remaining -= len(chunk)
            
        try:
            return json.loads(body.decode("utf-8"))
        except Exception as e:
            print("JSON parse error:", e, "Body bytes received:", len(body))
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health check
        if path in ["/health", "/api/health"]:
            self._send_json({"status": "ok", "app": "SR University PaperHub"})
            return

        # Announcement
        if path == "/api/announcement":
            self._send_json({"announcement": load_announcement()})
            return

        # Papers listing (always reads latest from disk so all devices see uploaded papers)
        if path == "/api/papers":
            papers = load_papers()
            branch = query.get("branch", ["ALL"])[0]
            exam = query.get("exam", ["ALL"])[0]
            reg = query.get("regulation", ["ALL"])[0]
            q = query.get("query", [""])[0].lower()

            res = papers
            if branch != "ALL":
                res = [p for p in res if p.get("branch", "").upper() == branch.upper()]
            if exam != "ALL":
                res = [p for p in res if p.get("examType", "").upper() == exam.upper()]
            if reg != "ALL":
                res = [p for p in res if p.get("regulation", "").upper() == reg.upper()]
            if q:
                res = [p for p in res if q in p.get("subjectName", "").lower() or q in p.get("subjectCode", "").lower()]
            self._send_json(res)
            return

        elif path.startswith("/api/papers/"):
            paper_id = path.replace("/api/papers/", "").strip()
            papers = load_papers()
            paper = next((p for p in papers if p.get("id") == paper_id), None)
            if paper:
                self._send_json(paper)
            else:
                self._send_json({"error": "Paper not found"}, status=404)
            return

        # Serve index.html for root or SPA fallback
        filepath = os.path.join(PUBLIC_DIR, path.lstrip("/"))
        if not os.path.exists(filepath) or os.path.isdir(filepath):
            self.path = "/index.html"

        try:
            return super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        data = self._read_body_json()

        # Student Login / Registration
        if path == "/api/login":
            roll = data.get("rollNo", "").strip().upper()
            email = data.get("email", "").strip().lower()
            branch = data.get("branch", "CSE")
            semester = int(data.get("semester", 1))
            name = data.get("name", "").strip() or "Student"

            student = next((s for s in STUDENTS if s["rollNo"] == roll), None)
            if not student:
                student = {
                    "rollNo": roll,
                    "name": name,
                    "email": email,
                    "branch": branch,
                    "semester": semester
                }
                STUDENTS.append(student)
            else:
                student["branch"] = branch
                student["semester"] = semester
                if name != "Student":
                    student["name"] = name

            self._send_json({"success": True, "student": student})
            return

        # Admin Login
        elif path == "/api/admin/login":
            password = data.get("password", "")
            if password == ADMIN_PASSWORD:
                self._send_json({"success": True, "role": "admin", "token": "sru_admin_valid"})
            else:
                self._send_json({"success": False, "error": "Invalid Admin Password"}, status=401)
            return

        # Admin Delete Paper
        elif path == "/api/admin/delete":
            password = data.get("password", "")
            if password != ADMIN_PASSWORD:
                self._send_json({"success": False, "error": "Unauthorized"}, status=401)
                return

            paper_id = data.get("paperId", "")
            papers = load_papers()
            target_paper = next((p for p in papers if p.get("id") == paper_id), None)
            
            if target_paper:
                # Remove file if in uploads
                img_url = target_paper.get("imageUrl", "")
                if img_url.startswith("/uploads/"):
                    fname = os.path.basename(img_url)
                    fpath = os.path.join(UPLOAD_DIR, fname)
                    if os.path.isfile(fpath):
                        try:
                            os.remove(fpath)
                        except Exception:
                            pass
                
                papers = [p for p in papers if p.get("id") != paper_id]
                save_papers(papers)
                self._send_json({"success": True, "message": "Paper deleted successfully"})
            else:
                self._send_json({"success": False, "error": "Paper not found"}, status=404)
            return

        # Admin Update Announcement
        elif path == "/api/admin/announcement":
            password = data.get("password", "")
            if password != ADMIN_PASSWORD:
                self._send_json({"success": False, "error": "Unauthorized"}, status=401)
                return

            text = data.get("text", "").strip()
            save_announcement(text)
            self._send_json({"success": True, "announcement": text})
            return

        # Paper Upload (Cross-Device Shared Archive)
        elif path == "/api/upload":
            code = data.get("subjectCode", "SUB101").upper()
            name = data.get("subjectName", "Untitled Subject")
            branch = data.get("branch", "CSE")
            sem = int(data.get("semester", 1))
            exam = data.get("examType", "MID_1")
            reg = data.get("regulation", "R22")
            year = data.get("academicYear", "2025-2026")
            uploader_name = data.get("uploaderName", "Student")
            uploader_roll = data.get("uploaderRollNo", "SRU")
            image_data = data.get("imageData", "")

            # If image_data is provided as data URL, save to uploads directory
            image_url = "/images/paper_dsa.svg"
            if image_data.startswith("data:image"):
                try:
                    header, encoded = image_data.split(",", 1)
                    ext = "jpg"
                    if "png" in header:
                        ext = "png"
                    elif "webp" in header:
                        ext = "webp"
                    elif "svg" in header:
                        ext = "svg"
                    
                    filename = f"paper_{int(time.time())}_{code.lower()}.{ext}"
                    filepath = os.path.join(UPLOAD_DIR, filename)
                    with open(filepath, "wb") as img_file:
                        img_file.write(base64.b64decode(encoded))
                    image_url = f"/uploads/{filename}"
                except Exception as e:
                    print("Error saving image to disk:", e)

            exam_labels = {
                "MID_1": "Mid-Term 1",
                "MID_2": "Mid-Term 2",
                "SEM_END": "Semester End Exam",
                "SUPPLY": "Supplementary Exam"
            }

            new_id = f"sru_{branch.lower()}_{code.lower()}_{int(time.time())}"
            new_paper = {
                "id": new_id,
                "subjectCode": code,
                "subjectName": name,
                "branch": branch,
                "semester": sem,
                "examType": exam,
                "examTypeLabel": exam_labels.get(exam, exam),
                "regulation": reg,
                "academicYear": year,
                "duration": "90 Mins" if "MID" in exam else "3 Hours",
                "maxMarks": 30 if "MID" in exam else 60,
                "school": "School of Computer Science & AI" if branch in ["CSE", "AIML", "AIDS"] else "School of Engineering",
                "uploaderName": uploader_name,
                "uploaderRollNo": uploader_roll,
                "uploadDate": "Just now",
                "imageUrl": image_url,
                "downloadCount": 1
            }

            papers = load_papers()
            papers.insert(0, new_paper)
            save_papers(papers)

            print(f"Successfully saved new paper: {code} - {name} ({branch}). Total papers: {len(papers)}")
            self._send_json({"success": True, "paper": new_paper})
            return

        # Clear All Papers
        elif path in ["/api/clear", "/api/admin/clear-all"]:
            save_papers([])
            if os.path.exists(UPLOAD_DIR):
                for fname in os.listdir(UPLOAD_DIR):
                    fpath = os.path.join(UPLOAD_DIR, fname)
                    if os.path.isfile(fpath):
                        try:
                            os.remove(fpath)
                        except Exception:
                            pass
            self._send_json({"success": True, "message": "All papers erased"})
            return

        self._send_json({"error": "Endpoint not found"}, status=404)

class ThreadingPaperHubServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    host = "0.0.0.0"
    with ThreadingPaperHubServer((host, PORT), PaperHubHandler) as httpd:
        print(f"SR UNIVERSITY PAPERHUB Multi-Threaded Server running on http://{host}:{PORT}")
        print(f"Tunnel & Mobile Ready (DevTunnels, ngrok, cloudflared, localtunnel)")
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
