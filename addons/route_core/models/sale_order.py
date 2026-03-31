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
        domain=[("outlet_operation_mode", "=", "direct_sale")],
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

    @api.onchange("route_outlet_id")
    def _onchange_route_outlet_id(self):
        for order in self:
            if order.route_outlet_id and order.route_outlet_id.partner_id:
                order.partner_id = order.route_outlet_id.partner_id


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

        for order in self:
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

        return action_result
