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
        default=lambda self: self._default_focus_target(),
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
    scan_alert_message = fields.Text(string="Scan Alert", readonly=True)
    scan_success_message = fields.Text(string="Scan Saved", readonly=True)
    product_lot_guidance = fields.Text(string="Lot/Serial Guidance", readonly=True)
    detected_product_requires_lot = fields.Boolean(string="Requires Lot/Serial", readonly=True, default=False)

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

    route_enable_lot_serial_tracking = fields.Boolean(
        string="Enable Lot/Serial Workflow",
        compute="_compute_route_feature_flags",
        store=False,
    )
    route_enable_expiry_tracking = fields.Boolean(
        string="Enable Expiry Workflow",
        compute="_compute_route_feature_flags",
        store=False,
    )

    def _default_focus_target(self):
        if self.env.context.get("default_focus_target"):
            return self.env.context["default_focus_target"]
        visit_id = self.env.context.get("default_visit_id")
        if visit_id:
            visit = self.env["route.visit"].browse(visit_id)
            if visit.exists() and hasattr(visit, "_is_route_lot_workflow_enabled"):
                return "lot" if visit._is_route_lot_workflow_enabled() else "product"
        return "lot"

    @api.depends("visit_id.company_id")
    def _compute_route_feature_flags(self):
        for rec in self:
            visit = rec.visit_id
            if visit and hasattr(visit, "_is_route_lot_workflow_enabled"):
                rec.route_enable_lot_serial_tracking = visit._is_route_lot_workflow_enabled()
                rec.route_enable_expiry_tracking = visit._is_route_expiry_workflow_enabled()
            else:
                rec.route_enable_lot_serial_tracking = True
                rec.route_enable_expiry_tracking = True


    @api.depends("active_lot_id", "visit_id.date", "visit_id.near_expiry_threshold_days")
    def _compute_active_lot_state(self):
        for rec in self:
            rec.active_lot_expiry_date = False
            rec.active_lot_days_left = 0
            rec.active_lot_status = False
            if not rec.route_enable_lot_serial_tracking or not rec.route_enable_expiry_tracking or not rec.active_lot_id:
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
            if not rec.route_enable_expiry_tracking or not rec.expiry_date:
                continue
            reference_date = rec.visit_id.date or fields.Date.context_today(rec)
            delta_days = (rec.expiry_date - reference_date).days
            rec.expiry_days_left = delta_days
            rec.is_near_expiry = delta_days <= (rec.visit_id.near_expiry_threshold_days or 0)

    @api.depends("active_lot_status", "near_expiry_decision", "expired_decision")
    def _compute_scan_guidance(self):
        for rec in self:
            if rec.active_lot_status == "expired":
                if rec.expired_decision == "damaged":
                    rec.scan_guidance = _(
                        "Expired lot action selected: this scan will return the counted quantity to Damaged Stock. Scan the product barcode, review Return Qty, then press Scan / Add."
                    )
                else:
                    rec.scan_guidance = _(
                        "Expired lot detected. Choose Return To Damaged Stock inside this popup before pressing Scan / Add. Do not use the visit line table for this step."
                    )
            elif rec.active_lot_status == "near_expiry":
                if rec.near_expiry_decision == "keep":
                    rec.scan_guidance = _(
                        "Near expiry decision selected: keep this lot on the shelf. Scan the product barcode, then press Scan / Add."
                    )
                elif rec.near_expiry_decision == "vehicle":
                    rec.scan_guidance = _(
                        "Near expiry decision selected: return part/all of this lot to the vehicle. Scan the product barcode, review Return Qty, then press Scan / Add."
                    )
                elif rec.near_expiry_decision == "near_expiry":
                    rec.scan_guidance = _(
                        "Near expiry decision selected: return part/all of this lot to Near Expiry Stock. Scan the product barcode, review Return Qty, then press Scan / Add."
                    )
                else:
                    rec.scan_guidance = _(
                        "Near expiry lot detected. Choose Keep On Shelf, Return To Vehicle, or Return To Near Expiry Stock inside this popup before pressing Scan / Add."
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
            rec.scan_alert_message = False
            rec.scan_success_message = False

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
            rec.product_lot_guidance = False
            rec.detected_product_requires_lot = False
            rec.scan_alert_message = False

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
                rec.product_lot_guidance = False
                rec.detected_product_requires_lot = False
                continue

            product = scan_info["product"]
            rec.detected_product_id = product.id
            rec.base_uom_id = product.uom_id.id
            rec.detected_scan_type = scan_info["scan_type_label"]
            rec.detected_product_requires_lot = bool(
                rec.route_enable_lot_serial_tracking
                and hasattr(rec.visit_id, "_is_product_tracked_by_lot")
                and rec.visit_id._is_product_tracked_by_lot(product)
            )
            if rec.detected_product_requires_lot and not rec.active_lot_id:
                available_lots = rec.visit_id._find_available_lots_for_product(product) if hasattr(rec.visit_id, "_find_available_lots_for_product") else rec.env["stock.lot"]
                if len(available_lots) > 1:
                    lot_names = ", ".join(available_lots[:5].mapped("display_name"))
                    more_text = _(" and more") if len(available_lots) > 5 else ""
                    rec.product_lot_guidance = _(
                        "This product is tracked by Lot/Serial. Use the Active Lot section first, then press Scan / Add. Available lots for this product in the outlet or van: %(lots)s%(more)s."
                    ) % {"lots": lot_names, "more": more_text}
                elif not available_lots:
                    rec.product_lot_guidance = _(
                        "This product is tracked by Lot/Serial, but no usable lot was found for this product in the outlet stock or van stock for this visit."
                    )
                else:
                    rec.product_lot_guidance = False
            else:
                rec.product_lot_guidance = False

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

            active_lot = rec.active_lot_id if rec.route_enable_lot_serial_tracking else False
            try:
                resolved_lot = rec.visit_id._resolve_product_active_lot(product, active_lot=active_lot)
            except UserError:
                resolved_lot = False

            rec.expiry_date = rec.visit_id._get_lot_expiry_date(resolved_lot) if (resolved_lot and rec.route_enable_expiry_tracking) else False
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

    def _get_lot_decision_default_qty(self):
        self.ensure_one()
        qty = 0.0
        if self.barcode and self.barcode.strip():
            qty = self._get_current_scan_counted_increase()
        return qty or self.counted_increase or self.quantity or 1.0

    def _reopen_with_scan_alert(self, message):
        self.ensure_one()
        self.write({"scan_alert_message": message, "scan_success_message": False})
        return self._action_reopen_scan_wizard()

    def action_choose_expired_return_damaged(self):
        self.ensure_one()
        if self.active_lot_status != "expired":
            raise UserError(_("This action is only available for expired lots."))
        self.write({
            "expired_decision": "damaged",
            "near_expiry_decision": False,
            "return_from_scan": True,
            "return_route": "damaged",
            "return_qty": self._get_lot_decision_default_qty(),
            "scan_alert_message": False,
            "scan_success_message": False,
            "focus_target": "product",
        })
        return self._action_reopen_scan_wizard()

    def action_choose_near_expiry_keep(self):
        self.ensure_one()
        if self.active_lot_status != "near_expiry":
            raise UserError(_("This action is only available for near expiry lots."))
        self.write({
            "near_expiry_decision": "keep",
            "expired_decision": False,
            "return_from_scan": False,
            "return_route": "vehicle",
            "return_qty": 0.0,
            "scan_alert_message": False,
            "scan_success_message": False,
            "focus_target": "product",
        })
        return self._action_reopen_scan_wizard()

    def action_choose_near_expiry_return_vehicle(self):
        self.ensure_one()
        if self.active_lot_status != "near_expiry":
            raise UserError(_("This action is only available for near expiry lots."))
        self.write({
            "near_expiry_decision": "vehicle",
            "expired_decision": False,
            "return_from_scan": True,
            "return_route": "vehicle",
            "return_qty": self._get_lot_decision_default_qty(),
            "scan_alert_message": False,
            "scan_success_message": False,
            "focus_target": "product",
        })
        return self._action_reopen_scan_wizard()

    def action_choose_near_expiry_return_near_expiry(self):
        self.ensure_one()
        if self.active_lot_status != "near_expiry":
            raise UserError(_("This action is only available for near expiry lots."))
        self.write({
            "near_expiry_decision": "near_expiry",
            "expired_decision": False,
            "return_from_scan": True,
            "return_route": "near_expiry",
            "return_qty": self._get_lot_decision_default_qty(),
            "scan_alert_message": False,
            "scan_success_message": False,
            "focus_target": "product",
        })
        return self._action_reopen_scan_wizard()

    def _action_reopen_scan_wizard(self, name=None):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name or _("Scan Barcode"),
            "res_model": "route.visit.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
            "context": {
                "default_visit_id": self.visit_id.id if self.visit_id else False,
                "default_scan_mode": self.scan_mode,
                "default_focus_target": self.focus_target or self._default_focus_target(),
            },
        }

    def _format_scan_qty(self, value):
        return "%(qty).2f" % {"qty": value or 0.0}

    def _reset_after_successful_scan(self, product=False, counted_qty=0.0, return_qty=0.0, return_route=False):
        self.ensure_one()
        # A successful scan has already written the visit line. Clear the active lot so
        # the next scan starts cleanly and the salesperson does not accidentally reuse
        # an expired/near-expiry lot decision. The parent visit table is refreshed when
        # the user taps Done.
        route_label = dict(self._fields["return_route"].selection).get(return_route, False) if return_route else False
        if return_qty:
            success_message = _(
                "Scan saved. Counted %(counted)s and returned %(returned)s to %(route)s. Tap Done to refresh the visit table, or continue with the next lot/product."
            ) % {
                "counted": self._format_scan_qty(counted_qty),
                "returned": self._format_scan_qty(return_qty),
                "route": route_label or _("the selected return route"),
            }
        else:
            success_message = _(
                "Scan saved. Counted %(counted)s. Tap Done to refresh the visit table, or continue with the next lot/product."
            ) % {"counted": self._format_scan_qty(counted_qty)}

        self.write({
            "barcode": False,
            "quantity": 1.0,
            "scanned_uom_id": False,
            "detected_product_id": False,
            "base_uom_id": False,
            "detected_scan_type": False,
            "counted_increase": 0.0,
            "detected_packaging_name": False,
            "product_lot_guidance": False,
            "detected_product_requires_lot": False,
            "scan_alert_message": False,
            "scan_success_message": success_message,
            "expiry_date": False,
            "add_to_near_expiry_return": False,
            "return_from_scan": False,
            "return_qty": 0.0,
            "return_route": "vehicle",
            "near_expiry_decision": False,
            "expired_decision": False,
            "active_lot_id": False,
            "lot_barcode": False,
            "focus_target": self._default_focus_target(),
            "last_product_id": product.id if product else False,
            "last_counted_qty": counted_qty or 0.0,
            "last_return_qty": return_qty or 0.0,
            "last_return_route": return_route or False,
            "auto_quantity_locked": False,
            "auto_uom_locked": False,
        })

    def action_set_active_lot(self):
        self.ensure_one()
        if not self.visit_id:
            raise UserError(_("Visit is required."))
        if not self.route_enable_lot_serial_tracking:
            self.write({"active_lot_id": False, "lot_barcode": False, "focus_target": "product"})
            return self._action_reopen_scan_wizard()

        product = self.detected_product_id
        if not product and self.barcode:
            try:
                scan_info = self.visit_id._resolve_scanned_barcode(self.barcode)
                product = scan_info.get("product")
            except Exception:
                product = False

        try:
            lot = self.visit_id._find_available_lot_from_code(self.lot_barcode, product=product)
        except TypeError:
            lot = self.visit_id._find_available_lot_from_code(self.lot_barcode)
        except UserError as error:
            self.write({
                "scan_alert_message": error.args[0] if error.args else str(error),
                "focus_target": "lot",
                "scan_success_message": False,
            })
            return self._action_reopen_scan_wizard()

        self.write({
            "active_lot_id": lot.id,
            "lot_barcode": False,
            "focus_target": "product",
            "scan_alert_message": False,
            "scan_success_message": False,
        })
        return self._action_reopen_scan_wizard()

    def action_clear_active_lot(self):
        self.ensure_one()
        self.write({
            "active_lot_id": False,
            "lot_barcode": False,
            "barcode": False,
            "detected_product_id": False,
            "base_uom_id": False,
            "scanned_uom_id": False,
            "detected_scan_type": False,
            "counted_increase": 0.0,
            "detected_packaging_name": False,
            "product_lot_guidance": False,
            "detected_product_requires_lot": False,
            "scan_alert_message": False,
            "scan_success_message": False,
            "expiry_date": False,
            "add_to_near_expiry_return": False,
            "return_from_scan": False,
            "return_qty": 0.0,
            "focus_target": self._default_focus_target(),
            "near_expiry_decision": False,
            "expired_decision": False,
            "return_route": "vehicle",
        })
        return self._action_reopen_scan_wizard()

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
            return self._reopen_with_scan_alert(_("Please scan or enter the product barcode first."))
        if self.quantity <= 0:
            return self._reopen_with_scan_alert(_("Quantity must be greater than zero."))

        if self.scan_mode == "count":
            try:
                scan_info = self.visit_id._resolve_scanned_barcode(self.barcode)
                product = scan_info["product"]
            except UserError:
                raise
            except Exception as error:
                raise UserError(_("Could not read this barcode. Please try again or contact your supervisor.\n\nTechnical detail: %s") % str(error))

            if (
                self.route_enable_lot_serial_tracking
                and hasattr(self.visit_id, "_is_product_tracked_by_lot")
                and self.visit_id._is_product_tracked_by_lot(product)
                and not self.active_lot_id
            ):
                available_lots = self.visit_id._find_available_lots_for_product(product) if hasattr(self.visit_id, "_find_available_lots_for_product") else self.env["stock.lot"]
                if not available_lots:
                    raise UserError(
                        _("Product '%s' requires a Lot/Serial Number, but no available lot was found in the vehicle stock or outlet stock for this visit.")
                        % product.display_name
                    )
                if len(available_lots) > 1:
                    lot_names = ", ".join(available_lots[:5].mapped("display_name"))
                    more_text = _(" and more") if len(available_lots) > 5 else ""
                    raise UserError(
                        _(
                            "Product '%(product)s' requires a Lot/Serial Number before scanning.\n\n"
                            "Available lots for this product in the outlet or van: %(lots)s%(more)s\n\n"
                            "Use the Active Lot section first, then press Scan / Add again."
                        )
                        % {"product": product.display_name, "lots": lot_names, "more": more_text}
                    )

        preview_counted_increase = 0.0
        if self.scan_mode == "count":
            preview_counted_increase = self._get_current_scan_counted_increase()
            if preview_counted_increase <= 0:
                preview_counted_increase = self.counted_increase or self.quantity or 0.0

        if self.scan_mode == "count" and self.active_lot_status == "expired" and self.expired_decision != "damaged":
            return self._reopen_with_scan_alert(
                _("Expired lot action is required. Tap 'Return To Damaged Stock' in this popup, then scan/add the product.")
            )

        if self.scan_mode == "count" and self.active_lot_status == "near_expiry":
            if not self.near_expiry_decision:
                return self._reopen_with_scan_alert(
                    _("Near expiry action is required. Choose Keep On Shelf, Return To Vehicle, or Return To Near Expiry Stock in this popup.")
                )
            if self.near_expiry_decision in ("vehicle", "near_expiry"):
                if self.return_qty <= 0:
                    return self._reopen_with_scan_alert(
                        _("Enter the quantity to return for this near expiry lot, then press Scan / Add again.")
                    )
                if self.return_qty - preview_counted_increase > 1e-9:
                    return self._reopen_with_scan_alert(
                        _("Return Qty cannot be greater than the counted quantity from this scan. Reduce Return Qty, then press Scan / Add again.")
                    )

        effective_qty = self.quantity
        effective_uom = self.base_uom_id if self.detected_scan_type == "Box Barcode" else self.scanned_uom_id

        if self.scan_mode == "count":
            result = self.visit_id._process_scanned_barcode(
                self.barcode,
                scan_qty=effective_qty,
                scanned_uom=effective_uom,
                active_lot=self.active_lot_id if self.route_enable_lot_serial_tracking else False,
            )
            line = result["line"]
            product = result["product"]
            resolved_lot = result.get("resolved_lot")
            effective_expiry_date = (result.get("resolved_expiry_date") or self.expiry_date) if self.route_enable_expiry_tracking else False

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

            self._reset_after_successful_scan(
                product=product,
                counted_qty=result["counted_increase"],
                return_qty=forced_return_qty,
                return_route=forced_return_route,
            )
            return self._action_reopen_scan_wizard()

        raise UserError(_("Return mode is not handled in this version."))

    def action_done(self):
        self.ensure_one()
        if self.visit_id and hasattr(self.visit_id, "_normalize_scanned_lot_previous_lines"):
            self.visit_id._normalize_scanned_lot_previous_lines()
        return {"type": "ir.actions.client", "tag": "reload"}


