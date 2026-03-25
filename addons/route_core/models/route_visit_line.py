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
            elif line.return_qty > 0 and line.return_route == "near_expiry":
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
