import sqlite3, json
from contextlib import contextmanager
from pathlib import Path
from .config import DB_PATH
SCHEMA = """
CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, customer_id TEXT, customer_name TEXT, product TEXT, batch TEXT, amount REAL, currency TEXT, paypal_order_id TEXT, capture_id TEXT, payment_status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, customer_id TEXT, customer_name TEXT, order_id TEXT, product TEXT, rating INTEGER, text TEXT, created_at TEXT, cluster_id TEXT, category TEXT, severity TEXT);
CREATE TABLE IF NOT EXISTS disputes(id TEXT PRIMARY KEY, order_id TEXT, reason TEXT, status TEXT, customer_message TEXT, evidence_json TEXT);
CREATE TABLE IF NOT EXISTS refunds(id TEXT PRIMARY KEY, order_id TEXT, capture_id TEXT, amount REAL, currency TEXT, reason TEXT, evidence_json TEXT, status TEXT, idem TEXT UNIQUE, paypal_id TEXT, paypal_status TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT, actor TEXT, entity TEXT, detail TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS paypal_webhook_events(event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, resource_id TEXT, status TEXT NOT NULL, workflow_run_id TEXT, summary_json TEXT NOT NULL, received_at TEXT NOT NULL, processed_at TEXT);
CREATE TABLE IF NOT EXISTS evidence_items(id TEXT PRIMARY KEY, order_id TEXT NOT NULL, evidence_type TEXT NOT NULL, description TEXT NOT NULL, reference TEXT, source TEXT NOT NULL DEFAULT 'merchant_uploaded', created_at TEXT NOT NULL);
"""
@contextmanager
def db():
    c=sqlite3.connect(DB_PATH,timeout=20); c.row_factory=sqlite3.Row
    try:
        yield c; c.commit()
    finally: c.close()
def init():
    with db() as c: c.executescript(SCHEMA)
def seed():
    path=Path(__file__).resolve().parents[1]/"seed"/"seed_data.json"
    with db() as c:
        if c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]: return
        if not path.exists(): return
        x=json.loads(path.read_text())
        c.executemany("INSERT OR IGNORE INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?)",[
        tuple(o[k] for k in ["id","customer_id","customer_name","product","batch","amount","currency","paypal_order_id","capture_id","payment_status","created_at"]) for o in x["orders"]])
        c.executemany("INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?,?)",[
        tuple(r.get(k) for k in ["id","customer_id","customer_name","order_id","product","rating","text","created_at","cluster_id","category","severity"]) for r in x["reviews"]])
        c.executemany("INSERT OR IGNORE INTO disputes VALUES(?,?,?,?,?,?)",[
        (d["id"],d["order_id"],d["reason"],d["status"],d["customer_message"],json.dumps(d["evidence"])) for d in x["disputes"]])

# Checkpoint 4: customer resolution lifecycle. Safe additive migration.
RESOLUTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS resolutions(
 id TEXT PRIMARY KEY, review_id TEXT NOT NULL, order_id TEXT NOT NULL,
 status TEXT NOT NULL, recommendation TEXT NOT NULL, reason TEXT NOT NULL,
 customer_message TEXT NOT NULL, merchant_note TEXT, created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(review_id) REFERENCES reviews(id), FOREIGN KEY(order_id) REFERENCES orders(id)
);
CREATE INDEX IF NOT EXISTS idx_resolutions_status ON resolutions(status);
CREATE INDEX IF NOT EXISTS idx_resolutions_review ON resolutions(review_id);
"""
_old_init = init
def init():
    _old_init()
    with db() as c:
        c.executescript(RESOLUTION_SCHEMA)
    from .merchant_intelligence import init_v2
    init_v2()

# Checkpoint 8: evidence files, inspection metadata, remote PayPal disputes and approvals.
EVIDENCE_DISPUTE_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_files(
 id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL, stored_name TEXT NOT NULL,
 original_name TEXT NOT NULL, mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
 sha256 TEXT NOT NULL, inspection_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
 integrity_status TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(evidence_id) REFERENCES evidence_items(id)
);
CREATE INDEX IF NOT EXISTS idx_evidence_files_evidence ON evidence_files(evidence_id);
CREATE TABLE IF NOT EXISTS paypal_disputes(
 dispute_id TEXT PRIMARY KEY, status TEXT, reason TEXT, lifecycle_stage TEXT,
 response_due_at TEXT, payload_json TEXT NOT NULL, synced_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dispute_submissions(
 id TEXT PRIMARY KEY, dispute_id TEXT NOT NULL, evidence_file_ids_json TEXT NOT NULL,
 evidence_type TEXT NOT NULL, notes TEXT, approved_by TEXT NOT NULL,
 approved_at TEXT NOT NULL, paypal_response_json TEXT, status TEXT NOT NULL,
 created_at TEXT NOT NULL
);
"""
_old_init_v8 = init
def init():
    _old_init_v8()
    with db() as c:
        c.executescript(EVIDENCE_DISPUTE_SCHEMA)
