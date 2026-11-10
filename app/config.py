import os
from dotenv import load_dotenv
load_dotenv()
def val(k, default=""): return os.getenv(k, default)
DEMO = val("DEMO_MODE","true").lower()=="true"
MODE = val("PAYPAL_MODE","sandbox")
CLIENT_ID, CLIENT_SECRET = val("PAYPAL_CLIENT_ID"), val("PAYPAL_CLIENT_SECRET")
MAX_REFUND = float(val("MAX_REFUND_AMOUNT","2000"))
DAILY_CAP = float(val("DAILY_REFUND_CAP","10000"))
DB_PATH = val("DATABASE_PATH","merchantos.db")
UPLOAD_DIR = val("EVIDENCE_UPLOAD_DIR", "evidence_uploads")
MAX_EVIDENCE_FILE_BYTES = int(val("MAX_EVIDENCE_FILE_BYTES", str(10 * 1024 * 1024)))
PAYPAL_WEBHOOK_ID = val("PAYPAL_WEBHOOK_ID", "")
PUBLIC_APP_URL = val("PUBLIC_APP_URL", "http://localhost:8000").rstrip("/")
