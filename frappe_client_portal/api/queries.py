import frappe
from frappe import _
from frappe_client_portal.permissions import get_user_client_company

@frappe.whitelist()
def get_queries():
    """Fetches Helpdesk tickets for client company."""
    company = get_user_client_company()
    # Check if Frappe Helpdesk app (HD Ticket) is installed
    if frappe.db.exists("DocType", "HD Ticket"):
        tickets = frappe.get_all(
            "HD Ticket",
            filters={"customer": company} if company else {},
            fields=["name", "subject", "status", "modified", "agent"],
            order_by="modified desc"
        )
        return {"status": "success", "data": tickets}
    return {"status": "success", "data": []}
