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

    def _prepare_default_vehicle_product_lines(self, visit):
        source_location = visit.source_location_id or visit.vehicle_id.stock_location_id
        if not source_location:
            return []

        quants = self.env["stock.quant"].search([
            ("location_id", "child_of", source_location.id),
            ("quantity", ">", 0),
        ])

        qty_by_product = defaultdict(float)
        for quant in quants:
            if quant.product_id and quant.quantity > 0:
                qty_by_product[quant.product_id.id] += quant.quantity

        rows = []
        Product = self.env["product.product"]
        for product_id, available_qty in qty_by_product.items():
            product = Product.browse(product_id)
            if not product.exists():
                continue
            rows.append({
                "product_id": product.id,
                "available_qty": available_qty,
                "quantity": 0.0,
                "unit_price": self._get_default_unit_price(visit, product),
            })

        rows.sort(key=lambda vals: Product.browse(vals["product_id"]).display_name or "")
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

        selected_lines = self.line_ids.filtered(lambda line: (line.quantity or 0.0) > 0)
        if not selected_lines:
            raise UserError(_("Enter at least one product quantity to add from the vehicle."))

        visit._sync_source_location_from_vehicle()
        visit_line_model = self.env["route.visit.line"]
        created_lines = self.env["route.visit.line"]
        for line in selected_lines:
            available_qty = visit._get_vehicle_available_qty_for_product(line.product_id)
            if line.quantity - available_qty > 1e-9:
                raise UserError(_(
                    "The requested quantity for %(product)s is greater than the vehicle available quantity.\nRequested: %(requested).2f\nAvailable: %(available).2f"
                ) % {
                    "product": line.product_id.display_name,
                    "requested": line.quantity,
                    "available": available_qty,
                })
            created_lines |= visit_line_model.create({
                "visit_id": visit.id,
                "company_id": visit.company_id.id if "company_id" in visit._fields else self.env.company.id,
                "product_id": line.product_id.id,
                "previous_qty": 0.0,
                "counted_qty": 0.0,
                "supplied_qty": line.quantity,
                "pending_refill_qty": 0.0,
                "vehicle_available_qty": available_qty,
                "unit_price": line.unit_price or line.product_id.lst_price or 0.0,
            })

        if created_lines:
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
    available_qty = fields.Float(string="Vehicle Available", readonly=True)
    quantity = fields.Float(string="Qty to Add", default=0.0)
    unit_price = fields.Float(string="Unit Price")
    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        related="product_id.uom_id",
        readonly=True,
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if not rec.product_id or not rec.wizard_id.visit_id:
                rec.available_qty = 0.0
                rec.unit_price = 0.0
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
