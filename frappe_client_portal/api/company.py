import frappe
from frappe import _
from frappe_client_portal.permissions import get_user_client_company

@frappe.whitelist()
def get_company_profile():
    """Returns company profile with masked bank account."""
    company = get_user_client_company()
    if not company:
        frappe.throw(_("Not permitted"))
        
    doc = frappe.get_doc("Client Company", company)
    data = doc.as_dict()
    
    # Bank masking
    if data.get("account_number"):
        data["account_number_masked"] = "•••• " + data["account_number"][-4:]
    if data.get("sort_code"):
        data["sort_code_masked"] = "•••• " + data["sort_code"][-2:]
        
    return {"status": "success", "data": data}

@frappe.whitelist()
def update_company_profile(data):
    """Updates company contact and address details."""
    company = get_user_client_company()
    if not company:
        frappe.throw(_("Not permitted"))
        
    doc = frappe.get_doc("Client Company", company)
    
    allowed_fields = ["email", "phone", "registered_address", "trading_address", "vat_number", "company_number"]
    for field in allowed_fields:
        if field in data:
            doc.set(field, data[field])
            
    doc.save()
    return {"status": "success", "message": "Company profile updated"}
