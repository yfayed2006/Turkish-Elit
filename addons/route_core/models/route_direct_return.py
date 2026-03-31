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
        domain="[('origin', '=', sale_order_id.name), ('state', '=', 'done')]",
        ondelete="set null",
    )
    return_date = fields.Date(string="Return Date", default=fields.Date.context_today, required=True)
    note = fields.Text(string="Notes")
    state = fields.Selection([("draft", "Draft"), ("done", "Done"), ("cancel", "Cancelled")], default="draft", tracking=True)
    line_ids = fields.One2many("route.direct.return.line", "return_id", string="Return Lines", copy=True)
    picking_ids = fields.One2many("stock.picking", "route_direct_return_id", string="Generated Returns")
    picking_count = fields.Integer(string="Return Pickings", compute="_compute_picking_count")

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = seq.next_by_code("route.direct.return") or "New"
            vals.setdefault("user_id", self.env.user.id)
            vals.setdefault("company_id", self.env.company.id)
        return super().create(vals_list)

    @api.model
    def _default_vehicle(self):
        return self.env["route.vehicle"].search([("user_id", "=", self.env.user.id)], order="id desc", limit=1)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if "vehicle_id" in self._fields and not vals.get("vehicle_id"):
            vehicle = self._default_vehicle()
            if vehicle:
                vals["vehicle_id"] = vehicle.id
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

    @api.onchange("sale_order_id")
    def _onchange_sale_order_id(self):
        for rec in self:
            if rec.sale_order_id and rec.sale_order_id.route_outlet_id:
                rec.outlet_id = rec.sale_order_id.route_outlet_id
            if rec.reference_picking_id and rec.reference_picking_id.origin != rec.sale_order_id.name:
                rec.reference_picking_id = False

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
            if line.product_id.tracking != "none" and not line.lot_name:
                raise UserError(_("Lot/Serial is required for tracked product %s.") % line.product_id.display_name)
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
                    "name": line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.quantity,
                    "product_uom": (line.uom_id or line.product_id.uom_id).id,
                    "location_id": customer_location.id,
                    "location_dest_id": destination.id,
                    "picking_id": picking.id,
                    "company_id": self.company_id.id,
                    "description_picking": line.return_reason_label,
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
                if move.product_id.tracking != "none":
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

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Return quantity must be greater than zero."))
