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


    route_direct_return_line_id = fields.Many2one(
        "route.direct.return.line",
        string="Direct Return Line",
        index=True,
        ondelete="set null",
        help="Direct return line that generated this stock move.",
    )

    route_currency_id = fields.Many2one(
        "res.currency",
        string="Route Currency",
        related="company_id.currency_id",
        store=False,
        readonly=True,
    )

    route_direct_return_unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="route_currency_id",
        copy=False,
        help="Estimated direct return unit price used for settlement visibility.",
    )

    route_direct_return_estimated_amount = fields.Monetary(
        string="Estimated Amount",
        currency_field="route_currency_id",
        copy=False,
        help="Estimated direct return line amount used for settlement visibility.",
    )
