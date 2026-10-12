import frappe
from frappe.utils import today

def send_overdue_request_reminders():
    """Sends email reminders for pending staff requests approaching due date."""
    pending_requests = frappe.get_all(
        "Staff Request",
        filters={"status": "Pending", "due_date": ["<=", today()]},
        fields=["name", "title", "company", "due_date", "is_urgent"]
    )
    for req in pending_requests:
        # Fetch company email
        company_email = frappe.db.get_value("Client Company", req.company, "email")
        if company_email:
            frappe.sendmail(
                recipients=[company_email],
                subject=f"Action Required: {req.title}",
                message=f"<p>Hello,</p><p>You have an outstanding request from your accountant: <b>{req.title}</b>.</p><p>Please log in to your portal to respond.</p>"
            )

def check_statutory_deadlines():
    """Checks statutory deadlines and updates client task alerts."""
    pass
