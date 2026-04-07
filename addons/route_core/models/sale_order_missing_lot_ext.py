from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    route_product_barcode = fields.Char(
        string="Barcode",
        copy=False,
    )

    route_available_product_ids = fields.Many2many(
        "product.product",
        string="Available Vehicle Products",
        compute="_compute_route_available_products",
        store=False,
    )
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
    route_vehicle_available_qty = fields.Float(
        string="Available In Vehicle",
        digits="Product Unit of Measure",
        compute="_compute_route_vehicle_available_qty",
        store=False,
    )

    def _route_get_line_uom(self):
        self.ensure_one()
        if "product_uom" in self._fields and self.product_uom:
            return self.product_uom
        if "product_uom_id" in self._fields and self.product_uom_id:
            return self.product_uom_id
        return self.product_id.uom_id

    def _route_get_qty_in_product_uom(self):
        self.ensure_one()
        if not self.product_id:
            return 0.0
        qty = self.product_uom_qty or 0.0
        line_uom = self._route_get_line_uom()
        if line_uom and self.product_id.uom_id and line_uom != self.product_id.uom_id:
            return line_uom._compute_quantity(qty, self.product_id.uom_id)
        return qty

    def _route_convert_qty_from_product_uom(self, qty):
        self.ensure_one()
        if not self.product_id:
            return qty or 0.0
        line_uom = self._route_get_line_uom()
        if line_uom and self.product_id.uom_id and line_uom != self.product_id.uom_id:
            return self.product_id.uom_id._compute_quantity(qty or 0.0, line_uom)
        return qty or 0.0

    def _route_get_available_qty_in_product_uom(self):
        self.ensure_one()
        order = self.order_id
        if not order or order.route_order_mode != "direct_sale" or not self.product_id or not order.route_source_location_id:
            return 0.0
        qty_map = order._get_route_vehicle_qty_map()
        return qty_map.get(self.product_id.id, 0.0)

    @api.depends(
        "product_id",
        "product_uom_qty",
        "order_id.route_order_mode",
        "order_id.route_source_location_id",
    )
    def _compute_route_vehicle_available_qty(self):
        for line in self:
            available_qty = line._route_get_available_qty_in_product_uom()
            line.route_vehicle_available_qty = line._route_convert_qty_from_product_uom(available_qty)

    @api.depends(
        "order_id.route_order_mode",
        "order_id.route_source_location_id",
        "order_id.order_line.product_id",
    )
    def _compute_route_available_products(self):
        Product = self.env["product.product"]
        all_sale_ok = Product.search([("sale_ok", "=", True), ("active", "=", True)])
        for line in self:
            order = line.order_id
            if not order or order.route_order_mode != "direct_sale" or not order.route_source_location_id:
                line.route_available_product_ids = all_sale_ok
                continue
            qty_map = order._get_route_vehicle_qty_map()
            allowed_ids = {product_id for product_id, qty in qty_map.items() if qty > 0.0}
            allowed_ids.update(order.order_line.mapped("product_id").ids)
            line.route_available_product_ids = Product.browse(sorted(allowed_ids))

    @api.onchange("order_id.route_order_mode", "order_id.route_source_location_id")
    def _onchange_route_available_product_domain(self):
        if len(self) != 1:
            return
        line = self
        order = line.order_id
        if order and order.route_order_mode == "direct_sale" and order.route_source_location_id:
            available_ids = line.route_available_product_ids.ids
            return {
                "domain": {
                    "product_id": [("sale_ok", "=", True), ("id", "in", available_ids or [0])]
                }
            }
        return {"domain": {"product_id": [("sale_ok", "=", True)]}}

    @api.onchange("product_id")
    def _onchange_route_product_barcode_from_product(self):
        for line in self:
            line.route_product_barcode = line.product_id.barcode if line.product_id else False

    @api.onchange("route_product_barcode")
    def _onchange_route_product_barcode_lookup(self):
        Product = self.env["product.product"]
        for line in self:
            barcode = (line.route_product_barcode or "").strip()
            if not barcode or (line.product_id and barcode == (line.product_id.barcode or "")):
                continue
            extra_domain = [("sale_ok", "=", True)]
            if line.order_id and line.order_id.route_order_mode == "direct_sale":
                available_ids = line.route_available_product_ids.ids
                extra_domain.append(("id", "in", available_ids or [0]))
            product = Product._route_find_product_by_barcode(barcode, extra_domain=extra_domain)
            if product:
                line.product_id = product
                line.route_product_barcode = product.barcode or barcode

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
                valid_quants = quants.filtered(
                    lambda q: max(
                        (q.quantity or 0.0) - ((q.reserved_quantity if "reserved_quantity" in q._fields else 0.0) or 0.0),
                        0.0,
                    ) > 0.0
                )
                lots = valid_quants.mapped("lot_id")
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

    @api.onchange("product_id", "product_uom_qty", "order_id.route_source_location_id")
    def _onchange_route_vehicle_qty_limit(self):
        for line in self:
            order = line.order_id
            if not order or order.route_order_mode != "direct_sale" or not line.product_id:
                continue
            available_qty = line._route_get_available_qty_in_product_uom()
            other_requested_qty = sum(
                sibling._route_get_qty_in_product_uom()
                for sibling in order.order_line.filtered(
                    lambda l: l != line and l.product_id == line.product_id and not l.display_type
                )
            )
            allowed_qty = max(available_qty - other_requested_qty, 0.0)
            requested_qty = line._route_get_qty_in_product_uom()
            rounding = line.product_id.uom_id.rounding if line.product_id.uom_id else 0.01
            if float_compare(requested_qty, allowed_qty, precision_rounding=rounding) > 0:
                line.product_uom_qty = line._route_convert_qty_from_product_uom(allowed_qty)
                return {
                    "warning": {
                        "title": _("Vehicle stock limit reached"),
                        "message": _(
                            "Only %(qty).2f %(uom)s of %(product)s is still available in the vehicle for this order."
                        )
                        % {
                            "qty": allowed_qty,
                            "uom": line.product_id.uom_id.display_name if line.product_id.uom_id else _("Units"),
                            "product": line.product_id.display_name,
                        },
                    }
                }

    @api.constrains("product_id", "product_uom_qty", "order_id", "order_id.route_source_location_id")
    def _check_route_vehicle_available_qty(self):
        for line in self:
            order = line.order_id
            if not order or order.route_order_mode != "direct_sale" or not line.product_id or line.display_type:
                continue
            available_qty = line._route_get_available_qty_in_product_uom()
            other_requested_qty = sum(
                sibling._route_get_qty_in_product_uom()
                for sibling in order.order_line.filtered(
                    lambda l: l != line and l.product_id == line.product_id and not l.display_type
                )
            )
            allowed_qty = max(available_qty - other_requested_qty, 0.0)
            requested_qty = line._route_get_qty_in_product_uom()
            rounding = line.product_id.uom_id.rounding if line.product_id.uom_id else 0.01
            if float_compare(requested_qty, allowed_qty, precision_rounding=rounding) > 0:
                raise ValidationError(
                    _(
                        "Only %(allowed).2f %(uom)s of %(product)s is available in vehicle stock for this direct sale order."
                    )
                    % {
                        "allowed": allowed_qty,
                        "uom": line.product_id.uom_id.display_name if line.product_id.uom_id else _("Units"),
                        "product": line.product_id.display_name,
                    }
                )

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

    def _route_get_tracked_quant_buckets(self, move):
        Quant = self.env["stock.quant"]
        quants = Quant.search(
            [
                ("location_id", "child_of", move.location_id.id),
                ("product_id", "=", move.product_id.id),
                ("quantity", ">", 0),
                ("lot_id", "!=", False),
            ],
            order="in_date, lot_id, id",
        )
        buckets = {}
        for quant in quants:
            lot = quant.lot_id
            if not lot:
                continue
            bucket = buckets.setdefault(
                lot.id,
                {
                    "lot": lot,
                    "qty": 0.0,
                    "expiry": lot.expiration_date or fields.Datetime.to_datetime("2099-12-31 00:00:00"),
                    "in_date": quant.in_date or fields.Datetime.to_datetime("2099-12-31 00:00:00"),
                },
            )
            bucket["qty"] += quant.quantity
        return sorted(buckets.values(), key=lambda b: (b["expiry"], b["in_date"], b["lot"].id))

    def _route_prepare_auto_tracked_move_line_vals(self, move, picking, qty):
        tracking = getattr(move.product_id, "tracking", "none") or "none"
        if tracking not in ("lot", "serial"):
            return []

        buckets = self._route_get_tracked_quant_buckets(move)
        available_qty = sum(bucket["qty"] for bucket in buckets)
        if available_qty < qty:
            raise UserError(
                _(
                    "Not enough tracked stock is available in source location %s for product %s. Available: %s, Required: %s."
                )
                % (
                    move.location_id.display_name,
                    move.product_id.display_name,
                    available_qty,
                    qty,
                )
            )

        vals_list = []
        remaining = qty
        if tracking == "serial":
            if int(qty) != qty:
                raise UserError(
                    _(
                        "Serial-tracked product %s must be delivered in whole units."
                    )
                    % move.product_id.display_name
                )
            unit_count = int(qty)
            serial_lots = []
            for bucket in buckets:
                for _i in range(int(bucket["qty"])):
                    serial_lots.append(bucket["lot"])
                    if len(serial_lots) >= unit_count:
                        break
                if len(serial_lots) >= unit_count:
                    break
            if len(serial_lots) < unit_count:
                raise UserError(
                    _(
                        "Not enough serial numbers are available in source location %s for product %s. Required: %s."
                    )
                    % (move.location_id.display_name, move.product_id.display_name, qty)
                )
            for lot in serial_lots:
                vals_list.append(
                    {
                        "move_id": move.id,
                        "picking_id": picking.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "quantity": 1.0,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                        "lot_id": lot.id,
                    }
                )
            return vals_list

        for bucket in buckets:
            if remaining <= 0:
                break
            take_qty = min(bucket["qty"], remaining)
            if take_qty <= 0:
                continue
            vals_list.append(
                {
                    "move_id": move.id,
                    "picking_id": picking.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "quantity": take_qty,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                    "lot_id": bucket["lot"].id,
                }
            )
            remaining -= take_qty

        if remaining > 0:
            raise UserError(
                _(
                    "Not enough lot quantity is available in source location %s for product %s. Remaining required: %s."
                )
                % (move.location_id.display_name, move.product_id.display_name, remaining)
            )
        return vals_list

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
            manual_route_lot_workflow = bool(
                line and getattr(line.order_id, "route_enable_lot_serial_tracking", True)
            )
            if line and manual_route_lot_workflow and tracking in ("lot", "serial"):
                lot = getattr(line, "route_lot_id", False) or getattr(line, "lot_id", False)

            if lot:
                if tracking == "serial" and qty != 1.0:
                    raise UserError(
                        _(
                            "Serial-tracked product %s must be delivered with quantity 1."
                        )
                        % move.product_id.display_name
                    )
                move_line_vals = {
                    "move_id": move.id,
                    "picking_id": picking.id,
                    "product_id": move.product_id.id,
                    "product_uom_id": move.product_uom.id,
                    "quantity": qty,
                    "location_id": move.location_id.id,
                    "location_dest_id": move.location_dest_id.id,
                    "lot_id": lot.id,
                }
                self.env["stock.move.line"].create(move_line_vals)
                continue

            if tracking in ("lot", "serial"):
                auto_vals = self._route_prepare_auto_tracked_move_line_vals(move, picking, qty)
                self.env["stock.move.line"].create(auto_vals)
                continue

            move_line_vals = {
                "move_id": move.id,
                "picking_id": picking.id,
                "product_id": move.product_id.id,
                "product_uom_id": move.product_uom.id,
                "quantity": qty,
                "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
            }
            self.env["stock.move.line"].create(move_line_vals)

