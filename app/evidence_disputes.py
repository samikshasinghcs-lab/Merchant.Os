"""Evidence file handling and PayPal dispute synchronization helpers.

Integrity hashes and metadata inspection do NOT prove that a document's claims are true.
"""
from __future__ import annotations
import hashlib, json, mimetypes, re, uuid, os, stat
from datetime import datetime, timezone
from pathlib import Path
from .config import UPLOAD_DIR, MAX_EVIDENCE_FILE_BYTES
from .db import db

ALLOWED = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".gif": {"image/gif"},
    ".txt": {"text/plain"}, ".csv": {"text/csv", "application/vnd.ms-excel"},
}

def utcnow(): return datetime.now(timezone.utc).isoformat()
def safe_name(name):
    name = Path(name or "evidence.bin").name
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]
    return name or "evidence.bin"

def sniff(data, ext):
    if ext == ".pdf" and data.startswith(b"%PDF-"): return "application/pdf"
    if ext == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if ext in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    if ext == ".gif" and data.startswith((b"GIF87a", b"GIF89a")): return "image/gif"
    if ext in {".txt", ".csv"}:
        try:
            data.decode("utf-8-sig")
            return "text/csv" if ext == ".csv" else "text/plain"
        except UnicodeDecodeError: return None
    return None

def inspect_bytes(data, mime):
    result = {"inspection_version": 1, "mime_type": mime, "inspected_at": utcnow(), "text_extraction": "not_attempted"}
    if mime == "application/pdf":
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                result["text_extraction"] = "encrypted_pdf"
            else:
                pages = []
                page_count = len(reader.pages)
                if page_count > 500:
                    raise ValueError("PDF page count exceeds the inspection safety limit")
                for page in reader.pages[:30]: pages.append((page.extract_text() or "")[:12000])
                result.update({"text_extraction": "pypdf", "page_count": page_count, "text_preview": "\n".join(pages)[:12000]})
        except ImportError: result["text_extraction"] = "unavailable_install_pypdf"
        except Exception as exc: raise ValueError("PDF structure validation failed") from exc
    elif mime.startswith("image/"):
        try:
            from PIL import Image
            import io
            im = Image.open(io.BytesIO(data))
            width, height = im.size
            if width <= 0 or height <= 0 or width * height > 40_000_000:
                raise ValueError("Image dimensions exceed the inspection safety limit")
            im.verify()
            im = Image.open(io.BytesIO(data))
            result.update({"image_format": im.format, "width": width, "height": height, "metadata_keys": sorted(list(im.info.keys()))[:30], "text_extraction": "image_metadata_only"})
        except ImportError: result["text_extraction"] = "unavailable_install_pillow"
        except Exception as exc: raise ValueError("Image structure validation failed") from exc
    else:
        result["text_extraction"] = "plain_text"
        result["text_preview"] = data.decode("utf-8-sig", errors="replace")[:12000]
    result["limitations"] = "Inspection checks file structure/metadata and may extract text. It does not establish authorship, truth, date of creation, or authenticity."
    return result

def store_upload(order_id, evidence_type, description, filename, data):
    if len(data) >= MAX_EVIDENCE_FILE_BYTES: raise ValueError(f"File must be smaller than {MAX_EVIDENCE_FILE_BYTES} bytes")
    original = safe_name(filename)
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED: raise ValueError("Allowed file types: PDF, PNG, JPG/JPEG, GIF, TXT, CSV")
    mime = sniff(data, ext)
    if mime not in ALLOWED[ext]: raise ValueError("File content does not match its extension or is malformed")
    sha = hashlib.sha256(data).hexdigest()
    inspection = inspect_bytes(data, mime)
    eid = "EV-" + uuid.uuid4().hex[:12].upper()
    fid = "EF-" + uuid.uuid4().hex[:12].upper()
    configured_root = Path(UPLOAD_DIR).expanduser()
    configured_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if configured_root.is_symlink():
        raise ValueError("Evidence storage directory must not be a symbolic link")
    root = configured_root.resolve()
    # Evidence is private application data: directory 0700, file 0600.
    try:
        os.chmod(root, 0o700)
    except OSError as exc:
        raise ValueError("Evidence storage permissions could not be hardened") from exc
    stored = fid + ext
    path = root / stored
    if root not in path.parents or path.exists() or path.is_symlink():
        raise ValueError("Invalid or conflicting storage path")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    created = utcnow()
    provenance = {"source": "merchant_upload", "original_filename": original, "merchant_attested": False, "uploaded_at": created}
    try:
        with db() as c:
            if not c.execute("SELECT 1 FROM orders WHERE id=?", (order_id,)).fetchone(): raise ValueError("Order not found")
            c.execute("INSERT INTO evidence_items VALUES(?,?,?,?,?,?,?)", (eid, order_id, evidence_type, description[:2000], None, "merchant_uploaded_file", created))
            c.execute("INSERT INTO evidence_files VALUES(?,?,?,?,?,?,?,?,?,?,?)", (fid,eid,stored,original,mime,len(data),sha,json.dumps(inspection),json.dumps(provenance),"HASH_RECORDED",created))
    except Exception:
        path.unlink(missing_ok=True); raise
    return {"evidence_id":eid,"file_id":fid,"order_id":order_id,"filename":original,"mime_type":mime,"size_bytes":len(data),"sha256":sha,"inspection":inspection,"integrity_status":"HASH_RECORDED","authenticity":"NOT_ESTABLISHED"}

def evidence_file(file_id):
    with db() as c:
        row=c.execute("SELECT ef.*, ei.order_id, ei.evidence_type FROM evidence_files ef JOIN evidence_items ei ON ei.id=ef.evidence_id WHERE ef.id=?",(file_id,)).fetchone()
    return dict(row) if row else None

def verify_file(file_id):
    row=evidence_file(file_id)
    if not row: return None
    path=(Path(UPLOAD_DIR).resolve()/row["stored_name"]).resolve()
    root=Path(UPLOAD_DIR).resolve()
    if root not in path.parents or path.is_symlink() or not path.is_file(): return {"file_id":file_id,"integrity":"MISSING_OR_INVALID_PATH","authenticity":"NOT_ESTABLISHED"}
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    intact=digest==row["sha256"]
    status="HASH_MATCH" if intact else "HASH_MISMATCH"
    with db() as c: c.execute("UPDATE evidence_files SET integrity_status=? WHERE id=?",(status,file_id))
    return {"file_id":file_id,"integrity":status,"sha256_expected":row["sha256"],"sha256_current":digest,"authenticity":"NOT_ESTABLISHED","meaning":"Hash match confirms bytes have not changed since registration; it does not prove the content is true or genuine."}

def due_state(due):
    if not due: return "UNKNOWN"
    try:
        d=datetime.fromisoformat(due.replace("Z","+00:00"))
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        seconds=(d-datetime.now(timezone.utc)).total_seconds()
        if seconds < 0: return "OVERDUE"
        if seconds < 86400: return "DUE_WITHIN_24_HOURS"
        if seconds < 3*86400: return "DUE_WITHIN_3_DAYS"
        return "UPCOMING"
    except Exception: return "UNKNOWN"
