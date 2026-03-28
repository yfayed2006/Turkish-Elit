from odoo import _, fields, models
from odoo.exceptions import UserError


class RouteVehicleClosingScanWizard(models.TransientModel):
    _name = "route.vehicle.closing.scan.wizard"
    _description = "Route Vehicle Closing Scan Wizard"

    closing_id = fields.Many2one("route.vehicle.closing", string="Vehicle Closing", required=True, readonly=True)
    product_barcode = fields.Char(string="Scan Product Barcode")
    lot_code = fields.Char(string="Scan Lot Code")
    quantity = fields.Float(string="Quantity", default=1.0)
    last_line_id = fields.Many2one("route.vehicle.closing.line", string="Last Updated Line", readonly=True)
    last_product_id = fields.Many2one("product.product", string="Last Product", readonly=True)
    last_lot_id = fields.Many2one("stock.lot", string="Last Lot", readonly=True)
    last_qty = fields.Float(string="Last Added Qty", readonly=True)
    message = fields.Char(string="Message", readonly=True)

    def _resolve_line(self):
        self.ensure_one()
        lines = self.closing_id.line_ids
        lot_code = (self.lot_code or "").strip()
        product_code = (self.product_barcode or "").strip()

        if lot_code:
            lot_line = lines.filtered(lambda l: l.lot_id and ((l.lot_id.name or '').strip().lower() == lot_code.lower()))[:1]
            if lot_line:
                return lot_line
            raise UserError(_("Scanned lot code '%s' was not found in the vehicle closing lines.") % lot_code)

        if not product_code:
            raise UserError(_("Please scan a product barcode or a lot code first."))

        product_lines = lines.filtered(lambda l: l.product_id and ((l.product_id.barcode or '').strip() == product_code))
        if not product_lines:
            raise UserError(_("Scanned product barcode '%s' was not found in the vehicle closing lines.") % product_code)
        if len(product_lines) > 1:
            raise UserError(_("This barcode exists on multiple lots. Please use the Lot Code field to scan the specific lot."))
        return product_lines[:1]

    def action_scan_add(self):
        self.ensure_one()
        if self.closing_id.state != 'draft':
            raise UserError(_("You can scan only while the vehicle closing is in draft."))
        if not self.closing_id.count_started_datetime:
            raise UserError(_("Please start the count first."))
        if self.quantity <= 0:
            raise UserError(_("Quantity must be greater than zero."))
        line = self._resolve_line()
        line.counted_qty = (line.counted_qty or 0.0) + self.quantity
        self.last_line_id = line
        self.last_product_id = line.product_id
        self.last_lot_id = line.lot_id
        self.last_qty = self.quantity
        self.message = _("Added %(qty).2f to %(product)s") % {
            'qty': self.quantity,
            'product': line.product_id.display_name,
        }
        self.product_barcode = False
        self.lot_code = False
        self.quantity = 1.0
        self.closing_id.count_done = False
        self.closing_id.count_done_datetime = False
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
        self.closing_id.action_mark_count_done()
        return self.closing_id._open_form_action()
