from odoo import fields, models


class RouteVehicle(models.Model):
    _inherit = "route.vehicle"

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Vehicle Stock Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        help="Internal stock location used as the main van location for this vehicle.",
    )
