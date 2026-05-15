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
    pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Pricelist",
        compute="_compute_pricelist_id",
        store=False,
        readonly=True,
        help="Pricelist used to price this direct return. Open direct returns use the outlet/customer direct-sale pricelist; reference documents are kept for tracking only.",
    )
    route_reference_product_ids = fields.Many2many(
        "product.product",
        string="Reference Return Products",
        compute="_compute_route_reference_product_ids",
        store=False,
        help="Products found in the selected reference sale order or delivery. Open direct returns can still use other saleable products when needed.",
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

    @api.depends("sale_order_id.pricelist_id", "outlet_id.direct_sale_pricelist_id", "outlet_id.partner_id.property_product_pricelist")
    def _compute_pricelist_id(self):
        for rec in self:
            rec.pricelist_id = rec._route_get_effective_pricelist()

    def _route_get_effective_pricelist(self):
        self.ensure_one()
        if self.outlet_id and getattr(self.outlet_id, "direct_sale_pricelist_id", False):
            return self.outlet_id.direct_sale_pricelist_id
        if self.sale_order_id and self.sale_order_id.pricelist_id:
            return self.sale_order_id.pricelist_id
        if self.outlet_id and self.outlet_id.partner_id and getattr(self.outlet_id.partner_id, "property_product_pricelist", False):
            return self.outlet_id.partner_id.property_product_pricelist
        return self.env["product.pricelist"]

    def _route_has_reference_return_source(self):
        self.ensure_one()
        return bool(self.sale_order_id or self.reference_picking_id)

    def _route_get_reference_sale_orders(self):
        self.ensure_one()
        SaleOrder = self.env["sale.order"]
        orders = SaleOrder.browse()

        if self.sale_order_id:
            orders |= self.sale_order_id

        reference_picking = self.reference_picking_id
        if reference_picking:
            picking_sale = getattr(reference_picking, "sale_id", False)
            if picking_sale:
                orders |= picking_sale
            elif reference_picking.origin:
                origin_order = SaleOrder.search([
                    ("name", "=", reference_picking.origin),
                    ("route_order_mode", "=", "direct_sale"),
                ], limit=1)
                if origin_order:
                    orders |= origin_order

        visit_sale_order = getattr(self.visit_id, "sale_order_id", False)
        if visit_sale_order and getattr(visit_sale_order, "route_order_mode", False) == "direct_sale":
            orders |= visit_sale_order

        return orders

    def _route_get_reference_products(self):
        self.ensure_one()
        Product = self.env["product.product"]
        products = Product.browse()

        orders = self._route_get_reference_sale_orders()
        if orders:
            products |= orders.mapped("order_line").filtered(
                lambda line: not line.display_type and line.product_id and line.product_id.sale_ok
            ).mapped("product_id")

        reference_picking = self.reference_picking_id
        if reference_picking:
            if "move_line_ids" in reference_picking._fields:
                products |= reference_picking.mapped("move_line_ids").filtered(
                    lambda move_line: move_line.product_id and move_line.product_id.sale_ok
                ).mapped("product_id")
            if "move_ids" in reference_picking._fields:
                products |= reference_picking.mapped("move_ids").filtered(
                    lambda move: move.product_id and move.product_id.sale_ok
                ).mapped("product_id")
            if "move_ids_without_package" in reference_picking._fields:
                products |= reference_picking.mapped("move_ids_without_package").filtered(
                    lambda move: move.product_id and move.product_id.sale_ok
                ).mapped("product_id")

        return products

    @api.depends(
        "sale_order_id",
        "sale_order_id.order_line.product_id",
        "reference_picking_id",
        "visit_id",
    )
    def _compute_route_reference_product_ids(self):
        for rec in self:
            rec.route_reference_product_ids = rec._route_get_reference_products()

    def action_back_to_outlet_form(self):
        self.ensure_one()
        outlet = self.outlet_id
        if not outlet:
            outlet_id = self.env.context.get("route_outlet_back_id") or self.env.context.get("default_outlet_id")
            outlet = self.env["route.outlet"].browse(outlet_id).exists()
        if outlet:
            return outlet.action_open_pda_form()
        home = self.env["route.pda.home"].create({})
        home._refresh_dashboard_snapshot()
        view = self.env.ref("route_core.view_route_pda_outlet_center_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Customer Profiles"),
            "res_model": "route.pda.home",
            "res_id": home.id,
            "view_mode": "form",
            "target": "main",
            "context": {"create": 0, "edit": 0, "delete": 0},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_route_direct_return_back_to_visit(self):
        self.ensure_one()
        visit_action = self._get_route_visit_return_action() if self.visit_id else False
        if visit_action:
            return visit_action
        return self.action_back_to_outlet_form()

    def _action_route_direct_return_line_popup(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("You can add return products only while the direct return is still Draft."))
        view = self.env.ref("route_core.view_route_direct_return_line_form_mobile", raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Add / Scan Return Product"),
            "res_model": "route.direct.return.line",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_return_id": self.id,
                "default_quantity": 1.0,
                "route_direct_return_mobile_line": True,
            },
            "views": [(view.id, "form")] if view else [(False, "form")],
        }

    def action_route_direct_return_add_product(self):
        return self._action_route_direct_return_line_popup()

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
            if vals.get("outlet_id") and not vals.get("vehicle_id"):
                outlet = self.env["route.outlet"].browse(vals["outlet_id"]).exists()
                vehicle = self._default_vehicle(outlet=outlet)
                if vehicle:
                    vals["vehicle_id"] = vehicle.id
        return super().create(vals_list)

    @api.model
    def _default_vehicle(self, outlet=False):
        outlet = outlet or self.env["route.outlet"].browse(
            self.env.context.get("default_outlet_id") or self.env.context.get("route_outlet_id") or False
        ).exists()
        if outlet and "default_vehicle_id" in outlet._fields and outlet.default_vehicle_id:
            return outlet.default_vehicle_id

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
            outlet = self.env["route.outlet"].browse(vals.get("outlet_id") or self.env.context.get("default_outlet_id") or False).exists()
            vehicle = self._default_vehicle(outlet=outlet)
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
        outlet = self.env["route.outlet"].browse(vals.get("outlet_id") or False).exists()
        if outlet and not vals.get("vehicle_id"):
            vehicle = self._default_vehicle(outlet=outlet)
            if vehicle:
                vals["vehicle_id"] = vehicle.id
        return vals

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        for rec in self:
            if not rec.outlet_id:
                continue
            if not rec.vehicle_id:
                rec.vehicle_id = self._default_vehicle(outlet=rec.outlet_id)
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
        vehicle = self.vehicle_id or self._default_vehicle(outlet=self.outlet_id)
        if vehicle and getattr(vehicle, "stock_location_id", False):
            return vehicle.stock_location_id
        raise UserError(_("Vehicle stock location is required for saleable or slow-moving direct returns."))

    def _get_default_destination_for_reason(self, reason):
        self.ensure_one()
        company = self.company_id or self.env.company
        outlet = self.outlet_id
        if reason in ("saleable", "slow_moving"):
            if outlet and "saleable_return_location_id" in outlet._fields and outlet.saleable_return_location_id:
                return outlet.saleable_return_location_id
            return self._get_vehicle_return_location()
        if reason in ("damaged", "expired"):
            if outlet and "damaged_return_location_id" in outlet._fields and outlet.damaged_return_location_id:
                return outlet.damaged_return_location_id
            if company.return_damaged_location_id:
                return company.return_damaged_location_id
            raise UserError(_("Please configure Damaged Return Location on the outlet or Return Damaged Location in Return Settings."))
        if reason == "near_expiry":
            if outlet and "expiry_return_location_id" in outlet._fields and outlet.expiry_return_location_id:
                return outlet.expiry_return_location_id
            if company.return_near_expiry_location_id:
                return company.return_near_expiry_location_id
            if company.return_damaged_location_id:
                return company.return_damaged_location_id
            raise UserError(_("Please configure Expired / Near Expiry Return Location on the outlet or Return Near Expiry Location in Return Settings."))
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
        lot_name = (lot_name or "").strip()
        if not product or not lot_name:
            return False
        lot = self.env["stock.lot"].search([
            ("name", "=", lot_name),
            ("product_id", "=", product.id),
            ("company_id", "in", [False, self.company_id.id]),
        ], limit=1)
        if lot:
            return lot
        return self.env["stock.lot"].sudo().create({
            "name": lot_name,
            "product_id": product.id,
            "company_id": self.company_id.id,
        })

    def _get_route_visit_return_action(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit or getattr(visit, "visit_execution_mode", False) != "direct_sales":
            return False
        if hasattr(visit, "_get_pda_form_action"):
            return visit._get_pda_form_action()
        return {
            "type": "ir.actions.act_window",
            "name": _("PDA Visit"),
            "res_model": "route.visit",
            "res_id": visit.id,
            "view_mode": "form",
            "target": "current",
        }

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
                if line.product_id.tracking != "none":
                    line._route_prepare_lot_for_picking()
                    if not (line.lot_id or line.lot_name):
                        raise UserError(
                            _(
                                "Lot/Serial is required for tracked product %(product)s. Please open the return line and choose an existing lot/serial or type a manual lot/serial number."
                            )
                            % {"product": line.product_id.display_name}
                        )
            else:
                if line.product_id.tracking != "none":
                    raise UserError(
                        _("Product %s is tracked in Inventory. Enable Route Lot/Serial Workflow or use a non-tracked product for this direct return.")
                        % line.product_id.display_name
                    )
                if line.lot_id:
                    line.lot_id = False
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

            auto_move_lines = self.env["stock.move.line"]
            for move in moves:
                if "move_line_ids" in move._fields:
                    auto_move_lines |= move.move_line_ids
            if auto_move_lines:
                auto_move_lines.sudo().unlink()

            for move, line in zip(moves, lines):
                lot = False
                if self.route_enable_lot_serial_tracking and move.product_id.tracking != "none":
                    lot = line._route_prepare_lot_for_picking()
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
                    lot = lot or line.lot_id or self._get_or_create_lot(move.product_id, line.lot_name)
                    if lot:
                        ml_vals["lot_id"] = lot.id
                    elif "lot_name" in self.env["stock.move.line"]._fields and line.lot_name:
                        ml_vals["lot_name"] = line.lot_name
                self.env["stock.move.line"].create(ml_vals)

            result = picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()
            if isinstance(result, dict):
                return result

        self.state = "done"
        visit_action = self._get_route_visit_return_action()
        if visit_action:
            return visit_action
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
    route_product_barcode = fields.Char(
        string="Barcode",
        copy=False,
    )
    route_product_image_128 = fields.Image(
        string="Product Image",
        related="product_id.image_128",
        readonly=True,
        store=False,
    )
    route_available_product_ids = fields.Many2many(
        "product.product",
        string="Available Return Products",
        compute="_compute_route_available_product_ids",
        store=False,
        help="Saleable products available for direct return entry. Reference products are used only to suggest price, discount, taxes, UoM, and lot defaults.",
    )
    quantity = fields.Float(string="Qty", required=True, default=1.0)
    uom_id = fields.Many2one("uom.uom", string="UoM", ondelete="restrict", required=True)
    available_lot_ids = fields.Many2many(
        "stock.lot",
        string="Available Return Lots",
        compute="_compute_available_lot_ids",
        store=False,
    )
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        domain="[('id', 'in', available_lot_ids)]",
        ondelete="restrict",
    )
    lot_name = fields.Char(string="Manual Lot/Serial")
    expiry_date = fields.Date(string="Expiry")
    expiry_month_label = fields.Char(
        string="Expiry",
        compute="_compute_expiry_month_label",
        store=False,
        readonly=True,
        help="Compact year-month expiry label for the Route/PDA return card.",
    )
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
    reference_discount = fields.Float(
        string="Discount (%)",
        compute="_compute_estimated_amount",
        store=False,
        readonly=True,
        help="Discount copied from the matching reference sale order line when available.",
    )
    route_reference_tax_ids = fields.Many2many(
        "account.tax",
        string="Reference Taxes",
        compute="_compute_estimated_amount",
        store=False,
        readonly=True,
        help="Taxes copied from the matching reference sale order line when available.",
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

    @api.depends("expiry_date")
    def _compute_expiry_month_label(self):
        for line in self:
            expiry_date = fields.Date.to_date(line.expiry_date) if line.expiry_date else False
            line.expiry_month_label = expiry_date.strftime("%Y-%m") if expiry_date else False

    @api.depends(
        "return_id",
        "return_id.sale_order_id",
        "return_id.reference_picking_id",
        "return_id.route_reference_product_ids",
    )
    def _compute_route_available_product_ids(self):
        Product = self.env["product.product"]
        saleable_products = Product.search([("sale_ok", "=", True)])
        for line in self:
            # Direct Return must support both reference returns and open returns.
            # The reference sale/delivery is used to suggest price, discount, taxes, UoM, and lots,
            # but it must not block returning older products sold in previous visits.
            line.route_available_product_ids = saleable_products

    def _route_product_allowed_by_reference(self, product):
        self.ensure_one()
        # Kept for compatibility with older code paths. Open direct returns are allowed.
        return True

    def _route_get_reference_lots(self):
        self.ensure_one()
        Lot = self.env["stock.lot"]
        product = self.product_id
        direct_return = self.return_id
        if not product or not direct_return:
            return Lot

        lots = Lot
        sale_order = direct_return.sale_order_id
        reference_picking = direct_return.reference_picking_id

        if sale_order and "route_lot_id" in self.env["sale.order.line"]._fields:
            lots |= sale_order.order_line.filtered(
                lambda line: not line.display_type and line.product_id == product and line.route_lot_id
            ).mapped("route_lot_id")

        if reference_picking:
            lots |= reference_picking.move_line_ids.filtered(
                lambda move_line: move_line.product_id == product and move_line.lot_id
            ).mapped("lot_id")

        if sale_order:
            pickings = self.env["stock.picking"].search([
                ("origin", "=", sale_order.name),
                ("state", "=", "done"),
            ])
            lots |= pickings.mapped("move_line_ids").filtered(
                lambda move_line: move_line.product_id == product and move_line.lot_id
            ).mapped("lot_id")

        return lots

    def _route_get_available_return_lots(self):
        self.ensure_one()
        Lot = self.env["stock.lot"]
        product = self.product_id
        if (
            not self.route_enable_lot_serial_tracking
            or not product
            or product.tracking == "none"
        ):
            return Lot

        reference_lots = self._route_get_reference_lots()
        if reference_lots:
            return reference_lots.sorted(
                key=lambda lot: (
                    lot.expiration_date or fields.Datetime.to_datetime("2099-12-31 00:00:00"),
                    lot.name or "",
                    lot.id or 0,
                )
            )

        domain = [
            ("product_id", "=", product.id),
            ("company_id", "in", [False, self.company_id.id if self.company_id else self.env.company.id]),
        ]
        return Lot.search(domain, order="expiration_date, name, id")

    @api.depends(
        "product_id",
        "return_id.sale_order_id",
        "return_id.reference_picking_id",
        "return_id.route_enable_lot_serial_tracking",
    )
    def _compute_available_lot_ids(self):
        for line in self:
            line.available_lot_ids = line._route_get_available_return_lots()

    @api.depends("return_reason")
    def _compute_return_reason_label(self):
        mapping = dict(self._fields["return_reason"].selection)
        for line in self:
            line.return_reason_label = mapping.get(line.return_reason, False)

    def _route_direct_return_line_matches_lot(self, sale_line):
        self.ensure_one()
        selected_lot = self.lot_id
        lot_name = (self.lot_name or "").strip()
        if not selected_lot and not lot_name:
            return True
        sale_lot = getattr(sale_line, "route_lot_id", False)
        if selected_lot and sale_lot and sale_lot == selected_lot:
            return True
        if lot_name and sale_lot and (sale_lot.name or "").strip() == lot_name:
            return True
        return False

    def _route_get_discounted_sale_line_unit_price(self, sale_line):
        """Return the reference sale unit price before discount, converted to the return UoM.

        The matching discount percentage is displayed separately and applied in
        _compute_estimated_amount so return lines mirror the original sale line:
        Unit Price + Discount % + Amount.
        """
        self.ensure_one()
        if not sale_line:
            return 0.0

        unit_price = sale_line.price_unit or 0.0

        if "product_uom_id" in sale_line._fields and sale_line.product_uom_id:
            sale_uom = sale_line.product_uom_id
        elif "product_uom" in sale_line._fields and sale_line.product_uom:
            sale_uom = sale_line.product_uom
        else:
            sale_uom = False
        return_uom = self.uom_id or self.product_id.uom_id
        if sale_uom and return_uom and sale_uom != return_uom and hasattr(sale_uom, "_compute_price"):
            unit_price = sale_uom._compute_price(unit_price, return_uom)
        return unit_price or 0.0

    def _route_get_return_pricelist(self):
        self.ensure_one()
        if self.return_id:
            return self.return_id._route_get_effective_pricelist()
        return self.env["product.pricelist"]

    def _route_match_pricelist_item(self, item, product, quantity, order_date):
        if not item or not product:
            return False
        if getattr(item, "date_start", False) and order_date and item.date_start > order_date:
            return False
        if getattr(item, "date_end", False) and order_date and item.date_end < order_date:
            return False
        if getattr(item, "min_quantity", 0.0) and (quantity or 0.0) < item.min_quantity:
            return False

        applied_on = getattr(item, "applied_on", False) or ""
        if applied_on in ("0_product_variant", "product_variant", "variant"):
            return bool(getattr(item, "product_id", False) and item.product_id == product)
        if applied_on in ("1_product", "product", "product_template", "template"):
            return bool(getattr(item, "product_tmpl_id", False) and item.product_tmpl_id == product.product_tmpl_id)
        if applied_on in ("2_product_category", "category", "product_category"):
            category = getattr(item, "categ_id", False)
            if not category or not product.categ_id:
                return False
            return product.categ_id == category or product.categ_id.id in self.env["product.category"].search([("id", "child_of", category.id)]).ids
        if applied_on in ("3_global", "global", "all_products", ""):
            return True
        return True

    def _route_pricelist_item_specificity(self, item):
        applied_on = getattr(item, "applied_on", False) or ""
        if applied_on in ("0_product_variant", "product_variant", "variant"):
            return 40
        if applied_on in ("1_product", "product", "product_template", "template"):
            return 30
        if applied_on in ("2_product_category", "category", "product_category"):
            return 20
        return 10

    def _route_get_pricelist_discount_percent(self, pricelist):
        self.ensure_one()
        if not pricelist or not self.product_id:
            return False
        quantity = self.quantity or 1.0
        return_date = self.return_id.return_date if self.return_id and self.return_id.return_date else fields.Date.context_today(self)
        item_ids = getattr(pricelist, "item_ids", self.env["product.pricelist.item"])
        matched_items = item_ids.filtered(lambda item: self._route_match_pricelist_item(item, self.product_id, quantity, return_date))
        if not matched_items:
            return False
        item = matched_items.sorted(
            key=lambda item: (
                self._route_pricelist_item_specificity(item),
                getattr(item, "min_quantity", 0.0) or 0.0,
                item.id or 0,
            ),
            reverse=True,
        )[:1]
        compute_price = getattr(item, "compute_price", False)
        if compute_price == "percentage" and "percent_price" in item._fields:
            return item.percent_price or 0.0
        if compute_price == "formula" and "price_discount" in item._fields and item.price_discount:
            discount = item.price_discount
            if abs(discount) <= 1.0:
                discount *= 100.0
            return abs(discount)
        return False

    def _route_get_base_unit_price_for_discount(self):
        self.ensure_one()
        product = self.product_id
        if not product:
            return 0.0
        price = product.lst_price or 0.0
        return_uom = self.uom_id or product.uom_id
        if product.uom_id and return_uom and product.uom_id != return_uom and hasattr(product.uom_id, "_compute_price"):
            price = product.uom_id._compute_price(price, return_uom)
        return price

    def _route_get_outlet_pricelist_return_unit_price(self):
        self.ensure_one()
        product = self.product_id
        direct_return = self.return_id
        if not product:
            return 0.0

        pricelist = self._route_get_return_pricelist()

        quantity = self.quantity or 1.0
        uom = self.uom_id or product.uom_id
        partner = direct_return.partner_id if direct_return else False
        return_date = direct_return.return_date if direct_return else fields.Date.context_today(self)

        if pricelist and hasattr(pricelist, "_get_product_price"):
            try:
                return pricelist._get_product_price(
                    product,
                    quantity,
                    partner=partner,
                    date=return_date,
                    uom_id=uom,
                ) or 0.0
            except TypeError:
                try:
                    return pricelist._get_product_price(product, quantity, partner) or 0.0
                except Exception:
                    pass
            except Exception:
                pass
        return product.lst_price or 0.0

    def _route_find_reference_sale_line(self):
        self.ensure_one()
        SaleOrder = self.env["sale.order"]
        product = self.product_id
        direct_return = self.return_id
        if not product or not direct_return:
            return self.env["sale.order.line"]

        orders = SaleOrder.browse()
        if direct_return.sale_order_id:
            orders |= direct_return.sale_order_id

        if direct_return.reference_picking_id:
            reference_picking = direct_return.reference_picking_id
            reference_order = getattr(reference_picking, "sale_id", False)
            if not reference_order and reference_picking.origin:
                reference_order = SaleOrder.search([
                    ("name", "=", reference_picking.origin),
                    ("route_order_mode", "=", "direct_sale"),
                ], limit=1)
            if reference_order:
                orders |= reference_order

        if not orders and direct_return.outlet_id:
            orders |= SaleOrder.search([
                ("route_order_mode", "=", "direct_sale"),
                ("route_outlet_id", "=", direct_return.outlet_id.id),
                ("state", "not in", ["cancel"]),
                ("order_line.product_id", "=", product.id),
            ], order="date_order desc, id desc", limit=1)

        sale_lines = orders.mapped("order_line").filtered(
            lambda l: not l.display_type and l.product_id == product
        )

        # If the selected reference order/delivery does not contain this product, treat the line
        # as an open return and try the latest historical direct-sale line for the same outlet.
        # This keeps old-visit returns usable while still copying the best available commercial terms.
        if not sale_lines and direct_return.outlet_id:
            historical_orders = SaleOrder.search([
                ("route_order_mode", "=", "direct_sale"),
                ("route_outlet_id", "=", direct_return.outlet_id.id),
                ("state", "not in", ["cancel"]),
                ("order_line.product_id", "=", product.id),
            ], order="date_order desc, id desc", limit=5)
            sale_lines = historical_orders.mapped("order_line").filtered(
                lambda l: not l.display_type and l.product_id == product
            )

        if not sale_lines:
            return self.env["sale.order.line"]

        matching_lot_lines = sale_lines.filtered(lambda l: self._route_direct_return_line_matches_lot(l))
        sale_lines = matching_lot_lines or sale_lines
        return sale_lines.sorted(key=lambda l: (l.order_id.date_order or fields.Datetime.now(), l.id or 0), reverse=True)[:1]

    def _route_apply_reference_sale_line_defaults(self):
        """Suggest UoM and lot from the reference sale/delivery when possible."""
        for line in self:
            if not line.product_id:
                continue

            sale_line = line._route_find_reference_sale_line()
            if sale_line:
                if "product_uom_id" in sale_line._fields and sale_line.product_uom_id:
                    line.uom_id = sale_line.product_uom_id
                elif "product_uom" in sale_line._fields and sale_line.product_uom:
                    line.uom_id = sale_line.product_uom
                elif not line.uom_id:
                    line.uom_id = line.product_id.uom_id

                sale_lot = getattr(sale_line, "route_lot_id", False)
                if (
                    line.route_enable_lot_serial_tracking
                    and line.product_id.tracking != "none"
                    and sale_lot
                    and not line.lot_id
                ):
                    line.lot_id = sale_lot
                    line._onchange_lot_id()

            if (
                line.route_enable_lot_serial_tracking
                and line.product_id.tracking != "none"
                and not line.lot_id
            ):
                available_lots = line._route_get_available_return_lots()
                if available_lots:
                    line.lot_id = available_lots[:1]
                    line._onchange_lot_id()

    def _route_build_auto_lot_name(self):
        """Build a safe fallback lot name for open direct returns.

        Open returns can include products from old visits where the salesperson does not
        know the original lot. Odoo still requires a lot for tracked products, so we create
        a clearly traceable return lot instead of blocking the return picking.
        """
        self.ensure_one()
        return_name = (self.return_id.name or "DIRECT-RETURN") if self.return_id else "DIRECT-RETURN"
        return_name = return_name.replace("/", "-").replace(" ", "-")
        product_part = self.product_id.default_code or str(self.product_id.id or "PRODUCT")
        product_part = str(product_part).replace("/", "-").replace(" ", "-")
        line_part = str(self.id or "NEW")
        return "OPEN-RETURN-%s-%s-%s" % (return_name, product_part, line_part)

    def _route_prepare_lot_for_picking(self):
        """Ensure tracked open-return lines have a valid lot before stock picking validation."""
        self.ensure_one()
        product = self.product_id
        direct_return = self.return_id
        if (
            not direct_return
            or not direct_return.route_enable_lot_serial_tracking
            or not product
            or product.tracking == "none"
        ):
            return False

        if self.lot_id:
            if not self.lot_name:
                self.lot_name = self.lot_id.name or False
            return self.lot_id

        self._route_apply_reference_sale_line_defaults()
        if self.lot_id:
            if not self.lot_name:
                self.lot_name = self.lot_id.name or False
            return self.lot_id

        lot_name = (self.lot_name or "").strip()
        if not lot_name:
            lot_name = self._route_build_auto_lot_name()
            self.lot_name = lot_name

        lot = direct_return._get_or_create_lot(product, lot_name)
        if lot:
            self.lot_id = lot
            self.lot_name = lot.name or lot_name
            self._onchange_lot_id()
        return lot

    @api.depends(
        "product_id",
        "quantity",
        "uom_id",
        "lot_id",
        "lot_name",
        "return_id.sale_order_id",
        "return_id.sale_order_id.pricelist_id",
        "return_id.sale_order_id.order_line.price_unit",
        "return_id.sale_order_id.order_line.discount",
        "return_id.sale_order_id.order_line.price_subtotal",
        "return_id.sale_order_id.order_line.price_total",
        "return_id.sale_order_id.order_line.route_lot_id",
        "return_id.reference_picking_id",
        "return_id.outlet_id",
        "return_id.outlet_id.direct_sale_pricelist_id",
    )
    def _compute_estimated_amount(self):
        for line in self:
            product = line.product_id
            if not product:
                line.estimated_unit_price = 0.0
                line.estimated_amount = 0.0
                line.reference_discount = 0.0
                line.route_reference_tax_ids = False
                continue

            sale_line = line._route_find_reference_sale_line()
            pricelist_discount = line._route_get_pricelist_discount_percent(line._route_get_return_pricelist())
            if sale_line:
                unit_price = line._route_get_discounted_sale_line_unit_price(sale_line)
                sale_discount = sale_line.discount if "discount" in sale_line._fields else 0.0
                if not sale_discount and pricelist_discount is not False:
                    sale_discount = pricelist_discount or 0.0
                    base_unit_price = line._route_get_base_unit_price_for_discount()
                    if base_unit_price:
                        unit_price = base_unit_price
                line.reference_discount = sale_discount or 0.0
                tax_field = "tax_ids" if "tax_ids" in sale_line._fields else ("tax_id" if "tax_id" in sale_line._fields else False)
                line.route_reference_tax_ids = getattr(sale_line, tax_field) if tax_field else False
            else:
                if pricelist_discount is not False:
                    unit_price = line._route_get_base_unit_price_for_discount()
                    line.reference_discount = pricelist_discount or 0.0
                else:
                    unit_price = line._route_get_outlet_pricelist_return_unit_price()
                    line.reference_discount = 0.0
                line.route_reference_tax_ids = False

            line.estimated_unit_price = unit_price
            discount_factor = 1.0 - ((line.reference_discount or 0.0) / 100.0)
            line.estimated_amount = (line.quantity or 0.0) * (unit_price or 0.0) * discount_factor

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            line.route_product_barcode = line.product_id.barcode if line.product_id else False
            if line.product_id and not line.uom_id:
                line.uom_id = line.product_id.uom_id
            if not line.product_id or line.product_id.tracking == "none" or not line.route_enable_lot_serial_tracking:
                line.lot_id = False
                line.lot_name = False
                line.expiry_date = False
                if line.product_id:
                    line._route_apply_reference_sale_line_defaults()
                continue
            available_lots = line._route_get_available_return_lots()
            if line.lot_id and line.lot_id not in available_lots:
                line.lot_id = False
            line._route_apply_reference_sale_line_defaults()

    @api.onchange("lot_id")
    def _onchange_lot_id(self):
        for line in self:
            if not line.lot_id:
                continue
            line.lot_name = line.lot_id.name or False
            if line.route_enable_expiry_tracking and "expiration_date" in line.lot_id._fields:
                line.expiry_date = fields.Date.to_date(line.lot_id.expiration_date) if line.lot_id.expiration_date else False
            elif not line.route_enable_expiry_tracking:
                line.expiry_date = False

    @api.onchange("lot_name", "product_id")
    def _onchange_lot_name(self):
        Lot = self.env["stock.lot"]
        for line in self:
            lot_name = (line.lot_name or "").strip()
            if line.lot_name and line.lot_name != lot_name:
                line.lot_name = lot_name
            if not lot_name or not line.product_id:
                continue
            if line.lot_id and (line.lot_id.name or "").strip() == lot_name:
                continue
            lot = Lot.search([
                ("name", "=", lot_name),
                ("product_id", "=", line.product_id.id),
                ("company_id", "in", [False, line.company_id.id if line.company_id else line.env.company.id]),
            ], limit=1)
            if lot:
                line.lot_id = lot
                line._onchange_lot_id()
            elif line.lot_id:
                line.lot_id = False

    @api.onchange("route_product_barcode")
    def _onchange_route_product_barcode_lookup(self):
        Product = self.env["product.product"]
        for line in self:
            barcode = (line.route_product_barcode or "").strip()
            if not barcode or (line.product_id and barcode == (line.product_id.barcode or "")):
                continue
            # Do not restrict barcode lookup to the selected reference sale/delivery.
            # Salespeople may need to return products sold in older visits.
            product = Product._route_find_product_by_barcode(barcode, extra_domain=[("sale_ok", "=", True)])
            if product:
                line.product_id = product
                line.route_product_barcode = product.barcode or barcode
                if not line.uom_id:
                    line.uom_id = product.uom_id
                line._onchange_product_id()
            else:
                line.product_id = False
                return {
                    "warning": {
                        "title": _("Product not found"),
                        "message": _(
                            "No saleable product was found for this barcode. Check the barcode or choose the product manually."
                        ),
                    }
                }

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
                line.lot_id = False
                line.lot_name = False
                line.expiry_date = False
            elif not line.route_enable_expiry_tracking:
                line.expiry_date = False

    @api.model_create_multi
    def create(self, vals_list):
        Lot = self.env["stock.lot"]
        Product = self.env["product.product"]
        for vals in vals_list:
            product = Product.browse(vals.get("product_id")).exists() if vals.get("product_id") else Product
            if product:
                vals.setdefault("route_product_barcode", product.barcode or False)
                vals.setdefault("uom_id", product.uom_id.id if product.uom_id else False)
            lot = Lot.browse(vals.get("lot_id")).exists() if vals.get("lot_id") else Lot
            if lot:
                vals.setdefault("lot_name", lot.name)
                if not vals.get("expiry_date") and "expiration_date" in lot._fields and lot.expiration_date:
                    vals["expiry_date"] = fields.Date.to_date(lot.expiration_date)
        lines = super().create(vals_list)
        lines._route_apply_reference_sale_line_defaults()
        for line in lines.filtered(lambda line: line.product_id and not line.route_product_barcode):
            line.route_product_barcode = line.product_id.barcode or False
        for line in lines.filtered(lambda line: line.product_id and line.product_id.tracking != "none" and line.route_enable_lot_serial_tracking and line.lot_name and not line.lot_id):
            lot = line.return_id._get_or_create_lot(line.product_id, line.lot_name) if line.return_id else False
            if lot:
                line.lot_id = lot
                line._onchange_lot_id()
        return lines

    def write(self, vals):
        vals = dict(vals)
        if vals.get("product_id") and "route_product_barcode" not in vals:
            product = self.env["product.product"].browse(vals["product_id"]).exists()
            if product:
                vals["route_product_barcode"] = product.barcode or False
                vals.setdefault("uom_id", product.uom_id.id if product.uom_id else False)
        if vals.get("lot_id"):
            lot = self.env["stock.lot"].browse(vals["lot_id"]).exists()
            if lot:
                vals.setdefault("lot_name", lot.name)
                if not vals.get("expiry_date") and "expiration_date" in lot._fields and lot.expiration_date:
                    vals["expiry_date"] = fields.Date.to_date(lot.expiration_date)
        return super().write(vals)

    @api.constrains("product_id", "return_id", "return_id.sale_order_id", "return_id.reference_picking_id")
    def _check_product_is_in_reference(self):
        # Open direct returns are allowed: the selected reference sale/delivery is a pricing/lot helper,
        # not a hard product restriction.
        return True

    @api.constrains("lot_id", "product_id")
    def _check_lot_product(self):
        for line in self:
            if line.lot_id and line.product_id and line.lot_id.product_id != line.product_id:
                raise ValidationError(
                    _("Selected Lot/Serial does not belong to product %s.")
                    % line.product_id.display_name
                )

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Return quantity must be greater than zero."))
