import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import base64
import time
import secrets
import mimetypes

PORT = int(os.environ.get("PORT", 3000))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(BASE_DIR, "public")
DATA_DIR = os.path.join(BASE_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "initial_papers.json")
ANNOUNCEMENT_FILE = os.path.join(DATA_DIR, "announcement.json")
UPLOAD_DIR = os.path.join(PUBLIC_DIR, "uploads")
FEEDBACK_FILE = os.path.join(DATA_DIR, "feedbacks.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Rate limiting data structures (in-memory per IP)
UPLOAD_RATE_LIMITS = {}
FEEDBACK_RATE_LIMITS = {}

def check_rate_limit(ip, store, max_requests=5, window_sec=600):
    now = time.time()
    timestamps = store.get(ip, [])
    timestamps = [t for t in timestamps if (now - t) < window_sec]
    if len(timestamps) >= max_requests:
        store[ip] = timestamps
        return False, int(window_sec - (now - timestamps[0]))
    timestamps.append(now)
    store[ip] = timestamps
    return True, 0

def load_feedbacks():
    try:
        if os.path.exists(FEEDBACK_FILE):
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_feedbacks(feedbacks):
    try:
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(feedbacks, f, indent=2)
    except Exception as e:
        print("Error saving feedbacks:", e)

# Admin password must be provided via environment variable
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
if not ADMIN_PASSWORD:
    # Generate ephemeral secret if not set
    ADMIN_PASSWORD = secrets.token_urlsafe(16)
    print(f"[SECURITY NOTE] No ADMIN_PASSWORD env var provided. Ephemeral admin key generated: {ADMIN_PASSWORD}")

ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf"
}

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
        # Security headers
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
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
        # Enforce max body size of 15MB
        if content_len <= 0 or content_len > 15 * 1024 * 1024:
            return {}
        
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

        # Papers listing
        if path == "/api/papers":
            papers = load_papers()
            branch = query.get("branch", ["ALL"])[0]
            exam = query.get("exam", ["ALL"])[0]
            reg = query.get("regulation", ["ALL"])[0]
            q = query.get("query", [""])[0].lower()

            # Public archive only returns approved papers
            res = [p for p in papers if p.get("is_approved") is not False and p.get("status") != "pending"]
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

        elif path == "/api/admin/papers":
            # Admin endpoint to list all papers (including pending)
            self._send_json(load_papers())
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
            if password and password == ADMIN_PASSWORD:
                self._send_json({"success": True, "role": "admin", "token": secrets.token_hex(16)})
            else:
                self._send_json({"success": False, "error": "Invalid Admin Credentials"}, status=401)
            return

        # Admin Delete Paper
        elif path == "/api/admin/delete":
            password = data.get("password", "")
            if not password or password != ADMIN_PASSWORD:
                self._send_json({"success": False, "error": "Unauthorized"}, status=401)
                return

            paper_id = data.get("paperId", "")
            papers = load_papers()
            target_paper = next((p for p in papers if p.get("id") == paper_id), None)
            
            if target_paper:
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
            if not password or password != ADMIN_PASSWORD:
                self._send_json({"success": False, "error": "Unauthorized"}, status=401)
                return

            text = data.get("text", "").strip()
            save_announcement(text)
            self._send_json({"success": True, "announcement": text})
            return

        # Paper Upload (Public Submission - Enters Pending Review)
        elif path == "/api/upload":
            client_ip = self.client_address[0]
            allowed, wait_sec = check_rate_limit(client_ip, UPLOAD_RATE_LIMITS, max_requests=5, window_sec=600)
            if not allowed:
                self._send_json({"success": False, "error": f"Rate limit reached. Please wait {wait_sec} seconds before uploading."}, status=429)
                return

            code = data.get("subjectCode", "SUB101").upper().strip()
            name = data.get("subjectName", "Untitled Subject").strip()
            branch = data.get("branch", "CSE")
            sem = int(data.get("semester", 1))
            exam = data.get("examType", "MID_1")
            reg = data.get("regulation", "R22")
            year = data.get("academicYear", "2025-2026")
            uploader_name = data.get("uploaderName", "Student Contributor")
            uploader_roll = data.get("uploaderRollNo", "Anonymous")
            uploader_email = data.get("uploaderEmail", "")
            image_data = data.get("imageData", "")

            # File size limit: 15MB
            if len(image_data) * 0.75 > 15 * 1024 * 1024:
                self._send_json({"success": False, "error": "File size exceeds maximum 15MB limit."}, status=413)
                return

            # Strict file validation - NO SVG, NO executables
            image_url = ""
            if image_data.startswith("data:"):
                try:
                    header, encoded = image_data.split(",", 1)
                    mime = header.split(";")[0].replace("data:", "").lower()
                    if mime not in ALLOWED_MIME_TYPES:
                        self._send_json({"success": False, "error": "Disallowed file format. Allowed: JPG, PNG, WEBP, PDF."}, status=400)
                        return
                    
                    ext = ALLOWED_MIME_TYPES[mime]
                    safe_token = secrets.token_hex(8)
                    filename = f"paper_{int(time.time())}_{safe_token}.{ext}"
                    filepath = os.path.join(UPLOAD_DIR, filename)
                    with open(filepath, "wb") as img_file:
                        img_file.write(base64.b64decode(encoded))
                    image_url = f"/uploads/{filename}"
                except Exception as e:
                    print("Error saving upload:", e)
                    self._send_json({"success": False, "error": "Invalid upload data"}, status=400)
                    return

            exam_labels = {
                "MID_1": "Mid-Term 1",
                "MID_2": "Re-Mid Exam",
                "RE_MID": "Re-Mid Exam",
                "SEM_END": "Semester End Exam",
                "SUPPLY": "Supplementary Exam"
            }

            new_id = f"sru_{branch.lower()}_{secrets.token_hex(6)}"
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
                "uploaderEmail": uploader_email,
                "uploadDate": "Just now",
                "imageUrl": image_url,
                "downloadCount": 0,
                "is_approved": False,
                "status": "pending",
                "created_at": int(time.time())
            }

            papers = load_papers()
            papers.insert(0, new_paper)
            save_papers(papers)

            print(f"Successfully saved new submission (pending review): {code} - {name} ({branch}).")
            self._send_json({
                "success": True, 
                "message": "Your question paper has been submitted successfully and is awaiting review.",
                "paper": new_paper
            })
            return

        # Admin Approve Paper
        elif path == "/api/admin/approve":
            password = data.get("password", "")
            if not password or password != ADMIN_PASSWORD:
                self._send_json({"success": False, "error": "Unauthorized"}, status=401)
                return

            paper_id = data.get("paperId", "")
            papers = load_papers()
            target_paper = next((p for p in papers if p.get("id") == paper_id), None)
            if target_paper:
                target_paper["is_approved"] = True
                target_paper["status"] = "approved"
                save_papers(papers)
                self._send_json({"success": True, "message": "Paper approved successfully", "paper": target_paper})
            else:
                self._send_json({"success": False, "error": "Paper not found"}, status=404)
            return

        # Public Student Feedback Submission
        elif path == "/api/feedback":
            client_ip = self.client_address[0]
            allowed, wait_sec = check_rate_limit(client_ip, FEEDBACK_RATE_LIMITS, max_requests=6, window_sec=600)
            if not allowed:
                self._send_json({"success": False, "error": f"Rate limit reached. Please wait {wait_sec} seconds before submitting."}, status=429)
                return

            message = data.get("message", "").strip()
            if not message or len(message) < 3:
                self._send_json({"success": False, "error": "Feedback message too short."}, status=400)
                return

            feedback_item = {
                "id": f"fb_{int(time.time())}_{secrets.token_hex(4)}",
                "email": data.get("email", "Anonymous Student"),
                "category": data.get("category", "General Feedback"),
                "message": message,
                "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }

            feedbacks = load_feedbacks()
            feedbacks.insert(0, feedback_item)
            save_feedbacks(feedbacks)
            self._send_json({"success": True, "message": "Feedback submitted successfully."})
            return

        # Admin Feedback Management (Protected)
        elif path == "/api/admin/feedbacks":
            password = data.get("password", "")
            if not password or password != ADMIN_PASSWORD:
                self._send_json({"success": False, "error": "Unauthorized"}, status=401)
                return

            feedbacks = load_feedbacks()
            self._send_json({"success": True, "feedbacks": feedbacks})
            return

        # Clear All Papers (Admin Only)
        elif path in ["/api/clear", "/api/admin/clear-all"]:
            password = data.get("password", "")
            if not password or password != ADMIN_PASSWORD:
                self._send_json({"success": False, "error": "Unauthorized"}, status=401)
                return

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
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
