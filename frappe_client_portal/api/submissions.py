import frappe
import json
from frappe import _
from frappe_client_portal.permissions import get_user_client_company

@frappe.whitelist()
def get_submissions(submission_type=None, status=None, period=None, search=None, start=0, page_length=20):
    """Returns filterable, paginated list of company submissions."""
    company = get_user_client_company()
    filters = {}
    if company:
        filters["company"] = company
    if submission_type:
        filters["submission_type"] = submission_type
    if status:
        filters["status"] = status
    if period:
        filters["period"] = period
        
    or_filters = []
    if search:
        or_filters = [
            ["Client Submission", "name", "like", f"%{search}%"],
            ["Client Submission", "notes", "like", f"%{search}%"]
        ]
        
    submissions = frappe.get_all(
        "Client Submission",
        filters=filters,
        or_filters=or_filters if or_filters else None,
        fields=["name", "submission_type", "status", "period", "submitted_by", "total_gross", "creation", "modified"],
        order_by="modified desc",
        start=int(start),
        page_length=int(page_length)
    )
    
    total = frappe.db.count("Client Submission", filters=filters)
    
    return {
        "status": "success",
        "data": submissions,
        "total": total
    }

@frappe.whitelist()
def get_submission_detail(reference):
    """Returns complete submission record with child items and audit history."""
    doc = frappe.get_doc("Client Submission", reference)
    company = get_user_client_company()
    
    if company and doc.company != company:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    return {
        "status": "success",
        "data": doc.as_dict()
    }

@frappe.whitelist()
def submit_expense_claim(period, notes="", items=None):
    """Submits a multi-line expense claim with VAT amounts and receipts."""
    company = get_user_client_company()
    if not company:
        frappe.throw(_("No client company linked to user"))
        
    if isinstance(items, str):
        items = json.loads(items)
        
    doc = frappe.get_doc({
        "doctype": "Client Submission",
        "company": company,
        "submission_type": "Expense Claim",
        "status": "Submitted",
        "period": period,
        "submitted_by": frappe.session.user,
        "notes": notes,
        "items": items or []
    })
    doc.insert()
    
    return {"status": "success", "reference": doc.name}

@frappe.whitelist()
def withdraw_submission(reference):
    """Allows client to cancel a pending submission before review begins."""
    doc = frappe.get_doc("Client Submission", reference)
    company = get_user_client_company()
    if company and doc.company != company:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    if doc.status not in ["Submitted", "Pending"]:
        frappe.throw(_("Cannot withdraw submission already in review or processed"))
        
    doc.status = "Rejected"
    doc.rejection_reason = "Withdrawn by client."
    doc.save()
    
    return {"status": "success", "message": "Submission withdrawn"}

def on_submission_update(doc, method):
    """Hook called when submission changes status."""
    pass
