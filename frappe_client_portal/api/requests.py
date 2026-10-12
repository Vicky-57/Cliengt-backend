import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe_client_portal.permissions import get_user_client_company

@frappe.whitelist()
def get_requests(status="Pending"):
    """Lists staff 'Needs Info' requests for company."""
    company = get_user_client_company()
    filters = {"status": status}
    if company:
        filters["company"] = company
        
    requests = frappe.get_all(
        "Staff Request",
        filters=filters,
        fields=["name", "submission", "title", "message", "due_date", "is_urgent", "status", "client_reply", "creation"],
        order_by="is_urgent desc, due_date asc"
    )
    return {"status": "success", "data": requests}

@frappe.whitelist()
def create_staff_request(submission, company, title, message, due_date=None, is_urgent=0):
    """Staff Desk action to request more information from client."""
    req = frappe.get_doc({
        "doctype": "Staff Request",
        "submission": submission,
        "company": company,
        "title": title,
        "message": message,
        "due_date": due_date,
        "is_urgent": int(is_urgent),
        "status": "Pending"
    })
    req.insert()
    
    # Update linked submission status to Needs Info
    sub = frappe.get_doc("Client Submission", submission)
    sub.status = "Needs Info"
    sub.rejection_reason = title
    sub.save()
    
    # Send email notification to client company
    company_email = frappe.db.get_value("Client Company", company, "email")
    if company_email:
        frappe.sendmail(
            recipients=[company_email],
            subject=f"Accountant Request: {title}",
            message=f"<p>Your accountant has requested more information regarding submission <b>{submission}</b>:</p><p>{message}</p><p>Please log in to your portal to reply.</p>"
        )
        
    return {"status": "success", "name": req.name}

@frappe.whitelist()
def reply_request(request_id, reply_text, reply_attachment=None):
    """Resolves a staff request and moves linked submission back to 'In Review'."""
    req = frappe.get_doc("Staff Request", request_id)
    company = get_user_client_company()
    if company and req.company != company:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    req.client_reply = reply_text
    req.status = "Resolved"
    req.resolved_at = now_datetime()
    if reply_attachment:
        req.reply_attachment = reply_attachment
    req.save()
    
    # Update linked submission status back to In Review
    if req.submission:
        sub = frappe.get_doc("Client Submission", req.submission)
        if sub.status == "Needs Info":
            sub.status = "In Review"
            sub.save()
            
    return {"status": "success", "message": "Reply sent successfully"}
