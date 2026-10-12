import frappe
from frappe import _
from frappe.auth import LoginManager
from frappe_client_portal.permissions import get_user_client_company

@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    """Standard Frappe login with session cookie."""
    try:
        login_manager = LoginManager()
        login_manager.authenticate(usr, pwd)
        login_manager.post_login()
        
        # Check if user belongs to an active client company
        company = get_user_client_company(usr)
        user_link = frappe.db.get_value("Client User Link", {"user": usr}, ["portal_role", "status"], as_dict=True)
        
        if user_link and user_link.status == "Disabled":
            frappe.local.login_manager.logout()
            frappe.throw(_("Your account has been deactivated. Please contact your company administrator."), frappe.AuthenticationError)
            
        return {
            "status": "success",
            "message": "Logged In",
            "user": usr,
            "company": company,
            "role": user_link.portal_role if user_link else "Staff"
        }
    except frappe.AuthenticationError:
        frappe.local.response["http_status_code"] = 401
        return {"status": "error", "message": "Invalid email or password"}
    except Exception as e:
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def logout():
    """Terminates user session."""
    frappe.local.login_manager.logout()
    return {"status": "success", "message": "Logged Out"}

@frappe.whitelist()
def get_current_user():
    """Returns active session user info, company details, and portal role."""
    if frappe.session.user == "Guest":
        frappe.local.response["http_status_code"] = 401
        return {"status": "error", "message": "Session expired"}
        
    user = frappe.session.user
    user_doc = frappe.get_doc("User", user)
    company_name = get_user_client_company(user)
    
    company = None
    role = "Staff"
    
    if company_name:
        company = frappe.get_doc("Client Company", company_name).as_dict()
        user_link = frappe.db.get_value("Client User Link", {"user": user}, ["portal_role"], as_dict=True)
        if user_link:
            role = user_link.portal_role
            
    return {
        "status": "success",
        "data": {
            "user": {
                "email": user_doc.email,
                "first_name": user_doc.first_name,
                "last_name": user_doc.last_name,
                "full_name": user_doc.full_name
            },
            "company": company,
            "role": role
        }
    }
