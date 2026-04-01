from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    route_order_mode = fields.Selection(
        [("standard", "Standard"), ("direct_sale", "Direct Sale")],
        string="Route Order Mode",
        default="standard",
        tracking=True,
    )
    route_outlet_id = fields.Many2one(
        "route.outlet",
        string="Route Outlet",
        domain=[("outlet_operation_mode", "=", "direct_sale"), ("active", "=", True)],
        ondelete="restrict",
        help="Direct-sale outlet linked to this sales order.",
    )
    route_source_location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        help="Internal source stock location used for direct sale fulfillment.",
    )
    route_payment_mode = fields.Selection(
        [("cash", "Cash"), ("bank", "Bank Transfer"), ("pos", "POS"), ("deferred", "Deferred")],
        string="Route Payment Mode",
        default="cash",
    )
    route_payment_due_date = fields.Date(string="Deferred Due Date")
    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        compute="_compute_route_visit_id",
        search="_search_route_visit_id",
        store=False,
        readonly=True,
        help="Direct sales stop linked to this order when the order is created from a direct sales route stop.",
    )
    direct_sale_payment_ids = fields.One2many(
        "route.visit.payment",
        "sale_order_id",
        string="Direct Sale Payments",
    )
    direct_sale_payment_count = fields.Integer(
        string="Payment Count",
        compute="_compute_direct_sale_payment_summary",
    )
    direct_sale_collected_amount = fields.Monetary(
        string="Collected Amount",
        currency_field="currency_id",
        compute="_compute_direct_sale_payment_summary",
    )
    direct_sale_remaining_due = fields.Monetary(
        string="Remaining Due",
        currency_field="currency_id",
        compute="_compute_direct_sale_payment_summary",
    )


    route_enable_direct_sale = fields.Boolean(
        related="company_id.route_enable_direct_sale",
        readonly=True,
        store=False,
    )
    route_operation_mode = fields.Selection(
        related="company_id.route_operation_mode",
        readonly=True,
        store=False,
    )
    route_enable_direct_return = fields.Boolean(
        related="company_id.route_enable_direct_return",
        readonly=True,
        store=False,
    )


    @api.depends("origin")
    def _compute_route_visit_id(self):
        Visit = self.env["route.visit"]
        names = {order.origin for order in self if order.origin and order.route_order_mode == "direct_sale"}
        visit_map = {}
        if names:
            visits = Visit.search([("name", "in", list(names))])
            visit_map = {visit.name: visit for visit in visits}
        for order in self:
            order.route_visit_id = visit_map.get(order.origin) if order.route_order_mode == "direct_sale" and order.origin else False

    def _search_route_visit_id(self, operator, value):
        if operator not in ("=", "in"):
            return [("id", "=", 0)]
        visit_ids = []
        if operator == "=":
            visit_ids = [value] if value else []
        elif isinstance(value, (list, tuple, set)):
            visit_ids = list(value)
        if not visit_ids:
            return [("id", "=", 0)]
        visits = self.env["route.visit"].browse(visit_ids).exists()
        names = [name for name in visits.mapped("name") if name]
        if not names:
            return [("id", "=", 0)]
        return [("origin", "in", names)]

    def _ensure_route_direct_sale_enabled(self):
        for order in self:
            if not order.company_id.route_operation_allows_direct_sale():
                raise UserError(_("Direct Sale is hidden because Route Operation Mode is Consignment Route."))
            if not order.company_id.route_enable_direct_sale:
                raise UserError(_("Direct Sale is disabled in Route Settings."))

    def _ensure_route_direct_return_enabled(self):
        for order in self:
            if not order.company_id.route_enable_direct_return:
                raise UserError(_("Direct Return is disabled in Route Settings."))

    @api.onchange("route_outlet_id")
    def _onchange_route_outlet_id(self):
        for order in self:
            if order.route_outlet_id and order.route_outlet_id.partner_id:
                partner = order.route_outlet_id.partner_id
                order.partner_id = partner
                if "partner_invoice_id" in order._fields:
                    order.partner_invoice_id = partner.address_get(["invoice"]).get("invoice") or partner.id
                if "partner_shipping_id" in order._fields:
                    order.partner_shipping_id = partner.address_get(["delivery"]).get("delivery") or partner.id

    @api.onchange("route_order_mode")
    def _onchange_route_order_mode(self):
        for order in self:
            if order.route_order_mode != "direct_sale":
                continue
            if not order.route_source_location_id:
                vehicle = order.env["route.vehicle"].search([("user_id", "=", order.env.user.id)], order="id desc", limit=1)
                if vehicle and getattr(vehicle, "stock_location_id", False):
                    order.route_source_location_id = vehicle.stock_location_id

    @api.model_create_multi
    def create(self, vals_list):
        default_route_visit_id = self.env.context.get("default_route_visit_id") or self.env.context.get("route_visit_id")
        for vals in vals_list:
            if vals.get("route_order_mode") == "direct_sale":
                company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
                if not company.route_operation_allows_direct_sale():
                    raise UserError(_("Direct Sale is hidden because Route Operation Mode is Consignment Route."))
                if not company.route_enable_direct_sale:
                    raise UserError(_("Direct Sale is disabled in Route Settings."))
                if default_route_visit_id and not vals.get("origin"):
                    visit = self.env["route.visit"].browse(default_route_visit_id).exists()
                    if visit:
                        vals["origin"] = visit.name
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("route_order_mode") == "direct_sale":
            for order in self:
                company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else order.company_id
                if not company.route_operation_allows_direct_sale():
                    raise UserError(_("Direct Sale is hidden because Route Operation Mode is Consignment Route."))
                if not company.route_enable_direct_sale:
                    raise UserError(_("Direct Sale is disabled in Route Settings."))
        return super().write(vals)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if vals.get("route_order_mode") == "direct_sale":
            if not self.env.company.route_operation_allows_direct_sale():
                raise UserError(_("Direct Sale is hidden because Route Operation Mode is Consignment Route."))
            if not self.env.company.route_enable_direct_sale:
                raise UserError(_("Direct Sale is disabled in Route Settings."))
            route_visit_id = self.env.context.get("default_route_visit_id") or self.env.context.get("route_visit_id")
            if route_visit_id and not vals.get("origin"):
                visit = self.env["route.visit"].browse(route_visit_id).exists()
                if visit:
                    vals.setdefault("origin", visit.name)
            outlet_id = vals.get("route_outlet_id")
            if outlet_id:
                outlet = self.env["route.outlet"].browse(outlet_id)
                if outlet.partner_id:
                    vals["partner_id"] = outlet.partner_id.id
                    invoice_partner = outlet.partner_id.address_get(["invoice"]).get("invoice") or outlet.partner_id.id
                    delivery_partner = outlet.partner_id.address_get(["delivery"]).get("delivery") or outlet.partner_id.id
                    if "partner_invoice_id" in self._fields:
                        vals["partner_invoice_id"] = invoice_partner
                    if "partner_shipping_id" in self._fields:
                        vals["partner_shipping_id"] = delivery_partner
        return vals


    @api.depends("amount_total", "direct_sale_payment_ids.amount", "direct_sale_payment_ids.state")
    def _compute_direct_sale_payment_summary(self):
        for order in self:
            active_payments = order.direct_sale_payment_ids.filtered(lambda p: p.state != "cancelled")
            confirmed_payments = active_payments.filtered(lambda p: p.state == "confirmed")
            order.direct_sale_payment_count = len(active_payments)
            order.direct_sale_collected_amount = sum(confirmed_payments.mapped("amount"))
            order.direct_sale_remaining_due = order._get_route_payment_remaining_due()

    def _get_route_payment_records(self):
        self.ensure_one()
        return self.direct_sale_payment_ids.filtered(lambda p: p.state != "cancelled").sorted(
            key=lambda p: (p.payment_date or fields.Datetime.now(), p.id),
            reverse=True,
        )

    def _get_route_payment_confirmed_amount(self, exclude_payment=None):
        self.ensure_one()
        payments = self.direct_sale_payment_ids.filtered(lambda p: p.state == "confirmed")
        if exclude_payment:
            payments = payments.filtered(lambda p: p.id != exclude_payment.id)
        return sum(payments.mapped("amount"))

    def _get_route_payment_remaining_due(self, exclude_payment=None):
        self.ensure_one()
        if self.route_order_mode != "direct_sale":
            return 0.0
        return max((self.amount_total or 0.0) - self._get_route_payment_confirmed_amount(exclude_payment=exclude_payment), 0.0)

    def _prepare_direct_sale_payment_vals(self):
        self.ensure_one()
        remaining_due = self._get_route_payment_remaining_due()
        if remaining_due <= 0:
            return False

        payment_mode = self.route_payment_mode or "cash"
        vals = {
            "source_type": "direct_sale",
            "sale_order_id": self.id,
            "payment_date": self.date_order or fields.Datetime.now(),
            "payment_mode": payment_mode,
            "reference": self.name,
        }

        if payment_mode == "deferred":
            vals.update(
                {
                    "collection_type": "defer_date",
                    "amount": 0.0,
                    "due_date": self.route_payment_due_date,
                    "promise_date": self.route_payment_due_date,
                    "promise_amount": remaining_due,
                    "note": _("Auto-created deferred collection record from direct sale order %s.") % (self.name or "-"),
                }
            )
        else:
            vals.update(
                {
                    "collection_type": "full",
                    "amount": remaining_due,
                    "note": _("Auto-created payment record from direct sale order %s.") % (self.name or "-"),
                }
            )

        return vals

    def _ensure_direct_sale_payment_record(self):
        Payment = self.env["route.visit.payment"]
        for order in self:
            if order.route_order_mode != "direct_sale":
                continue
            if order.route_visit_id and getattr(order.route_visit_id, "visit_execution_mode", False) == "direct_sales":
                continue
            existing = order.direct_sale_payment_ids.filtered(lambda p: p.state != "cancelled")
            if existing:
                continue
            vals = order._prepare_direct_sale_payment_vals()
            if not vals:
                continue
            payment = Payment.create(vals)
            payment.action_confirm()

    def action_open_direct_sale_payments(self):
        self.ensure_one()
        self._ensure_route_direct_sale_enabled()
        action = self.env.ref("route_core.action_route_direct_sale_payment").read()[0]
        action["name"] = _("Direct Sale Payments")
        action["domain"] = [("sale_order_id", "=", self.id)]
        action["context"] = {
            "default_source_type": "direct_sale",
            "default_sale_order_id": self.id,
        }
        return action


    def _get_linked_route_visit(self):
        self.ensure_one()
        return self.env["route.visit"].search(
            [("sale_order_id", "=", self.id)],
            limit=1,
        )

    def _get_route_outgoing_picking_type(self):
        self.ensure_one()

        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if warehouse and warehouse.out_type_id:
            return warehouse.out_type_id

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id.company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if picking_type:
            return picking_type

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if picking_type:
            return picking_type

        raise UserError(
            _("No outgoing delivery operation type was found for this company.")
        )

    def _get_route_sale_source_location(self, visit):
        self.ensure_one()

        if not visit.outlet_id or not getattr(visit.outlet_id, "stock_location_id", False):
            raise UserError(
                _(
                    "The selected outlet does not have a stock location for route sale delivery."
                )
            )

        return visit.outlet_id.stock_location_id

    def _get_route_sale_destination_location(self, visit):
        self.ensure_one()

        partner = visit.partner_id or self.partner_shipping_id or self.partner_id
        if partner and "property_stock_customer" in partner._fields and partner.property_stock_customer:
            return partner.property_stock_customer

        customer_location = self.env.ref("stock.stock_location_customers", raise_if_not_found=False)
        if customer_location:
            return customer_location

        raise UserError(_("Customer Location could not be determined for this route sale."))

    def _prepare_route_delivery_vals(
        self,
        visit,
        picking_type,
        source_location,
        dest_location,
    ):
        self.ensure_one()

        vals = {
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": self.name,
            "partner_id": (self.partner_shipping_id or self.partner_id).id,
            "move_type": "direct",
            "route_visit_id": visit.id,
            "company_id": self.company_id.id,
        }

        if "sale_id" in self.env["stock.picking"]._fields:
            vals["sale_id"] = self.id

        return vals

    def _get_sale_line_uom(self, order_line):
        self.ensure_one()

        if "product_uom_id" in order_line._fields and order_line.product_uom_id:
            return order_line.product_uom_id

        if "product_uom" in order_line._fields and order_line.product_uom:
            return order_line.product_uom

        if order_line.product_id and order_line.product_id.uom_id:
            return order_line.product_id.uom_id

        raise UserError(
            _("Could not determine the unit of measure for sale order line: %s")
            % (order_line.display_name or order_line.id)
        )

    def _prepare_route_delivery_move_vals(
        self,
        picking,
        order_line,
        source_location,
        dest_location,
    ):
        self.ensure_one()

        uom = self._get_sale_line_uom(order_line)

        vals = {
            "product_id": order_line.product_id.id,
            "product_uom_qty": order_line.product_uom_qty,
            "product_uom": uom.id,
            "picking_id": picking.id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "company_id": self.company_id.id,
            "origin": self.name,
        }

        if "sale_line_id" in self.env["stock.move"]._fields:
            vals["sale_line_id"] = order_line.id

        if "route_visit_id" in self.env["stock.move"]._fields:
            vals["route_visit_id"] = picking.route_visit_id.id

        return vals

    def _fill_move_line_qty_done(self, picking):
        for move in picking.move_ids:
            qty = move.product_uom_qty or 0.0
            if qty <= 0:
                continue

            if move.move_line_ids:
                remaining = qty
                for move_line in move.move_line_ids:
                    if remaining <= 0:
                        break
                    move_line.quantity = remaining
                    remaining = 0.0
            else:
                self.env["stock.move.line"].create(
                    {
                        "move_id": move.id,
                        "picking_id": picking.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "quantity": qty,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                    }
                )

    def _get_existing_route_delivery(self, visit):
        self.ensure_one()

        if not visit.outlet_id or not getattr(visit.outlet_id, "stock_location_id", False):
            return False

        return self.env["stock.picking"].search(
            [
                ("route_visit_id", "=", visit.id),
                ("origin", "=", self.name),
                ("state", "!=", "cancel"),
                ("location_id", "=", visit.outlet_id.stock_location_id.id),
            ],
            order="id desc",
            limit=1,
        )

    def _get_route_delivery_form_action(self, picking):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["res_id"] = picking.id
        action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        action["context"] = {
            "default_route_visit_id": picking.route_visit_id.id if getattr(picking, "route_visit_id", False) else False,
            "default_picking_type_id": picking.picking_type_id.id,
            "default_location_id": picking.location_id.id,
            "default_location_dest_id": picking.location_dest_id.id,
        }
        return action

    def _create_and_validate_route_delivery(self, visit):
        self.ensure_one()

        if not visit:
            raise UserError(_("This Sale Order is not linked to a route visit."))

        existing_picking = self._get_existing_route_delivery(visit)
        if existing_picking:
            picking = existing_picking
        else:
            source_location = self._get_route_sale_source_location(visit)
            dest_location = self._get_route_sale_destination_location(visit)
            picking_type = self._get_route_outgoing_picking_type()

            sale_lines = self.order_line.filtered(
                lambda line: line.product_id
                and not line.display_type
                and (line.product_uom_qty or 0.0) > 0
            )
            if not sale_lines:
                raise UserError(_("There are no sale lines with quantities to deliver."))

            picking = self.env["stock.picking"].create(
                self._prepare_route_delivery_vals(
                    visit=visit,
                    picking_type=picking_type,
                    source_location=source_location,
                    dest_location=dest_location,
                )
            )

            for line in sale_lines:
                self.env["stock.move"].create(
                    self._prepare_route_delivery_move_vals(
                        picking=picking,
                        order_line=line,
                        source_location=picking.location_id,
                        dest_location=picking.location_dest_id,
                    )
                )

        if picking.state == "draft":
            picking.action_confirm()

        if picking.state in ("confirmed", "waiting"):
            picking.action_assign()

        self._fill_move_line_qty_done(picking)

        if picking.state not in ("done", "cancel"):
            result = picking.button_validate()
            if isinstance(result, dict):
                return result

        if picking.state != "done":
            return self._get_route_delivery_form_action(picking)

        return picking

    def _get_direct_sale_destination_location(self):
        self.ensure_one()
        partner = self.partner_shipping_id or self.partner_id
        if partner and "property_stock_customer" in partner._fields and partner.property_stock_customer:
            return partner.property_stock_customer
        customer_location = self.env.ref("stock.stock_location_customers", raise_if_not_found=False)
        if customer_location:
            return customer_location
        raise UserError(_("Customer Location could not be determined for this direct sale."))

    def _get_existing_direct_sale_delivery(self):
        self.ensure_one()
        if not self.route_source_location_id:
            return False
        return self.env["stock.picking"].search([
            ("origin", "=", self.name),
            ("state", "!=", "cancel"),
            ("location_id", "=", self.route_source_location_id.id),
        ], order="id desc", limit=1)

    def _create_and_validate_direct_sale_delivery(self):
        self.ensure_one()
        if not self.route_source_location_id:
            raise UserError(_("Source Location is required for direct sale delivery."))
        if not self.partner_id:
            raise UserError(_("Customer is required for direct sale delivery."))

        existing_picking = self._get_existing_direct_sale_delivery()
        if existing_picking:
            picking = existing_picking
        else:
            dest_location = self._get_direct_sale_destination_location()
            picking_type = self._get_route_outgoing_picking_type()
            sale_lines = self.order_line.filtered(lambda line: line.product_id and not line.display_type and (line.product_uom_qty or 0.0) > 0)
            if not sale_lines:
                raise UserError(_("There are no sale lines with quantities to deliver."))

            vals = {
                "picking_type_id": picking_type.id,
                "location_id": self.route_source_location_id.id,
                "location_dest_id": dest_location.id,
                "origin": self.name,
                "partner_id": (self.partner_shipping_id or self.partner_id).id,
                "move_type": "direct",
                "company_id": self.company_id.id,
            }
            if "sale_id" in self.env["stock.picking"]._fields:
                vals["sale_id"] = self.id
            picking = self.env["stock.picking"].create(vals)

            for line in sale_lines:
                self.env["stock.move"].create(
                    self._prepare_route_delivery_move_vals(
                        picking=picking,
                        order_line=line,
                        source_location=picking.location_id,
                        dest_location=picking.location_dest_id,
                    )
                )

        if picking.state == "draft":
            picking.action_confirm()
        if picking.state in ("confirmed", "waiting"):
            picking.action_assign()
        self._fill_move_line_qty_done(picking)
        if picking.state not in ("done", "cancel"):
            result = picking.button_validate()
            if isinstance(result, dict):
                return result
        if picking.state != "done":
            return self._get_route_delivery_form_action(picking)
        return picking


    def _get_direct_sale_deliveries(self):
        self.ensure_one()
        return self.env["stock.picking"].search([
            ("origin", "=", self.name),
            ("state", "!=", "cancel"),
            ("location_id", "=", self.route_source_location_id.id),
        ], order="id desc")

    def _get_direct_sale_return_pickings(self):
        self.ensure_one()
        deliveries = self._get_direct_sale_deliveries()
        if not deliveries:
            return self.env["stock.picking"]
        return_moves = self.env["stock.move"].search([
            ("origin_returned_move_id", "in", deliveries.move_ids.ids),
            ("picking_id", "!=", False),
            ("state", "!=", "cancel"),
        ])
        return return_moves.mapped("picking_id").sorted(lambda p: p.id, reverse=True)

    def _get_stock_picking_action(self, name):
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["name"] = name
        action.setdefault("context", {})
        return action

    def action_open_direct_sale_deliveries(self):
        self.ensure_one()
        self._ensure_route_direct_sale_enabled()
        pickings = self._get_direct_sale_deliveries()
        action = self._get_stock_picking_action(_("Direct Sale Deliveries"))
        action["domain"] = [("id", "in", pickings.ids)]
        if len(pickings) == 1:
            form_view = self.env.ref("stock.view_picking_form", raise_if_not_found=False)
            if form_view:
                action["views"] = [(form_view.id, "form")]
            action["res_id"] = pickings.id
            action["view_mode"] = "form"
        return action

    def action_open_direct_sale_returns(self):
        self.ensure_one()
        self._ensure_route_direct_return_enabled()
        pickings = self._get_direct_sale_return_pickings()
        action = self._get_stock_picking_action(_("Direct Returns"))
        action["domain"] = [("id", "in", pickings.ids)]
        if len(pickings) == 1:
            form_view = self.env.ref("stock.view_picking_form", raise_if_not_found=False)
            if form_view:
                action["views"] = [(form_view.id, "form")]
            action["res_id"] = pickings.id
            action["view_mode"] = "form"
        return action

    def action_create_direct_return(self):
        self.ensure_one()
        self._ensure_route_direct_return_enabled()
        if self.route_order_mode != "direct_sale":
            raise UserError(_("Create Return is available only for Direct Sale orders."))

        delivery = self._get_direct_sale_deliveries().filtered(lambda p: p.state == "done")[:1]
        if not delivery:
            raise UserError(_("There is no completed delivery available to return for this order."))

        view = self.env.ref("stock.view_stock_return_picking_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Create Direct Return"),
            "res_model": "stock.return.picking",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_id": delivery.id,
                "active_ids": [delivery.id],
                "active_model": "stock.picking",
                "default_picking_id": delivery.id,
            },
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def _route_confirm_without_procurement(self):
        for order in self:
            if order.state not in ("draft", "sent"):
                continue

            vals = {"state": "sale"}
            if "confirmation_date" in order._fields and not order.confirmation_date:
                vals["confirmation_date"] = fields.Datetime.now()
            order.write(vals)

    def action_confirm(self):
        normal_orders = self.env["sale.order"]
        route_orders = self.env["sale.order"]
        direct_sale_orders = self.env["sale.order"]

        for order in self:
            if order.route_order_mode == "direct_sale":
                direct_sale_orders |= order
                continue
            visit = order._get_linked_route_visit()
            if visit:
                route_orders |= order
            else:
                normal_orders |= order

        action_result = True
        if normal_orders:
            action_result = super(SaleOrder, normal_orders).action_confirm()

        for order in route_orders:
            visit = order._get_linked_route_visit()
            if not visit:
                continue

            order._route_confirm_without_procurement()
            delivery_result = order._create_and_validate_route_delivery(visit)
            if isinstance(delivery_result, dict):
                action_result = delivery_result

        for order in direct_sale_orders:
            order._ensure_route_direct_sale_enabled()
            if not order.route_outlet_id:
                raise UserError(_("Route Outlet is required for Direct Sale orders."))
            if not order.partner_id:
                raise UserError(_("Customer is required for Direct Sale orders."))
            if not order.route_source_location_id:
                raise UserError(_("Source Location is required for Direct Sale orders."))
            if order.route_payment_mode == "deferred" and not order.route_payment_due_date:
                raise UserError(_("Deferred Due Date is required when Route Payment Mode is Deferred."))

            order._route_confirm_without_procurement()
            delivery_result = order._create_and_validate_direct_sale_delivery()
            if isinstance(delivery_result, dict):
                action_result = delivery_result
            elif order._get_direct_sale_deliveries().filtered(lambda p: p.state == "done"):
                order._ensure_direct_sale_payment_record()

        return action_result



