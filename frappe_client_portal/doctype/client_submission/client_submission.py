from frappe.model.document import Document

class ClientSubmission(Document):
    def validate(self):
        # Auto calculate financial totals from child items
        net = 0.0
        vat = 0.0
        for item in self.get("items", []):
            item_net = float(item.net_amount or 0.0)
            item_vat_rate = float(item.vat_rate or 0.0)
            item_vat = round(item_net * (item_vat_rate / 100.0), 2)
            item.vat_amount = item_vat
            item.total_amount = round(item_net + item_vat, 2)
            net += item_net
            vat += item_vat
            
        self.total_net = round(net, 2)
        self.total_vat = round(vat, 2)
        self.total_gross = round(net + vat, 2)
