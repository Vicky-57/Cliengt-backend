# Frappe Client Portal - System Memory & Integration Reference

## 1. Project Directory Structure & Paths

| Component | Physical Path | Tech Stack | Port / URL |
| :--- | :--- | :--- | :--- |
| **Backend** | `D:\Frappe-client dashboard\Cliengt-backend` | Python 3, SQLite (`dev.db`), Token Auth | `http://localhost:8000` |
| **Frontend** | `D:\Frappe-client dashboard\Frappe-Client-Portal` | React 18, Vite, React Router v6, CSS | `http://localhost:5173` |

### Starting the Applications Locally
- **Start Backend:**
  ```powershell
  cd "D:\Frappe-client dashboard\Cliengt-backend"
  python run_dev.py
  ```
- **Start Frontend:**
  ```powershell
  cd "D:\Frappe-client dashboard\Frappe-Client-Portal"
  npm run dev
  ```

---

## 2. Architecture & Key Design Decisions

1. **Database-Driven Multi-Tenancy (SQLite `dev.db`):**
   - No mock/static data in `useState` or `localStorage`.
   - Every business record (`submissions`, `requests`, `queries`, `tasks`, `notifications`) has a foreign key `company_id`.
   - Requests from the frontend include the active company ID via the `X-Company` HTTP header.
   - The backend validates membership in `company_members` table; accessing another company's data returns `403 Forbidden`.

2. **Authentication & Session:**
   - Token-based Bearer authentication: `Authorization: Bearer <token>`.
   - 2FA (6-digit code) is disabled by default (`ENABLE_2FA = False` in backend and frontend). Login takes email and password directly to `/portal` or `/setup`.
   - Seed accounts start with **0 companies** and **0 business records**:
     - `alice.test@portal.dev` | `Test@1234`
     - `bob.test@portal.dev`   | `Test@1234`

3. **Onboarding / Company Setup Guard:**
   - In `App.jsx`, `ProtectedRoute` inspects `companies.length`. If `0`, it redirects to `/setup` (`CompanySetup.jsx`).
   - Filling the company form creates the company in `companies`, makes the user `Owner` in `company_members`, selects it as `activeCompany`, and forwards to `/portal`.

4. **Dynamic Live Badges:**
   - **Queries badge** in `Sidebar.jsx` only shows when `open_queries_count > 0`.
   - **Requests badge** in `Sidebar.jsx` only shows when `urgent_requests.length > 0`.
   - **Notifications bell** in `TopBar.jsx` only displays an `<em>` count when `unreadCount > 0`.
   - Custom events (`queries_updated`, `request_resolved`, `submissions_updated`, `company_changed`) trigger real-time refetches across the layout.

---

## 3. Comprehensive Backend API & Frontend Usage Mapping

All endpoints are hosted at `http://localhost:8000/api/method/frappe_client_portal.api.<module>.<method>`:

| # | Backend Method | HTTP | Required Headers | Frontend API Service | Used in Frontend Page / Component | Purpose |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `auth.login` | POST | None | `src/api/auth.js` (`authService.login`) | `src/pages/Login.jsx` | Authenticates user credentials, generates bearer session token, returns profile & companies. |
| 2 | `auth.logout` | POST | `Authorization` | `src/api/auth.js` (`authService.logout`) | `src/context/AuthContext.jsx` (`logout`) | Deletes active token from `sessions` table. |
| 3 | `auth.get_current_user` | GET | `Authorization` | `src/api/auth.js` (`authService.getCurrentUser`) | `src/context/AuthContext.jsx` | Validates session token on page reload, restores profile and associated companies. |
| 4 | `company.get_my_companies` | GET | `Authorization` | `src/api/company.js` (`companyService.getMyCompanies`) | `src/context/AuthContext.jsx` | Fetches all companies where user is an active member. |
| 5 | `company.create_company` | POST | `Authorization` | `src/api/company.js` (`companyService.createCompany`) | `src/pages/CompanySetup.jsx` | Creates a new company in `dev.db` and assigns user as `Owner`. |
| 6 | `company.get_company_profile` | GET | `Authorization`, `X-Company` | `src/api/company.js` (`companyService.getProfile`) | `src/pages/Profile.jsx` | Retrieves legal name, VAT, registration number, address, and contact details for active company. |
| 7 | `company.update_company_profile` | POST | `Authorization`, `X-Company` | `src/api/company.js` (`companyService.updateProfile`) | `src/pages/Profile.jsx` | Updates company details (restricted to `Owner` / `Admin`). |
| 8 | `company.save_onboarding_step` | POST | `Authorization`, `X-Company` | `src/api/company.js` (`companyService.saveOnboardingStep`) | `src/pages/Onboarding.jsx` | Saves statutory entity onboarding step (1 to 4) and completion status in `dev.db`. |
| 9 | `dashboard.get_dashboard_summary`| GET | `Authorization`, `X-Company` | `src/api/dashboard.js` (`dashboardService.getSummary`) | `src/pages/Dashboard.jsx`, `src/components/Sidebar.jsx` | Returns live KPI counts (`submitted`, `in_review`, `needs_info`, `processed`), urgent requests, upcoming tasks, open queries count, and recent activity. |
| 10 | `submissions.get_submissions` | GET | `Authorization`, `X-Company` | `src/api/submissions.js` (`submissionsService.getSubmissions`) | `src/pages/Submissions.jsx`, `src/pages/Expenses.jsx`, `src/pages/SalesInvoices.jsx`, `src/pages/Bookkeeping.jsx` | Lists submissions filtered by type (`Expense Claim`, `Sales Invoice`, `Bank Statement`, `Document`), status, or search query. |
| 11 | `submissions.get_submission_detail` | GET | `Authorization`, `X-Company` | `src/api/submissions.js` (`submissionsService.getSubmissionDetail`) | `src/pages/SubmissionDetail.jsx` | Fetches full submission details, uploaded file attachments, and linked accountant information requests. |
| 12 | `submissions.submit_expense_claim` | POST | `Authorization`, `X-Company` | `src/api/submissions.js` (`submissionsService.submitExpenseClaim`) | `src/pages/Expenses.jsx` | Creates a new expense claim submission (e.g. `EXP-2026-000001`), logs items & receipt files, and creates a notification. |
| 13 | `submissions.submit_sales_invoice` | POST | `Authorization`, `X-Company` | `src/api/submissions.js` (`submissionsService.submitSalesInvoice`) | `src/pages/SalesInvoices.jsx` | Creates a sales invoice record (e.g. `INV-2026-000001`) with amount, customer, and period. |
| 14 | `submissions.upload_documents` | POST | `Authorization`, `X-Company` | `src/api/submissions.js` (`submissionsService.uploadDocuments`) | `src/pages/Upload.jsx`, `src/pages/Bookkeeping.jsx` | Batches uploaded documents / statements (e.g. `DOC-2026-000001`), creates notifications, and logs activity. |
| 15 | `requests.get_requests` | GET | `Authorization`, `X-Company` | `src/api/requests.js` (`requestsService.getRequests`) | `src/pages/Requests.jsx` | Returns all pending and completed information requests from the accounting team. |
| 16 | `requests.reply_request` | POST | `Authorization`, `X-Company` | `src/api/requests.js` (`requestsService.replyRequest`) | `src/pages/Requests.jsx` | Resolves an information request with client notes / uploaded files, updates status to `Completed`, and creates a notification. |
| 17 | `queries.get_queries` | GET | `Authorization`, `X-Company` | `src/api/queries.js` (`queriesService.getQueries`) | `src/pages/Queries.jsx` | Lists all support / accounting inquiry tickets for the active company. |
| 18 | `queries.get_query_detail` | GET | `Authorization`, `X-Company` | `src/api/queries.js` (`queriesService.getQueryDetail`) | `src/pages/QueryDetail.jsx` | Retrieves complete inquiry thread messages, author attribution, and ticket status. |
| 19 | `queries.create_query` | POST | `Authorization`, `X-Company` | `src/api/queries.js` (`queriesService.createQuery`) | `src/pages/NewQuery.jsx` | Opens a new inquiry ticket (e.g. `HD-2026-000001`) with initial message, category, and priority. |
| 20 | `queries.reply_query` | POST | `Authorization`, `X-Company` | `src/api/queries.js` (`queriesService.replyQuery`) | `src/pages/QueryDetail.jsx` | Appends a client reply message to an existing inquiry ticket thread. |
| 21 | `tasks.get_tasks` | GET | `Authorization`, `X-Company` | `src/api/tasks.js` (`tasksService.getTasks`) | `src/pages/Tasks.jsx` | Retrieves internal delegation tasks (`Open`, `In Progress`, `Done`) for the active company. |
| 22 | `tasks.create_task` | POST | `Authorization`, `X-Company` | `src/api/tasks.js` (`tasksService.createTask`) | `src/pages/Tasks.jsx` | Adds an internal delegation task, logs due date, and generates a notification. |
| 23 | `tasks.update_task_status` | POST | `Authorization`, `X-Company` | `src/api/tasks.js` (`tasksService.updateTaskStatus`) | `src/pages/Tasks.jsx` | Updates task status between columns (`Open` -> `In Progress` -> `Done`). |
| 24 | `team.get_team_members` | GET | `Authorization`, `X-Company` | `src/api/team.js` (`teamService.getTeamMembers`) | `src/pages/Team.jsx` | Lists all members associated with the active company and their roles (`Owner`, `Admin`, `Bookkeeping`, `View-only`). |
| 25 | `team.invite_team_member` | POST | `Authorization`, `X-Company` | `src/api/team.js` (`teamService.inviteMember`) | `src/pages/Team.jsx` | Records an invited member for the active company. |
| 26 | `notifications.get_notifications` | GET | `Authorization`, `X-Company` | `src/api/notifications.js` (`notificationsService.getNotifications`) | `src/pages/Notifications.jsx`, `src/components/TopBar.jsx` | Fetches notification list and calculates unread count for the top bar badge. |
| 27 | `notifications.mark_all_read` | POST | `Authorization`, `X-Company` | `src/api/notifications.js` (`notificationsService.markAllRead`) | `src/pages/Notifications.jsx` | Marks all notifications as read for the current user and clears the badge. |

---

## 4. End-to-End User Testing Guide

Follow these testing scenarios to verify the system end-to-end:

### Scenario 1: Fresh Account Login & Company Setup
1. Go to `http://localhost:5173/login`.
2. Sign in with:
   - **Email:** `alice.test@portal.dev`
   - **Password:** `Test@1234`
3. Notice that no 2FA prompt appears.
4. Because Alice has no company yet, the portal automatically routes to `http://localhost:5173/setup`.
5. Enter:
   - **Company name:** `Alice Tech Ltd`
   - **Business type:** `Limited Company`
   - **Company number:** `12345678`
   - **VAT number:** `GB 123 4567 89`
   - **Address:** `12 Innovation Way, London`
6. Click **Create company**.
7. You land on the Dashboard. Notice:
   - All 6 KPI cards show `0`.
   - Sidebar badges for **Queries** and **Requests** are hidden (clean zero state).
   - Top bar notification bell has no badge.

### Scenario 2: Helpdesk Queries & Dynamic Sidebar Badge
1. Go to **Queries** in the sidebar (or navigate to `http://localhost:5173/portal/queries`).
2. Click **New Query**.
3. Enter:
   - **Subject:** `VAT Registration Schedule`
   - **Category:** `Tax & Compliance`
   - **Message:** `When should we submit our first quarterly return?`
4. Click **Submit Query**.
5. Notice:
   - The query appears in the Queries list.
   - The **Queries** sidebar link immediately displays badge **`1`**.
   - Click on the query to view `QueryDetail`: the thread loads from SQLite, showing Alice's message and status `Open`.
   - Type a reply in the thread (e.g. `Please confirm accountant details`) and click **Send Reply**. The message is appended live.

### Scenario 3: Document Uploads & My Submissions
1. In the sidebar, expand **Upload documents** -> click **Upload files** (`/portal/upload`).
2. Drop or select a file (e.g. `receipt.pdf` or any image/text file).
3. Select Period (e.g. `Oct 2026`) and Category (`VAT Receipts`).
4. Click **Upload & Submit**.
5. Once complete, navigate to **My submissions** (`/portal/submissions`).
6. You will see the new submission listed with reference `DOC-2026-000001`, status `Submitted`, and submitted by Alice.
7. Return to the **Dashboard**: The **Submitted** KPI card now reflects `1`.

### Scenario 4: Internal Delegation Tasks
1. Go to **Tasks** (`/portal/tasks`).
2. Notice the board starts completely empty (no hardcoded demo tasks).
3. Click **New Task**:
   - Title: `Review March bank reconciliations`
   - Due Date: Pick a date next week.
4. Click **Create Task**:
   - It appears in the **To Do** column.
   - Click **Start Task**: It moves to **In Progress**.
   - Click **Mark as Done**: It moves to **Done**.

### Scenario 5: Multi-Tenant Data Isolation (Alice vs. Bob)
1. Open an Incognito window (or log out) and go to `http://localhost:5173/login`.
2. Sign in as Bob:
   - **Email:** `bob.test@portal.dev`
   - **Password:** `Test@1234`
3. Notice:
   - Bob is immediately prompted to set up his own company because **he has 0 access to Alice's company**.
   - Create Bob's company: `Bob Freight Ltd`.
   - Bob's dashboard shows all `0`s.
   - Bob's **Queries** page is completely empty (Alice's VAT query is invisible to Bob).
   - Bob's **Submissions** page is completely empty.
4. Try adding a query as Bob (`Freight invoice query`). Bob sees his 1 query, and Alice only sees her 1 query.

---

## 5. Development Cheat Sheet

### Resetting Database for Fresh Testing
To reset `dev.db` back to zero companies and clean demo users:
```powershell
python "C:\Users\vikas\.gemini\antigravity-ide\brain\272dd772-914b-4f02-b04f-07c100bea4d1\scratch\reset_db.py"
```

### Checking Running Ports (Windows PowerShell)
```powershell
Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue | Select-Object LocalPort, OwningProcess, State
```

### Update: Document Upload Streamlining & Transaction Date Selection (Oct 14, 2026)
- **Eliminated Redundant Upload Files Page**:
  - Removed confusing `/portal/upload` page and its 4 redirect cards.
  - Redirected `/portal/upload` -> `/portal/expenses` via react-router `Navigate`.
  - Streamlined Sidebar navigation to strictly the 3 actual document categories:
    1. **Expenses** (`/portal/expenses`)
    2. **Purchase Invoices** (`/portal/invoices`)
    3. **Bank Statements** (`/portal/bookkeeping`)
- **Transaction Date Picker Across All 3 Upload Screens**:
  - Added dedicated `<input type="date">` picker defaulting to today's date (editable) with 'Today' quick button.
  - Automatically synchronizes the accounting reporting period (e.g. `Oct 2026`) from the selected date.
  - Kept the `PeriodSelector` card in all 3 screens for optional custom month or quarterly reporting periods.
  - Updated API payloads and backend `run_dev.py` to store and return the document date.
  - Updated Submissions table and CSV export to display the chosen transaction date.
