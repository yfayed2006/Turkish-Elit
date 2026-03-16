from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        index=True,
        ondelete="set null",
        help="Route visit linked to this stock move.",
    )

    route_visit_line_id = fields.Many2one(
        "route.visit.line",
        string="Route Visit Line",
        index=True,
        ondelete="set null",
        help="Visit line that generated this stock move.",
    )
