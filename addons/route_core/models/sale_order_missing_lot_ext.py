from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    route_product_barcode = fields.Char(
        string="Barcode",
        copy=False,
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
    route_available_product_ids = fields.Many2many(
        "product.product",
        string="Available Vehicle Products",
        compute="_compute_route_available_products",
        store=False,
    )
    route_available_product_tmpl_ids = fields.Many2many(
        "product.template",
        string="Available Vehicle Product Templates",
        compute="_compute_route_available_products",
        store=False,
    )
    route_source_available_qty = fields.Float(
        string="Available in Vehicle",
        compute="_compute_route_source_available_qty",
        digits="Product Unit of Measure",
        store=False,
    )


    def _route_get_line_uom(self):
        self.ensure_one()
        if "product_uom" in self._fields and self.product_uom:
            return self.product_uom
        if "product_uom_id" in self._fields and self.product_uom_id:
            return self.product_uom_id
        if self.product_id and self.product_id.uom_id:
            return self.product_id.uom_id
        return False

    @staticmethod
    def _route_get_quant_available_qty(quant):
        reserved = 0.0
        if "reserved_quantity" in quant._fields:
            reserved = quant.reserved_quantity or 0.0
        return max((quant.quantity or 0.0) - reserved, 0.0)

    def _route_get_source_available_qty_base(self):
        self.ensure_one()
        if (
            self.order_id.route_order_mode != "direct_sale"
            or not self.product_id
            or not self.order_id.route_source_location_id
        ):
            return 0.0
        quants = self.env["stock.quant"].search(
            [
                ("location_id", "child_of", self.order_id.route_source_location_id.id),
                ("product_id", "=", self.product_id.id),
                ("quantity", ">", 0),
            ]
        )
        return sum(self._route_get_quant_available_qty(quant) for quant in quants)

    @api.depends(
        "order_id.route_order_mode",
        "order_id.route_source_location_id",
        "product_id",
        "product_uom_qty",
        "product_uom",
    )
    def _compute_route_source_available_qty(self):
        for line in self:
            available_qty = line._route_get_source_available_qty_base()
            uom = line._route_get_line_uom()
            if line.product_id and uom:
                available_qty = line.product_id.uom_id._compute_quantity(available_qty, uom)
            line.route_source_available_qty = available_qty

    @api.depends(
        "order_id.route_order_mode",
        "order_id.route_source_location_id",
    )
    def _compute_route_available_products(self):
        Quant = self.env["stock.quant"]
        product_cache = {}
        template_cache = {}
        source_locations = {
            line.order_id.route_source_location_id.id
            for line in self
            if line.order_id.route_order_mode == "direct_sale" and line.order_id.route_source_location_id
        }
        Product = self.env["product.product"]
        ProductTemplate = self.env["product.template"]

        for location_id in source_locations:
            quants = Quant.search(
                [
                    ("location_id", "child_of", location_id),
                    ("quantity", ">", 0),
                    ("product_id.sale_ok", "=", True),
                    ("product_id.active", "=", True),
                ]
            )
            available_by_product = {}
            for quant in quants:
                product = quant.product_id
                if not product:
                    continue
                available_by_product[product.id] = available_by_product.get(product.id, 0.0) + self._route_get_quant_available_qty(quant)
            product_ids = [product_id for product_id, qty in available_by_product.items() if qty > 0]
            products = Product.browse(product_ids)
            product_cache[location_id] = products
            template_cache[location_id] = products.mapped("product_tmpl_id")

        for line in self:
            if line.order_id.route_order_mode == "direct_sale" and line.order_id.route_source_location_id:
                location_id = line.order_id.route_source_location_id.id
                line.route_available_product_ids = product_cache.get(location_id, Product)
                line.route_available_product_tmpl_ids = template_cache.get(location_id, ProductTemplate)
            else:
                line.route_available_product_ids = Product
                line.route_available_product_tmpl_ids = ProductTemplate

    @api.onchange("product_id", "product_uom_qty", "order_id.route_source_location_id", "order_id.route_order_mode")
    def _onchange_route_direct_sale_qty_limit(self):
        warning = False
        for line in self:
            if line.order_id.route_order_mode != "direct_sale" or not line.product_id:
                continue
            available_qty = line.route_source_available_qty
            entered_qty = line.product_uom_qty or 0.0
            if entered_qty <= available_qty:
                continue
            line.product_uom_qty = available_qty
            warning = {
                "title": _("Vehicle stock limit"),
                "message": _(
                    "Only %(available)s %(uom)s of %(product)s are available in vehicle source %(source)s. The quantity was adjusted automatically."
                )
                % {
                    "available": round(available_qty, 2),
                    "uom": line._route_get_line_uom().display_name if line._route_get_line_uom() else "",
                    "product": line.product_id.display_name,
                    "source": line.order_id.route_source_location_id.display_name if line.order_id.route_source_location_id else "-",
                },
            }
        if warning:
            return {"warning": warning}

    @api.constrains("product_id", "product_uom_qty", "order_id.route_order_mode", "order_id.route_source_location_id")
    def _check_route_direct_sale_vehicle_qty(self):
        for line in self:
            if (
                line.display_type
                or line.order_id.route_order_mode != "direct_sale"
                or not line.product_id
                or not line.order_id.route_source_location_id
            ):
                continue
            requested_qty = line.product_uom_qty or 0.0
            available_qty = line.route_source_available_qty
            if requested_qty > available_qty:
                raise ValidationError(
                    _(
                        "You cannot sell %(requested)s %(uom)s of %(product)s from vehicle source %(source)s because only %(available)s %(uom)s are available."
                    )
                    % {
                        "requested": round(requested_qty, 2),
                        "available": round(available_qty, 2),
                        "uom": line._route_get_line_uom().display_name if line._route_get_line_uom() else "",
                        "product": line.product_id.display_name,
                        "source": line.order_id.route_source_location_id.display_name,
                    }
                )


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
            if line.order_id.route_order_mode == "direct_sale" and line.order_id.route_source_location_id:
                available_products = line.route_available_product_ids
                extra_domain.append(("id", "in", available_products.ids or [0]))
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

            if line and not manual_route_lot_workflow and tracking in ("lot", "serial"):
                if move.move_line_ids:
                    move.move_line_ids.unlink()
                auto_vals_list = self._route_prepare_auto_tracked_move_line_vals(move, picking, qty)
                for vals in auto_vals_list:
                    self.env["stock.move.line"].create(vals)
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
