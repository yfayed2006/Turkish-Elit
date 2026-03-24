from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisitReturnScanWizard(models.TransientModel):
    _name = "route.visit.return.scan.wizard"
    _description = "Route Visit Return Scan Wizard"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )

    barcode = fields.Char(string="Barcode")
    product_id = fields.Many2one(
        "product.product",
        string="Product",
    )
    quantity = fields.Float(
        string="Return Quantity",
        default=1.0,
    )

    return_route = fields.Selection(
        [
            ("vehicle", "To Vehicle"),
            ("damaged", "To Damaged Stock"),
            ("near_expiry", "To Near Expiry Stock"),
        ],
        string="Return Route",
        required=True,
        default="vehicle",
    )

    detected_product_id = fields.Many2one(
        "product.product",
        string="Detected Product",
        readonly=True,
    )

    last_product_id = fields.Many2one(
        "product.product",
        string="Last Product",
        readonly=True,
    )

    last_return_qty = fields.Float(
        string="Last Return Qty",
        readonly=True,
    )

    last_return_route = fields.Selection(
        [
            ("vehicle", "To Vehicle"),
            ("damaged", "To Damaged Stock"),
            ("near_expiry", "To Near Expiry Stock"),
        ],
        string="Last Return Route",
        readonly=True,
    )

    @api.onchange("barcode")
    def _onchange_barcode_preview(self):
        for rec in self:
            rec.detected_product_id = False
            if not rec.barcode or not rec.visit_id:
                continue
            try:
                scan_info = rec.visit_id._resolve_scanned_barcode(rec.barcode)
                rec.detected_product_id = scan_info["product"].id
            except Exception:
                rec.detected_product_id = False

    def _get_target_product(self):
        self.ensure_one()

        if self.barcode:
            try:
                scan_info = self.visit_id._resolve_scanned_barcode(self.barcode)
                return scan_info["product"]
            except Exception:
                pass

        if self.product_id:
            return self.product_id

        raise UserError(_("Please scan a barcode or select a product."))

    def action_apply_return(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("Visit is required."))

        if self.quantity <= 0:
            raise UserError(_("Return quantity must be greater than zero."))

        if self.return_route not in ("vehicle", "damaged", "near_expiry"):
            raise UserError(_("Please select a valid return route."))

        product = self._get_target_product()
        line = self.visit_id._add_return_qty(
            product,
            self.quantity,
            return_route=self.return_route,
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Additional Returns"),
            "res_model": "route.visit.return.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.visit_id.id,
                "default_quantity": 1.0,
                "default_return_route": self.return_route or "vehicle",
                "default_last_product_id": product.id,
                "default_last_return_qty": line.return_qty,
                "default_last_return_route": line.return_route,
            },
        }

    def action_done(self):
        self.ensure_one()

        if not any((line.return_qty or 0.0) > 0 for line in self.visit_id.line_ids):
            raise UserError(_("No additional returns were recorded. Use No Additional Returns if there are no extra returns."))

        self.visit_id.write({
            "has_returns_declared": any((line.return_qty or 0.0) > 0 for line in self.visit_id.line_ids),
            "returns_step_done": True,
        })
        return self.visit_id._action_reopen_visit_form()
