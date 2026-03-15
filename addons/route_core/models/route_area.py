from odoo import fields, models


class RouteArea(models.Model):
    _name = "route.area"
    _description = "Route Area"
    _order = "name"

    name = fields.Char(
        string="Area Name",
        required=True,
    )
    code = fields.Char(
        string="Code",
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

    def _compute_visit_count(self):
        for rec in self:
            rec.visit_count = len(rec.visit_ids)

    def action_view_visits(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["domain"] = [("area_id", "=", self.id)]
        action["context"] = dict(self.env.context, default_area_id=self.id)
        return action

    def action_save_and_back(self):
        return self.env.ref("route_core.action_route_area").read()[0]
