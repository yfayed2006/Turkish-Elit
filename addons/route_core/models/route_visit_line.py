from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
        index=True,
    )

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Product Template",
        related="product_id.product_tmpl_id",
        store=True,
        readonly=True,
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

    note = fields.Char(string="Note")

    previous_qty = fields.Float(string="Previous Qty", default=0.0)
    counted_qty = fields.Float(string="Counted Qty", default=0.0)
    return_qty = fields.Float(string="Return Qty", default=0.0)
    supplied_qty = fields.Float(string="Supplied Qty", default=0.0)

    return_route = fields.Selection(
        [
            ("vehicle", "To Vehicle"),
            ("damaged", "To Damaged Stock"),
            ("near_expiry", "To Near Expiry Stock"),
        ],
        string="Return Route",
        default="vehicle",
        required=True,
        help="حدد مسار المرتجع لهذا الصنف. الافتراضي هو الإرجاع إلى السيارة.",
    )

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

    pending_refill_qty = fields.Float(
        string="Pending Refill Qty",
        compute="_compute_pending_refill_qty",
        store=True,
    )

    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        default=0.0,
    )

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

    count_confirmed = fields.Boolean(string="Count Confirmed", default=False)
    return_confirmed = fields.Boolean(string="Return Confirmed", default=False)
    supply_confirmed = fields.Boolean(string="Supply Confirmed", default=False)

    @api.onchange("product_id")
    def _onchange_product_id_set_unit_price(self):
        for line in self:
            if line.product_id:
                line.unit_price = line.product_id.lst_price or 0.0

    @api.onchange("return_qty")
    def _onchange_return_qty_set_default_route(self):
        for line in self:
            if line.return_qty > 0 and not line.return_route:
                line.return_route = "vehicle"

    @api.depends("previous_qty", "counted_qty", "return_qty", "supplied_qty")
    def _compute_quantities(self):
        for line in self:
            sold_qty = line.previous_qty - line.counted_qty - line.return_qty
            line.sold_qty = sold_qty if sold_qty > 0 else 0.0
            line.new_balance_qty = line.counted_qty + line.supplied_qty

    @api.depends("sold_qty", "supplied_qty")
    def _compute_pending_refill_qty(self):
        for line in self:
            pending = line.sold_qty - line.supplied_qty
            line.pending_refill_qty = pending if pending > 0 else 0.0

    @api.depends(
        "previous_qty",
        "counted_qty",
        "return_qty",
        "supplied_qty",
        "sold_qty",
        "new_balance_qty",
        "unit_price",
    )
    def _compute_amounts(self):
        for line in self:
            line.previous_value = line.previous_qty * line.unit_price
            line.counted_value = line.counted_qty * line.unit_price
            line.sold_amount = line.sold_qty * line.unit_price
            line.return_amount = line.return_qty * line.unit_price
            line.supply_value = line.supplied_qty * line.unit_price
            line.new_balance_value = line.new_balance_qty * line.unit_price

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product_id = vals.get("product_id")
            if product_id and not vals.get("unit_price"):
                product = self.env["product.product"].browse(product_id)
                vals["unit_price"] = product.lst_price or 0.0

            if vals.get("return_qty", 0.0) > 0 and not vals.get("return_route"):
                vals["return_route"] = "vehicle"

        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals or {})
        if vals.get("product_id") and not vals.get("unit_price"):
            product = self.env["product.product"].browse(vals["product_id"])
            vals["unit_price"] = product.lst_price or 0.0

        if vals.get("return_qty", 0.0) > 0 and not vals.get("return_route"):
            vals["return_route"] = "vehicle"

        return super().write(vals)

    @api.constrains(
        "previous_qty",
        "counted_qty",
        "return_qty",
        "supplied_qty",
        "unit_price",
        "vehicle_available_qty",
    )
    def _check_non_negative_values(self):
        for line in self:
            if line.previous_qty < 0:
                raise ValidationError("Previous Qty cannot be negative.")
            if line.counted_qty < 0:
                raise ValidationError("Counted Qty cannot be negative.")
            if line.return_qty < 0:
                raise ValidationError("Return Qty cannot be negative.")
            if line.supplied_qty < 0:
                raise ValidationError("Supplied Qty cannot be negative.")
            if line.vehicle_available_qty < 0:
                raise ValidationError("Vehicle Available Qty cannot be negative.")
            if line.unit_price < 0:
                raise ValidationError("Unit Price cannot be negative.")

    @api.constrains("previous_qty", "counted_qty", "return_qty")
    def _check_sold_qty_not_negative(self):
        for line in self:
            sold_qty_raw = line.previous_qty - line.counted_qty - line.return_qty
            if sold_qty_raw < 0:
                raise ValidationError(
                    "Sold Qty cannot be negative. Please check Previous Qty, Counted Qty, and Return Qty."
                )

    @api.constrains("supplied_qty", "vehicle_available_qty")
    def _check_supplied_qty_vs_vehicle(self):
        for line in self:
            if line.supplied_qty > line.vehicle_available_qty:
                raise ValidationError(
                    "Supplied Qty cannot be greater than Vehicle Available Qty."
                )

    @api.constrains("return_qty", "return_route")
    def _check_return_route_when_return_exists(self):
        for line in self:
            if line.return_qty > 0 and not line.return_route:
                raise ValidationError(
                    "Please select Return Route when Return Qty is greater than zero."
                )
