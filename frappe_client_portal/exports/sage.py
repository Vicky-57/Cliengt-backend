import frappe
import csv
import io

@frappe.whitelist()
def export_sage_50(submission_names):
    """Generates Sage 50 Audit Trail CSV format for selected submissions."""
    if isinstance(submission_names, str):
        import json
        submission_names = json.loads(submission_names)
        
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Sage 50 Header
    writer.writerow(["Type", "Account Ref", "Nominal Code", "Date", "Reference", "Details", "Net", "Tax Code", "Tax Amount"])
    
    for sub_name in submission_names:
        sub = frappe.get_doc("Client Submission", sub_name)
        for item in sub.get("items", []):
            tax_code = "T1" if item.vat_rate == 20 else ("T5" if item.vat_rate == 5 else "T0")
            writer.writerow([
                "PI",  # Purchase Invoice
                item.supplier_customer or "EXPENSE",
                "7500", # Default Nominal Code
                item.date or sub.creation.strftime("%d/%m/%Y"),
                sub.name,
                item.description or item.category,
                f"{item.net_amount:.2f}",
                tax_code,
                f"{item.vat_amount:.2f}"
            ])
            
    return output.getvalue()
