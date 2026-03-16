from odoo import fields, models


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    stock_location_id = fields.Many2one(
        "stock.location",
        string="Outlet Stock Location",
        domain=[("usage", "=", "internal")],
        ondelete="restrict",
        help="Internal stock location used for this outlet consignment/location mapping.",
    )

    def get_stock_location(self):
        self.ensure_one()
        return self.stock_location_id

    def has_stock_location(self):
        self.ensure_one()
        return bool(self.stock_location_id)
