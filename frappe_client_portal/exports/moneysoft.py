import frappe
import csv
import io

@frappe.whitelist()
def export_moneysoft(period):
    """Generates Moneysoft Payroll CSV import template."""
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["Employer Ref", "Employee ID", "Employee Name", "Period", "Basic Hours", "Overtime Hours", "Additions", "Notes"])
    
    entries = frappe.get_all(
        "Client Payroll Entry",
        filters={"company": ["!=", ""], "entry_type": ["in", ["Monthly Hours", "New Starter", "Leaver"]]},
        fields=["company", "employee_id", "employee_name", "hours_worked", "overtime_hours", "notes"]
    )
    
    for e in entries:
        writer.writerow([
            e.company,
            e.employee_id or "",
            e.employee_name,
            period,
            f"{e.hours_worked or 0:.2f}",
            f"{e.overtime_hours or 0:.2f}",
            "0.00",
            e.notes or ""
        ])
        
    return output.getvalue()
