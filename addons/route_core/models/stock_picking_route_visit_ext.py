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

    is_return_transfer = fields.Boolean(
        string="Is Return Transfer",
        default=False,
        help="Indicates that this internal transfer was created for returned products from a route visit.",
    )
