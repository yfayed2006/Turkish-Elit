from odoo import fields, models


class RouteRefillBackorderLine(models.Model):
    _name = "route.refill.backorder.line"
    _description = "Route Refill Backorder Line"
    _order = "backorder_id, id"

    backorder_id = fields.Many2one(
        "route.refill.backorder",
        string="Backorder",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="backorder_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="backorder_id.currency_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        index=True,
    )
    barcode = fields.Char(
        string="Barcode",
        related="product_id.barcode",
        store=True,
        readonly=True,
    )
    needed_qty = fields.Float(string="Needed Qty", default=0.0)
    available_qty_at_visit = fields.Float(string="Available Qty At Visit", default=0.0)
    delivered_qty = fields.Float(string="Delivered Qty", default=0.0)
    pending_qty = fields.Float(string="Pending Qty", default=0.0)
    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        default=0.0,
    )
    note = fields.Char(string="Note")
