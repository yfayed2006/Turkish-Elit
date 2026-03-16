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

    base_uom_id = fields.Many2one(
        "uom.uom",
        string="Base UoM",
        readonly=True,
    )

    scanned_uom_id = fields.Many2one(
        "uom.uom",
        string="Count As UoM",
    )

    detected_scan_type = fields.Char(
        string="Detected Source",
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

    @api.onchange("barcode", "quantity", "scanned_uom_id", "visit_id")
    def _onchange_barcode_preview(self):
        for rec in self:
            rec.detected_product_id = False
            rec.base_uom_id = False
            rec.detected_scan_type = False
            rec.counted_increase = 0.0

            if not rec.visit_id or not rec.barcode or not rec.barcode.strip():
                rec.scanned_uom_id = False
                continue

            try:
                scan_info = rec.visit_id._resolve_scanned_barcode(rec.barcode)
            except UserError:
                rec.scanned_uom_id = False
                continue

            product = scan_info["product"]
            rec.detected_product_id = product.id
            rec.base_uom_id = product.uom_id.id
            rec.detected_scan_type = scan_info["scan_type_label"]

            if not rec.scanned_uom_id:
                rec.scanned_uom_id = product.uom_id.id

            qty = rec.quantity if rec.quantity and rec.quantity > 0 else 0.0
            if qty and rec.scanned_uom_id:
                try:
                    rec.counted_increase = rec.scanned_uom_id._compute_quantity(qty, product.uom_id)
                except Exception:
                    rec.counted_increase = 0.0
            else:
                rec.counted_increase = 0.0

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
            scanned_uom=self.scanned_uom_id,
        )
        line = result["line"]
        product = result["product"]

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
                "default_detected_product_id": product.id,
                "default_base_uom_id": product.uom_id.id,
                "default_scanned_uom_id": product.uom_id.id,
                "default_detected_scan_type": False,
                "default_counted_increase": 0.0,
            },
        }

    def action_done(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}
