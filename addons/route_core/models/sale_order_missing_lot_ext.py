from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    route_available_lot_ids = fields.Many2many(
        "stock.lot",
        string="Available Lots",
        compute="_compute_route_available_lot_ids",
    )
    route_lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        domain="[('id', 'in', route_available_lot_ids)]",
        ondelete="restrict",
    )
    route_expiry_date = fields.Datetime(
        string="Expiry",
        related="route_lot_id.expiration_date",
        readonly=True,
        store=False,
    )

    @api.depends(
        "product_id",
        "product_uom_qty",
        "order_id.route_order_mode",
        "order_id.route_source_location_id",
        "order_id.route_enable_lot_serial_tracking",
    )
    def _compute_route_available_lot_ids(self):
        Quant = self.env["stock.quant"]
        for line in self:
            lots = self.env["stock.lot"]
            if not line.order_id.route_enable_lot_serial_tracking:
                line.route_available_lot_ids = lots
                line.route_lot_id = False
                continue
            if (
                line.order_id.route_order_mode == "direct_sale"
                and line.product_id
                and line.product_id.tracking != "none"
                and line.order_id.route_source_location_id
            ):
                quants = Quant.search(
                    [
                        ("location_id", "child_of", line.order_id.route_source_location_id.id),
                        ("product_id", "=", line.product_id.id),
                        ("quantity", ">", 0),
                        ("lot_id", "!=", False),
                    ],
                    order="in_date, lot_id, id",
                )
                lots = quants.mapped("lot_id")
            line.route_available_lot_ids = lots
            if line.route_lot_id and line.route_lot_id not in lots:
                line.route_lot_id = False

    @api.onchange("product_id", "order_id.route_source_location_id", "order_id.route_enable_lot_serial_tracking")
    def _onchange_route_product_or_source(self):
        for line in self:
            if not line.order_id.route_enable_lot_serial_tracking:
                line.route_lot_id = False
                continue
            if not line.product_id or line.product_id.tracking == "none":
                line.route_lot_id = False
                continue
            if line.order_id.route_order_mode != "direct_sale":
                continue
            available_lots = line.route_available_lot_ids
            if available_lots and (not line.route_lot_id or line.route_lot_id not in available_lots):
                sorted_lots = available_lots.sorted(
                    key=lambda lot: (
                        lot.expiration_date or fields.Datetime.to_datetime("2099-12-31 00:00:00"),
                        lot.id,
                    )
                )
                line.route_lot_id = sorted_lots[:1]

    @api.constrains("route_lot_id", "product_id")
    def _check_route_lot_product(self):
        for line in self:
            if line.route_lot_id and line.product_id and line.route_lot_id.product_id != line.product_id:
                raise ValidationError(
                    _("Selected Lot/Serial does not belong to product %s.")
                    % line.product_id.display_name
                )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    route_enable_lot_serial_tracking = fields.Boolean(
        string="Route Lot/Serial Workflow",
        compute="_compute_route_feature_flags",
        store=False,
    )
    route_enable_expiry_tracking = fields.Boolean(
        string="Route Expiry Workflow",
        compute="_compute_route_feature_flags",
        store=False,
    )

    @api.depends("company_id")
    def _compute_route_feature_flags(self):
        for order in self:
            company = order.company_id or self.env.company
            order.route_enable_lot_serial_tracking = bool(company.route_enable_lot_serial_tracking)
            order.route_enable_expiry_tracking = bool(company.route_enable_expiry_tracking)

    def _prepare_route_delivery_move_vals(
        self,
        picking,
        order_line,
        source_location,
        dest_location,
    ):
        vals = super()._prepare_route_delivery_move_vals(
            picking=picking,
            order_line=order_line,
            source_location=source_location,
            dest_location=dest_location,
        )
        if (
            getattr(order_line, "route_lot_id", False)
            and getattr(order_line.order_id, "route_enable_lot_serial_tracking", False)
            and "restrict_lot_id" in self.env["stock.move"]._fields
        ):
            vals["restrict_lot_id"] = order_line.route_lot_id.id
        return vals

    def _check_direct_sale_tracked_lines(self):
        Quant = self.env["stock.quant"]
        for order in self.filtered(lambda o: o.route_order_mode == "direct_sale"):
            if not order.route_enable_lot_serial_tracking:
                continue
            for line in order.order_line.filtered(
                lambda l: l.product_id and not l.display_type and (l.product_uom_qty or 0.0) > 0
            ):
                tracking = line.product_id.tracking or "none"
                if tracking == "none":
                    continue
                if not line.route_lot_id:
                    raise UserError(
                        _(
                            "Please select Lot/Serial for tracked product %s before confirming the Direct Sale order."
                        )
                        % line.product_id.display_name
                    )
                if line.route_lot_id.product_id != line.product_id:
                    raise UserError(
                        _("Selected Lot/Serial does not belong to product %s.")
                        % line.product_id.display_name
                    )
                if tracking == "serial" and (line.product_uom_qty or 0.0) != 1.0:
                    raise UserError(
                        _(
                            "Serial-tracked product %s must be sold with quantity 1 per line. Please split it into separate lines."
                        )
                        % line.product_id.display_name
                    )
                if order.route_source_location_id:
                    quants = Quant.search(
                        [
                            ("location_id", "child_of", order.route_source_location_id.id),
                            ("product_id", "=", line.product_id.id),
                            ("lot_id", "=", line.route_lot_id.id),
                        ]
                    )
                    available_qty = sum(quants.mapped("quantity"))
                    if available_qty < (line.product_uom_qty or 0.0):
                        raise UserError(
                            _(
                                "Selected lot %s does not have enough quantity in source location %s for product %s. Available: %s, Required: %s."
                            )
                            % (
                                line.route_lot_id.display_name,
                                order.route_source_location_id.display_name,
                                line.product_id.display_name,
                                available_qty,
                                line.product_uom_qty or 0.0,
                            )
                        )

    def _fill_move_line_qty_done(self, picking):
        visit = getattr(picking, "route_visit_id", False)
        for move in picking.move_ids:
            qty = move.product_uom_qty or 0.0
            if qty <= 0:
                continue

            line = False
            if getattr(move, "sale_line_id", False):
                line = move.sale_line_id
            if not line and visit:
                line = move.route_visit_line_id or visit.line_ids.filtered(lambda l: l.product_id == move.product_id)[:1]

            tracking = getattr(move.product_id, "tracking", "none") or "none"
            lot = False
            if (
                line
                and getattr(line.order_id, "route_enable_lot_serial_tracking", True)
                and tracking in ("lot", "serial")
            ):
                lot = getattr(line, "route_lot_id", False) or getattr(line, "lot_id", False)

            if lot:
                if tracking == "serial" and qty != 1.0:
                    raise UserError(
                        _(
                            "Serial-tracked product %s must be delivered with quantity 1 per move line."
                        )
                        % move.product_id.display_name
                    )
                if move.move_line_ids:
                    move.move_line_ids.unlink()
                self.env["stock.move.line"].create(
                    {
                        "move_id": move.id,
                        "picking_id": picking.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "quantity": qty,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                        "lot_id": lot.id,
                    }
                )
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

    def action_confirm(self):
        self._check_direct_sale_tracked_lines()
        return super().action_confirm()
