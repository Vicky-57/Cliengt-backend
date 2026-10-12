import frappe
from frappe_client_portal.permissions import get_user_client_company

@frappe.whitelist()
def get_dashboard_summary():
    """Returns aggregate KPI counts, urgent requests, and upcoming deadlines."""
    company = get_user_client_company()
    filters = {"company": company} if company else {}
    
    # Counts by status
    statuses = ["Submitted", "Received", "In Review", "Needs Info", "Processed", "Rejected"]
    counts = {}
    for st in statuses:
        st_filters = dict(filters)
        st_filters["status"] = st
        counts[st.lower().replace(" ", "_")] = frappe.db.count("Client Submission", st_filters)
        
    # Outstanding Needs Info requests
    req_filters = {"status": "Pending"}
    if company:
        req_filters["company"] = company
        
    urgent_requests = frappe.get_all(
        "Staff Request",
        filters=req_filters,
        fields=["name", "title", "submission", "due_date", "is_urgent", "message"],
        order_by="is_urgent desc, due_date asc",
        limit=5
    )
    
    # Upcoming tasks/deadlines
    task_filters = {"status": ["!=", "Done"]}
    if company:
        task_filters["company"] = company
        
    upcoming_tasks = frappe.get_all(
        "Client Task",
        filters=task_filters,
        fields=["name", "title", "due_date", "priority", "status", "assigned_to"],
        order_by="due_date asc",
        limit=5
    )
    
    return {
        "status": "success",
        "data": {
            "counts": counts,
            "urgent_requests": urgent_requests,
            "upcoming_tasks": upcoming_tasks
        }
    }
