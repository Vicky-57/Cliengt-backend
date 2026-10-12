import frappe
import json
import hashlib
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
    return {"status": "success", "data": submissions, "total": total}

@frappe.whitelist()
def get_submission_detail(reference):
    """Returns complete submission record with child items and audit history."""
    doc = frappe.get_doc("Client Submission", reference)
    company = get_user_client_company()
    if company and doc.company != company:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    # Also fetch linked staff requests
    staff_requests = frappe.get_all(
        "Staff Request",
        filters={"submission": reference},
        fields=["name", "title", "message", "status", "is_urgent", "due_date", "client_reply", "creation"]
    )
    
    res = doc.as_dict()
    res["staff_requests"] = staff_requests
    return {"status": "success", "data": res}

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
    _log_activity("Submit Expense Claim", "Client Submission", doc.name)
    return {"status": "success", "reference": doc.name}

@frappe.whitelist()
def submit_sales_invoice(customer, invoice_number, issue_date, due_date, net_amount, vat_amount, period, notes="", attachment=None):
    """Submits a sales invoice record with attached PDF."""
    company = get_user_client_company()
    if not company:
        frappe.throw(_("No client company linked to user"))
        
    net = float(net_amount or 0.0)
    vat = float(vat_amount or 0.0)
    
    items = [{
        "date": issue_date,
        "supplier_customer": customer,
        "description": f"Invoice #{invoice_number} (Due: {due_date})",
        "category": "Sales",
        "net_amount": net,
        "vat_amount": vat,
        "total_amount": net + vat,
        "receipt_file": attachment
    }]
    
    doc = frappe.get_doc({
        "doctype": "Client Submission",
        "company": company,
        "submission_type": "Sales Invoice",
        "status": "Submitted",
        "period": period,
        "submitted_by": frappe.session.user,
        "notes": notes,
        "items": items
    })
    doc.insert()
    _log_activity("Submit Sales Invoice", "Client Submission", doc.name)
    return {"status": "success", "reference": doc.name}

@frappe.whitelist()
def submit_payroll(period, entries=None, notes=""):
    """Submits monthly payroll hours, starters, and leavers."""
    company = get_user_client_company()
    if not company:
        frappe.throw(_("No client company linked to user"))
        
    if isinstance(entries, str):
        entries = json.loads(entries)
        
    sub = frappe.get_doc({
        "doctype": "Client Submission",
        "company": company,
        "submission_type": "Payroll Input",
        "status": "Submitted",
        "period": period,
        "submitted_by": frappe.session.user,
        "notes": notes
    })
    sub.insert()
    
    for e in (entries or []):
        entry_doc = frappe.get_doc({
            "doctype": "Client Payroll Entry",
            "submission": sub.name,
            "company": company,
            "entry_type": e.get("type", "Monthly Hours"),
            "employee_name": e.get("name"),
            "employee_id": e.get("employee_id"),
            "hours_worked": float(e.get("hours", 0) or 0),
            "overtime_hours": float(e.get("overtime", 0) or 0),
            "notes": e.get("notes")
        })
        entry_doc.insert()
        
    _log_activity("Submit Payroll Input", "Client Submission", sub.name)
    return {"status": "success", "reference": sub.name}

@frappe.whitelist()
def upload_documents(category, period, file_urls, notes=""):
    """Batch creates document submissions with duplicate checking."""
    company = get_user_client_company()
    if not company:
        frappe.throw(_("No client company linked to user"))
        
    if isinstance(file_urls, str):
        file_urls = json.loads(file_urls)
        
    items = []
    for f in file_urls:
        items.append({
            "description": f.get("name", "Document"),
            "category": category,
            "receipt_file": f.get("file_url")
        })
        
    sub = frappe.get_doc({
        "doctype": "Client Submission",
        "company": company,
        "submission_type": "Document",
        "status": "Submitted",
        "period": period,
        "submitted_by": frappe.session.user,
        "notes": notes,
        "items": items
    })
    sub.insert()
    _log_activity("Batch Upload Documents", "Client Submission", sub.name)
    return {"status": "success", "reference": sub.name}

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
    _log_activity("Withdraw Submission", "Client Submission", doc.name)
    return {"status": "success", "message": "Submission withdrawn"}

@frappe.whitelist()
def bulk_update_status(names, status):
    """Staff desk action to bulk update submission statuses."""
    if isinstance(names, str):
        names = json.loads(names)
    for n in names:
        sub = frappe.get_doc("Client Submission", n)
        sub.status = status
        sub.save()
    return {"status": "success"}

def on_submission_update(doc, method):
    """Audit log on status update."""
    pass

def _log_activity(action, doctype, name):
    try:
        frappe.get_doc({
            "doctype": "Client Activity Log",
            "user": frappe.session.user,
            "action": action,
            "reference_doctype": doctype,
            "reference_name": name,
            "ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else ""
        }).insert(ignore_permissions=True)
    except Exception:
        pass
