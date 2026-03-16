from odoo import api, fields, models, _
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
    )

    quantity = fields.Float(
        string="Quantity",
        default=1.0,
    )

    detected_product_id = fields.Many2one(
        "product.product",
        string="Detected Product",
        readonly=True,
    )

    detected_scan_type = fields.Char(
        string="Detected Type",
        readonly=True,
    )

    detected_factor = fields.Float(
        string="Units per Scan",
        readonly=True,
    )

    counted_increase = fields.Float(
        string="Count Increase",
        readonly=True,
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

    @api.onchange("barcode", "quantity", "visit_id")
    def _onchange_barcode_preview(self):
        for rec in self:
            rec.detected_product_id = False
            rec.detected_scan_type = False
            rec.detected_factor = 0.0
            rec.counted_increase = 0.0

            if not rec.visit_id or not rec.barcode or not rec.barcode.strip():
                continue

            try:
                scan_info = rec.visit_id._resolve_scanned_barcode(rec.barcode)
            except Exception:
                continue

            factor = scan_info["factor"] or 1.0
            qty = rec.quantity if rec.quantity and rec.quantity > 0 else 0.0

            rec.detected_product_id = scan_info["product"].id
            rec.detected_scan_type = scan_info["scan_type_label"]
            rec.detected_factor = factor
            rec.counted_increase = qty * factor

    def action_scan_and_add(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("Visit is required."))

        if not self.barcode or not self.barcode.strip():
            raise UserError(_("Please enter or scan a barcode first."))

        if self.quantity <= 0:
            raise UserError(_("Quantity must be greater than zero."))

        result = self.visit_id._process_scanned_barcode(
            self.barcode,
            scan_qty=self.quantity,
        )
        line = result["line"]

        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Barcode"),
            "res_model": "route.visit.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.visit_id.id,
                "default_quantity": 1.0,
                "default_last_product_id": line.product_id.id,
                "default_last_counted_qty": line.counted_qty,
                "default_detected_product_id": line.product_id.id,
                "default_detected_scan_type": False,
                "default_detected_factor": 0.0,
                "default_counted_increase": 0.0,
            },
        }

    def action_done(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}
