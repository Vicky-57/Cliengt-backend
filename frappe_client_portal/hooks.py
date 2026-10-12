app_name = "frappe_client_portal"
app_title = "Client Portal"
app_publisher = "McKHTech"
app_description = "Frappe Client Portal App for Accounting Submissions, Helpdesk & CSV Exports"
app_email = "info@mckhtech.com"
app_license = "MIT"

# Document Event Hooks
doc_events = {
    "Client User Link": {
        "on_update": "frappe_client_portal.api.team.on_user_link_update"
    },
    "Client Submission": {
        "on_update": "frappe_client_portal.api.submissions.on_submission_update"
    },
    "File": {
        "has_permission": "frappe_client_portal.permissions.has_file_permission"
    }
}

# Permission Query Conditions (Multi-Tenant Company Segregation)
permission_query_conditions = {
    "Client Submission": "frappe_client_portal.permissions.get_company_permission_query",
    "Staff Request": "frappe_client_portal.permissions.get_company_permission_query",
    "Client Task": "frappe_client_portal.permissions.get_company_permission_query",
    "Client Activity Log": "frappe_client_portal.permissions.get_company_permission_query",
    "Client Payroll Entry": "frappe_client_portal.permissions.get_company_permission_query"
}

# Document Level Permissions
has_permission = {
    "Client Submission": "frappe_client_portal.permissions.has_company_permission",
    "Staff Request": "frappe_client_portal.permissions.has_company_permission",
    "Client Task": "frappe_client_portal.permissions.has_company_permission"
}

# Scheduled Tasks (Cron Jobs)
scheduler_events = {
    "daily": [
        "frappe_client_portal.tasks.send_overdue_request_reminders",
        "frappe_client_portal.tasks.check_statutory_deadlines"
    ]
}
