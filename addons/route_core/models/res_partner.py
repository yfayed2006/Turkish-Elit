from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_route_market = fields.Boolean(
        string="Route Market",
        default=False,
        help="Enable this for supermarkets or outlets served by route sales.",
    )
    route_area_id = fields.Many2one(
        "route.area",
        string="Route Area",
    )
    market_location_id = fields.Many2one(
        "stock.location",
        string="Market Stock Location",
        domain="[('usage', '=', 'internal')]",
        help="Internal stock location that represents this market in the route stock workflow.",
    )
