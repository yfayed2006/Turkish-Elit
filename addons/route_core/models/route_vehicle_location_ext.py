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

    def get_stock_location(self):
        self.ensure_one()
        return self.stock_location_id

    def has_stock_location(self):
        self.ensure_one()
        return bool(self.stock_location_id)
