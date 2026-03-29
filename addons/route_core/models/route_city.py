from odoo import api, fields, models


class RouteCity(models.Model):
    _name = "route.city"
    _description = "Route City"
    _order = "country_id, name"

    name = fields.Char(
        string="City Name",
        required=True,
    )
    country_id = fields.Many2one(
        "res.country",
        string="Country",
        required=True,
        ondelete="restrict",
        index=True,
    )
    active = fields.Boolean(
        default=True,
    )
    notes = fields.Text(
        string="Notes",
    )

    area_ids = fields.One2many(
        "route.area",
        "city_id",
        string="Areas",
    )
    area_count = fields.Integer(
        string="Areas Count",
        compute="_compute_area_count",
    )

    @api.depends("area_ids")
    def _compute_area_count(self):
        for rec in self:
            rec.area_count = len(rec.area_ids)

    def action_view_areas(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_area").read()[0]
        action["domain"] = [("city_id", "=", self.id)]
        action["context"] = dict(
            self.env.context,
            default_city_id=self.id,
        )
        return action

    def action_save_and_back(self):
        return self.env.ref("route_core.action_route_city").read()[0]
