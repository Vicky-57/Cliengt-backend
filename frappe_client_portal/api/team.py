import frappe
from frappe import _
from frappe_client_portal.permissions import get_user_client_company

@frappe.whitelist()
def get_team_members():
    """Lists all client team members and their roles."""
    company = get_user_client_company()
    if not company:
        frappe.throw(_("Not permitted"))
        
    members = frappe.get_all(
        "Client User Link",
        filters={"client_company": company},
        fields=["name", "user", "portal_role", "status", "creation"]
    )
    
    # Fetch names and emails
    for m in members:
        user_info = frappe.db.get_value("User", m.user, ["first_name", "last_name", "last_login"], as_dict=True)
        if user_info:
            m["name_display"] = f"{user_info.first_name or ''} {user_info.last_name or ''}".strip() or m.user
            m["last_login"] = user_info.last_login
            
    return {"status": "success", "data": members}

@frappe.whitelist()
def toggle_team_member_status(user_link_id, status):
    """Enables or disables sub-user access. Disabling revokes active sessions immediately."""
    link = frappe.get_doc("Client User Link", user_link_id)
    company = get_user_client_company()
    if company and link.client_company != company:
        frappe.throw(_("Not permitted"), frappe.PermissionError)
        
    if link.portal_role == "Owner":
        frappe.throw(_("Cannot disable the company Owner"))
        
    link.status = status
    link.save()
    
    if status == "Disabled":
        # Immediate session kill
        frappe.db.delete("Sessions", {"user": link.user})
        
    return {"status": "success", "message": f"User status set to {status}"}

def on_user_link_update(doc, method):
    if doc.status == "Disabled":
        frappe.db.delete("Sessions", {"user": doc.user})
