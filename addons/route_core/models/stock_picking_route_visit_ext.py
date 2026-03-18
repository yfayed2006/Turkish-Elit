from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        index=True,
        ondelete="set null",
        help="Route visit linked to this stock transfer.",
    )
