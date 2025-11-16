import os
import tempfile
import joblib
import pdfplumber
import docx
import re
import pandas as pd
import datetime
import bcrypt
import jwt
import json

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from notifications import send_email, send_slack_to_user, append_to_google_sheet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Config

# ---------------- CONFIG ---------------- #
ALLOWED_EXTENSIONS = {"pdf", "docx"}
UPLOAD_FOLDER = tempfile.gettempdir()
SECRET_KEY = "MY_SUPER_SECRET_KEY"  # change this in production!

app = Flask(__name__)
CORS(app)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# In-memory notifications store (simple demo; replace with durable store in prod)
NOTIFICATIONS = []

def add_notification(payload: dict):
    """Add a notification to the in-memory list (keeps latest 100)."""
    try:
        payload.setdefault("timestamp", datetime.datetime.utcnow().isoformat())
        NOTIFICATIONS.insert(0, payload)
        # keep bounded
        if len(NOTIFICATIONS) > 100:
            NOTIFICATIONS.pop()
    except Exception:
        pass

# Track latest amended contract file path
LATEST_AMENDED_PATH = None

# ------------------ Simple DB (SQLite) for admin config ------------------
DB_PATH = os.getenv("APP_DB", "app_config.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_config_dict():
    s = SessionLocal()
    try:
        rows = s.query(Config).all()
        return {r.key: r.value for r in rows}
    finally:
        s.close()


def get_smtp_config():
    """Return SMTP configuration, merging env vars with DB-stored config values.

    Returns a dict with keys: SMTP_HOST, SMTP_PORT (int), SMTP_USE_SSL (bool), EMAIL_SENDER, EMAIL_SMTP_PASS
    """
    cfg = get_config_dict()
    # prefer DB config over env vars if present
    def _get(k, default=None):
        v = cfg.get(k)
        if v is not None:
            return v
        return os.getenv(k, default)

    smtp_host = _get("SMTP_HOST", "smtp.gmail.com")
    smtp_port_raw = _get("SMTP_PORT", None)
    smtp_port = int(smtp_port_raw) if smtp_port_raw not in (None, "") else None
    smtp_use_ssl_raw = _get("SMTP_USE_SSL", None)
    if smtp_use_ssl_raw is None:
        smtp_use_ssl = None
    else:
        smtp_use_ssl = str(smtp_use_ssl_raw) not in ("0", "false", "False")

    sender = _get("EMAIL_SENDER", None)
    smtp_pass = _get("EMAIL_SMTP_PASS", None)

    return {
        "SMTP_HOST": smtp_host,
        "SMTP_PORT": smtp_port,
        "SMTP_USE_SSL": smtp_use_ssl,
        "EMAIL_SENDER": sender,
        "EMAIL_SMTP_PASS": smtp_pass,
    }

def set_config_items(items: dict):
    s = SessionLocal()
    try:
        for k, v in items.items():
            row = s.query(Config).filter(Config.key == k).first()
            if row:
                row.value = str(v) if v is not None else None
            else:
                row = Config(key=k, value=str(v) if v is not None else None)
                s.add(row)
        s.commit()
    finally:
        s.close()

def is_admin_request(req):
    # checks token email against admin_emails in config or ADMIN_EMAILS env var
    cfg = get_config_dict()
    admin_emails = []
    if cfg.get("admin_emails"):
        admin_emails = [e.strip() for e in cfg.get("admin_emails", "").split(",") if e.strip()]
    elif os.getenv("ADMIN_EMAILS"):
        admin_emails = [e.strip() for e in os.getenv("ADMIN_EMAILS").split(",") if e.strip()]

    token = req.headers.get("Authorization")
    decoded = decode_token(token) if token else None
    if isinstance(decoded, dict):
        user_email = decoded.get("email")
        if user_email and user_email in admin_emails:
            return True
    return False

# ---------------- USER STORAGE ---------------- #
USER_DB = "users.json"

def load_users():
    if not os.path.exists(USER_DB):
        return {}
    with open(USER_DB, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USER_DB, "w") as f:
        json.dump(users, f, indent=4)

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def generate_token(email):
    payload = {
        "email": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=10)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except:
        return None

# ---------------- PHASE 1 MODEL ---------------- #
try:
    clf_pipeline = joblib.load("models/logistic_tfidf_pipeline.pkl")
    print("✅ Phase 1 Model loaded successfully.")
except Exception as e:
    clf_pipeline = None
    print(f"⚠️ Phase 1 model missing: {e}")

try:
    df = pd.read_csv("clean_legal_clauses.csv")
    df = df.dropna(subset=["clean_text", "clause_type"])
    class_map = dict(enumerate(df["clause_type"].astype("category").cat.categories))
    print("✅ Class map loaded.")
except Exception as e:
    class_map = {}
    print(f"⚠️ Class map missing: {e}")

# ---------------- PHASE 3 MODEL ---------------- #
try:
    risk_pipeline = joblib.load("models/logistic_reg_risk.pkl")
except Exception as e:
    risk_pipeline = None
    print(f"⚠️ Risk model missing: {e}")

if hasattr(risk_pipeline, "named_steps"):
    vectorizer = risk_pipeline.named_steps.get("tfidf")
    clf = risk_pipeline.named_steps.get("clf")
else:
    clf = risk_pipeline
    try:
        vectorizer = joblib.load("models/tfidf_vectorizer.pkl")
    except Exception as e:
        vectorizer = None
        print(f"⚠️ Vectorizer missing: {e}")

try:
    shap_explainer = joblib.load("models/shap_explainer.pkl")
except Exception as e:
    shap_explainer = None
    print(f"⚠️ SHAP explainer missing: {e}")

# ---------------- UTILITIES ---------------- #
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(path):
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"PDF extraction error: {e}")
    return text

def extract_text_from_docx(path):
    text = ""
    try:
        doc = docx.Document(path)
        text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print(f"DOCX extraction error: {e}")
    return text

def split_into_clauses(text):
    text = re.sub(r"WEBSITE DESIGN AGREEMENT", r"0. WEBSITE DESIGN AGREEMENT", text, 1)
    raw_clauses = re.split(r"(\n\d{1,2}\. )", text)
    clauses = []
    preamble = raw_clauses[0].strip()
    if len(preamble) > 20:
        clauses.append(preamble)
    for i in range(1, len(raw_clauses), 2):
        if i + 1 < len(raw_clauses):
            clause = (raw_clauses[i] + raw_clauses[i + 1]).strip()
            if len(clause) > 20:
                clauses.append(clause)
    if not clauses:
        clauses = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 20]
    return clauses

WORD_RISK_MAP = {
    "assignment": "allows unrestricted rights transfer",
    "ten": "contains ambiguous numeric thresholds",
    "business": "affects business-wide clauses",
    "party": "unclear responsibility wording",
    "confidential": "incomplete confidentiality terms",
}

def generate_human_readable_justification(top_words):
    explanations = []
    for w, v in top_words:
        direction = "increases risk" if v > 0 else "reduces risk"
        if w.lower() in WORD_RISK_MAP:
            explanations.append(f"{WORD_RISK_MAP[w.lower()]} ({direction})")
        else:
            explanations.append(f"'{w}' ({direction})")
    return " ".join(explanations) if explanations else "No strong risk indicators found."

def analyze_risk_with_model(clause):
    if not clf or not vectorizer:
        return {"risk_level": "Unknown", "confidence": 0.0, "justification": "Risk model unavailable"}

    try:
        vec = vectorizer.transform([clause])
        pred = clf.predict(vec)[0]
        prob = clf.predict_proba(vec).max()

        justification = "Explainability not available"
        if shap_explainer:
            try:
                shap_vals = shap_explainer(vec).values.flatten()
                words = vectorizer.get_feature_names_out()
                important = sorted(zip(words, shap_vals), key=lambda x: abs(x[1]), reverse=True)[:5]
                justification = generate_human_readable_justification(important)
            except Exception as e:
                justification = f"SHAP error: {e}"

        return {"risk_level": pred, "confidence": float(prob), "justification": justification}
    except Exception as e:
        return {"risk_level": "Error", "confidence": 0.0, "justification": f"Risk analysis failed: {e}"}

# ---------------- AUTH ROUTES ---------------- #
@app.route("/register", methods=["POST"])
def register():
    users = load_users()
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if email in users:
        return jsonify({"error": "User already exists"}), 400

    users[email] = {"password": hash_password(password)}
    save_users(users)

    return jsonify({"message": "User registered successfully"})

@app.route("/login", methods=["POST"])
def login():
    users = load_users()
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if email not in users:
        return jsonify({"error": "User not found"}), 404

    if not verify_password(password, users[email]["password"]):
        return jsonify({"error": "Incorrect password"}), 401

    token = generate_token(email)
    return jsonify({"message": "Login successful", "token": token})

@app.route("/protected", methods=["GET"])
def protected():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"error": "Invalid token"}), 403

    return jsonify({"message": "Access granted", "user": decoded})

# ---------------- UPLOAD + ANALYSIS ROUTE ---------------- #
@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    # Extract text
    text = extract_text_from_pdf(path) if filename.lower().endswith(".pdf") else extract_text_from_docx(path)
    os.remove(path)

    if not text:
        return jsonify({"error": "No readable text found."}), 422

    clauses = split_into_clauses(text)
    if not clauses:
        return jsonify({"error": "No clauses detected."}), 422

    results = []
    frontend_clauses = []

    for idx, clause in enumerate(clauses):
        # Phase 1
        try:
            pred_code = int(clf_pipeline.predict([clause])[0]) if clf_pipeline else None
            pred_class = class_map.get(pred_code, "Unknown") if pred_code is not None else "N/A"
            confidence = float(clf_pipeline.predict_proba([clause]).max()) if clf_pipeline else 0.0
        except Exception as e:
            pred_class = "N/A"
            confidence = 0.0
            print(f"Phase 1 error: {e}")

        # Phase 3
        risk_info = analyze_risk_with_model(clause)

        results.append({
            "clause": clause,
            "phase1": {"predicted_clause_type": pred_class, "confidence": confidence},
            "phase3": risk_info
        })

        frontend_clauses.append({
            "label": f"Clause {idx + 1}",
            "text": clause
        })

    # ---------------- MISSING CLAUSES DETECTION (simple rule-based)
    # NOTE: for this assignment we assume a small set of required clauses.
    # In a production system you'd load required clauses from policy/config
    required_clauses = [
        "Data privacy protection",
        "Confidentiality",
        "Indemnity",
        "Termination"
    ]

    # present_types are taken from phase1 predicted labels
    present_types = set([r["phase1"]["predicted_clause_type"] for r in results if r.get("phase1")])
    missing_simple = [rc for rc in required_clauses if rc not in present_types]

    # format missing_clauses as expected by frontend: list of objects
    missing_clauses = [{"label": rc, "reason": "Required clause not present"} for rc in missing_simple]

    # Generate an amended contract when missing clauses found
    amended_contract = ""
    notifications = []

    if missing_simple:
        # Templates for missing clauses (simple placeholders)
        clause_templates = {
            "Data privacy protection": (
                "Data Privacy Protection:\nThe parties agree to comply with applicable data protection laws and implement reasonable technical and organizational measures to protect personal data."
            ),
            "Confidentiality": (
                "Confidentiality:\nEach party shall keep confidential all non-public information disclosed by the other party and shall not disclose such information to third parties without prior written consent."
            ),
            "Indemnity": (
                "Indemnity:\nEach party agrees to indemnify and hold harmless the other party from and against any claims, liabilities, losses, and expenses arising out of its breach of this agreement."
            ),
            "Termination": (
                "Termination:\nEither party may terminate this agreement upon thirty (30) days written notice if the other party materially breaches any obligation and fails to cure within the notice period."
            )
        }

        # Build amended contract by appending missing clause templates to original text
        appended = []
        for m in missing_simple:
            appended.append(clause_templates.get(m, f"{m}: [Please add clause text here]") )

        amended_contract = text + "\n\n--- ADDED MISSING CLAUSES ---\n\n" + "\n\n".join(appended)

        # Save amended contract to a temporary file for download
        try:
            import tempfile as _temp
            fd, path = _temp.mkstemp(prefix="amended_contract_", suffix=".txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(amended_contract)
            # store globally so download endpoint can serve it
            global LATEST_AMENDED_PATH
            LATEST_AMENDED_PATH = path
        except Exception as e:
            print(f"Failed to write amended contract file: {e}")

        # Determine recipient early: extract authenticated user's email from token
        token = request.headers.get("Authorization")
        decoded_payload = decode_token(token) if token else None
        recipient = None
        if isinstance(decoded_payload, dict):
            recipient = decoded_payload.get("email")
        # If no authenticated user, reject (notifications must go to a registered user)
        if not recipient:
            return jsonify({"error": "Authentication required to upload and receive notifications"}), 401

        # prepare a clearer, per-upload message and include a download link if available
        download_url = None
        try:
            # request.url_root gives something like http://127.0.0.1:5000/
            base = request.url_root.rstrip("/")
            download_url = f"{base}/download/amended"
        except Exception:
            download_url = None

        pretty_list = "\n".join([f"- {c}" for c in missing_simple])
        msg = (
            f"Hello {recipient},\n\n"
            f"We analyzed your uploaded contract file: {filename}\n\n"
            f"Missing clauses detected ({len(missing_simple)}):\n{pretty_list}\n\n"
            f"An amended contract with the missing clauses has been generated.\n"
        )

        if download_url:
            msg += f"You can download it here: {download_url}\n\n"
        else:
            msg += "\n"

        # allow configurable email signature via DB or env var
        cfg = get_config_dict()
        signature = cfg.get("EMAIL_SIGNATURE") or os.getenv("EMAIL_SIGNATURE") or "Finance team (Masthan)"
        msg += f"Regards,\n{signature}"

        

        notification = {"type": "missing_clauses", "message": msg, "missing": missing_simple, "amended_available": bool(LATEST_AMENDED_PATH), "recipient": recipient}
        # store notification for frontend
        add_notification(notification)
        notifications.append(notification)

        # send email (best-effort)
        try:
            to_addr = recipient
            smtp_cfg = get_smtp_config()
            send_email(
                to_addr,
                "Compliance update: missing clauses detected",
                msg,
                from_email=smtp_cfg.get("EMAIL_SENDER") or smtp_cfg.get("EMAIL_USER"),
                smtp_host=smtp_cfg.get("SMTP_HOST"),
                smtp_port=smtp_cfg.get("SMTP_PORT"),
                smtp_use_ssl=smtp_cfg.get("SMTP_USE_SSL"),
                smtp_password=smtp_cfg.get("EMAIL_SMTP_PASS") or smtp_cfg.get("EMAIL_PASS"),
                attachment_path=LATEST_AMENDED_PATH if LATEST_AMENDED_PATH else None,
                attachment_name=f"amended_{filename}" if filename else None,
            )
            notification["email_sent"] = True
        except Exception as e:
            print(f"Email send failed: {e}")
            notification["email_sent"] = False

        # append to google sheet (best-effort)
        try:
            append_to_google_sheet(os.getenv("GOOGLE_SHEET_NAME", "MissingClauses"), [datetime.datetime.utcnow().isoformat(), ", ".join(missing_simple)])
            notification["sheet_appended"] = True
        except Exception as e:
            print(f"Google Sheets append failed: {e}")
            notification["sheet_appended"] = False

        # send slack (best-effort)
        try:
            slack_dest = os.getenv("SLACK_DEFAULT_CHANNEL", "#general")
            send_slack_to_user(slack_dest, msg)
            notification["slack_sent"] = True
        except Exception as e:
            print(f"Slack send failed: {e}")
            notification["slack_sent"] = False

    return jsonify({
        "total_clauses": len(clauses),
        "analysis": results,
        "clauses": frontend_clauses,
        "missing_clauses": missing_clauses,
        "amended_contract": amended_contract,
        "notifications": notifications
    })


@app.route("/notifications/latest", methods=["GET"])
def notifications_latest():
    # return last N notifications
    n = int(request.args.get("n", 10))
    return jsonify({"notifications": NOTIFICATIONS[:n]})


@app.route('/notifications/dismiss', methods=['POST'])
def notifications_dismiss():
    """Dismiss a notification so it won't be returned in future polls.

    Expects JSON: { "timestamp": "..." }
    Only the recipient of a notification (or an admin) can dismiss it.
    """
    data = request.json or {}
    ts = data.get('timestamp')
    token = request.headers.get('Authorization')
    decoded = decode_token(token) if token else None
    user_email = None
    if isinstance(decoded, dict):
        user_email = decoded.get('email')

    if not user_email:
        return jsonify({'ok': False, 'error': 'Authentication required'}), 401

    removed = False
    try:
        global NOTIFICATIONS
        new_list = []
        for notif in NOTIFICATIONS:
            # match by timestamp and recipient
            if ts and notif.get('timestamp') == ts:
                # allow recipient or admin to remove
                if notif.get('recipient') == user_email or is_admin_request(request):
                    removed = True
                    continue
            new_list.append(notif)
        NOTIFICATIONS = new_list
    except Exception:
        return jsonify({'ok': False, 'error': 'Failed to dismiss notification'}), 500

    return jsonify({'ok': True, 'removed': removed})


@app.route("/slack/receive", methods=["POST"])
def slack_receive():
    """Endpoint to receive Slack messages/webhooks (simple receiver for demo).

    Expected JSON: { "text": "...message...", "channel": "#channel-or-id" }
    """
    data = request.json or {}
    text = data.get("text")
    channel = data.get("channel", os.getenv("SLACK_DEFAULT_CHANNEL", "#general"))
    if not text:
        return jsonify({"error": "Missing text"}), 400

    notification = {"type": "slack_incoming", "message": text, "channel": channel}
    add_notification(notification)

    # Optionally re-broadcast to configured recipients
    try:
        # echo back to slack (if bot token configured)
        send_slack_to_user(channel, f"[Received] {text}")
        notification["echoed"] = True
    except Exception:
        notification["echoed"] = False

    return jsonify({"ok": True, "notification": notification})


@app.route('/download/amended', methods=['GET'])
def download_amended():
    """Download the latest amended contract file if available."""
    global LATEST_AMENDED_PATH
    if not LATEST_AMENDED_PATH or not os.path.exists(LATEST_AMENDED_PATH):
        return jsonify({"error": "No amended contract available"}), 404
    try:
        return send_file(LATEST_AMENDED_PATH, as_attachment=True, download_name=os.path.basename(LATEST_AMENDED_PATH))
    except Exception as e:
        return jsonify({"error": f"Failed to send file: {e}"}), 500


@app.route('/admin/config', methods=['GET'])
def admin_get_config():
    if not is_admin_request(request):
        return jsonify({"error": "admin required"}), 403
    cfg = get_config_dict()
    # never return secrets like EMAIL_SMTP_PASS unless explicitly requested
    masked = dict(cfg)
    if masked.get('EMAIL_SMTP_PASS'):
        masked['EMAIL_SMTP_PASS'] = '****'
    return jsonify({'config': masked})


@app.route('/admin/config', methods=['POST'])
def admin_set_config():
    if not is_admin_request(request):
        return jsonify({"error": "admin required"}), 403
    data = request.json or {}
    # accept keys like SMTP_HOST, SMTP_PORT, SMTP_USE_SSL, EMAIL_SENDER, EMAIL_SMTP_PASS, NOTIFICATION_EMAIL, admin_emails
    allowed = ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USE_SSL', 'EMAIL_SENDER', 'EMAIL_SMTP_PASS', 'NOTIFICATION_EMAIL', 'admin_emails']
    updates = {k: v for k, v in data.items() if k in allowed}
    set_config_items(updates)
    return jsonify({'ok': True, 'saved': list(updates.keys())})


@app.route('/admin/test-email', methods=['POST'])
def admin_test_email():
    if not is_admin_request(request):
        return jsonify({"error": "admin required"}), 403
    data = request.json or {}
    recipient = data.get('recipient') or os.getenv('NOTIFICATION_EMAIL')
    subject = data.get('subject', 'Admin test email')
    body = data.get('body', 'This is a test from admin')
    try:
        smtp_cfg = get_smtp_config()
        send_email(
            recipient,
            subject,
            body,
            from_email=smtp_cfg.get("EMAIL_SENDER"),
            smtp_host=smtp_cfg.get("SMTP_HOST"),
            smtp_port=smtp_cfg.get("SMTP_PORT"),
            smtp_use_ssl=smtp_cfg.get("SMTP_USE_SSL"),
            smtp_password=smtp_cfg.get("EMAIL_SMTP_PASS"),
        )
        return jsonify({'ok': True, 'recipient': recipient})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'recipient': recipient}), 500


@app.route('/test-email', methods=['POST'])
def test_email():
    """Trigger a test email to the registered user (or NOTIFICATION_EMAIL if unauthenticated).

    POST body (optional): { "subject": "...", "body": "..." }
    """
    data = request.json or {}
    subject = data.get('subject', 'Test: Compliance Notification')
    body = data.get('body', 'This is a test notification from Compliance Checker')

    # determine recipient from token if present
    token = request.headers.get('Authorization')
    decoded_payload = decode_token(token) if token else None
    recipient = None
    try:
        if isinstance(decoded_payload, dict):
            recipient = decoded_payload.get('email')
    except Exception:
        recipient = None
    if not recipient:
        recipient = os.getenv('NOTIFICATION_EMAIL', 'dharanixyz02@gmail.com')

    # require admin to run test email
    if not is_admin_request(request):
        return jsonify({"ok": False, "error": "admin required"}), 403

    try:
        smtp_cfg = get_smtp_config()
        send_email(
            recipient,
            subject,
            body,
            from_email=smtp_cfg.get("EMAIL_SENDER"),
            smtp_host=smtp_cfg.get("SMTP_HOST"),
            smtp_port=smtp_cfg.get("SMTP_PORT"),
            smtp_use_ssl=smtp_cfg.get("SMTP_USE_SSL"),
            smtp_password=smtp_cfg.get("EMAIL_SMTP_PASS"),
        )
        return jsonify({'ok': True, 'recipient': recipient})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'recipient': recipient}), 500

# ---------------- MAIN ---------------- #
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
