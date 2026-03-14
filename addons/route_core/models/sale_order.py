from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        copy=False,
    )
