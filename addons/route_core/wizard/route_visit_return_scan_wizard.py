from odoo import api, fields, models, _
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
    scan_mode = fields.Selection(
        [
            ("count", "Count"),
            ("return", "Return"),
        ],
        string="Scan Mode",
        default="return",
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
    active_lot_id = fields.Many2one("stock.lot", string="Active Lot", readonly=True)
    active_lot_product_id = fields.Many2one(
        "product.product", string="Lot Product", related="active_lot_id.product_id", readonly=True
    )
    active_lot_expiry_date = fields.Date(string="Lot Expiry Date", compute="_compute_active_lot_state", store=False)
    active_lot_days_left = fields.Integer(string="Lot Days Left", compute="_compute_active_lot_state", store=False)
    active_lot_status = fields.Selection(
        [("normal", "Normal"), ("near_expiry", "Near Expiry"), ("expired", "Expired")],
        string="Lot Status",
        compute="_compute_active_lot_state",
        store=False,
    )

    barcode = fields.Char(string="Barcode")
    quantity = fields.Float(string="Quantity", default=1.0)
    expiry_date = fields.Date(string="Expiry Date")
    expiry_days_left = fields.Integer(string="Days Left", compute="_compute_expiry_preview", store=False)
    is_near_expiry = fields.Boolean(string="Near Expiry", compute="_compute_expiry_preview", store=False)
    add_to_near_expiry_return = fields.Boolean(string="Add This Quantity to Near Expiry Return", default=False)
    return_from_scan = fields.Boolean(string="Return from this scan", default=False)
    return_qty = fields.Float(string="Return Qty", default=0.0)
    return_route = fields.Selection(
        [("vehicle", "To Vehicle"), ("damaged", "To Damaged Stock"), ("near_expiry", "To Near Expiry Stock")],
        string="Return Route",
        default="vehicle",
    )
    near_expiry_decision = fields.Selection(
        [
            ("keep", "Keep On Shelf"),
            ("vehicle", "Return To Vehicle"),
            ("near_expiry", "Return To Near Expiry Stock"),
        ],
        string="Near Expiry Decision",
    )
    expired_decision = fields.Selection(
        [("damaged", "Return To Damaged Stock")],
        string="Expired Lot Decision",
    )
    scan_guidance = fields.Text(string="Scan Guidance", compute="_compute_scan_guidance", store=False)

    detected_product_id = fields.Many2one("product.product", string="Detected Product", readonly=True)
    base_uom_id = fields.Many2one("uom.uom", string="Base UoM", readonly=True)
    scanned_uom_id = fields.Many2one("uom.uom", string="Count As UoM")
    detected_scan_type = fields.Char(string="Detected Source", readonly=True)
    counted_increase = fields.Float(string="Count Increase", readonly=True)
    detected_packaging_name = fields.Char(string="Detected Packaging", readonly=True)
    auto_quantity_locked = fields.Boolean(string="Auto Quantity Locked", readonly=True, default=False)
    auto_uom_locked = fields.Boolean(string="Auto UoM Locked", readonly=True, default=False)

    last_product_id = fields.Many2one("product.product", string="Last Product", readonly=True)
    last_counted_qty = fields.Float(string="Last Counted Qty", readonly=True)
    last_return_qty = fields.Float(string="Last Return Qty", readonly=True)
    last_return_route = fields.Selection(
        [("vehicle", "To Vehicle"), ("damaged", "To Damaged Stock"), ("near_expiry", "To Near Expiry Stock")],
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

    @api.depends("active_lot_status", "near_expiry_decision", "expired_decision")
    def _compute_scan_guidance(self):
        for rec in self:
            if rec.active_lot_status == "expired":
                rec.scan_guidance = _(
                    "This lot is expired. You must choose 'Return To Damaged Stock' before the scan can continue."
                )
            elif rec.active_lot_status == "near_expiry":
                rec.scan_guidance = _(
                    "This lot is near expiry. Choose whether to keep it on the shelf or return part/all of it to the vehicle or Near Expiry Stock."
                )
            else:
                rec.scan_guidance = False

    @api.onchange("expiry_date")
    def _onchange_expiry_date_default_near_expiry(self):
        for rec in self:
            rec.add_to_near_expiry_return = False

    @api.onchange("active_lot_id")
    def _onchange_active_lot_reset_decisions(self):
        for rec in self:
            rec.near_expiry_decision = False
            rec.expired_decision = False
            rec.return_from_scan = False
            rec.return_qty = 0.0
            rec.return_route = "vehicle"

    @api.onchange("near_expiry_decision", "counted_increase")
    def _onchange_near_expiry_decision(self):
        for rec in self:
            if rec.active_lot_status != "near_expiry":
                continue
            if rec.near_expiry_decision == "keep":
                rec.return_from_scan = False
                rec.return_qty = 0.0
                rec.return_route = "vehicle"
            elif rec.near_expiry_decision in ("vehicle", "near_expiry"):
                rec.return_from_scan = True
                rec.return_route = rec.near_expiry_decision
                if rec.return_qty <= 0:
                    rec.return_qty = rec.counted_increase or rec.quantity or 1.0
            else:
                rec.return_from_scan = False
                rec.return_qty = 0.0
                rec.return_route = "vehicle"

    @api.onchange("expired_decision", "counted_increase")
    def _onchange_expired_decision(self):
        for rec in self:
            if rec.active_lot_status != "expired":
                continue
            if rec.expired_decision == "damaged":
                rec.return_from_scan = True
                rec.return_route = "damaged"
                rec.return_qty = rec.counted_increase or rec.quantity or 1.0
            else:
                rec.return_from_scan = False
                rec.return_qty = 0.0
                rec.return_route = "vehicle"

    @api.onchange("return_from_scan", "counted_increase")
    def _onchange_return_from_scan(self):
        for rec in self:
            if rec.scan_mode != "count":
                rec.return_from_scan = False
                rec.return_qty = 0.0
                continue
            if rec.active_lot_status == "expired":
                # Expired lots must be explicitly acknowledged via expired_decision.
                continue
            if rec.active_lot_status == "near_expiry":
                # Near expiry lots are controlled by near_expiry_decision.
                continue
            if rec.return_from_scan:
                if rec.return_qty <= 0:
                    rec.return_qty = rec.counted_increase or 1.0
            else:
                rec.return_qty = 0.0

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
                rec.return_from_scan = False
                rec.return_qty = 0.0
                rec.near_expiry_decision = False
                rec.expired_decision = False
                continue

            try:
                scan_info = rec.visit_id._resolve_scanned_barcode(rec.barcode)
            except UserError:
                rec.scanned_uom_id = False
                rec.expiry_date = False
                rec.add_to_near_expiry_return = False
                rec.return_from_scan = False
                rec.return_qty = 0.0
                rec.near_expiry_decision = False
                rec.expired_decision = False
                continue

            product = scan_info["product"]
            rec.detected_product_id = product.id
            rec.base_uom_id = product.uom_id.id
            rec.detected_scan_type = scan_info["scan_type_label"]

            if scan_info.get("scan_type") == "box":
                rec.auto_quantity_locked = False
                rec.auto_uom_locked = True
                rec.detected_packaging_name = scan_info.get("packaging_display_name") or rec.visit_id._get_packaging_display_name(scan_info.get("packaging")) or "Box"
                if rec.quantity <= 0:
                    rec.quantity = 1.0
                rec.scanned_uom_id = product.uom_id.id
                rec.counted_increase = (rec.quantity or 0.0) * (scan_info.get("box_qty") or 1.0)
            else:
                if not rec.scanned_uom_id:
                    rec.scanned_uom_id = product.uom_id.id
                if rec.quantity <= 0:
                    rec.quantity = 1.0
                qty = rec.quantity if rec.quantity and rec.quantity > 0 else 0.0
                if qty and rec.scanned_uom_id:
                    try:
                        rec.counted_increase = rec.scanned_uom_id._compute_quantity(qty, product.uom_id)
                    except Exception:
                        rec.counted_increase = 0.0
                else:
                    rec.counted_increase = 0.0

            try:
                resolved_lot = rec.visit_id._resolve_product_active_lot(product, active_lot=rec.active_lot_id)
            except UserError:
                resolved_lot = False

            rec.expiry_date = rec.visit_id._get_lot_expiry_date(resolved_lot) if resolved_lot else False
            rec.add_to_near_expiry_return = False

            # Reset decisions when the scan context changes.
            if rec.active_lot_status == "expired":
                if rec.expired_decision == "damaged":
                    rec.return_from_scan = True
                    rec.return_route = "damaged"
                    rec.return_qty = rec.counted_increase or rec.quantity or 1.0
                else:
                    rec.return_from_scan = False
                    rec.return_qty = 0.0
                    rec.return_route = "vehicle"
                rec.near_expiry_decision = False
            elif rec.active_lot_status == "near_expiry":
                if rec.near_expiry_decision in ("vehicle", "near_expiry"):
                    rec.return_from_scan = True
                    rec.return_route = rec.near_expiry_decision
                    if rec.return_qty <= 0:
                        rec.return_qty = rec.counted_increase or rec.quantity or 1.0
                elif rec.near_expiry_decision == "keep":
                    rec.return_from_scan = False
                    rec.return_qty = 0.0
                    rec.return_route = "vehicle"
                else:
                    rec.return_from_scan = False
                    rec.return_qty = 0.0
                    rec.return_route = "vehicle"
                rec.expired_decision = False
            elif rec.return_from_scan and rec.return_qty <= 0:
                rec.return_qty = rec.counted_increase or 1.0
                rec.near_expiry_decision = False
                rec.expired_decision = False
            else:
                rec.near_expiry_decision = False
                rec.expired_decision = False

    def action_set_active_lot(self):
        self.ensure_one()
        if not self.visit_id:
            raise UserError(_("Visit is required."))
        lot = self.visit_id._find_available_lot_from_code(self.lot_barcode)
        self.write({"active_lot_id": lot.id, "lot_barcode": False, "focus_target": "product"})
        return {"type": "ir.actions.act_window", "name": _("Scan Barcode"), "res_model": "route.visit.return.scan.wizard", "view_mode": "form", "target": "new", "res_id": self.id}

    def action_clear_active_lot(self):
        self.ensure_one()
        self.write({
            "active_lot_id": False,
            "lot_barcode": False,
            "barcode": False,
            "quantity": 1.0,
            "detected_product_id": False,
            "base_uom_id": False,
            "scanned_uom_id": False,
            "detected_scan_type": False,
            "counted_increase": 0.0,
            "detected_packaging_name": False,
            "expiry_date": False,
            "add_to_near_expiry_return": False,
            "return_from_scan": False,
            "return_qty": 0.0,
            "focus_target": "lot",
            "near_expiry_decision": False,
            "expired_decision": False,
            "return_route": "vehicle",
            "auto_quantity_locked": False,
            "auto_uom_locked": False,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Scan Barcode"),
            "res_model": "route.visit.return.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
            "context": {
                "default_visit_id": self.visit_id.id,
                "default_scan_mode": self.scan_mode,
                "default_focus_target": "lot",
                "default_lot_barcode": False,
                "default_barcode": False,
                "default_quantity": 1.0,
                "default_scanned_uom_id": False,
                "default_return_from_scan": False,
                "default_return_qty": 0.0,
                "default_near_expiry_decision": False,
                "default_expired_decision": False,
                "default_return_route": "vehicle",
                "default_last_product_id": self.last_product_id.id if self.last_product_id else False,
                "default_last_counted_qty": self.last_counted_qty,
                "default_last_return_qty": self.last_return_qty,
                "default_last_return_route": self.last_return_route,
            },
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

    def _get_current_scan_counted_increase(self):
        self.ensure_one()
        if not self.visit_id or not self.barcode or not self.barcode.strip() or self.quantity <= 0:
            return 0.0
        try:
            scan_info = self.visit_id._resolve_scanned_barcode(self.barcode)
            product = scan_info["product"]
            if scan_info.get("scan_type") == "box":
                return (self.quantity or 0.0) * (scan_info.get("box_qty") or 1.0)
            scanned_uom = self.scanned_uom_id or product.uom_id
            return self.visit_id._get_scan_counted_increase(
                product,
                scan_qty=self.quantity or 0.0,
                scanned_uom=scanned_uom,
            )
        except Exception:
            return self.counted_increase or self.quantity or 0.0

    def action_scan_and_add(self):
        self.ensure_one()
        if not self.visit_id:
            raise UserError(_("Visit is required."))
        if not self.barcode or not self.barcode.strip():
            raise UserError(_("Please enter or scan a barcode first."))
        if self.quantity <= 0:
            raise UserError(_("Quantity must be greater than zero."))

        preview_counted_increase = 0.0
        if self.scan_mode == "count":
            preview_counted_increase = self._get_current_scan_counted_increase()
            if preview_counted_increase <= 0:
                preview_counted_increase = self.counted_increase or self.quantity or 0.0

        if self.scan_mode == "count" and self.active_lot_status == "expired" and self.expired_decision != "damaged":
            raise UserError(_("This lot is expired. Choose 'Return To Damaged Stock' before scanning can continue."))

        if self.scan_mode == "count" and self.active_lot_status == "near_expiry":
            if not self.near_expiry_decision:
                raise UserError(_("This lot is near expiry. Please choose whether to keep it on the shelf or return part/all of it before continuing."))
            if self.near_expiry_decision in ("vehicle", "near_expiry"):
                if self.return_qty <= 0:
                    raise UserError(_("Please enter the quantity to return for the near expiry lot."))
                if self.return_qty - preview_counted_increase > 1e-9:
                    raise UserError(_("Return Qty cannot be greater than the counted quantity from this scan."))

        effective_qty = self.quantity
        effective_uom = self.base_uom_id if self.detected_scan_type == "Box Barcode" else self.scanned_uom_id

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

            counted_increase = preview_counted_increase or result["counted_increase"] or 0.0
            forced_return_qty = 0.0
            forced_return_route = False

            if resolved_lot and self.active_lot_status == "expired":
                forced_return_qty = counted_increase
                forced_return_route = "damaged"
                line_vals["suggest_near_expiry_return"] = False
            elif self.active_lot_status == "near_expiry":
                if self.near_expiry_decision == "keep":
                    forced_return_qty = 0.0
                    forced_return_route = False
                elif self.near_expiry_decision in ("vehicle", "near_expiry"):
                    forced_return_qty = self.return_qty or 0.0
                    forced_return_route = self.near_expiry_decision
                    if forced_return_qty - counted_increase > 1e-9:
                        raise UserError(_("Return Qty cannot be greater than the counted quantity from this scan."))
                    line_vals["suggest_near_expiry_return"] = False
            elif self.return_from_scan:
                requested_return_qty = self.return_qty or 0.0
                if requested_return_qty <= 0:
                    requested_return_qty = counted_increase
                if requested_return_qty - counted_increase > 1e-9:
                    raise UserError(_("Return Qty cannot be greater than the counted quantity from this scan."))
                forced_return_qty = requested_return_qty
                forced_return_route = self.return_route or "vehicle"
                line_vals["suggest_near_expiry_return"] = False

            if forced_return_qty:
                line_vals["return_qty"] = (line.return_qty or 0.0) + forced_return_qty
                line_vals["return_route"] = forced_return_route

            if line_vals:
                line.write(line_vals)
                line.invalidate_recordset()

            return {
                "type": "ir.actions.act_window",
                "name": _("Scan Barcode"),
                "res_model": "route.visit.return.scan.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_visit_id": self.visit_id.id,
                    "default_scan_mode": self.scan_mode,
                    "default_active_lot_id": self.active_lot_id.id,
                    "default_focus_target": "product" if self.active_lot_id else "lot",
                    "default_last_product_id": product.id,
                    "default_last_counted_qty": result["counted_increase"],
                    "default_last_return_qty": forced_return_qty,
                    "default_last_return_route": forced_return_route,
                    "default_return_from_scan": False,
                    "default_return_qty": 0.0,
                    "default_near_expiry_decision": False,
                    "default_expired_decision": False,
                },
            }

        if self.scan_mode == "return":
            scan_info = self.visit_id._resolve_scanned_barcode(self.barcode)
            product = scan_info["product"]
            effective_return_qty = self._get_current_scan_counted_increase()
            if effective_return_qty <= 0:
                effective_return_qty = self.quantity or 0.0
            if effective_return_qty <= 0:
                raise UserError(_("Return quantity must be greater than zero."))

            resolved_lot = False
            effective_expiry_date = False
            try:
                resolved_lot = self.visit_id._resolve_product_active_lot(product, active_lot=self.active_lot_id)
                effective_expiry_date = self.visit_id._get_lot_expiry_date(resolved_lot) if resolved_lot else False
            except UserError:
                resolved_lot = False
                effective_expiry_date = False

            self.visit_id._add_return_qty(
                product,
                effective_return_qty,
                return_route=self.return_route or "vehicle",
                lot=resolved_lot,
                expiry_date=effective_expiry_date,
            )

            return {
                "type": "ir.actions.act_window",
                "name": _("Scan Returns"),
                "res_model": "route.visit.return.scan.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_visit_id": self.visit_id.id,
                    "default_scan_mode": "return",
                    "default_focus_target": "product",
                    "default_quantity": 1.0,
                    "default_scanned_uom_id": False,
                    "default_return_route": self.return_route or "vehicle",
                    "default_last_product_id": product.id,
                    "default_last_return_qty": effective_return_qty,
                    "default_last_return_route": self.return_route or "vehicle",
                },
            }

        raise UserError(_("Return mode is not handled in this version."))

    def action_done(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}
