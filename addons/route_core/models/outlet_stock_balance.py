from odoo import api, fields, models
from odoo.exceptions import ValidationError


class OutletStockBalance(models.Model):
    _name = "outlet.stock.balance"
    _description = "Outlet Stock Balance"
    _order = "outlet_id, product_id"
    _rec_name = "product_id"

    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        ondelete="cascade",
        index=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
        index=True,
    )

    barcode = fields.Char(
        string="Barcode",
        related="product_id.barcode",
        store=True,
        readonly=True,
    )

    qty = fields.Float(string="Quantity", default=0.0, required=True)

    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        default=0.0,
    )

    last_visit_id = fields.Many2one(
        "route.visit",
        string="Last Visit",
        ondelete="set null",
    )

    last_updated_at = fields.Datetime(
        string="Last Updated At",
        default=fields.Datetime.now,
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

    _sql_constraints = [
        (
            "outlet_product_unique",
            "unique(outlet_id, product_id)",
            "Only one stock balance record is allowed per outlet and product.",
        ),
    ]

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.outlet_id.display_name} - {rec.product_id.display_name}"
            result.append((rec.id, name))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_updated_at", fields.Datetime.now())
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals or {})
        vals["last_updated_at"] = fields.Datetime.now()
        return super().write(vals)

    @api.constrains("qty", "unit_price")
    def _check_non_negative_qty_and_price(self):
        for rec in self:
            if rec.qty < 0:
                raise ValidationError("Quantity cannot be negative.")
            if rec.unit_price < 0:
                raise ValidationError("Unit Price cannot be negative.")
