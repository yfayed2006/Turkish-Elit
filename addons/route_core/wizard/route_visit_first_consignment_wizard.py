from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisitFirstConsignmentWizard(models.TransientModel):
    _name = "route.visit.first.consignment.wizard"
    _description = "First Consignment Visit Setup"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        related="visit_id.outlet_id",
        readonly=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        related="visit_id.vehicle_id",
        readonly=True,
    )
    source_location_id = fields.Many2one(
        "stock.location",
        string="Vehicle Stock Location",
        compute="_compute_source_location",
        store=False,
        readonly=True,
    )
    outlet_location_id = fields.Many2one(
        "stock.location",
        string="Outlet Stock Location",
        related="visit_id.outlet_id.stock_location_id",
        readonly=True,
    )
    setup_mode = fields.Selection(
        [
            ("empty_balance", "Start with empty shelf balance"),
            ("vehicle_refill", "Add products from vehicle stock"),
            ("visit_only", "Continue visit only"),
        ],
        string="How do you want to continue?",
        default="empty_balance",
        required=True,
    )
    line_ids = fields.One2many(
        "route.visit.first.consignment.wizard.line",
        "wizard_id",
        string="Vehicle Products",
    )
    has_vehicle_stock = fields.Boolean(
        string="Vehicle Has Stock",
        compute="_compute_has_vehicle_stock",
        store=False,
    )
    help_text = fields.Text(
        string="Help",
        compute="_compute_help_text",
        store=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        visit_id = self.env.context.get("default_visit_id") or self.env.context.get("active_id")
        if not visit_id:
            return res

        visit = self.env["route.visit"].browse(visit_id).exists()
        if not visit:
            return res

        res["visit_id"] = visit.id
        if "line_ids" in fields_list:
            res["line_ids"] = [
                (0, 0, vals) for vals in self._prepare_default_vehicle_product_lines(visit)
            ]
        return res

    def _get_quant_available_qty(self, quant):
        """Return usable qty for a vehicle quant without assuming a fixed Odoo version."""
        if "available_quantity" in quant._fields:
            return quant.available_quantity or 0.0
        reserved_qty = quant.reserved_quantity if "reserved_quantity" in quant._fields else 0.0
        return (quant.quantity or 0.0) - (reserved_qty or 0.0)

    def _get_lot_expiry_date(self, lot):
        if not lot:
            return False
        expiry_value = False
        for field_name in ("expiration_date", "use_date", "removal_date", "alert_date"):
            if field_name in lot._fields and lot[field_name]:
                expiry_value = lot[field_name]
                break
        if expiry_value and hasattr(expiry_value, "date"):
            return expiry_value.date()
        return expiry_value or False

    def _prepare_default_vehicle_product_lines(self, visit):
        source_location = visit.source_location_id or visit.vehicle_id.stock_location_id
        if not source_location:
            return []

        quants = self.env["stock.quant"].search([
            ("location_id", "child_of", source_location.id),
            ("quantity", ">", 0),
        ])

        qty_by_product_lot = defaultdict(float)
        lot_by_key = {}
        for quant in quants:
            available_qty = self._get_quant_available_qty(quant)
            if not quant.product_id or available_qty <= 0:
                continue
            lot = quant.lot_id if "lot_id" in quant._fields else False
            key = (quant.product_id.id, lot.id if lot else False)
            qty_by_product_lot[key] += available_qty
            if lot:
                lot_by_key[key] = lot

        rows = []
        Product = self.env["product.product"]
        for (product_id, lot_id), available_qty in qty_by_product_lot.items():
            product = Product.browse(product_id)
            if not product.exists() or available_qty <= 0:
                continue
            lot = lot_by_key.get((product_id, lot_id))
            rows.append({
                "product_id": product.id,
                "lot_id": lot.id if lot else False,
                "expiry_date": self._get_lot_expiry_date(lot),
                "available_qty": available_qty,
                "quantity": 0.0,
                "unit_price": self._get_default_unit_price(visit, product),
            })

        rows.sort(key=lambda vals: (
            Product.browse(vals["product_id"]).display_name or "",
            self.env["stock.lot"].browse(vals.get("lot_id")).name if vals.get("lot_id") else "",
        ))
        return rows

    def _get_default_unit_price(self, visit, product):
        balance = self.env["outlet.stock.balance"].search([
            ("outlet_id", "=", visit.outlet_id.id),
            ("product_id", "=", product.id),
        ], limit=1)
        if balance and balance.unit_price:
            return balance.unit_price
        return product.lst_price or 0.0

    @api.depends("visit_id.source_location_id", "visit_id.vehicle_id.stock_location_id")
    def _compute_source_location(self):
        for rec in self:
            visit = rec.visit_id
            rec.source_location_id = visit.source_location_id or visit.vehicle_id.stock_location_id

    @api.depends("line_ids.available_qty")
    def _compute_has_vehicle_stock(self):
        for rec in self:
            rec.has_vehicle_stock = any((line.available_qty or 0.0) > 0 for line in rec.line_ids)

    @api.depends("setup_mode")
    def _compute_help_text(self):
        messages = {
            "empty_balance": _(
                "Use this when this is the first shelf count. The visit will continue with zero previous quantities, and you can count/refill normally."
            ),
            "vehicle_refill": _(
                "Use this when you want to place starting consignment products from the vehicle. Enter the quantities, then confirm the refill transfer from the visit."
            ),
            "visit_only": _(
                "Use this for an introductory visit or notes-only visit. No shelf products will be added now."
            ),
        }
        for rec in self:
            rec.help_text = messages.get(rec.setup_mode, "")

    def _validate_visit(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit:
            raise UserError(_("Visit is required."))
        if getattr(visit, "_is_direct_sales_stop", False) and visit._is_direct_sales_stop():
            raise UserError(_("First consignment setup is not used for Direct Sales stops."))
        if visit.state != "in_progress":
            raise UserError(_("First consignment setup can only be used while the visit is in progress."))
        if visit.visit_process_state not in ("pending", "checked_in"):
            raise UserError(_("First consignment setup can only be used before shelf counting starts."))
        if visit.line_ids:
            raise UserError(_("This visit already has product lines. First consignment setup is only for an empty first visit."))
        if not visit.outlet_id.stock_location_id:
            raise UserError(_("Please set an Outlet Stock Location before continuing."))
        if not visit.vehicle_id or not visit.vehicle_id.stock_location_id:
            raise UserError(_("Please set a Vehicle Stock Location before continuing."))
        return visit

    def _return_visit_action(self):
        self.ensure_one()
        if hasattr(self.visit_id, "_get_pda_form_action"):
            return self.visit_id._get_pda_form_action()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.visit_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def _write_visit_state(self, visit, vals):
        vals = dict(vals)
        vals["first_consignment_empty_balance"] = True
        if "check_in_datetime" in visit._fields:
            vals["check_in_datetime"] = visit.check_in_datetime or fields.Datetime.now()
        visit.write(vals)

    def _post_visit_message(self, visit, body):
        if hasattr(visit, "message_post"):
            visit.message_post(body=body)

    def _prepare_visit_line_values(self, visit, line, available_qty):
        visit_line_model = self.env["route.visit.line"]
        vals = {
            "visit_id": visit.id,
            "company_id": visit.company_id.id if "company_id" in visit._fields else self.env.company.id,
            "product_id": line.product_id.id,
            "previous_qty": 0.0,
            "counted_qty": 0.0,
            "supplied_qty": line.quantity,
            "pending_refill_qty": 0.0,
            "vehicle_available_qty": available_qty,
            "unit_price": line.unit_price or line.product_id.lst_price or 0.0,
        }
        if "lot_id" in visit_line_model._fields and line.lot_id:
            vals["lot_id"] = line.lot_id.id
        if "expiry_date" in visit_line_model._fields and line.expiry_date:
            vals["expiry_date"] = line.expiry_date
        if "expiration_date" in visit_line_model._fields and line.expiry_date:
            vals["expiration_date"] = line.expiry_date
        if "barcode" in visit_line_model._fields and line.product_barcode:
            vals["barcode"] = line.product_barcode
        if "product_barcode" in visit_line_model._fields and line.product_barcode:
            vals["product_barcode"] = line.product_barcode
        if "uom_id" in visit_line_model._fields and line.uom_id:
            vals["uom_id"] = line.uom_id.id
        if "product_uom_id" in visit_line_model._fields and line.uom_id:
            vals["product_uom_id"] = line.uom_id.id
        return vals

    def action_apply(self):
        self.ensure_one()
        visit = self._validate_visit()

        if self.setup_mode == "empty_balance":
            self._write_visit_state(visit, {
                "visit_process_state": "checked_in",
            })
            message = _(
                "First consignment visit: no previous shelf stock was found. The visit will continue with an empty shelf balance."
            )
            self._post_visit_message(visit, message)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("First Consignment Visit"),
                    "message": message,
                    "type": "info",
                    "sticky": False,
                    "next": self._return_visit_action(),
                },
            }

        if self.setup_mode == "visit_only":
            self._write_visit_state(visit, {
                "visit_process_state": "reconciled",
                "no_refill": True,
                "returns_step_done": True,
                "refill_datetime": fields.Datetime.now(),
            })
            message = _(
                "First consignment visit: no previous shelf stock was found. The visit will continue without adding shelf products now."
            )
            self._post_visit_message(visit, message)
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("First Consignment Visit"),
                    "message": message,
                    "type": "info",
                    "sticky": False,
                    "next": self._return_visit_action(),
                },
            }

        invalid_quantity_lines = self.line_ids.filtered(
            lambda line: not line.product_id and (line.quantity or 0.0) > 0
        )
        if invalid_quantity_lines:
            raise UserError(_(
                "One or more wizard lines lost the product value before saving. "
                "Close this setup window, open Load Previous Balance again, then enter the quantities again."
            ))

        selected_lines = self.line_ids.filtered(
            lambda line: line.product_id and (line.quantity or 0.0) > 0
        )
        if not selected_lines:
            raise UserError(_("Enter at least one product quantity to add from the vehicle."))

        if hasattr(visit, "_sync_source_location_from_vehicle"):
            visit._sync_source_location_from_vehicle()

        visit_line_model = self.env["route.visit.line"]
        created_lines = self.env["route.visit.line"]
        for line in selected_lines:
            available_qty = line.available_qty or visit._get_vehicle_available_qty_for_product(line.product_id)
            if line.quantity - available_qty > 1e-9:
                raise UserError(_(
                    "The requested quantity for %(product)s is greater than the vehicle available quantity.\nRequested: %(requested).2f\nAvailable: %(available).2f"
                ) % {
                    "product": line.product_id.display_name,
                    "requested": line.quantity,
                    "available": available_qty,
                })
            created_lines |= visit_line_model.create(
                self._prepare_visit_line_values(visit, line, available_qty)
            )

        if created_lines and hasattr(visit, "_update_vehicle_available_on_lines"):
            visit._update_vehicle_available_on_lines(created_lines)

        self._write_visit_state(visit, {
            "visit_process_state": "reconciled",
            "has_refill": True,
            "no_refill": False,
            "returns_step_done": True,
            "refill_datetime": fields.Datetime.now(),
        })
        message = _(
            "Initial consignment products were prepared from vehicle stock. Confirm Refill to create the vehicle-to-outlet transfer."
        )
        self._post_visit_message(visit, message)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Initial Consignment Refill"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": self._return_visit_action(),
            },
        }


class RouteVisitFirstConsignmentWizardLine(models.TransientModel):
    _name = "route.visit.first.consignment.wizard.line"
    _description = "First Consignment Vehicle Product Line"

    wizard_id = fields.Many2one(
        "route.visit.first.consignment.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        readonly=True,
    )
    expiry_date = fields.Date(
        string="Expiry Date",
        readonly=True,
    )
    available_qty = fields.Float(string="Vehicle Available", readonly=True)
    quantity = fields.Float(string="Qty to Add", default=0.0)
    product_image_128 = fields.Image(
        string="Image",
        related="product_id.image_128",
        readonly=True,
    )
    product_barcode = fields.Char(
        string="Barcode",
        compute="_compute_product_barcode",
        store=False,
        readonly=True,
    )
    unit_price = fields.Float(string="Unit Price")
    estimated_value = fields.Float(
        string="Estimated Value",
        compute="_compute_estimated_value",
        store=False,
        readonly=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        related="product_id.uom_id",
        readonly=True,
    )

    @api.depends("product_id", "product_id.barcode", "product_id.default_code")
    def _compute_product_barcode(self):
        for rec in self:
            rec.product_barcode = rec.product_id.barcode or rec.product_id.default_code or ""

    @api.depends("quantity", "unit_price")
    def _compute_estimated_value(self):
        for rec in self:
            rec.estimated_value = (rec.quantity or 0.0) * (rec.unit_price or 0.0)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if not rec.product_id or not rec.wizard_id.visit_id:
                rec.available_qty = 0.0
                rec.unit_price = 0.0
                rec.lot_id = False
                rec.expiry_date = False
                continue
            visit = rec.wizard_id.visit_id
            rec.available_qty = visit._get_vehicle_available_qty_for_product(rec.product_id)
            rec.unit_price = rec.wizard_id._get_default_unit_price(visit, rec.product_id)

    @api.onchange("quantity")
    def _onchange_quantity(self):
        for rec in self:
            if rec.quantity and rec.quantity < 0:
                rec.quantity = 0.0
            if rec.available_qty and rec.quantity and rec.quantity > rec.available_qty:
                rec.quantity = rec.available_qty
