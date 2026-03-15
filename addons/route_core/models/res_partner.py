from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_route_market = fields.Boolean(
        string="Route Market",
        default=False,
        help="Enable this for supermarkets or outlets that are served by route sales.",
    )
    route_area_id = fields.Many2one(
        "route.area",
        string="Route Area",
    )
    market_location_id = fields.Many2one(
        "stock.location",
        string="Market Stock Location",
        domain="[('usage', '=', 'internal')]",
        help="Internal stock location that represents this market in the consignment workflow.",
    )
    visit_count = fields.Integer(
        string="Visits Count",
        compute="_compute_visit_count",
    )

    def _compute_visit_count(self):
        visit_model = self.env["route.visit"]
        for rec in self:
            rec.visit_count = visit_model.search_count([("partner_id", "=", rec.id)])

    def action_view_route_visits(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["domain"] = [("partner_id", "=", self.id)]
        action["context"] = dict(self.env.context, default_partner_id=self.id)
        return action
