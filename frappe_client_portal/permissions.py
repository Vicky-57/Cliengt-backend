import frappe

def get_user_client_company(user=None):
    """Helper to fetch the linked Client Company for a given user."""
    if not user:
        user = frappe.session.user
    
    # Staff / System Managers have access across all clients
    if "System Manager" in frappe.get_roles(user) or "Client Portal Staff" in frappe.get_roles(user):
        return None
    
    user_link = frappe.db.get_value(
        "Client User Link", 
        {"user": user, "status": "Active"}, 
        ["client_company", "portal_role"], 
        as_dict=True
    )
    return user_link.client_company if user_link else None

def get_company_permission_query(user):
    """SQL condition injected into frappe.get_list queries to enforce company isolation."""
    company = get_user_client_company(user)
    if not company:
        # None means user is staff or admin - no company filter needed
        return ""
    
    # Escape and return SQL condition
    escaped_company = frappe.db.escape(company)
    return f"`tabClient Submission`.`company` = {escaped_company}"

def has_company_permission(doc, user=None, permission_type=None):
    """Validates document-level permission based on linked company."""
    if not user:
        user = frappe.session.user
        
    if "System Manager" in frappe.get_roles(user) or "Client Portal Staff" in frappe.get_roles(user):
        return True
        
    company = get_user_client_company(user)
    if not company:
        return False
        
    doc_company = getattr(doc, "company", None)
    return doc_company == company

def has_file_permission(doc, user=None, permission_type=None):
    """Validates permission before downloading private files."""
    if not user:
        user = frappe.session.user
        
    if "System Manager" in frappe.get_roles(user) or "Client Portal Staff" in frappe.get_roles(user):
        return True
        
    company = get_user_client_company(user)
    if not company:
        return False
        
    # Check attached document company
    if doc.attached_to_doctype and doc.attached_to_name:
        try:
            attached_doc = frappe.get_doc(doc.attached_to_doctype, doc.attached_to_name)
            doc_company = getattr(attached_doc, "company", None)
            if doc_company:
                return doc_company == company
        except Exception:
            return False
            
    return True
