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
    focus_target = fields.Selection(
        [
            ("lot", "Lot"),
            ("product", "Product"),
        ],
        string="Focus Target",
        default="lot",
        readonly=True,
    )

    lot_barcode = fields.Char(string="Scan Lot")
    active_lot_id = fields.Many2one(
        "stock.lot",
        string="Active Lot",
        readonly=True,
    )
    active_lot_product_id = fields.Many2one(
        "product.product",
        string="Lot Product",
        related="active_lot_id.product_id",
        readonly=True,
    )
    active_lot_expiry_date = fields.Date(
        string="Lot Expiry Date",
        compute="_compute_active_lot_state",
        store=False,
    )
    active_lot_days_left = fields.Integer(
        string="Lot Days Left",
        compute="_compute_active_lot_state",
        store=False,
    )
    active_lot_status = fields.Selection(
        [
            ("normal", "Normal"),
            ("near_expiry", "Near Expiry"),
            ("expired", "Expired"),
        ],
        string="Lot Status",
        compute="_compute_active_lot_state",
        store=False,
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

    detected_packaging_name = fields.Char(
        string="Detected Packaging",
        readonly=True,
    )
    auto_quantity_locked = fields.Boolean(
        string="Auto Quantity Locked",
        readonly=True,
        default=False,
    )
    auto_uom_locked = fields.Boolean(
        string="Auto UoM Locked",
        readonly=True,
        default=False,
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

    @api.depends("active_lot_id", "visit_id.date", "visit_id.near_expiry_threshold_days")
    def _compute_active_lot_state(self):
        for rec in self:
            rec.active_lot_expiry_date = False
            rec.active_lot_days_left = 0
            rec.active_lot_status = False

            if not rec.active_lot_id:
                continue

            expiry_date = rec.visit_id._get_lot_expiry_date(rec.active_lot_id)
            rec.active_lot_expiry_date = expiry_date

            if not expiry_date:
                rec.active_lot_status = "normal"
                continue

            reference_date = rec.visit_id.date or fields.Date.context_today(rec)
            delta_days = (expiry_date - reference_date).days
            rec.active_lot_days_left = delta_days

            if delta_days < 0:
                rec.active_lot_status = "expired"
            elif delta_days <= (rec.visit_id.near_expiry_threshold_days or 0):
                rec.active_lot_status = "near_expiry"
            else:
                rec.active_lot_status = "normal"

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

    @api.onchange("barcode", "quantity", "scanned_uom_id", "visit_id", "active_lot_id")
    def _onchange_barcode_preview(self):
        for rec in self:
            rec.detected_product_id = False
            rec.base_uom_id = False
            rec.detected_scan_type = False
            rec.counted_increase = 0.0
            rec.detected_packaging_name = False
            rec.auto_quantity_locked = False
            rec.auto_uom_locked = False

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
            rec.base_uom_id = product.uom_id.id
            rec.detected_scan_type = scan_info["scan_type_label"]

            suggested_qty = scan_info.get("default_scan_qty") or 1.0

            if scan_info.get("scan_type") == "box":
                rec.auto_quantity_locked = True
                rec.auto_uom_locked = True
                rec.detected_packaging_name = (
                    rec.visit_id._get_packaging_display_name(
                        scan_info.get("packaging"),
                        product=product,
                    )
                    if scan_info.get("packaging")
                    else "Box"
                )
                rec.quantity = 1.0
                rec.scanned_uom_id = product.uom_id.id
                rec.counted_increase = suggested_qty
            else:
                if not rec.scanned_uom_id:
                    rec.scanned_uom_id = product.uom_id.id
                if rec.quantity <= 0:
                    rec.quantity = 1.0

                qty = rec.quantity if rec.quantity and rec.quantity > 0 else 0.0
                if qty and rec.scanned_uom_id:
                    try:
                        rec.counted_increase = rec.scanned_uom_id._compute_quantity(
                            qty,
                            product.uom_id,
                        )
                    except Exception:
                        rec.counted_increase = 0.0
                else:
                    rec.counted_increase = 0.0

            try:
                resolved_lot = rec.visit_id._resolve_product_active_lot(
                    product,
                    active_lot=rec.active_lot_id,
                )
            except UserError:
                resolved_lot = False

            rec.expiry_date = rec.visit_id._get_lot_expiry_date(resolved_lot) if resolved_lot else False
            rec.add_to_near_expiry_return = bool(rec.expiry_date and rec.is_near_expiry)

    def action_set_active_lot(self):
        self.ensure_one()
        if not self.visit_id:
            raise UserError(_("Visit is required."))

        lot = self.visit_id._find_available_lot_from_code(self.lot_barcode)
        self.write({
            "active_lot_id": lot.id,
            "lot_barcode": False,
            "focus_target": "product",
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Barcode"),
            "res_model": "route.visit.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
        }

    def action_clear_active_lot(self):
        self.ensure_one()
        self.write({
            "active_lot_id": False,
            "lot_barcode": False,
            "expiry_date": False,
            "add_to_near_expiry_return": False,
            "focus_target": "lot",
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Barcode"),
            "res_model": "route.visit.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
        }

    def _get_or_create_visit_line(self, product):
        self.ensure_one()
        line = self.visit_id.line_ids.filtered(lambda l: l.product_id == product)[:1]
        if line:
            return line
        return self.env["route.visit.line"].create({
            "visit_id": self.visit_id.id,
            "company_id": self.visit_id.company_id.id if "company_id" in self.visit_id._fields else self.env.company.id,
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

        effective_qty = self.quantity
        effective_uom = self.scanned_uom_id

        if self.detected_scan_type == "Box Barcode":
            effective_qty = 1.0
            effective_uom = self.base_uom_id

        if self.scan_mode == "count":
            result = self.visit_id._process_scanned_barcode(
                self.barcode,
                scan_qty=effective_qty,
                scanned_uom=effective_uom,
                active_lot=self.active_lot_id,
            )

            line = result["line"]
            product = result["product"]
            resolved_lot = result.get("resolved_lot")
            effective_expiry_date = result.get("resolved_expiry_date") or self.expiry_date

            line_vals = {}
            if effective_expiry_date:
                line_vals["expiry_date"] = effective_expiry_date

            line_vals["suggest_near_expiry_return"] = self.is_near_expiry

            if resolved_lot and self.active_lot_status == "expired":
                line_vals["return_qty"] = (line.return_qty or 0.0) + (result["counted_increase"] or 0.0)
                line_vals["return_route"] = "damaged"
                line_vals["suggest_near_expiry_return"] = False
            elif self.add_to_near_expiry_return:
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
                    "default_scan_mode": self.scan_mode,
                    "default_active_lot_id": self.active_lot_id.id,
                    "default_focus_target": "product" if self.active_lot_id else "lot",
                    "default_last_product_id": product.id,
                    "default_last_counted_qty": result["counted_increase"],
                },
            }

        raise UserError(_("Return mode is not handled in this version."))

    def action_done(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}
