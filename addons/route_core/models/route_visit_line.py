from odoo import api, fields, models


class RouteVisitLine(models.Model):
    _name = "route.visit.line"
    _description = "Route Visit Line"
    _order = "visit_id, id"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        ondelete="cascade",
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
        index=True,
    )


    lot_id = fields.Many2one(
        "stock.lot",
        string="Lot/Serial",
        ondelete="set null",
        index=True,
        domain="[('product_id', '=', product_id)]",
        help="Lot/Serial used for this visit line when the product is tracked.",
    )

    barcode = fields.Char(
        string="Barcode",
        related="product_id.barcode",
        store=True,
        readonly=True,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="UoM",
        related="product_id.uom_id",
        store=True,
        readonly=True,
    )

    previous_qty = fields.Float(string="Previous Qty", default=0.0)
    counted_qty = fields.Float(string="Counted Qty", default=0.0)
    return_qty = fields.Float(string="Return Qty", default=0.0)
    supplied_qty = fields.Float(string="Supplied Qty", default=0.0)
    pending_refill_qty = fields.Float(string="Pending Refill Qty", default=0.0)

    sold_qty = fields.Float(
        string="Sold Qty",
        compute="_compute_quantities",
        store=True,
    )

    new_balance_qty = fields.Float(
        string="New Balance Qty",
        compute="_compute_quantities",
        store=True,
    )

    vehicle_available_qty = fields.Float(
        string="Vehicle Available Qty",
        default=0.0,
    )

    unit_price = fields.Float(string="Unit Price", default=0.0)

    previous_value = fields.Monetary(
        string="Previous Value",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    counted_value = fields.Monetary(
        string="Counted Value",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    sold_amount = fields.Monetary(
        string="Sold Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    return_amount = fields.Monetary(
        string="Return Amount",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    supply_value = fields.Monetary(
        string="Supply Value",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    new_balance_value = fields.Monetary(
        string="New Balance Value",
        currency_field="currency_id",
        compute="_compute_amounts",
        store=True,
    )

    note = fields.Char(string="Note")

    return_route = fields.Selection(
        [
            ("vehicle", "To Vehicle"),
            ("damaged", "To Damaged Stock"),
            ("near_expiry", "To Near Expiry Stock"),
        ],
        string="Return Route",
        default="vehicle",
        required=True,
    )

    expiry_date = fields.Date(string="Expiry Date")

    expiry_days_left = fields.Integer(
        string="Days Left",
        compute="_compute_expiry_info",
        store=True,
    )

    is_near_expiry = fields.Boolean(
        string="Near Expiry",
        compute="_compute_expiry_info",
        store=True,
    )

    suggest_near_expiry_return = fields.Boolean(
        string="Suggest Near Expiry Return",
        default=False,
        help="Checked automatically when the expiry date is within the visit threshold and no final decision has been taken yet.",
    )

    near_expiry_action_state = fields.Selection(
        [
            ("none", "Not Applicable"),
            ("pending", "Pending Decision"),
            ("returned", "Returned"),
            ("kept", "Kept at Outlet"),
        ],
        string="Near Expiry Action",
        compute="_compute_near_expiry_action_state",
        store=True,
        default="none",
    )

    near_expiry_decision_note = fields.Char(
        string="Near Expiry Decision Note",
        help="Optional note when the representative decides to keep a near-expiry item at the outlet.",
    )


    last_sold_date = fields.Date(
        string="Last Sold Date",
        compute="_compute_shelf_movement_metrics",
        store=False,
    )

    last_supply_date = fields.Date(
        string="Last Supply Date",
        compute="_compute_shelf_movement_metrics",
        store=False,
    )

    days_since_last_sale = fields.Integer(
        string="Days Since Last Sale",
        compute="_compute_shelf_movement_metrics",
        store=False,
    )

    days_on_shelf = fields.Integer(
        string="Days On Shelf",
        compute="_compute_shelf_movement_metrics",
        store=False,
        help="Estimated days the current stock has been sitting on the shelf based on the last refill/stock entry signal.",
    )

    movement_status = fields.Selection(
        [
            ("active", "Active"),
            ("watch", "Monitor"),
            ("slow", "Slow Moving"),
            ("very_slow", "Very Slow"),
            ("no_sale_history", "No Sale History"),
            ("no_stock", "No Stock"),
        ],
        string="Movement Status",
        compute="_compute_shelf_movement_metrics",
        store=False,
    )

    movement_status_note = fields.Char(
        string="Movement Note",
        compute="_compute_shelf_movement_metrics",
        store=False,
    )

    keep_near_expiry = fields.Boolean(
        string="Keep Near Expiry",
        default=False,
        help="Enable this when the near-expiry item is intentionally kept at the outlet instead of being returned.",
    )

    @api.depends("previous_qty", "counted_qty", "return_qty", "supplied_qty")
    def _compute_quantities(self):
        for line in self:
            line.sold_qty = max((line.previous_qty or 0.0) - (line.counted_qty or 0.0), 0.0)
            line.new_balance_qty = (line.counted_qty or 0.0) + (line.supplied_qty or 0.0) - (line.return_qty or 0.0)

    @api.depends(
        "previous_qty",
        "counted_qty",
        "sold_qty",
        "return_qty",
        "supplied_qty",
        "new_balance_qty",
        "unit_price",
    )
    def _compute_amounts(self):
        for line in self:
            price = line.unit_price or 0.0
            line.previous_value = (line.previous_qty or 0.0) * price
            line.counted_value = (line.counted_qty or 0.0) * price
            line.sold_amount = (line.sold_qty or 0.0) * price
            line.return_amount = (line.return_qty or 0.0) * price
            line.supply_value = (line.supplied_qty or 0.0) * price
            line.new_balance_value = (line.new_balance_qty or 0.0) * price

    @api.depends("expiry_date", "visit_id.date", "visit_id.near_expiry_threshold_days")
    def _compute_expiry_info(self):
        for line in self:
            line.expiry_days_left = 0
            line.is_near_expiry = False

            if not line.expiry_date:
                continue

            ref_date = line.visit_id.date or fields.Date.context_today(line)
            days_left = (line.expiry_date - ref_date).days
            line.expiry_days_left = days_left
            line.is_near_expiry = days_left <= (line.visit_id.near_expiry_threshold_days or 0)

    @api.depends(
        "is_near_expiry",
        "return_qty",
        "return_route",
        "keep_near_expiry",
        "expiry_date",
    )
    def _compute_near_expiry_action_state(self):
        for line in self:
            if not line.expiry_date or not line.is_near_expiry:
                line.near_expiry_action_state = "none"
            elif line.return_qty > 0:
                line.near_expiry_action_state = "returned"
            elif line.keep_near_expiry:
                line.near_expiry_action_state = "kept"
            else:
                line.near_expiry_action_state = "pending"

    @api.onchange("expiry_date")
    def _onchange_expiry_date(self):
        for line in self:
            if not line.expiry_date:
                line.suggest_near_expiry_return = False
                if not line.is_near_expiry:
                    line.keep_near_expiry = False
                continue

            if line.is_near_expiry:
                if line.return_qty <= 0 and not line.keep_near_expiry:
                    line.suggest_near_expiry_return = True
            else:
                line.suggest_near_expiry_return = False
                line.keep_near_expiry = False
                if line.return_route == "near_expiry" and line.return_qty <= 0:
                    line.return_route = "vehicle"

    @api.onchange("return_qty", "return_route")
    def _onchange_return_near_expiry(self):
        for line in self:
            if line.return_qty > 0 and line.return_route == "near_expiry":
                line.suggest_near_expiry_return = False
                line.keep_near_expiry = False
                if not line.near_expiry_decision_note:
                    line.near_expiry_decision_note = "Returned to near expiry stock."
            elif line.return_qty <= 0 and line.is_near_expiry and not line.keep_near_expiry:
                line.suggest_near_expiry_return = True
                if line.near_expiry_decision_note == "Returned to near expiry stock.":
                    line.near_expiry_decision_note = False

    @api.onchange("keep_near_expiry")
    def _onchange_keep_near_expiry(self):
        for line in self:
            if line.keep_near_expiry:
                line.suggest_near_expiry_return = False
                if line.return_route == "near_expiry" and line.return_qty <= 0:
                    line.return_route = "vehicle"
                if not line.near_expiry_decision_note:
                    line.near_expiry_decision_note = "Kept at outlet by representative decision."
            else:
                if line.is_near_expiry and line.return_qty <= 0:
                    line.suggest_near_expiry_return = True
                if line.near_expiry_decision_note == "Kept at outlet by representative decision.":
                    line.near_expiry_decision_note = False


    @api.depends(
        "product_id",
        "visit_id.outlet_id",
        "visit_id.date",
        "previous_qty",
        "counted_qty",
        "supplied_qty",
        "new_balance_qty",
        "sold_qty",
    )
    def _compute_shelf_movement_metrics(self):
        VisitLine = self.env["route.visit.line"]
        today = fields.Date.context_today(self)

        for line in self:
            line.last_sold_date = False
            line.last_supply_date = False
            line.days_since_last_sale = 0
            line.days_on_shelf = 0
            line.movement_status = "no_stock"
            line.movement_status_note = "No stock on shelf."

            if not line.product_id or not line.visit_id or not line.visit_id.outlet_id:
                continue

            reference_date = line.visit_id.date or today
            shelf_qty = (line.counted_qty or 0.0) if (line.counted_qty or 0.0) > 0 else (line.previous_qty or 0.0)
            if (line.new_balance_qty or 0.0) > 0:
                shelf_qty = line.new_balance_qty or 0.0

            history = VisitLine.search([
                ("id", "!=", line.id),
                ("visit_id.outlet_id", "=", line.visit_id.outlet_id.id),
                ("product_id", "=", line.product_id.id),
                ("visit_id.state", "!=", "cancelled"),
                ("visit_id.date", "<=", reference_date),
            ], order="id desc", limit=120)

            history = history.sorted(
                key=lambda l: ((l.visit_id.date or fields.Date.from_string("1900-01-01")), l.id),
                reverse=True,
            )

            sale_history = history.filtered(lambda l: (l.sold_qty or 0.0) > 0)
            supply_history = history.filtered(lambda l: (l.supplied_qty or 0.0) > 0 or (l.previous_qty or 0.0) > 0)

            last_sale_line = sale_history[:1] if sale_history else VisitLine.browse()
            last_supply_line = supply_history[:1] if supply_history else VisitLine.browse()

            if last_sale_line:
                line.last_sold_date = last_sale_line.visit_id.date
                if line.last_sold_date:
                    line.days_since_last_sale = max((reference_date - line.last_sold_date).days, 0)

            if last_supply_line:
                line.last_supply_date = last_supply_line.visit_id.date
                if line.last_supply_date:
                    line.days_on_shelf = max((reference_date - line.last_supply_date).days, 0)

            if shelf_qty <= 0:
                line.movement_status = "no_stock"
                line.movement_status_note = "No stock on shelf."
                continue

            if not line.last_sold_date:
                line.movement_status = "no_sale_history"
                line.movement_status_note = "Stock exists but there is no recorded sale history yet."
                continue

            days = line.days_since_last_sale or 0
            if days <= 7:
                line.movement_status = "active"
                line.movement_status_note = "Healthy movement based on recent sales."
            elif days <= 21:
                line.movement_status = "watch"
                line.movement_status_note = "Monitor this item; recent movement is slowing down."
            elif days <= 45:
                line.movement_status = "slow"
                line.movement_status_note = "Slow-moving item; consider refill carefully."
            else:
                line.movement_status = "very_slow"
                line.movement_status_note = "Very slow item; review expiry and stock decision."

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_near_expiry_flags_after_write()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._sync_near_expiry_flags_after_write()
        return result

    def _sync_near_expiry_flags_after_write(self):
        for line in self:
            if not line.expiry_date or not line.is_near_expiry:
                if line.suggest_near_expiry_return:
                    super(RouteVisitLine, line).write({"suggest_near_expiry_return": False})
                continue

            if line.return_qty > 0 and line.return_route == "near_expiry":
                vals = {"suggest_near_expiry_return": False}
                if line.keep_near_expiry:
                    vals["keep_near_expiry"] = False
                super(RouteVisitLine, line).write(vals)
            elif line.keep_near_expiry:
                if line.suggest_near_expiry_return:
                    super(RouteVisitLine, line).write({"suggest_near_expiry_return": False})
            else:
                if not line.suggest_near_expiry_return:
                    super(RouteVisitLine, line).write({"suggest_near_expiry_return": True})
