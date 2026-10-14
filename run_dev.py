"""
Frappe Client Portal - Local Dev Server (SQLite backed)

* Persistent data in dev.db (next to this file)
* Token auth (Authorization: Bearer <token>)
* Every business record is scoped to a company; the caller must be a member
  of the company named in the X-Company header.
* Two seeded users with NO companies / NO data.

Run:  python run_dev.py
"""
import datetime
import hashlib
import json
import os
import random
import secrets
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dev.db")
FRONTEND_ORIGIN = "http://localhost:5173"

ENABLE_2FA = os.environ.get("ENABLE_2FA", "false").lower() == "true"
ENABLE_DEV_STAFF = os.environ.get("ENABLE_DEV_STAFF", "true").lower() == "true"

SEED_USERS = [
    ("alice.test@portal.dev", "Alice Walker", "Test@1234"),
    ("bob.test@portal.dev", "Bob Turner", "Test@1234"),
]

OTPS = {}  # in-memory, only used when ENABLE_2FA is on


# ─────────────────────────────── DB ───────────────────────────────
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def check_pw(password, stored):
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return secrets.compare_digest(hash_pw(password, salt), stored)


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users(
            email TEXT PRIMARY KEY, full_name TEXT, password_hash TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS sessions(
            token TEXT PRIMARY KEY, user_email TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS companies(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, company_number TEXT,
            type TEXT, address TEXT, vat_number TEXT, year_end TEXT, phone TEXT,
            email TEXT, created_by TEXT, created_at TEXT,
            onboarding_step INTEGER DEFAULT 1, onboarding_completed INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS company_members(
            company_id INTEGER, user_email TEXT, role TEXT, status TEXT DEFAULT 'Active',
            PRIMARY KEY(company_id, user_email));
        CREATE TABLE IF NOT EXISTS submissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, company_id INTEGER,
            submission_type TEXT, status TEXT, period TEXT, submitted_by TEXT,
            notes TEXT, total_gross REAL DEFAULT 0, items TEXT, files TEXT,
            created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, company_id INTEGER,
            submission_ref TEXT, title TEXT, message TEXT, due_date TEXT,
            status TEXT DEFAULT 'Pending', assigned_to TEXT, client_reply TEXT,
            created_at TEXT);
        CREATE TABLE IF NOT EXISTS queries(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, company_id INTEGER,
            subject TEXT, category TEXT, status TEXT DEFAULT 'Open',
            assigned_to TEXT DEFAULT 'Unassigned', created_by TEXT,
            created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS query_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT, query_id INTEGER, sender TEXT,
            is_staff INTEGER DEFAULT 0, body TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT, company_id INTEGER,
            title TEXT, due_date TEXT, priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Open', created_at TEXT);
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, user_email TEXT,
            title TEXT, body TEXT, is_read INTEGER DEFAULT 0, created_at TEXT);
        """
    )
    for email, name, pwd in SEED_USERS:
        if not conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            conn.execute(
                "INSERT INTO users VALUES(?,?,?,?)", (email, name, hash_pw(pwd), now())
            )
    conn.commit()
    conn.close()


# ─────────────────────────────── helpers ───────────────────────────────
class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def company_dict(row, role=None):
    d = dict(row)
    d["onboarding_completed"] = bool(d.get("onboarding_completed"))
    if role:
        d["role"] = role
    return d


def days_until(date_str):
    try:
        d = datetime.datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (d - datetime.date.today()).days
    except Exception:
        return None


def rel_time(ts):
    try:
        t = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts or ""
    delta = datetime.datetime.now() - t
    if delta.total_seconds() < 60:
        return "Just now"
    if t.date() == datetime.date.today():
        return "Today, " + t.strftime("%I:%M %p").lstrip("0")
    if t.date() == datetime.date.today() - datetime.timedelta(days=1):
        return "Yesterday, " + t.strftime("%I:%M %p").lstrip("0")
    return t.strftime("%d %b %Y")


def sub_to_api(r):
    d = dict(r)
    items = json.loads(d["items"] or "[]")
    doc_date = None
    if items and isinstance(items, list) and len(items) > 0 and isinstance(items[0], dict):
        doc_date = items[0].get("date")
    return {
        "name": d["ref"],
        "submission_type": d["submission_type"],
        "status": d["status"],
        "period": d["period"],
        "submitted_by": d["submitted_by"],
        "total_gross": d["total_gross"],
        "date": doc_date or (d["created_at"].split(" ")[0] if d.get("created_at") else ""),
        "creation": d["created_at"],
        "modified": d["updated_at"],
        "notes": d["notes"],
        "items": items,
        "files": json.loads(d["files"] or "[]"),
    }


def req_to_api(r):
    d = dict(r)
    left = days_until(d["due_date"]) if d["due_date"] else None
    return {
        "name": d["ref"],
        "submission": d["submission_ref"],
        "title": d["title"],
        "message": d["message"],
        "due_date": d["due_date"],
        "days_left": left if left is not None else 7,
        "is_urgent": 1 if (left is not None and left <= 3) else 0,
        "status": d["status"],
        "assigned_to": d["assigned_to"] or "Accounting Team",
        "client_reply": d["client_reply"],
    }


def query_to_api(r):
    d = dict(r)
    return {
        "id": d["ref"],
        "subject": d["subject"],
        "category": d["category"],
        "status": d["status"],
        "updated": rel_time(d["updated_at"]),
        "assigned": d["assigned_to"],
        "created_by": d["created_by"],
    }


def initials(name):
    return "".join(p[0] for p in (name or "").split()[:2]).upper() or "AC"


# ─────────────────────────────── handler ───────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "PortalDev/2.0"

    # ---- plumbing
    def log_message(self, fmt, *args):
        pass

    def _cors(self):
        origin = self.headers.get("Origin") or FRONTEND_ORIGIN
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Company, Accept")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Vary", "Origin")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _send(self, data, status=200):
        raw = json.dumps(data, default=str).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _args(self, parsed):
        args = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            try:
                body = json.loads(self.rfile.read(length).decode() or "{}")
                if isinstance(body, dict):
                    args.update(body)
            except Exception:
                raise ApiError("Invalid JSON body")
        return args

    def _user(self, conn, required=True):
        auth = self.headers.get("Authorization", "")
        token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else ""
        row = None
        if token:
            row = conn.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.email=s.user_email WHERE s.token=?",
                (token,),
            ).fetchone()
        if not row and required:
            raise ApiError("Not authenticated. Please sign in.", 401)
        return row

    def _company(self, conn, user):
        """Resolve and authorise the active company (X-Company header)."""
        cid = self.headers.get("X-Company")
        if not cid or not str(cid).isdigit():
            raise ApiError("No active company selected.", 400)
        m = conn.execute(
            "SELECT * FROM company_members WHERE company_id=? AND user_email=?",
            (int(cid), user["email"]),
        ).fetchone()
        if not m:
            raise ApiError("You are not a member of this company.", 403)
        return int(cid), m["role"]

    def _dispatch(self):
        parsed = urllib.parse.urlparse(self.path)
        method = parsed.path.rsplit("/", 1)[-1]
        try:
            args = self._args(parsed)
            conn = db()
            try:
                short = method.split("frappe_client_portal.api.")[-1].replace(".", "_")
                fn = getattr(self, "api_" + short, None)
                if not fn:
                    raise ApiError(f"Unknown method: {method}", 404)
                result = fn(conn, args)
                conn.commit()
                return self._send(result)
            finally:
                conn.close()
        except ApiError as e:
            return self._send({"status": "error", "message": e.message}, e.status)
        except Exception as e:  # pragma: no cover
            import traceback
            traceback.print_exc()
            return self._send({"status": "error", "message": f"Server error: {e}"}, 500)

    def do_GET(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    # ─────────────── auth ───────────────
    def _user_payload(self, conn, user):
        comps = conn.execute(
            "SELECT c.*, m.role FROM companies c JOIN company_members m ON m.company_id=c.id "
            "WHERE m.user_email=? ORDER BY c.id",
            (user["email"],),
        ).fetchall()
        return {
            "user": user["email"],
            "email": user["email"],
            "name": user["full_name"],
            "full_name": user["full_name"],
            "companies": [company_dict(c, c["role"]) for c in comps],
        }

    def api_auth_login(self, conn, a):
        usr = (a.get("usr") or "").strip().lower()
        pwd = a.get("pwd") or ""
        user = conn.execute("SELECT * FROM users WHERE email=?", (usr,)).fetchone()
        if not user or not check_pw(pwd, user["password_hash"]):
            raise ApiError("Incorrect email or password.", 401)
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO sessions VALUES(?,?,?)", (token, usr, now()))
        out = {"status": "success", "message": "Logged In", "token": token,
               "two_factor_required": ENABLE_2FA}
        out.update(self._user_payload(conn, user))
        if ENABLE_2FA:
            code = str(random.randint(100000, 999999))
            OTPS[usr] = code
            print(f"[2FA] code for {usr}: {code}")
            out["otp"] = code
        return out

    def api_auth_logout(self, conn, a):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            conn.execute("DELETE FROM sessions WHERE token=?", (auth.split(" ", 1)[1],))
        return {"status": "success", "message": "Logged Out"}

    def api_auth_get_current_user(self, conn, a):
        user = self._user(conn)
        out = {"status": "success"}
        out.update(self._user_payload(conn, user))
        return out

    def api_auth_send_otp(self, conn, a):
        usr = (a.get("usr") or "").strip().lower()
        code = str(random.randint(100000, 999999))
        OTPS[usr] = code
        print(f"[2FA] code for {usr}: {code}")
        return {"status": "success", "otp": code, "email": usr}

    def api_auth_verify_otp(self, conn, a):
        usr = (a.get("usr") or "").strip().lower()
        code = str(a.get("code", "")).strip()
        if code == OTPS.get(usr) or code == "123456":
            return {"status": "success", "verified": True, "user": usr}
        raise ApiError("Invalid verification code.", 400)

    # ─────────────── companies ───────────────
    def api_company_get_my_companies(self, conn, a):
        user = self._user(conn)
        return {"status": "success", "data": self._user_payload(conn, user)["companies"]}

    def api_company_create_company(self, conn, a):
        user = self._user(conn)
        data = a.get("data") if isinstance(a.get("data"), dict) else a
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("Company name is required.")
        cur = conn.execute(
            "INSERT INTO companies(name,company_number,type,address,vat_number,year_end,phone,email,"
            "created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (name, data.get("company_number", ""), data.get("type", "Limited Company"),
             data.get("address", ""), data.get("vat_number", ""), data.get("year_end", ""),
             data.get("phone", ""), data.get("email", user["email"]), user["email"], now()),
        )
        cid = cur.lastrowid
        conn.execute("INSERT INTO company_members(company_id,user_email,role) VALUES(?,?,?)",
                     (cid, user["email"], "Owner"))
        row = conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
        return {"status": "success", "data": company_dict(row, "Owner")}

    def api_company_get_company_profile(self, conn, a):
        user = self._user(conn)
        cid, role = self._company(conn, user)
        row = conn.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
        return {"status": "success", "data": company_dict(row, role)}

    def api_company_update_company_profile(self, conn, a):
        user = self._user(conn)
        cid, role = self._company(conn, user)
        if role not in ("Owner", "Admin"):
            raise ApiError("Only owners can edit the company profile.", 403)
        data = a.get("data") if isinstance(a.get("data"), dict) else {}
        allowed = {"name", "company_number", "type", "address", "vat_number", "year_end", "phone", "email"}
        for k, v in data.items():
            if k in allowed:
                conn.execute(f"UPDATE companies SET {k}=? WHERE id=?", (v, cid))
        return {"status": "success", "message": "Company profile updated"}

    def api_company_save_onboarding_step(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        step = int(a.get("step") or 1)
        done = 1 if a.get("completed") in (True, "true", 1, "1") else 0
        conn.execute("UPDATE companies SET onboarding_step=?, onboarding_completed=? WHERE id=?",
                     (step, done, cid))
        return {"status": "success"}

    # ─────────────── dashboard ───────────────
    def api_dashboard_get_dashboard_summary(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)

        def count(status):
            return conn.execute(
                "SELECT COUNT(*) FROM submissions WHERE company_id=? AND status=?", (cid, status)
            ).fetchone()[0]

        reqs = [req_to_api(r) for r in conn.execute(
            "SELECT * FROM requests WHERE company_id=? AND status='Pending' ORDER BY due_date", (cid,))]
        tasks = []
        for t in conn.execute(
                "SELECT * FROM tasks WHERE company_id=? AND status!='Done' ORDER BY due_date", (cid,)):
            left = days_until(t["due_date"]) if t["due_date"] else None
            tasks.append({"name": t["ref"], "title": t["title"], "due_date": t["due_date"],
                          "days_remaining": left if left is not None else 0,
                          "priority": t["priority"], "status": t["status"]})
        open_q = conn.execute(
            "SELECT COUNT(*) FROM queries WHERE company_id=? AND status!='Closed'", (cid,)).fetchone()[0]
        activity = []
        for r in conn.execute(
                "SELECT * FROM submissions WHERE company_id=? ORDER BY id DESC LIMIT 5", (cid,)):
            activity.append({"type": "submission", "text": f"{r['submission_type']} {r['ref']} is {r['status']}",
                             "time": rel_time(r["updated_at"])})
        return {"status": "success", "data": {
            "counts": {"submitted": count("Submitted"), "received": count("Received"),
                       "in_review": count("In Review"), "needs_info": count("Needs Info"),
                       "processed": count("Processed"), "rejected": count("Rejected")},
            "urgent_requests": reqs, "upcoming_tasks": tasks,
            "open_queries_count": open_q, "recent_activity": activity}}

    # ─────────────── submissions ───────────────
    def _new_ref(self, conn, table, prefix):
        n = conn.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM {table}").fetchone()[0]
        return f"{prefix}-{datetime.date.today().year}-{n:06d}"

    def _create_submission(self, conn, user, cid, stype, prefix, a, items=None, total=0, files=None):
        ref = self._new_ref(conn, "submissions", prefix)
        ts = now()
        date_val = a.get("date")
        if date_val:
            if not items:
                items = [{"date": date_val}]
            elif isinstance(items, list) and len(items) > 0 and isinstance(items[0], dict) and not items[0].get("date"):
                items[0]["date"] = date_val
        conn.execute(
            "INSERT INTO submissions(ref,company_id,submission_type,status,period,submitted_by,notes,"
            "total_gross,items,files,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (ref, cid, stype, "Submitted", a.get("period", ""), user["full_name"], a.get("notes", ""),
             total, json.dumps(items or []), json.dumps(files or []), ts, ts))
        self._notify(conn, cid, f"{stype} submitted", f"{ref} has been received for processing.")
        return ref

    def _as_list(self, v):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                v = [v]
        return v or []

    def api_submissions_get_submissions(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        sql, p = "SELECT * FROM submissions WHERE company_id=?", [cid]
        if a.get("submission_type"):
            stype = a["submission_type"]
            if stype in ("Sales Invoice", "Purchase Invoice"):
                sql += " AND (submission_type='Purchase Invoice' OR submission_type='Sales Invoice')"
            elif stype in ("Expense", "Expense Claim"):
                sql += " AND (submission_type='Expense Claim' OR submission_type='Expense')"
            elif stype in ("Bank Statement", "Document"):
                sql += " AND (submission_type='Bank Statement' OR submission_type='Document')"
            else:
                sql += " AND submission_type=?"
                p.append(stype)
        if a.get("status"):
            sql += " AND status=?"
            p.append(a["status"])
        if a.get("period"):
            sql += " AND period=?"
            p.append(a["period"])
        if a.get("search"):
            sql += " AND (ref LIKE ? OR notes LIKE ?)"
            p += [f"%{a['search']}%"] * 2
        sql += " ORDER BY id DESC"
        return {"status": "success", "data": [sub_to_api(r) for r in conn.execute(sql, p)]}

    def api_submissions_get_submission_detail(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        r = conn.execute("SELECT * FROM submissions WHERE company_id=? AND ref=?",
                         (cid, a.get("reference"))).fetchone()
        if not r:
            raise ApiError("Submission not found.", 404)
        d = sub_to_api(r)
        d["staff_requests"] = [req_to_api(x) for x in conn.execute(
            "SELECT * FROM requests WHERE company_id=? AND submission_ref=?", (cid, r["ref"]))]
        return {"status": "success", "data": d}

    def api_submissions_submit_expense_claim(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        items = self._as_list(a.get("items"))
        total = sum(float(i.get("total_amount", 0) or 0) for i in items if isinstance(i, dict))
        ref = self._create_submission(conn, user, cid, "Expense Claim", "EXP", a, items, total)
        return {"status": "success", "reference": ref}

    def api_submissions_submit_sales_invoice(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        items = self._as_list(a.get("items"))
        total = float(a.get("total_amount") or a.get("total") or a.get("amount") or 0)
        ref = self._create_submission(conn, user, cid, "Purchase Invoice", "INV", a, items, total)
        return {"status": "success", "reference": ref}

    def api_submissions_submit_payroll(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        entries = self._as_list(a.get("entries"))
        ref = self._create_submission(conn, user, cid, "Payroll", "PAY", a, entries)
        return {"status": "success", "reference": ref}

    def api_submissions_upload_documents(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        files = self._as_list(a.get("file_urls") or a.get("fileUrls"))
        if not files:
            raise ApiError("No files provided.")
        names = [f.get("name") if isinstance(f, dict) else str(f) for f in files]
        notes = a.get("notes", "")
        a = dict(a)
        a["notes"] = (notes + " " if notes else "") + ", ".join(names)
        ref = self._create_submission(conn, user, cid, a.get("category", "Document"), "DOC", a,
                                      files=[{"name": n} for n in names])
        return {"status": "success", "reference": ref, "message": f"Uploaded {len(names)} file(s)"}

    def api_submissions_withdraw_submission(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        conn.execute("DELETE FROM submissions WHERE company_id=? AND ref=? AND status='Submitted'",
                     (cid, a.get("reference")))
        return {"status": "success"}

    # ─────────────── requests ───────────────
    def api_requests_get_requests(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        status = a.get("status")
        sql, p = "SELECT * FROM requests WHERE company_id=?", [cid]
        if status and status != "All":
            sql += " AND status=?"
            p.append(status)
        sql += " ORDER BY id DESC"
        return {"status": "success", "data": [req_to_api(r) for r in conn.execute(sql, p)]}

    def api_requests_reply_request(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        rid = a.get("request_id") or a.get("requestId")
        r = conn.execute("SELECT * FROM requests WHERE company_id=? AND ref=?", (cid, rid)).fetchone()
        if not r:
            raise ApiError("Request not found.", 404)
        conn.execute("UPDATE requests SET status='Completed', client_reply=? WHERE id=?",
                     (a.get("reply_text") or a.get("replyText") or "", r["id"]))
        conn.execute("UPDATE submissions SET status='In Review', updated_at=? "
                     "WHERE company_id=? AND ref=? AND status='Needs Info'", (now(), cid, r["submission_ref"]))
        return {"status": "success", "message": "Reply sent successfully"}

    # ─────────────── queries (helpdesk) ───────────────
    def api_queries_get_queries(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        rows = conn.execute("SELECT * FROM queries WHERE company_id=? ORDER BY id DESC", (cid,)).fetchall()
        out = []
        for r in rows:
            d = query_to_api(r)
            last = conn.execute("SELECT * FROM query_messages WHERE query_id=? ORDER BY id DESC LIMIT 1",
                                (r["id"],)).fetchone()
            d["message"] = last["body"] if last else ""
            d["has_staff_reply"] = bool(last and last["is_staff"])
            out.append(d)
        return {"status": "success", "data": out}

    def api_queries_get_query_detail(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        r = conn.execute("SELECT * FROM queries WHERE company_id=? AND ref=?", (cid, a.get("id"))).fetchone()
        if not r:
            raise ApiError("Query not found.", 404)
        d = query_to_api(r)
        d["messages"] = [{"sender": m["sender"], "is_staff": bool(m["is_staff"]), "body": m["body"],
                          "time": rel_time(m["created_at"])}
                         for m in conn.execute("SELECT * FROM query_messages WHERE query_id=? ORDER BY id",
                                               (r["id"],))]
        return {"status": "success", "data": d}

    def api_queries_create_query(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        subject = (a.get("subject") or "").strip()
        if not subject:
            raise ApiError("Subject is required.")
        ref = self._new_ref(conn, "queries", "HD")
        ts = now()
        cur = conn.execute(
            "INSERT INTO queries(ref,company_id,subject,category,created_by,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?)", (ref, cid, subject, a.get("category", "General"), user["full_name"], ts, ts))
        conn.execute("INSERT INTO query_messages(query_id,sender,is_staff,body,created_at) VALUES(?,?,?,?,?)",
                     (cur.lastrowid, user["full_name"], 0, a.get("message", ""), ts))
        self._notify(conn, cid, "Query submitted", f"Ticket {ref}: {subject} is now open with accounting.")
        r = conn.execute("SELECT * FROM queries WHERE id=?", (cur.lastrowid,)).fetchone()
        d = query_to_api(r)
        d["message"] = a.get("message", "")
        return {"status": "success", "data": d}

    def api_queries_reply_query(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        r = conn.execute("SELECT * FROM queries WHERE company_id=? AND ref=?", (cid, a.get("id"))).fetchone()
        if not r:
            raise ApiError("Query not found.", 404)
        ts = now()
        conn.execute("INSERT INTO query_messages(query_id,sender,is_staff,body,created_at) VALUES(?,?,?,?,?)",
                     (r["id"], user["full_name"], 0, a.get("message", ""), ts))
        conn.execute("UPDATE queries SET status='Open', updated_at=? WHERE id=?", (ts, r["id"]))
        return {"status": "success"}

    # ─────────────── team ───────────────
    def api_team_get_team_members(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        rows = conn.execute(
            "SELECT m.*, u.full_name FROM company_members m LEFT JOIN users u ON u.email=m.user_email "
            "WHERE m.company_id=?", (cid,)).fetchall()
        return {"status": "success", "data": [
            {"name": r["user_email"], "email": r["user_email"], "full_name": r["full_name"] or r["user_email"],
             "role": r["role"], "status": r["status"], "initials": initials(r["full_name"] or r["user_email"])}
            for r in rows]}

    def api_team_invite_team_member(self, conn, a):
        user = self._user(conn)
        cid, role = self._company(conn, user)
        if role not in ("Owner", "Admin"):
            raise ApiError("Only owners can invite members.", 403)
        email = (a.get("email") or "").strip().lower()
        if not email:
            raise ApiError("Email is required.")
        target = conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
        conn.execute("INSERT OR REPLACE INTO company_members VALUES(?,?,?,?)",
                     (cid, email, a.get("role", "Bookkeeping"), "Active" if target else "Invited"))
        return {"status": "success", "message": "Invitation recorded"}

    # ─────────────── tasks / notifications ───────────────
    def api_tasks_create_task(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        ref = self._new_ref(conn, "tasks", "TSK")
        due = a.get("due_date") or ""
        title = (a.get("title") or "Task").strip()
        conn.execute(
            "INSERT INTO tasks(ref,company_id,title,due_date,priority,created_at) VALUES(?,?,?,?,?,?)",
            (ref, cid, title, due, a.get("priority", "Medium"), now()),
        )
        self._notify(conn, cid, "New task scheduled", title)
        return {"status": "success", "reference": ref}

    def api_tasks_update_task_status(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        status = a.get("status", "Done")
        ref = a.get("id") or a.get("reference")
        conn.execute("UPDATE tasks SET status=? WHERE company_id=? AND (ref=? OR id=?)",
                     (status, cid, ref, ref))
        return {"status": "success"}

    def api_tasks_get_tasks(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        rows = conn.execute("SELECT * FROM tasks WHERE company_id=? ORDER BY due_date", (cid,)).fetchall()
        return {"status": "success", "data": [
            {"name": r["ref"], "title": r["title"], "due_date": r["due_date"], "priority": r["priority"],
             "status": r["status"], "days_remaining": days_until(r["due_date"]) if r["due_date"] else None}
            for r in rows]}

    def api_notifications_get_notifications(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        rows = conn.execute("SELECT * FROM notifications WHERE company_id=? AND user_email=? ORDER BY id DESC",
                            (cid, user["email"])).fetchall()
        return {"status": "success", "data": [
            {"id": r["id"], "title": r["title"], "body": r["body"], "is_read": bool(r["is_read"]),
             "time": rel_time(r["created_at"])} for r in rows]}

    def api_notifications_mark_all_read(self, conn, a):
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        conn.execute("UPDATE notifications SET is_read=1 WHERE company_id=? AND user_email=?",
                     (cid, user["email"]))
        return {"status": "success"}

    # ─────────────── dev-only staff actions ───────────────
    def _dev(self, conn):
        if not ENABLE_DEV_STAFF:
            raise ApiError("Dev staff actions are disabled.", 403)
        user = self._user(conn)
        cid, _ = self._company(conn, user)
        return user, cid

    def _notify(self, conn, cid, title, body):
        for m in conn.execute("SELECT user_email FROM company_members WHERE company_id=?", (cid,)):
            conn.execute("INSERT INTO notifications(company_id,user_email,title,body,created_at) VALUES(?,?,?,?,?)",
                         (cid, m["user_email"], title, body, now()))

    def api_dev_set_submission_status(self, conn, a):
        user, cid = self._dev(conn)
        status = a.get("status")
        if status not in ("Submitted", "Received", "In Review", "Needs Info", "Processed", "Rejected"):
            raise ApiError("Invalid status.")
        conn.execute("UPDATE submissions SET status=?, updated_at=? WHERE company_id=? AND ref=?",
                     (status, now(), cid, a.get("reference")))
        self._notify(conn, cid, "Submission updated", f"{a.get('reference')} is now {status}")
        return {"status": "success"}

    def api_dev_create_request(self, conn, a):
        user, cid = self._dev(conn)
        ref = self._new_ref(conn, "requests", "RQ")
        due = a.get("due_date") or (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
        conn.execute(
            "INSERT INTO requests(ref,company_id,submission_ref,title,message,due_date,assigned_to,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (ref, cid, a.get("submission"), a.get("title", "Information needed"), a.get("message", ""),
             due, "Accounting Team", now()))
        if a.get("submission"):
            conn.execute("UPDATE submissions SET status='Needs Info', updated_at=? WHERE company_id=? AND ref=?",
                         (now(), cid, a["submission"]))
        self._notify(conn, cid, "Information requested", a.get("title", "Information needed"))
        return {"status": "success", "reference": ref}

    def api_dev_create_task(self, conn, a):
        user, cid = self._dev(conn)
        ref = self._new_ref(conn, "tasks", "TSK")
        conn.execute("INSERT INTO tasks(ref,company_id,title,due_date,priority,created_at) VALUES(?,?,?,?,?,?)",
                     (ref, cid, a.get("title", "Task"), a.get("due_date", ""), a.get("priority", "Medium"), now()))
        return {"status": "success", "reference": ref}

    def api_dev_staff_reply_query(self, conn, a):
        user, cid = self._dev(conn)
        r = conn.execute("SELECT * FROM queries WHERE company_id=? AND ref=?", (cid, a.get("id"))).fetchone()
        if not r:
            raise ApiError("Query not found.", 404)
        conn.execute("INSERT INTO query_messages(query_id,sender,is_staff,body,created_at) VALUES(?,?,?,?,?)",
                     (r["id"], "Accounting Team", 1, a.get("message", ""), now()))
        conn.execute("UPDATE queries SET status='Replied', assigned_to='Accounting Team', updated_at=? WHERE id=?",
                     (now(), r["id"]))
        self._notify(conn, cid, "New reply on your query", r["subject"])
        return {"status": "success"}


def run():
    init_db()
    httpd = ThreadingHTTPServer(("", PORT), Handler)
    print("=" * 60)
    print("[SERVER] Frappe Client Portal Local Dev Server (SQLite) running")
    print(f"[SERVER] Address: http://localhost:{PORT}")
    print(f"[SERVER] DB: {DB_PATH}")
    print(f"[SERVER] 2FA enabled: {ENABLE_2FA}")
    print("[SERVER] Test accounts (no data, no companies):")
    for email, name, pwd in SEED_USERS:
        print(f"         {email}  /  {pwd}")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down")


if __name__ == "__main__":
    run()
