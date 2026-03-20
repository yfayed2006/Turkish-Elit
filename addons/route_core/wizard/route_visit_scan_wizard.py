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
    is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_expiry_preview",
        store=False,
    )
    requires_expiry_decision = fields.Boolean(
        string="Requires Expiry Decision",
        compute="_compute_expiry_preview",
        store=False,
    )
    requires_return_route = fields.Boolean(
        string="Requires Return Route",
        compute="_compute_expiry_preview",
        store=False,
    )
    expiry_decision_help = fields.Char(
        string="Expiry Decision Help",
        compute="_compute_expiry_preview",
        store=False,
    )

    near_expiry_decision = fields.Selection(
        [
            ("keep", "Keep at Outlet"),
            ("return", "Return"),
        ],
        string="Expiry Decision",
    )

    add_to_near_expiry_return = fields.Boolean(
        string="Add This Quantity to Near Expiry Return",
        default=False,
        help="Backward compatibility field driven by popup decision.",
    )

    return_route = fields.Selection(
        [
            ("vehicle", "To Vehicle"),
            ("near_expiry", "To Near Expiry Stock"),
        ],
        string="Return Route",
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
    last_return_qty = fields.Float(
        string="Last Return Qty",
        readonly=True,
    )
    last_return_route = fields.Selection(
        [
            ("vehicle", "To Vehicle"),
            ("near_expiry", "To Near Expiry Stock"),
        ],
        string="Last Return Route",
        readonly=True,
    )

    @api.depends(
        "expiry_date",
        "visit_id.date",
        "visit_id.near_expiry_threshold_days",
        "scan_mode",
        "near_expiry_decision",
    )
    def _compute_expiry_preview(self):
        for rec in self:
            rec.expiry_days_left = 0
            rec.is_near_expiry = False
            rec.is_expired = False
            rec.requires_expiry_decision = False
            rec.requires_return_route = False
            rec.expiry_decision_help = False

            if not rec.expiry_date:
                continue

            reference_date = rec.visit_id.date or fields.Date.context_today(rec)
            delta_days = (rec.expiry_date - reference_date).days

            rec.expiry_days_left = delta_days
            rec.is_near_expiry = delta_days <= (rec.visit_id.near_expiry_threshold_days or 0)
            rec.is_expired = delta_days < 0
            rec.requires_expiry_decision = bool(rec.scan_mode == "count" and rec.is_near_expiry)
            rec.requires_return_route = bool(
                rec.scan_mode == "count"
                and rec.is_near_expiry
                and (rec.is_expired or rec.near_expiry_decision == "return")
            )

            if rec.scan_mode != "count" or not rec.is_near_expiry:
                rec.expiry_decision_help = False
            elif rec.is_expired:
                rec.expiry_decision_help = _(
                    "This product is expired. Return is mandatory. Choose the return route to continue."
                )
            else:
                rec.expiry_decision_help = _(
                    "This product is near expiry. Choose Keep at Outlet or Return. If you choose Return, select the return route."
                )

    @api.onchange("expiry_date")
    def _onchange_expiry_date_default_near_expiry(self):
        for rec in self:
            if rec.scan_mode != "count":
                rec.add_to_near_expiry_return = False
                rec.near_expiry_decision = False
                rec.return_route = False
                continue

            if not rec.expiry_date or not rec.is_near_expiry:
                rec.add_to_near_expiry_return = False
                rec.near_expiry_decision = False
                rec.return_route = False
                continue

            if rec.is_expired:
                # لا نسمح إلا بالإرجاع، لكن لا نختار route تلقائيًا
                rec.near_expiry_decision = "return"
                rec.add_to_near_expiry_return = True
                rec.return_route = False
            else:
                if rec.near_expiry_decision == "return":
                    rec.add_to_near_expiry_return = True
                else:
                    rec.add_to_near_expiry_return = False
                    rec.return_route = False

    @api.onchange("near_expiry_decision")
    def _onchange_near_expiry_decision(self):
        for rec in self:
            if rec.scan_mode != "count":
                continue

            if rec.is_expired:
                rec.near_expiry_decision = "return"
                rec.add_to_near_expiry_return = True
                return

            if rec.near_expiry_decision == "return":
                rec.add_to_near_expiry_return = True
            elif rec.near_expiry_decision == "keep":
                rec.add_to_near_expiry_return = False
                rec.return_route = False
            else:
                rec.add_to_near_expiry_return = False
                rec.return_route = False

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
                    rec.counted_increase = rec.scanned_uom_id._compute_quantity(
                        qty,
                        product.uom_id,
                    )
                except Exception:
                    rec.counted_increase = 0.0
            else:
                rec.counted_increase = 0.0

    def _get_or_create_visit_line(self, product):
        self.ensure_one()

        line = self.visit_id.line_ids.filtered(lambda l: l.product_id == product)[:1]
        if line:
            return line

        return self.env["route.visit.line"].create(
            {
                "visit_id": self.visit_id.id,
                "company_id": self.visit_id.company_id.id,
                "product_id": product.id,
                "unit_price": product.lst_price or 0.0,
            }
        )

    def _get_scan_product_and_qty(self):
        self.ensure_one()

        scan_info = self.visit_id._resolve_scanned_barcode(self.barcode)
        product = scan_info["product"]
        scanned_uom = self.scanned_uom_id or product.uom_id

        try:
            qty_in_base = scanned_uom._compute_quantity(
                self.quantity,
                product.uom_id,
            )
        except Exception:
            raise UserError(
                _("Could not convert the entered quantity to the product base unit.")
            )

        if qty_in_base <= 0:
            raise UserError(_("Quantity must be greater than zero."))

        return product, qty_in_base

    def _apply_near_expiry_count_decision(self):
        self.ensure_one()

        product, counted_increase = self._get_scan_product_and_qty()
        line = self._get_or_create_visit_line(product)

        line_vals = {
            "counted_qty": (line.counted_qty or 0.0) + counted_increase,
            "expiry_date": self.expiry_date or line.expiry_date,
        }

        if self.is_expired:
            # للمنتهي الصلاحية: فقط Return + route إجباري
            if not self.return_route:
                raise UserError(
                    _("This product is expired. You must choose the return route before continuing.")
                )

            line_vals.update(
                {
                    "return_qty": (line.return_qty or 0.0) + counted_increase,
                    "return_route": self.return_route,
                    "suggest_near_expiry_return": False,
                    "keep_near_expiry": False,
                    "near_expiry_decision_note": _(
                        "Returned from scan popup because the product is expired."
                    ),
                }
            )

        else:
            if not self.near_expiry_decision:
                raise UserError(
                    _("This product is near expiry. Please choose Keep at Outlet or Return before continuing.")
                )

            if self.near_expiry_decision == "return":
                if not self.return_route:
                    raise UserError(
                        _("Please choose where to return this product: To Vehicle or To Near Expiry Stock.")
                    )

                line_vals.update(
                    {
                        "return_qty": (line.return_qty or 0.0) + counted_increase,
                        "return_route": self.return_route,
                        "suggest_near_expiry_return": False,
                        "keep_near_expiry": False,
                        "near_expiry_decision_note": _(
                            "Returned from scan popup due to near expiry."
                        ),
                    }
                )

            elif self.near_expiry_decision == "keep":
                line_vals.update(
                    {
                        "suggest_near_expiry_return": False,
                        "keep_near_expiry": True,
                        "near_expiry_decision_note": _("Kept at outlet from scan popup."),
                    }
                )

        line.write(line_vals)

        if hasattr(line, "_onchange_counted_qty"):
            try:
                line._onchange_counted_qty()
            except Exception:
                pass
        if hasattr(line, "_onchange_return_qty"):
            try:
                line._onchange_return_qty()
            except Exception:
                pass

        return product, line

    def _reopen_scan_wizard_action(self, *, name, product, line):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "route.visit.scan.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.visit_id.id,
                "default_scan_mode": self.scan_mode,
                "default_quantity": 1.0,
                "default_return_route": False,
                "default_expiry_date": False,
                "default_near_expiry_decision": False,
                "default_add_to_near_expiry_return": False,
                "default_last_product_id": line.product_id.id,
                "default_last_counted_qty": line.counted_qty,
                "default_last_return_qty": line.return_qty,
                "default_last_return_route": line.return_route,
                "default_detected_product_id": product.id,
                "default_base_uom_id": product.uom_id.id,
                "default_scanned_uom_id": product.uom_id.id,
                "default_detected_scan_type": False,
                "default_counted_increase": 0.0,
            },
        }

    def action_scan_and_add(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("Visit is required."))

        if not self.barcode or not self.barcode.strip():
            raise UserError(_("Please enter or scan a barcode first."))

        if self.quantity <= 0:
            raise UserError(_("Quantity must be greater than zero."))

        if self.scan_mode == "count":
            if self.expiry_date and self.is_near_expiry:
                product, line = self._apply_near_expiry_count_decision()
                return self._reopen_scan_wizard_action(
                    name=_("Scan Barcode"),
                    product=product,
                    line=line,
                )

            result = self.visit_id._process_scanned_barcode(
                self.barcode,
                scan_qty=self.quantity,
                scanned_uom=self.scanned_uom_id,
            )
            line = result["line"]
            product = result["product"]

            if self.expiry_date:
                line.write(
                    {
                        "expiry_date": self.expiry_date,
                        "suggest_near_expiry_return": False,
                        "keep_near_expiry": False,
                        "near_expiry_decision_note": False,
                    }
                )

            return self._reopen_scan_wizard_action(
                name=_("Scan Barcode"),
                product=product,
                line=line,
            )

        if self.scan_mode == "return":
            product, return_increase = self._get_scan_product_and_qty()

            if not self.return_route:
                raise UserError(_("Please choose a return route."))

            line = self._get_or_create_visit_line(product)
            line.write(
                {
                    "return_qty": (line.return_qty or 0.0) + return_increase,
                    "return_route": self.return_route,
                }
            )

            if hasattr(line, "_onchange_return_qty"):
                try:
                    line._onchange_return_qty()
                except Exception:
                    pass

            return self._reopen_scan_wizard_action(
                name=_("Scan Returns"),
                product=product,
                line=line,
            )

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
