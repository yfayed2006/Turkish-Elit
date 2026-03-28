from odoo import _, fields, models
from odoo.exceptions import UserError


class RouteVehicleClosingScanWizard(models.TransientModel):
    _name = "route.vehicle.closing.scan.wizard"
    _description = "Route Vehicle Closing Scan Wizard"

    closing_id = fields.Many2one("route.vehicle.closing", string="Vehicle Closing", required=True, readonly=True)
    barcode = fields.Char(string="Scan Product / Lot")
    quantity = fields.Float(string="Quantity", default=1.0)
    last_line_id = fields.Many2one("route.vehicle.closing.line", string="Last Updated Line", readonly=True)
    last_product_id = fields.Many2one("product.product", string="Last Product", readonly=True)
    last_lot_id = fields.Many2one("stock.lot", string="Last Lot", readonly=True)
    last_qty = fields.Float(string="Last Added Qty", readonly=True)
    message = fields.Char(string="Message", readonly=True)

    def _resolve_line(self, code):
        self.ensure_one()
        code = (code or "").strip()
        if not code:
            raise UserError(_("Please scan a product barcode or lot code first."))

        lines = self.closing_id.line_ids
        lot_line = lines.filtered(lambda l: l.lot_id and ((l.lot_id.name or '').strip().lower() == code.lower()))[:1]
        if lot_line:
            return lot_line

        product_lines = lines.filtered(lambda l: l.product_id and ((l.product_id.barcode or '').strip() == code))
        if not product_lines:
            raise UserError(_("Scanned code '%s' was not found in the vehicle closing lines.") % code)
        if len(product_lines) > 1:
            raise UserError(_("This barcode exists on multiple lots. Please scan the lot code instead."))
        return product_lines[:1]

    def action_scan_add(self):
        self.ensure_one()
        if self.closing_id.state != 'draft':
            raise UserError(_("You can scan only while the vehicle closing is in draft."))
        if not self.closing_id.count_started_datetime:
            raise UserError(_("Please start the count first."))
        if self.quantity <= 0:
            raise UserError(_("Quantity must be greater than zero."))
        line = self._resolve_line(self.barcode)
        line.counted_qty = (line.counted_qty or 0.0) + self.quantity
        self.last_line_id = line
        self.last_product_id = line.product_id
        self.last_lot_id = line.lot_id
        self.last_qty = self.quantity
        self.message = _("Added %(qty).2f to %(product)s") % {
            'qty': self.quantity,
            'product': line.product_id.display_name,
        }
        self.barcode = False
        self.quantity = 1.0
        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Vehicle Stock"),
            "res_model": "route.vehicle.closing.scan.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_done(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}
