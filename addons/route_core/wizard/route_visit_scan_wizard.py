from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisitScanWizard(models.TransientModel):
    _name = "route.visit.scan.wizard"
    _description = "Route Visit Scan Wizard"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )

    barcode = fields.Char(
        string="Barcode",
        required=True,
    )

    last_product_id = fields.Many2one(
        "product.product",
        string="Last Product",
        readonly=True,
    )

    last_counted_qty = fields.Float(
        string="Last Counted Qty",
        readonly=True,
    )

    def action_scan_and_add(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("Visit is required."))

        line = self.visit_id._process_scanned_barcode(self.barcode)

        self.write({
            "last_product_id": line.product_id.id,
            "last_counted_qty": line.counted_qty,
            "barcode": False,
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Barcode"),
            "res_model": "route.visit.scan.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }

    def action_done(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}
