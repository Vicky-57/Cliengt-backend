frappe.ui.form.on('Client Submission', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            // Button for Staff to create a Needs Info Request
            if (frm.doc.status !== "Processed") {
                frm.add_custom_button(__('Request More Info'), function() {
                    let d = new frappe.ui.Dialog({
                        title: __('Request Information from Client'),
                        fields: [
                            { fieldname: 'title', fieldtype: 'Data', label: __('Title / Subject'), reqd: 1 },
                            { fieldname: 'message', fieldtype: 'Long Text', label: __('Details / Missing Documents Required'), reqd: 1 },
                            { fieldname: 'due_date', fieldtype: 'Date', label: __('Due Date'), default: frappe.datetime.add_days(frappe.datetime.now_date(), 5) },
                            { fieldname: 'is_urgent', fieldtype: 'Check', label: __('Mark as Urgent'), default: 0 }
                        ],
                        primary_action_label: __('Send Request'),
                        primary_action: function(values) {
                            frappe.call({
                                method: 'frappe_client_portal.api.requests.create_staff_request',
                                args: {
                                    submission: frm.doc.name,
                                    company: frm.doc.company,
                                    title: values.title,
                                    message: values.message,
                                    due_date: values.due_date,
                                    is_urgent: values.is_urgent
                                },
                                callback: function() {
                                    d.hide();
                                    frm.reload_doc();
                                    frappe.show_alert({ message: __('Request sent to client'), indicator: 'orange' });
                                }
                            });
                        }
                    });
                    d.show();
                }, __('Actions'));
            }
        }
    }
});
