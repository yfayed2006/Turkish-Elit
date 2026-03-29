from odoo import api, fields, models


class RouteArea(models.Model):
    _name = "route.area"
    _description = "Route Area"
    _order = "country_id, city_id, name"

    name = fields.Char(
        string="Area Name",
        required=True,
    )
    code = fields.Char(
        string="Code",
    )
    city_id = fields.Many2one(
        "route.city",
        string="City",
        ondelete="restrict",
        index=True,
    )
    country_id = fields.Many2one(
        "res.country",
        string="Country",
        related="city_id.country_id",
        store=True,
        readonly=True,
        index=True,
    )
    active = fields.Boolean(
        default=True,
    )
    notes = fields.Text(
        string="Notes",
    )

    visit_ids = fields.One2many(
        "route.visit",
        "area_id",
        string="Visits",
    )
    visit_count = fields.Integer(
        string="Visits Count",
        compute="_compute_visit_count",
    )

    outlet_ids = fields.One2many(
        "route.outlet",
        "area_id",
        string="Outlets",
    )
    outlet_count = fields.Integer(
        string="Outlets Count",
        compute="_compute_outlet_count",
    )

    @api.depends("visit_ids")
    def _compute_visit_count(self):
        for rec in self:
            rec.visit_count = len(rec.visit_ids)

    @api.depends("outlet_ids")
    def _compute_outlet_count(self):
        for rec in self:
            rec.outlet_count = len(rec.outlet_ids)

    def action_view_visits(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["domain"] = [("area_id", "=", self.id)]
        action["context"] = dict(
            self.env.context,
            default_area_id=self.id,
        )
        return action

    def action_view_outlets(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_outlet").read()[0]
        action["domain"] = [("area_id", "=", self.id)]
        action["context"] = dict(
            self.env.context,
            default_area_id=self.id,
        )
        return action

    def action_save_and_back(self):
        return self.env.ref("route_core.action_route_area").read()[0]
