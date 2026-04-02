from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class RouteDirectReturn(models.Model):
    _name = "route.direct.return"
    _description = "Route Direct Return"
    _order = "id desc"

    name = fields.Char(string="Reference", default="New", copy=False, readonly=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", default=lambda self: self.env.user, required=True, index=True, readonly=True)
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        domain=[("outlet_operation_mode", "=", "direct_sale"), ("active", "=", True)],
        ondelete="restrict",
    )
    partner_id = fields.Many2one("res.partner", string="Customer", related="outlet_id.partner_id", store=True, readonly=True)
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle", ondelete="restrict")
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Reference Sale Order",
        domain="[('route_order_mode', '=', 'direct_sale'), ('route_outlet_id', '=', outlet_id)]",
        ondelete="set null",
    )
    reference_picking_id = fields.Many2one(
        "stock.picking",
        string="Reference Delivery",
        ondelete="set null",
    )
    visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        ondelete="set null",
        index=True,
    )
    return_date = fields.Date(string="Return Date", default=fields.Date.context_today, required=True)
    note = fields.Text(string="Notes")
    state = fields.Selection([("draft", "Draft"), ("done", "Done"), ("cancel", "Cancelled")], default="draft", tracking=True)
    line_ids = fields.One2many("route.direct.return.line", "return_id", string="Return Lines", copy=True)
    picking_ids = fields.One2many("stock.picking", "route_direct_return_id", string="Generated Returns")
    picking_count = fields.Integer(string="Return Pickings", compute="_compute_picking_count")
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=False,
        readonly=True,
    )
    amount_total = fields.Monetary(
        string="Estimated Return Value",
        currency_field="currency_id",
        compute="_compute_amount_total",
        store=False,
        readonly=True,
    )

    route_enable_lot_serial_tracking = fields.Boolean(
        string="Enable Lot/Serial Workflow",
        related="company_id.route_enable_lot_serial_tracking",
        readonly=True,
        store=False,
    )
    route_enable_expiry_tracking = fields.Boolean(
        string="Enable Expiry Workflow",
        related="company_id.route_enable_expiry_tracking",
        readonly=True,
        store=False,
    )


    route_enable_direct_sale = fields.Boolean(
        string="Enable Direct Sale",
        related="company_id.route_enable_direct_sale",
        readonly=True,
        store=False,
    )
    route_enable_direct_return = fields.Boolean(
        string="Enable Direct Return",
        related="company_id.route_enable_direct_return",
        readonly=True,
        store=False,
    )

    @api.depends("line_ids.estimated_amount")
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("estimated_amount"))

    def _ensure_direct_return_enabled(self):
        for rec in self:
            if not rec.company_id.route_enable_direct_return:
                raise UserError(_("Direct Return is disabled in Route Settings."))

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        default_visit_id = self.env.context.get("default_visit_id") or self.env.context.get("route_visit_id")
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            if not company.route_enable_direct_return:
                raise UserError(_("Direct Return is disabled in Route Settings."))
            if vals.get("name", "New") == "New":
                vals["name"] = seq.next_by_code("route.direct.return") or "New"
            vals.setdefault("user_id", self.env.user.id)
            vals.setdefault("company_id", self.env.company.id)
            if default_visit_id and not vals.get("visit_id") and "visit_id" in self._fields:
                vals["visit_id"] = default_visit_id
        return super().create(vals_list)

    @api.model
    def _default_vehicle(self):
        today = fields.Date.context_today(self)

        current_visit = self.env["route.visit"].search([
            ("user_id", "=", self.env.user.id),
            ("state", "=", "in_progress"),
            ("vehicle_id", "!=", False),
        ], order="start_datetime desc, id desc", limit=1)
        if current_visit and current_visit.vehicle_id:
            return current_visit.vehicle_id

        today_plan = self.env["route.plan"].search([
            ("user_id", "=", self.env.user.id),
            ("date", "=", today),
            ("vehicle_id", "!=", False),
        ], order="id desc", limit=1)
        if today_plan and today_plan.vehicle_id:
            return today_plan.vehicle_id

        latest_visit = self.env["route.visit"].search([
            ("user_id", "=", self.env.user.id),
            ("vehicle_id", "!=", False),
        ], order="date desc, id desc", limit=1)
        if latest_visit and latest_visit.vehicle_id:
            return latest_visit.vehicle_id

        latest_plan = self.env["route.plan"].search([
            ("user_id", "=", self.env.user.id),
            ("vehicle_id", "!=", False),
        ], order="date desc, id desc", limit=1)
        return latest_plan.vehicle_id if latest_plan else False

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if not self.env.company.route_enable_direct_return:
            raise UserError(_("Direct Return is disabled in Route Settings."))
        if "vehicle_id" in self._fields and not vals.get("vehicle_id"):
            vehicle = self._default_vehicle()
            if vehicle:
                vals["vehicle_id"] = vehicle.id
        visit_id = self.env.context.get("default_visit_id") or self.env.context.get("route_visit_id")
        if visit_id and "visit_id" in self._fields:
            vals.setdefault("visit_id", visit_id)
        if not vals.get("outlet_id"):
            outlet = self.env["route.outlet"].search([
                ("outlet_operation_mode", "=", "direct_sale"),
                ("active", "=", True),
            ], order="id desc", limit=1)
            if outlet:
                vals["outlet_id"] = outlet.id
        return vals

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        for rec in self:
            if not rec.outlet_id:
                continue
            if not rec.vehicle_id:
                rec.vehicle_id = self._default_vehicle()
            if rec.sale_order_id and rec.sale_order_id.route_outlet_id != rec.outlet_id:
                rec.sale_order_id = False
                rec.reference_picking_id = False
        if self:
            return {"domain": {"reference_picking_id": self._get_reference_picking_domain()}}

    def _get_reference_picking_domain(self):
        self.ensure_one()
        domain = [("state", "=", "done")]
        if "picking_type_code" in self.env["stock.picking"]._fields:
            domain.append(("picking_type_code", "=", "outgoing"))
        if self.sale_order_id:
            domain.append(("origin", "=", self.sale_order_id.name))
        elif self.partner_id:
            domain.append(("partner_id", "=", self.partner_id.id))
        return domain

    @api.onchange("sale_order_id")
    def _onchange_sale_order_id(self):
        for rec in self:
            if rec.sale_order_id and rec.sale_order_id.route_outlet_id:
                rec.outlet_id = rec.sale_order_id.route_outlet_id
            if rec.reference_picking_id and rec.sale_order_id and rec.reference_picking_id.origin != rec.sale_order_id.name:
                rec.reference_picking_id = False
            if rec.reference_picking_id and not rec.sale_order_id and rec.partner_id and rec.reference_picking_id.partner_id != rec.partner_id:
                rec.reference_picking_id = False
        if self:
            return {"domain": {"reference_picking_id": self._get_reference_picking_domain()}}

    def _get_customer_location(self):
        self.ensure_one()
        partner = self.partner_id or self.outlet_id.partner_id
        if partner and "property_stock_customer" in partner._fields and partner.property_stock_customer:
            return partner.property_stock_customer
        customer_location = self.env.ref("stock.stock_location_customers", raise_if_not_found=False)
        if customer_location:
            return customer_location
        raise UserError(_("Customer location could not be determined for this return."))

    def _get_vehicle_return_location(self):
        self.ensure_one()
        vehicle = self.vehicle_id or self._default_vehicle()
        if vehicle and getattr(vehicle, "stock_location_id", False):
            return vehicle.stock_location_id
        raise UserError(_("Vehicle stock location is required for saleable or slow-moving direct returns."))

    def _get_default_destination_for_reason(self, reason):
        self.ensure_one()
        company = self.company_id or self.env.company
        if reason in ("saleable", "slow_moving"):
            return self._get_vehicle_return_location()
        if reason in ("damaged", "expired"):
            if company.return_damaged_location_id:
                return company.return_damaged_location_id
            raise UserError(_("Please configure Return Damaged Location in Return Settings."))
        if reason == "near_expiry":
            if company.return_near_expiry_location_id:
                return company.return_near_expiry_location_id
            if company.return_damaged_location_id:
                return company.return_damaged_location_id
            raise UserError(_("Please configure Return Near Expiry Location in Return Settings."))
        return False

    def _get_incoming_picking_type(self):
        self.ensure_one()
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.company_id.id)], limit=1)
        if warehouse and warehouse.in_type_id:
            return warehouse.in_type_id
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "incoming"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if picking_type:
            return picking_type
        raise UserError(_("No incoming picking type was found for this company."))

    def _get_or_create_lot(self, product, lot_name):
        self.ensure_one()
        if not lot_name:
            return False
        lot = self.env["stock.lot"].search([
            ("name", "=", lot_name),
            ("product_id", "=", product.id),
            ("company_id", "in", [False, self.company_id.id]),
        ], limit=1)
        if lot:
            return lot
        return self.env["stock.lot"].create({
            "name": lot_name,
            "product_id": product.id,
            "company_id": self.company_id.id,
        })

    def action_create_pickings(self):
        self.ensure_one()
        self._ensure_direct_return_enabled()
        if self.state != "draft":
            raise UserError(_("Only draft direct returns can generate return pickings."))
        if not self.outlet_id:
            raise UserError(_("Outlet is required."))
        if self.outlet_id.outlet_operation_mode != "direct_sale":
            raise UserError(_("Create Direct Return is allowed only for Direct Sale outlets."))
        if not self.partner_id:
            raise UserError(_("Related Contact is required on the outlet before creating direct returns."))
        if not self.line_ids:
            raise UserError(_("Please add at least one return line."))

        picking_type = self._get_incoming_picking_type()
        customer_location = self._get_customer_location()
        lines_by_dest = defaultdict(lambda: self.env["route.direct.return.line"])

        for line in self.line_ids:
            if not line.product_id:
                raise UserError(_("Every return line must have a product."))
            if line.quantity <= 0:
                raise UserError(_("Return quantity must be greater than zero for product %s.") % line.product_id.display_name)
            if self.route_enable_lot_serial_tracking:
                if line.product_id.tracking != "none" and not line.lot_name:
                    raise UserError(_("Lot/Serial is required for tracked product %s.") % line.product_id.display_name)
            else:
                if line.product_id.tracking != "none":
                    raise UserError(
                        _("Product %s is tracked in Inventory. Enable Route Lot/Serial Workflow or use a non-tracked product for this direct return.")
                        % line.product_id.display_name
                    )
                if line.lot_name:
                    line.lot_name = False
                if line.expiry_date:
                    line.expiry_date = False
            if not self.route_enable_expiry_tracking and line.expiry_date:
                line.expiry_date = False
            if not line.destination_location_id:
                line.destination_location_id = self._get_default_destination_for_reason(line.return_reason)
            lines_by_dest[line.destination_location_id] |= line

        created_pickings = self.env["stock.picking"]
        for destination, lines in lines_by_dest.items():
            picking_vals = {
                "picking_type_id": picking_type.id,
                "location_id": customer_location.id,
                "location_dest_id": destination.id,
                "origin": self.name,
                "partner_id": self.partner_id.id,
                "company_id": self.company_id.id,
                "move_type": "direct",
                "route_direct_return_id": self.id,
            }
            picking = self.env["stock.picking"].create(picking_vals)
            created_pickings |= picking

            moves = self.env["stock.move"]
            for line in lines:
                move = self.env["stock.move"].create({
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.quantity,
                    "product_uom": (line.uom_id or line.product_id.uom_id).id,
                    "location_id": customer_location.id,
                    "location_dest_id": destination.id,
                    "picking_id": picking.id,
                    "company_id": self.company_id.id,
                    "description_picking": _("%(reason)s | Unit Price: %(price).2f | Amount: %(amount).2f") % {
                        "reason": line.return_reason_label or _("Direct Return"),
                        "price": line.estimated_unit_price or 0.0,
                        "amount": line.estimated_amount or 0.0,
                    },
                    "route_direct_return_line_id": line.id,
                    "route_direct_return_unit_price": line.estimated_unit_price or 0.0,
                    "route_direct_return_estimated_amount": line.estimated_amount or 0.0,
                })
                line.picking_id = picking
                moves |= move

            if picking.state == "draft":
                picking.action_confirm()

            for move, line in zip(moves, lines):
                ml_vals = {
                    "picking_id": picking.id,
                    "move_id": move.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "quantity": line.quantity,
                    "location_id": customer_location.id,
                    "location_dest_id": destination.id,
                }
                if self.route_enable_lot_serial_tracking and move.product_id.tracking != "none":
                    lot = self._get_or_create_lot(move.product_id, line.lot_name)
                    if lot:
                        ml_vals["lot_id"] = lot.id
                self.env["stock.move.line"].create(ml_vals)

            result = picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()
            if isinstance(result, dict):
                return result

        self.state = "done"
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["name"] = _("Direct Return Pickings")
        action["domain"] = [("id", "in", created_pickings.ids)]
        if len(created_pickings) == 1:
            form_view = self.env.ref("stock.view_picking_form", raise_if_not_found=False)
            if form_view:
                action["views"] = [(form_view.id, "form")]
            action["res_id"] = created_pickings.id
            action["view_mode"] = "form"
        return action

    def action_view_pickings(self):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["name"] = _("Direct Return Pickings")
        action["domain"] = [("id", "in", self.picking_ids.ids)]
        if len(self.picking_ids) == 1:
            form_view = self.env.ref("stock.view_picking_form", raise_if_not_found=False)
            if form_view:
                action["views"] = [(form_view.id, "form")]
            action["res_id"] = self.picking_ids.id
            action["view_mode"] = "form"
        return action


class RouteDirectReturnLine(models.Model):
    _name = "route.direct.return.line"
    _description = "Route Direct Return Line"
    _order = "id"

    return_id = fields.Many2one("route.direct.return", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="return_id.company_id", store=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Product", required=True, domain=[("sale_ok", "=", True)])
    quantity = fields.Float(string="Qty", required=True, default=1.0)
    uom_id = fields.Many2one("uom.uom", string="UoM", ondelete="restrict", required=True)
    lot_name = fields.Char(string="Lot/Serial")
    expiry_date = fields.Date(string="Expiry")
    currency_id = fields.Many2one(related="return_id.company_id.currency_id", store=False, readonly=True)
    estimated_unit_price = fields.Monetary(
        string="Estimated Unit Price",
        currency_field="currency_id",
        compute="_compute_estimated_amount",
        store=False,
        readonly=True,
    )
    estimated_amount = fields.Monetary(
        string="Estimated Amount",
        currency_field="currency_id",
        compute="_compute_estimated_amount",
        store=False,
        readonly=True,
    )
    route_enable_lot_serial_tracking = fields.Boolean(related="return_id.route_enable_lot_serial_tracking", readonly=True, store=False)
    route_enable_expiry_tracking = fields.Boolean(related="return_id.route_enable_expiry_tracking", readonly=True, store=False)
    return_reason = fields.Selection(
        [
            ("saleable", "Saleable Return"),
            ("damaged", "Damaged"),
            ("expired", "Expired"),
            ("near_expiry", "Near Expiry"),
            ("slow_moving", "Slow Moving"),
        ],
        string="Return Reason",
        required=True,
        default="saleable",
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Destination",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        required=True,
    )
    note = fields.Char(string="Line Note")
    picking_id = fields.Many2one("stock.picking", string="Generated Picking", readonly=True)
    return_reason_label = fields.Char(string="Reason Label", compute="_compute_return_reason_label")

    @api.depends("return_reason")
    def _compute_return_reason_label(self):
        mapping = dict(self._fields["return_reason"].selection)
        for line in self:
            line.return_reason_label = mapping.get(line.return_reason, False)

    @api.depends(
        "product_id",
        "quantity",
        "return_id.sale_order_id",
        "return_id.sale_order_id.order_line.price_unit",
        "return_id.reference_picking_id",
        "return_id.outlet_id",
    )
    def _compute_estimated_amount(self):
        SaleOrder = self.env["sale.order"]
        for line in self:
            unit_price = 0.0
            product = line.product_id
            direct_return = line.return_id

            if not product:
                line.estimated_unit_price = 0.0
                line.estimated_amount = 0.0
                continue

            sale_line = False
            if direct_return and direct_return.sale_order_id:
                sale_line = direct_return.sale_order_id.order_line.filtered(lambda l: l.product_id == product)[:1]

            if not sale_line and direct_return and direct_return.reference_picking_id:
                reference_picking = direct_return.reference_picking_id
                reference_order = getattr(reference_picking, "sale_id", False)
                if not reference_order and reference_picking.origin:
                    reference_order = SaleOrder.search([
                        ("name", "=", reference_picking.origin),
                        ("route_order_mode", "=", "direct_sale"),
                    ], limit=1)
                if reference_order:
                    sale_line = reference_order.order_line.filtered(lambda l: l.product_id == product)[:1]

            if not sale_line and direct_return and direct_return.outlet_id:
                latest_order = SaleOrder.search([
                    ("route_order_mode", "=", "direct_sale"),
                    ("route_outlet_id", "=", direct_return.outlet_id.id),
                    ("state", "not in", ["cancel"]),
                    ("order_line.product_id", "=", product.id),
                ], order="date_order desc, id desc", limit=1)
                if latest_order:
                    sale_line = latest_order.order_line.filtered(lambda l: l.product_id == product)[:1]

            if sale_line:
                unit_price = sale_line.price_unit or 0.0
            else:
                unit_price = product.lst_price or 0.0

            line.estimated_unit_price = unit_price
            line.estimated_amount = (line.quantity or 0.0) * unit_price

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id and not line.uom_id:
                line.uom_id = line.product_id.uom_id

    @api.onchange("return_reason")
    def _onchange_return_reason(self):
        for line in self:
            if line.return_id and line.return_reason:
                try:
                    line.destination_location_id = line.return_id._get_default_destination_for_reason(line.return_reason)
                except UserError:
                    line.destination_location_id = False

    @api.onchange("route_enable_lot_serial_tracking", "route_enable_expiry_tracking")
    def _onchange_route_feature_flags(self):
        for line in self:
            if not line.route_enable_lot_serial_tracking:
                line.lot_name = False
                line.expiry_date = False
            elif not line.route_enable_expiry_tracking:
                line.expiry_date = False

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Return quantity must be greater than zero."))
