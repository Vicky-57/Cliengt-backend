"""
Standalone Local Development Server for Frappe Client Portal Backend
Runs directly on Windows without requiring WSL or Frappe Bench setup.
Serves Frappe API endpoints on port 8000 with CORS enabled for Vite frontend (5173).
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import os

PORT = 8000

# In-memory test state
STATE = {
    "user": {
        "email": "finance@northstarcreative.co.uk",
        "first_name": "Sarah",
        "last_name": "Mitchell",
        "full_name": "Sarah Mitchell"
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
    "submissions": [
        {
            "name": "REF-1042",
            "submission_type": "Sales Invoice",
            "status": "Submitted",
            "period": "Oct 2026",
            "submitted_by": "Sarah Mitchell",
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
            "message": "Hi Sarah, the attachment for REF-1041 is just a booking confirmation. Please attach the tax receipt showing the VAT breakdown.",
            "due_date": "2026-10-15",
            "is_urgent": 1,
            "status": "Pending",
            "client_reply": None
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
                    "user": STATE["user"],
                    "company": STATE["company"],
                    "role": STATE["role"]
                }
            })

        # 2. get_dashboard_summary
        if path.endswith("/frappe_client_portal.api.dashboard.get_dashboard_summary"):
            counts = {
                "submitted": sum(1 for s in STATE["submissions"] if s["status"] == "Submitted"),
                "received": 0,
                "in_review": sum(1 for s in STATE["submissions"] if s["status"] == "In Review"),
                "needs_info": sum(1 for s in STATE["submissions"] if s["status"] == "Needs Info"),
                "processed": sum(1 for s in STATE["submissions"] if s["status"] == "Processed"),
                "rejected": sum(1 for s in STATE["submissions"] if s["status"] == "Rejected")
            }
            return self._send_json({
                "status": "success",
                "data": {
                    "counts": counts,
                    "urgent_requests": [r for r in STATE["requests"] if r["status"] == "Pending"],
                    "upcoming_tasks": [
                        {"name": "TSK-01", "title": "Upload October bank statements", "due_date": "2026-10-25", "priority": "High", "status": "Open"},
                        {"name": "TSK-02", "title": "Review Q3 VAT Return draft", "due_date": "2026-10-31", "priority": "Urgent", "status": "In Progress"}
                    ]
                }
            })

        # 3. get_submissions
        if path.endswith("/frappe_client_portal.api.submissions.get_submissions"):
            return self._send_json({
                "status": "success",
                "data": STATE["submissions"],
                "total": len(STATE["submissions"])
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
            return self._send_json({
                "status": "success",
                "data": STATE["requests"]
            })

        # 6. get_company_profile
        if path.endswith("/frappe_client_portal.api.company.get_company_profile"):
            return self._send_json({
                "status": "success",
                "data": STATE["company"]
            })

        # 7. get_team_members
        if path.endswith("/frappe_client_portal.api.team.get_team_members"):
            return self._send_json({
                "status": "success",
                "data": [
                    {"name": "LINK-01", "user": "finance@northstarcreative.co.uk", "name_display": "Sarah Mitchell", "portal_role": "Owner", "status": "Active", "last_login": "Today, 14:00"},
                    {"name": "LINK-02", "user": "priya@northstarcreative.co.uk", "name_display": "Priya Nair", "portal_role": "Admin", "status": "Active", "last_login": "Yesterday, 09:15"},
                    {"name": "LINK-03", "user": "mike@northstarcreative.co.uk", "name_display": "Mike Ross", "portal_role": "Payroll", "status": "Active", "last_login": "05 Oct 2026"}
                ]
            })

        # Fallback
        self._send_json({"status": "success", "message": "Dev Server OK", "path": path})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        body = self._read_body()

        # Login
        if path.endswith("/frappe_client_portal.api.auth.login"):
            return self._send_json({
                "status": "success",
                "message": "Logged In",
                "user": body.get("usr", "finance@northstarcreative.co.uk"),
                "company": STATE["company"]["name"],
                "role": STATE["role"]
            })

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
                "creation": "Just now",
                "modified": "Just now",
                "notes": body.get("notes", ""),
                "items": items
            }
            STATE["submissions"].insert(0, new_sub)
            return self._send_json({"status": "success", "reference": ref})

        # Reply to Staff Request
        if path.endswith("/frappe_client_portal.api.requests.reply_request"):
            req_id = body.get("request_id")
            for r in STATE["requests"]:
                if r["name"] == req_id:
                    r["status"] = "Resolved"
                    r["client_reply"] = body.get("reply_text")
            return self._send_json({"status": "success", "message": "Reply sent successfully"})

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
    print(f"🚀 Frappe Client Portal Local Dev Server Running!")
    print(f"📍 Address: http://localhost:{PORT}")
    print(f"🔗 Connected to React Frontend: http://localhost:5173")
    print(f"Press Ctrl+C to stop the server.")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped.")

if __name__ == "__main__":
    run()
