# Frappe Client Portal Backend (`frappe_client_portal`)

A dedicated **Frappe Framework (v15 / v16)** custom application powering the modern accounting Client Portal. 

Designed for UK & EU accounting and bookkeeping firms:
* **Multi-Tenant Security:** Strict client-level data isolation using Frappe User Permissions and custom SQL permission query hooks.
* **Submissions Lifecycle:** Full pipeline for Expenses, Sales Invoices, Bookkeeping, Payroll, and Document uploads (`Submitted` -> `Received` -> `In Review` -> `Needs Info` -> `Processed` / `Rejected`).
* **Staff Desk Backoffice:** Accountants review incoming client records and manage "Needs Info" requests directly in Frappe Desk.
* **Exports Engine:** One-click batch CSV exports for **Sage 50**, **QuickBooks Online**, and **Moneysoft Payroll**.
* **Helpdesk Integration:** Built to connect natively with official `frappe/helpdesk` (`HD Ticket`).
* **Private Storage:** Permission-gated private file downloads with SHA-256 duplicate detection.

---

## Installation on Frappe Bench

```bash
# 1. In your Frappe Bench directory
cd ~/frappe-bench

# 2. Get the app from GitHub
bench get-app https://github.com/mckhtech/Cliengt-backend.git frappe_client_portal

# 3. Install the app on your site
bench --site portal.yourdomain.com install-app frappe_client_portal

# 4. Run database migrations
bench --site portal.yourdomain.com migrate
```

---

## CORS & Site Configuration

To connect this backend to the Vite React frontend (`d:\Frappe-Client-Portal`), add the following to `sites/<your-site>/site_config.json`:

```json
{
  "cors_allow_origin": [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://portal.yourdomain.com"
  ],
  "allow_cors": 1,
  "session_expiry": "06:00:00",
  "enable_two_factor_auth": 1
}
```

---

## App Structure

```
frappe_client_portal/
├── api/                   # Whitelisted JSON REST API endpoints
│   ├── auth.py            # Login, 2FA, session check, logout
│   ├── dashboard.py       # KPI card counts, deadlines, urgent requests
│   ├── submissions.py     # Submissions CRUD, line-items, duplicate hashing
│   ├── requests.py        # Staff "Needs Info" requests & client replies
│   ├── queries.py         # Helpdesk ticketing integration
│   ├── team.py            # Sub-user management & instant session kill
│   └── company.py         # Company profile & bank detail masking
├── permissions.py         # Multi-tenancy SQL filters & private file authorization
├── exports/               # Accounting export engines
│   ├── sage.py            # Sage 50 Audit Trail CSV format
│   ├── quickbooks.py      # QuickBooks Online Batch CSV format
│   └── moneysoft.py       # Moneysoft Payroll CSV format
└── doctype/               # Custom DocTypes
    ├── client_company/
    ├── client_user_link/
    ├── client_submission/
    ├── client_submission_item/
    ├── client_payroll_entry/
    ├── staff_request/
    ├── client_task/
    └── client_activity_log/
```

---

## API Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `frappe_client_portal.api.auth.login` | Authenticates client user and returns session |
| `GET` | `frappe_client_portal.api.auth.get_current_user` | Returns profile, active company, and portal role |
| `GET` | `frappe_client_portal.api.dashboard.get_dashboard_summary` | KPI counts for dashboard status cards |
| `GET` | `frappe_client_portal.api.submissions.get_submissions` | Filterable, paginated submissions list |
| `POST` | `frappe_client_portal.api.submissions.submit_expense_claim` | Multi-row expense claim with VAT calculation |
| `POST` | `frappe_client_portal.api.submissions.submit_sales_invoice` | Sales invoice logging with file attachment |
| `POST` | `frappe_client_portal.api.submissions.submit_payroll` | Monthly payroll, starters, leavers, hours |
| `POST` | `frappe_client_portal.api.submissions.upload_documents` | Batch document upload with duplicate check |
| `POST` | `frappe_client_portal.api.requests.reply_request` | Resolves "Needs Info" request with reply/files |
| `GET` | `frappe_client_portal.api.team.get_team_members` | List client company team members |
| `POST` | `frappe_client_portal.api.team.toggle_team_member_status` | Enables/disables user (kills active sessions) |

---

## License
MIT License - McKHTech.
