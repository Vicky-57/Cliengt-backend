import frappe

def after_install():
    """Setup custom roles automatically when app is installed on a bench site."""
    roles = [
        {"role_name": "Client Portal User", "desk_access": 0},
        {"role_name": "Client Portal Staff", "desk_access": 1}
    ]
    for r in roles:
        if not frappe.db.exists("Role", r["role_name"]):
            role = frappe.get_doc({
                "doctype": "Role",
                "role_name": r["role_name"],
                "desk_access": r["desk_access"]
            })
            role.insert(ignore_permissions=True)
            print(f"Created role: {r['role_name']}")
