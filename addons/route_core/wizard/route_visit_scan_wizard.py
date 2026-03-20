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

    scan_mode = fields.Selection(
        [
            ("count", "Count"),
            ("return", "Return"),
        ],
        string="Scan Mode",
        default="count",
        required=True,
        readonly=True,
    )

    barcode = fields.Char(string="Barcode")
    quantity = fields.Float(string="Quantity", default=1.0)

    expiry_date = fields.Date(string="Expiry Date")

    expiry_days_left = fields.Integer(
        string="Days Left",
        compute="_compute_expiry_preview",
        store=False,
    )

    is_near_expiry = fields.Boolean(
        string="Near Expiry",
        compute="_compute_expiry_preview",
        store=False,
    )

    add_to_near_expiry_return = fields.Boolean(
        string="Add This Quantity to Near Expiry Return",
        default=False,
        help="When enabled in Count mode, the counted quantity will also be added to return qty with route Near Expiry.",
    )

    return_route = fields.Selection(
        [
            ("vehicle", "To Vehicle"),
            ("damaged", "To Damaged Stock"),
            ("near_expiry", "To Near Expiry Stock"),
        ],
        string="Return Route",
        default="vehicle",
    )

    detected_product_id = fields.Many2one(
        "product.product",
        string="Detected Product",
        readonly=True,
    )

    detected_lot_id = fields.Many2one(
        "stock.lot",
        string="Detected Lot / Serial",
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

    @api.depends("expiry_date", "visit_id.date", "visit_id.near_expiry_threshold_days")
    def _compute_expiry_preview(self):
        for rec in self:
            rec.expiry_days_left = 0
            rec.is_near_expiry = False

            if not rec.expiry_date:
                continue

            reference_date = rec.visit_id.date or fields.Date.context_today(rec)
            delta_days = (rec.expiry_date - reference_date).days
            rec.expiry_days_left = delta_days
            rec.is_near_expiry = delta_days <= (rec.visit_id.near_expiry_threshold_days or 0)

    @api.onchange("expiry_date")
    def _onchange_expiry_date_default_near_expiry(self):
        for rec in self:
            if rec.scan_mode != "count":
                rec.add_to_near_expiry_return = False
                continue
            rec.add_to_near_expiry_return = bool(rec.is_near_expiry)

    @api.onchange("barcode", "visit_id")
    def _onchange_barcode_detection(self):
        for rec in self:
            rec.detected_product_id = False
            rec.detected_lot_id = False
            rec.base_uom_id = False
            rec.detected_scan_type = False
            rec.counted_increase = 0.0

            if not rec.visit_id or not rec.barcode or not rec.barcode.strip():
                rec.scanned_uom_id = False
                rec.expiry_date = False
                rec.add_to_near_expiry_return = False
                continue

            try:
                scan_info = rec.visit_id._resolve_scanned_barcode(rec.barcode)
            except UserError:
                rec.scanned_uom_id = False
                rec.expiry_date = False
                rec.add_to_near_expiry_return = False
                continue

            product = scan_info["product"]
            rec.detected_product_id = product.id
            rec.detected_lot_id = scan_info.get("lot") and scan_info["lot"].id or False
            rec.base_uom_id = product.uom_id.id
            rec.detected_scan_type = scan_info["scan_type_label"]

            if not rec.scanned_uom_id:
                rec.scanned_uom_id = product.uom_id.id

            # Phase C1:
            # If we resolved a real lot/serial with expiry, auto-fill expiry.
            # If scan is only product barcode, keep expiry empty and allow fallback.
            if rec.scan_mode == "count":
                rec.expiry_date = scan_info.get("expiry_date") or False
                rec.add_to_near_expiry_return = bool(rec.expiry_date and rec.is_near_expiry)

    @api.onchange("quantity", "scanned_uom_id", "detected_product_id")
    def _onchange_quantity_preview(self):
        for rec in self:
            rec.counted_increase = 0.0

            product = rec.detected_product_id
            if not product:
                continue

            qty = rec.quantity if rec.quantity and rec.quantity > 0 else 0.0
            used_uom = rec.scanned_uom_id or product.uom_id

            if qty and used_uom:
                try:
                    rec.counted_increase = used_uom._compute_quantity(qty, product.uom_id)
                except Exception:
                    rec.counted_increase = 0.0

    def _get_or_create_visit_line(self, product):
        self.ensure_one()

        line = self.visit_id.line_ids.filtered(lambda l: l.product_id == product)[:1]
        if line:
            return line

        return self.env["route.visit.line"].create({
            "visit_id": self.visit_id.id,
            "company_id": self.visit_id.company_id.id,
            "product_id": product.id,
            "unit_price": product.lst_price or 0.0,
        })

    def action_scan_and_add(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("Visit is required."))
        if not self.barcode or not self.barcode.strip():
            raise UserError(_("Please enter or scan a barcode first."))
        if self.quantity <= 0:
            raise UserError(_("Quantity must be greater than zero."))

        if self.scan_mode == "count":
            result = self.visit_id._process_scanned_barcode(
                self.barcode,
                scan_qty=self.quantity,
                scanned_uom=self.scanned_uom_id,
            )
            line = result["line"]
            product = result["product"]

            effective_expiry_date = self.expiry_date or result.get("expiry_date")

            line_vals = {}
            if effective_expiry_date:
                line_vals["expiry_date"] = effective_expiry_date
                line_vals["suggest_near_expiry_return"] = self.is_near_expiry

            if self.add_to_near_expiry_return:
                line_vals["return_qty"] = (line.return_qty or 0.0) + (result["counted_increase"] or 0.0)
                line_vals["return_route"] = "near_expiry"
                line_vals["suggest_near_expiry_return"] = False

            if line_vals:
                line.write(line_vals)
                line.invalidate_recordset()

            return {
                "type": "ir.actions.act_window",
                "name": _("Scan Barcode"),
                "res_model": "route.visit.scan.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_visit_id": self.visit_id.id,
                    "default_scan_mode": "count",
                    "default_quantity": 1.0,
                    "default_expiry_date": False,
                    "default_add_to_near_expiry_return": False,
                    "default_last_product_id": line.product_id.id,
                    "default_last_counted_qty": line.counted_qty,
                    "default_last_return_qty": 0.0,
                    "default_last_return_route": False,
                    "default_detected_product_id": product.id,
                    "default_detected_lot_id": result.get("lot") and result["lot"].id or False,
                    "default_base_uom_id": product.uom_id.id,
                    "default_scanned_uom_id": product.uom_id.id,
                    "default_detected_scan_type": result.get("scan_type_label"),
                    "default_counted_increase": 0.0,
                },
            }

        if self.scan_mode == "return":
            scan_info = self.visit_id._resolve_scanned_barcode(self.barcode)
            product = scan_info["product"]

            if not self.scanned_uom_id:
                scanned_uom = product.uom_id
            else:
                scanned_uom = self.scanned_uom_id

            try:
                return_increase = scanned_uom._compute_quantity(self.quantity, product.uom_id)
            except Exception:
                raise UserError(_("Could not convert the entered quantity to the product base unit."))

            if return_increase <= 0:
                raise UserError(_("Return quantity must be greater than zero."))

            line = self._get_or_create_visit_line(product)

            line.write({
                "return_qty": (line.return_qty or 0.0) + return_increase,
                "return_route": self.return_route or "vehicle",
            })

            return {
                "type": "ir.actions.act_window",
                "name": _("Scan Returns"),
                "res_model": "route.visit.scan.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_visit_id": self.visit_id.id,
                    "default_scan_mode": "return",
                    "default_quantity": 1.0,
                    "default_return_route": self.return_route or "vehicle",
                    "default_last_product_id": line.product_id.id,
                    "default_last_counted_qty": line.counted_qty,
                    "default_last_return_qty": line.return_qty,
                    "default_last_return_route": line.return_route,
                    "default_detected_product_id": product.id,
                    "default_detected_lot_id": scan_info.get("lot") and scan_info["lot"].id or False,
                    "default_base_uom_id": product.uom_id.id,
                    "default_scanned_uom_id": product.uom_id.id,
                    "default_detected_scan_type": scan_info.get("scan_type_label"),
                    "default_counted_increase": 0.0,
                },
            }

        raise UserError(_("Unsupported scan mode."))

    def action_done(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.visit_id.id,
            "view_mode": "form",
            "target": "current",
        }
