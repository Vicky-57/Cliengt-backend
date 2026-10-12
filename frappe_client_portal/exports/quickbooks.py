import frappe
import csv
import io

@frappe.whitelist()
def export_quickbooks(submission_names):
    """Generates QuickBooks Online Batch CSV format."""
    if isinstance(submission_names, str):
        import json
        submission_names = json.loads(submission_names)
        
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Date", "Transaction Type", "No.", "Payee", "Account", "Description", "Amount", "VAT Code", "VAT Amount"])
    
    for sub_name in submission_names:
        sub = frappe.get_doc("Client Submission", sub_name)
        for item in sub.get("items", []):
            writer.writerow([
                item.date or sub.creation.strftime("%Y-%m-%d"),
                "Expense",
                sub.name,
                item.supplier_customer or "",
                item.category or "General Expense",
                item.description or "",
                f"{item.total_amount:.2f}",
                "20.0% S" if item.vat_rate == 20 else "0.0% Z",
                f"{item.vat_amount:.2f}"
            ])
            
    return output.getvalue()
