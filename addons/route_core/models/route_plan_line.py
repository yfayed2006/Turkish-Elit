from odoo import api, _, fields, models
from odoo.exceptions import UserError


class RoutePlanLine(models.Model):
    _name = "route.plan.line"
    _description = "Route Plan Line"
    _order = "sequence, id"

    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    plan_id = fields.Many2one(
        "route.plan",
        string="Route Plan",
        required=True,
        ondelete="cascade",
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        ondelete="restrict",
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        related="outlet_id.area_id",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="outlet_id.partner_id",
        store=True,
        readonly=True,
    )
    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("visited", "Visited"),
            ("skipped", "Skipped"),
        ],
        string="Line Status",
        default="pending",
        required=True,
    )
    note = fields.Text(string="Line Note")

    @property
    def _plan_sync_context_key(self):
        return "route_plan_line_skip_plan_sync"

    def _sync_parent_plan_state(self):
        plans = self.mapped("plan_id")
        if plans:
            plans._sync_state_from_lines()

    def action_open_or_create_visit(self):
        self.ensure_one()

        if self.visit_id:
            action = self.env.ref("route_core.action_route_visit").read()[0]
            action["res_id"] = self.visit_id.id
            action["views"] = [(False, "form")]
            return action

        if not self.plan_id:
            raise UserError(_("Please save the route plan first."))

        visit_vals = {
            "date": self.plan_id.date,
            "outlet_id": self.outlet_id.id,
            "area_id": self.area_id.id if self.area_id else False,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "vehicle_id": self.plan_id.vehicle_id.id if self.plan_id.vehicle_id else False,
            "user_id": self.plan_id.user_id.id if self.plan_id.user_id else self.env.user.id,
            "notes": self.note or False,
        }

        visit = self.env["route.visit"].create(visit_vals)
        self.visit_id = visit.id

        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["res_id"] = visit.id
        action["views"] = [(False, "form")]
        return action

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_parent_plan_state()
        return records

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get(self._plan_sync_context_key):
            self._sync_parent_plan_state()
        return result

    def unlink(self):
        plans = self.mapped("plan_id")
        result = super().unlink()
        if plans:
            plans._sync_state_from_lines()
        return result
