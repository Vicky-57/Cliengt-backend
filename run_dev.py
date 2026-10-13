"""
Standalone Local Development Server for Frappe Client Portal Backend
Runs directly on Windows without requiring WSL or Frappe Bench setup.
Serves Frappe API endpoints on port 8000 with CORS enabled for Vite frontend (5173).
Includes real 2FA OTP generation and verification, submissions engine, requests & helpdesk.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import os
import datetime
import random
import sys

# Ensure UTF-8 output on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PORT = 8000

DEMO_USERS = {
    "vikaspurohit105@gmail.com": {
        "name": "Vikas Purohit",
        "role": "Owner",
        "company": "Northstar Creative Ltd",
        "password": "Password123!",
        "phone": "+44 7700 900123"
    },
    "owner@northstar.co.uk": {
        "name": "Sarah Mitchell",
        "role": "Owner",
        "company": "Northstar Creative Ltd",
        "password": "Password123!",
        "phone": "+44 7700 900456"
    },
    "bookkeeper@northstar.co.uk": {
        "name": "Priya Nair",
        "role": "Bookkeeping",
        "company": "Northstar Creative Ltd",
        "password": "Password123!",
        "phone": "+44 7700 900789"
    },
    "payroll@northstar.co.uk": {
        "name": "Mike Ross",
        "role": "Payroll",
        "company": "Northstar Creative Ltd",
        "password": "Password123!",
        "phone": "+44 7700 900321"
    }
}

# In-memory dynamic test state
STATE = {
    "user": {
        "email": "vikaspurohit105@gmail.com",
        "first_name": "Vikas",
        "last_name": "Purohit",
        "full_name": "Vikas Purohit"
    },
    "company": {
        "name": "Northstar Creative Ltd",
        "email": "finance@northstarcreative.co.uk",
        "phone": "+44 20 7946 0842",
        "company_number": "09284117",
        "vat_number": "GB 217 8494 31",
        "registered_address": "41 Clerkenwell Road, London, EC1M 5RS",
        "trading_address": "Unit 8, The Loom, London, E1 1DU",
        "bank_name": "Monzo Business",
        "account_number": "34891234",
        "account_number_masked": "•••• 1234",
        "sort_code": "40-08-41",
        "sort_code_masked": "•••• 41",
        "status": "Active"
    },
    "role": "Owner",
    "active_otps": {},
    "submissions": [
        {
            "name": "REF-1042",
            "submission_type": "Sales Invoice",
            "status": "Submitted",
            "period": "Oct 2026",
            "submitted_by": "Vikas Purohit",
            "total_gross": 2400.0,
            "creation": "2026-10-08 14:30:00",
            "modified": "2026-10-08 14:30:00",
            "notes": "Acme Corp INV-0042",
            "items": [
                {
                    "date": "2026-10-08",
                    "supplier_customer": "Acme Corp",
                    "description": "Consulting Services Q3",
                    "category": "Sales",
                    "net_amount": 2000.0,
                    "vat_rate": 20.0,
                    "vat_amount": 400.0,
                    "total_amount": 2400.0
                }
            ]
        },
        {
            "name": "REF-1041",
            "submission_type": "Expense Claim",
            "status": "Needs Info",
            "period": "Oct 2026",
            "submitted_by": "Mike Ross",
            "total_gross": 142.50,
            "creation": "2026-10-05 09:15:00",
            "modified": "2026-10-06 11:20:00",
            "notes": "Train ticket to London",
            "items": [
                {
                    "date": "2026-10-05",
                    "supplier_customer": "LNER Trains",
                    "description": "Off-peak travel to client meeting",
                    "category": "Travel",
                    "net_amount": 118.75,
                    "vat_rate": 20.0,
                    "vat_amount": 23.75,
                    "total_amount": 142.50
                }
            ]
        },
        {
            "name": "REF-1040",
            "submission_type": "Bookkeeping Batch",
            "status": "Processed",
            "period": "Oct 2026",
            "submitted_by": "Priya Nair",
            "total_gross": 1850.0,
            "creation": "2026-10-01 10:00:00",
            "modified": "2026-10-02 16:40:00",
            "notes": "Monthly office rent",
            "items": []
        }
    ],
    "requests": [
        {
            "name": "RQ-001",
            "submission": "REF-1041",
            "title": "Missing VAT Receipt for Trainline",
            "message": "Hi Vikas, the attachment for REF-1041 is just a booking confirmation. Please attach the tax receipt showing the VAT breakdown.",
            "due_date": "2026-10-15",
            "days_left": 2,
            "is_urgent": 1,
            "status": "Pending",
            "assigned_to": "Alex Morgan",
            "client_reply": None
        }
    ],
    "queries": [
        {
            "id": "HD-2045",
            "subject": "Tax code discrepancy on September invoice",
            "category": "Tax",
            "status": "Replied",
            "updated": "Today, 10:45 AM",
            "assigned": "Sarah Jenkins",
            "message": "We noticed a discrepancy in the tax code applied on the INV-0042 draft."
        },
        {
            "id": "HD-2044",
            "subject": "Question regarding travel expense VAT",
            "category": "Expenses",
            "status": "Open",
            "updated": "Yesterday, 3:20 PM",
            "assigned": "Unassigned",
            "message": "Can we reclaim VAT on international train bookings?"
        }
    ]
}

class FrappeApiHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Allow-Credentials", "true")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body_bytes = self.rfile.read(content_length)
            try:
                return json.loads(body_bytes.decode("utf-8"))
            except Exception:
                return {}
        return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. get_current_user
        if path.endswith("/frappe_client_portal.api.auth.get_current_user"):
            return self._send_json({
                "status": "success",
                "data": {
                    "user": STATE["user"]["email"],
                    "name": STATE["user"]["full_name"],
                    "email": STATE["user"]["email"],
                    "company": STATE["company"]["name"],
                    "company_details": STATE["company"],
                    "role": STATE["role"],
                    "portal_role": STATE["role"]
                }
            })

        # 2. get_dashboard_summary (Dynamic real counts & tasks)
        if path.endswith("/frappe_client_portal.api.dashboard.get_dashboard_summary"):
            counts = {
                "submitted": sum(1 for s in STATE["submissions"] if s["status"] == "Submitted"),
                "received": sum(1 for s in STATE["submissions"] if s["status"] == "Received"),
                "in_review": sum(1 for s in STATE["submissions"] if s["status"] == "In Review"),
                "needs_info": sum(1 for s in STATE["submissions"] if s["status"] == "Needs Info"),
                "processed": sum(1 for s in STATE["submissions"] if s["status"] == "Processed"),
                "rejected": sum(1 for s in STATE["submissions"] if s["status"] == "Rejected")
            }
            pending_requests = [r for r in STATE["requests"] if r["status"] == "Pending"]
            return self._send_json({
                "status": "success",
                "data": {
                    "counts": counts,
                    "urgent_requests": pending_requests,
                    "upcoming_tasks": [
                        {"name": "TSK-01", "title": "VAT Return Q3 Review", "due_date": "2026-11-07", "days_remaining": 25, "priority": "Urgent", "status": "In Progress"},
                        {"name": "TSK-02", "title": "Annual Accounts Preparation", "due_date": "2026-12-31", "days_remaining": 79, "priority": "High", "status": "Open"}
                    ],
                    "open_queries_count": len([q for q in STATE["queries"] if q["status"] != "Closed"])
                }
            })

        # 3. get_submissions
        if path.endswith("/frappe_client_portal.api.submissions.get_submissions"):
            sub_type = query.get("submission_type", [""])[0]
            status = query.get("status", [""])[0]
            period = query.get("period", [""])[0]
            search = query.get("search", [""])[0].lower()

            results = list(STATE["submissions"])
            if sub_type:
                results = [s for s in results if s.get("submission_type") == sub_type]
            if status:
                results = [s for s in results if s.get("status") == status]
            if period:
                results = [s for s in results if s.get("period") == period]
            if search:
                results = [s for s in results if search in s.get("name", "").lower() or search in s.get("notes", "").lower()]

            return self._send_json({
                "status": "success",
                "data": results,
                "total": len(results)
            })

        # 4. get_submission_detail
        if path.endswith("/frappe_client_portal.api.submissions.get_submission_detail"):
            ref = query.get("reference", [""])[0]
            sub = next((s for s in STATE["submissions"] if s["name"] == ref), None)
            if sub:
                sub_dict = dict(sub)
                sub_dict["staff_requests"] = [r for r in STATE["requests"] if r.get("submission") == ref]
                return self._send_json({"status": "success", "data": sub_dict})
            return self._send_json({"status": "error", "message": "Not found"}, 404)

        # 5. get_requests
        if path.endswith("/frappe_client_portal.api.requests.get_requests"):
            req_status = query.get("status", [""])[0]
            reqs = STATE["requests"]
            if req_status:
                reqs = [r for r in reqs if r["status"] == req_status]
            return self._send_json({
                "status": "success",
                "data": reqs
            })

        # 6. get_queries
        if path.endswith("/frappe_client_portal.api.queries.get_queries"):
            return self._send_json({
                "status": "success",
                "data": STATE["queries"]
            })

        # 7. get_company_profile
        if path.endswith("/frappe_client_portal.api.company.get_company_profile"):
            return self._send_json({
                "status": "success",
                "data": STATE["company"]
            })

        # 8. get_team_members
        if path.endswith("/frappe_client_portal.api.team.get_team_members"):
            return self._send_json({
                "status": "success",
                "data": [
                    {"name": "LINK-01", "user": "vikaspurohit105@gmail.com", "name_display": "Vikas Purohit", "portal_role": "Owner", "status": "Active", "last_login": "Today, 17:30"},
                    {"name": "LINK-02", "user": "owner@northstar.co.uk", "name_display": "Sarah Mitchell", "portal_role": "Owner", "status": "Active", "last_login": "Today, 14:00"},
                    {"name": "LINK-03", "user": "bookkeeper@northstar.co.uk", "name_display": "Priya Nair", "portal_role": "Bookkeeping", "status": "Active", "last_login": "Yesterday, 09:15"},
                    {"name": "LINK-04", "user": "payroll@northstar.co.uk", "name_display": "Mike Ross", "portal_role": "Payroll", "status": "Active", "last_login": "05 Oct 2026"}
                ]
            })

        # Fallback
        self._send_json({"status": "success", "message": "Dev Server OK", "path": path})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self._read_body()

        # Login
        if path.endswith("/frappe_client_portal.api.auth.login"):
            usr = body.get("usr", "").strip().lower()
            pwd = body.get("pwd", "")

            matched = DEMO_USERS.get(usr)
            if not matched:
                return self._send_json({
                    "status": "error",
                    "message": "Invalid email address. Please use vikaspurohit105@gmail.com or one of the demo accounts."
                }, 401)
            
            if pwd != matched["password"]:
                return self._send_json({
                    "status": "error",
                    "message": "Invalid password. The account password is Password123!"
                }, 401)
            
            STATE["user"]["email"] = usr
            STATE["user"]["full_name"] = matched["name"]
            STATE["role"] = matched["role"]
            STATE["company"]["name"] = matched["company"]

            # Generate 2FA code
            otp_code = str(random.randint(100000, 999999))
            STATE["active_otps"][usr] = otp_code
            print(f"[2FA AUTH] >>> Sent 6-digit verification code: {otp_code} to {usr} <<<")
            
            return self._send_json({
                "status": "success",
                "message": "Logged In",
                "user": usr,
                "full_name": matched["name"],
                "company": matched["company"],
                "role": matched["role"],
                "portal_role": matched["role"],
                "two_factor_required": True,
                "otp": otp_code
            })

        # Send 2FA OTP Code
        if path.endswith("/frappe_client_portal.api.auth.send_otp"):
            usr = body.get("usr", "").strip().lower() or STATE["user"]["email"]
            otp_code = str(random.randint(100000, 999999))
            STATE["active_otps"][usr] = otp_code
            print(f"[2FA AUTH] >>> Dispatched 6-digit verification code: {otp_code} to {usr} <<<")
            return self._send_json({
                "status": "success",
                "message": f"Verification code sent to {usr}",
                "otp": otp_code,
                "email": usr
            })

        # Verify 2FA OTP Code
        if path.endswith("/frappe_client_portal.api.auth.verify_otp"):
            usr = body.get("usr", "").strip().lower() or STATE["user"]["email"]
            code = str(body.get("code", "")).strip()
            valid_code = STATE.get("active_otps", {}).get(usr)
            if code == valid_code or code == "123456":
                return self._send_json({
                    "status": "success",
                    "message": "2FA verification successful",
                    "verified": True,
                    "user": usr
                })
            return self._send_json({
                "status": "error",
                "message": "Invalid 2FA code. Please enter the code sent to your email or use 123456."
            }, 400)

        # Logout
        if path.endswith("/frappe_client_portal.api.auth.logout"):
            return self._send_json({"status": "success", "message": "Logged Out"})

        # Submit Expense Claim
        if path.endswith("/frappe_client_portal.api.submissions.submit_expense_claim"):
            ref = f"REF-{1043 + len(STATE['submissions'])}"
            items = body.get("items", [])
            if isinstance(items, str):
                items = json.loads(items)
            total = sum(float(i.get("total_amount", 0) or 0) for i in items)
            new_sub = {
                "name": ref,
                "submission_type": "Expense Claim",
                "status": "Submitted",
                "period": body.get("period", "Oct 2026"),
                "submitted_by": STATE["user"]["full_name"],
                "total_gross": total,
                "creation": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "modified": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "notes": body.get("notes", ""),
                "items": items
            }
            STATE["submissions"].insert(0, new_sub)
            return self._send_json({"status": "success", "reference": ref})

        # Batch Upload Documents
        if path.endswith("/frappe_client_portal.api.submissions.upload_documents"):
            category = body.get("category", "Document")
            period = body.get("period", "Oct 2026")
            file_urls = body.get("file_urls") or body.get("fileUrls") or []
            if isinstance(file_urls, str):
                try:
                    file_urls = json.loads(file_urls)
                except Exception:
                    file_urls = [file_urls]
            
            if not file_urls:
                file_urls = ["Uploaded_Document.pdf"]
            
            ref = f"DOC-{1050 + len(STATE['submissions'])}"
            created_docs = []
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for item in file_urls:
                doc_name = item.get("name", "Document.pdf") if isinstance(item, dict) else str(item)
                new_sub = {
                    "name": ref,
                    "submission_type": category,
                    "status": "Submitted",
                    "period": period,
                    "submitted_by": STATE["user"]["full_name"],
                    "total_gross": 0.0,
                    "creation": now_str,
                    "modified": now_str,
                    "notes": doc_name,
                    "items": []
                }
                STATE["submissions"].insert(0, new_sub)
                created_docs.append(new_sub)

            return self._send_json({
                "status": "success",
                "reference": ref,
                "message": f"Successfully uploaded {len(created_docs)} file(s)",
                "data": STATE["submissions"]
            })

        # Reply to Staff Request
        if path.endswith("/frappe_client_portal.api.requests.reply_request"):
            req_id = body.get("request_id") or body.get("requestId")
            reply_text = body.get("reply_text") or body.get("replyText")
            for r in STATE["requests"]:
                if r["name"] == req_id:
                    r["status"] = "Completed"
                    r["client_reply"] = reply_text
            return self._send_json({"status": "success", "message": "Reply sent successfully"})

        # Create New Query (Helpdesk)
        if path.endswith("/frappe_client_portal.api.queries.create_query"):
            new_id = f"HD-{2046 + len(STATE['queries'])}"
            new_q = {
                "id": new_id,
                "subject": body.get("subject", "General Inquiry"),
                "category": body.get("category", "General"),
                "status": "Open",
                "updated": "Just now",
                "assigned": "Accounting Team",
                "message": body.get("message", "")
            }
            STATE["queries"].insert(0, new_q)
            return self._send_json({"status": "success", "data": new_q})

        # Update company profile
        if path.endswith("/frappe_client_portal.api.company.update_company_profile"):
            data = body.get("data", {})
            STATE["company"].update(data)
            return self._send_json({"status": "success", "message": "Company profile updated"})

        self._send_json({"status": "success", "message": "Action completed", "path": path})

def run():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, FrappeApiHandler)
    print("=" * 60)
    print("[SERVER] Frappe Client Portal Local Dev Server Running!")
    print(f"[SERVER] Address: http://localhost:{PORT}")
    print(f"[SERVER] Connected to React Frontend: http://localhost:5173")
    print(f"[SERVER] Active Users: vikaspurohit105@gmail.com | owner@northstar.co.uk | bookkeeper@northstar.co.uk | payroll@northstar.co.uk")
    print(f"[SERVER] 2FA OTP Service: Active on /send_otp and /verify_otp (Demo code 123456 supported)")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Server stopped.")

if __name__ == "__main__":
    run()
