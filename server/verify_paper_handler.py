"""HTTP multipart/form-data handler, rate limiting, and error boundary for POST /api/verify-paper."""

import email.policy
from email.parser import BytesParser
import json
import threading
import time
from typing import Any, Dict, Tuple

try:
    from .ai_examiner import examiner_service
except (ImportError, ValueError):
    from ai_examiner import examiner_service


_RATE_LIMIT_LOCK = threading.Lock()
_VERIFY_PAPER_RATE_LIMITS: Dict[str, list] = {}


def check_examiner_rate_limit(
    client_ip: str, max_requests: int = 15, window_sec: int = 60
) -> Tuple[bool, int]:
    """Thread-safe sliding window rate limiter for /api/verify-paper."""
    now = time.time()
    key = client_ip or "unknown"
    with _RATE_LIMIT_LOCK:
        stamps = [t for t in _VERIFY_PAPER_RATE_LIMITS.get(key, []) if now - t < window_sec]
        if len(stamps) >= max_requests:
            _VERIFY_PAPER_RATE_LIMITS[key] = stamps
            wait_seconds = max(1, int(window_sec - (now - stamps[0])))
            return False, wait_seconds
        stamps.append(now)
        _VERIFY_PAPER_RATE_LIMITS[key] = stamps
        return True, 0


def parse_multipart_upload(
    content_type: str, body_bytes: bytes
) -> Tuple[bytes, str, str, Dict[str, Any]]:
    """Parse multipart/form-data cleanly using stdlib email parser without cgi."""
    if "multipart/form-data" not in (content_type or "").lower():
        raise ValueError("Request Content-Type must be multipart/form-data with field 'file'.")

    raw_mime = (
        b"Content-Type: "
        + content_type.encode("latin-1", errors="ignore")
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + body_bytes
    )
    msg = BytesParser(policy=email.policy.HTTP).parsebytes(raw_mime)
    if not msg.is_multipart():
        raise ValueError("Malformed multipart/form-data request body.")

    file_bytes: bytes = b""
    filename: str = ""
    declared_mime: str = ""
    found_file = False
    user_metadata: Dict[str, Any] = {}

    for part in msg.iter_parts():
        field_name = part.get_param("name", header="content-disposition")
        part_filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""

        if field_name == "file" or (not found_file and part_filename is not None):
            found_file = True
            file_bytes = payload
            filename = part_filename or "uploaded_paper"
            declared_mime = part.get_content_type() or ""
        elif field_name == "metadata":
            raw_meta = payload.decode("utf-8", errors="replace").strip()
            if raw_meta:
                try:
                    parsed_meta = json.loads(raw_meta)
                    if isinstance(parsed_meta, dict):
                        user_metadata.update(parsed_meta)
                except json.JSONDecodeError:
                    pass
        elif field_name and part_filename is None:
            text_val = payload.decode("utf-8", errors="replace").strip()
            if text_val:
                user_metadata[str(field_name)] = text_val

    if not found_file:
        raise ValueError("Missing required 'file' field in multipart/form-data request.")

    return file_bytes, filename, declared_mime, user_metadata


def _extract_client_ip(handler: Any) -> str:
    forwarded = (handler.headers.get("X-Forwarded-For") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    addr = getattr(handler, "client_address", None)
    return addr[0] if addr else "unknown"


def handle_verify_paper_request(handler: Any) -> None:
    """Handle POST /api/verify-paper cleanly with size guards, rate limits, and sanitized JSON output."""
    try:
        cfg = examiner_service.config
        client_ip = _extract_client_ip(handler)
        allowed, wait_sec = check_examiner_rate_limit(
            client_ip, max_requests=cfg.rate_limit_per_min, window_sec=60
        )
        if not allowed:
            handler._send_json(
                {
                    "success": False,
                    "error": f"Too many verification requests. Please wait {wait_sec}s before trying again.",
                    "error_code": "RATE_LIMITED",
                },
                status=429,
            )
            return

        content_type = handler.headers.get("Content-Type", "")
        raw_len = handler.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_len)
        except ValueError:
            content_length = -1

        if content_length <= 0:
            handler._send_json(
                {
                    "success": False,
                    "error": "Empty or invalid Content-Length in upload request.",
                    "error_code": "INVALID_REQUEST",
                },
                status=400,
            )
            return

        max_body_bytes = (cfg.max_upload_mb + 2) * 1024 * 1024
        if content_length > max_body_bytes:
            handler._send_json(
                {
                    "success": False,
                    "error": f"Upload exceeds maximum allowed size of {cfg.max_upload_mb} MB.",
                    "error_code": "FILE_TOO_LARGE",
                },
                status=413,
            )
            return

        body_bytes = handler.rfile.read(content_length)
        try:
            file_bytes, filename, declared_mime, user_metadata = parse_multipart_upload(
                content_type=content_type,
                body_bytes=body_bytes,
            )
        except ValueError as exc:
            handler._send_json(
                {
                    "success": False,
                    "error": str(exc),
                    "error_code": "INVALID_MULTIPART",
                },
                status=400,
            )
            return

        status_code, payload = examiner_service.examine_upload(
            file_bytes=file_bytes,
            filename=filename,
            declared_mime=declared_mime,
            user_metadata=user_metadata,
        )
        handler._send_json(payload, status=status_code)
    except Exception:
        # Never leak stack traces, paths, keys, or document bytes in error responses
        handler._send_json(
            {
                "success": False,
                "error": "Unable to complete document verification due to an internal error.",
                "error_code": "INTERNAL_ERROR",
            },
            status=500,
        )
