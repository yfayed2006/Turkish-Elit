from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    vehicle_closing_id = fields.Many2one(
        "route.vehicle.closing",
        string="Vehicle Closing",
        index=True,
        copy=False,
        ondelete="set null",
    )
