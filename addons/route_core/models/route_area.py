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
    partner_ids = fields.One2many(
        "res.partner",
        "route_area_id",
        string="Markets",
    )
    partner_count = fields.Integer(
        string="Markets Count",
        compute="_compute_partner_count",
    )

    def _compute_partner_count(self):
        for rec in self:
            rec.partner_count = len(rec.partner_ids)

    def action_view_markets(self):
        self.ensure_one()
        action = self.env.ref("base.action_partner_form").read()[0]
        action["domain"] = [("route_area_id", "=", self.id)]
        action["context"] = dict(self.env.context, default_route_area_id=self.id)
        return action
