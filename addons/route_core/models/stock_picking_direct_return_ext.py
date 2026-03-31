from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    route_direct_return_id = fields.Many2one(
        "route.direct.return",
        string="Route Direct Return",
        index=True,
        copy=False,
        ondelete="set null",
    )
