frappe.listview_settings['Client Submission'] = {
    add_fields: ["status", "company", "total_gross"],
    get_indicator: function(doc) {
        if (doc.status === "Processed") {
            return [__("Processed"), "green", "status,=,Processed"];
        } else if (doc.status === "In Review") {
            return [__("In Review"), "orange", "status,=,In Review"];
        } else if (doc.status === "Needs Info") {
            return [__("Needs Info"), "purple", "status,=,Needs Info"];
        } else if (doc.status === "Rejected") {
            return [__("Rejected"), "red", "status,=,Rejected"];
        } else {
            return [__("Submitted"), "blue", "status,=,Submitted"];
        }
    },
    onload: function(listview) {
        // Bulk Export to Sage 50
        listview.page.add_action_item(__('Export to Sage 50 (CSV)'), function() {
            const checked = listview.get_checked_items();
            if (checked.length === 0) {
                frappe.msgprint(__('Please select at least one submission to export.'));
                return;
            }
            const names = checked.map(d => d.name);
            frappe.call({
                method: 'frappe_client_portal.exports.sage.export_sage_50',
                args: { submission_names: names },
                callback: function(r) {
                    if (r.message) {
                        frappe.tools.downloadify(r.message, null, 'Sage50_Export_' + frappe.datetime.now_date() + '.csv');
                        frappe.show_alert({ message: __('Exported to Sage 50'), indicator: 'green' });
                    }
                }
            });
        });

        // Bulk Export to QuickBooks Online
        listview.page.add_action_item(__('Export to QuickBooks (CSV)'), function() {
            const checked = listview.get_checked_items();
            if (checked.length === 0) {
                frappe.msgprint(__('Please select at least one submission to export.'));
                return;
            }
            const names = checked.map(d => d.name);
            frappe.call({
                method: 'frappe_client_portal.exports.quickbooks.export_quickbooks',
                args: { submission_names: names },
                callback: function(r) {
                    if (r.message) {
                        frappe.tools.downloadify(r.message, null, 'QuickBooks_Export_' + frappe.datetime.now_date() + '.csv');
                        frappe.show_alert({ message: __('Exported to QuickBooks'), indicator: 'green' });
                    }
                }
            });
        });

        // Bulk Mark as Processed
        listview.page.add_action_item(__('Mark as Processed'), function() {
            const checked = listview.get_checked_items();
            if (checked.length === 0) return;
            frappe.confirm(__('Mark ' + checked.length + ' submissions as Processed?'), function() {
                const names = checked.map(d => d.name);
                frappe.call({
                    method: 'frappe_client_portal.api.submissions.bulk_update_status',
                    args: { names: names, status: 'Processed' },
                    callback: function() {
                        listview.refresh();
                        frappe.show_alert({ message: __('Updated to Processed'), indicator: 'green' });
                    }
                });
            });
        });
    }
};
