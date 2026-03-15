from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RoutePlan(models.Model):
    _name = "route.plan"
    _description = "Daily Route Plan"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Plan Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )
    date = fields.Date(
        string="Plan Date",
        required=True,
        default=fields.Date.context_today,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        required=True,
        default=lambda self: self.env.user,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        required=True,
        ondelete="restrict",
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        ondelete="restrict",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )
    notes = fields.Text(string="Notes")

    line_ids = fields.One2many(
        "route.plan.line",
        "plan_id",
        string="Plan Lines",
    )
    line_count = fields.Integer(
        string="Lines Count",
        compute="_compute_line_count",
    )
    visit_count = fields.Integer(
        string="Visits Count",
        compute="_compute_visit_count",
    )

    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def _compute_visit_count(self):
        for rec in self:
            rec.visit_count = len(rec.line_ids.filtered(lambda l: l.visit_id))

    def _sync_state_from_lines(self):
        for rec in self:
            if rec.state == "cancel":
                continue

            if not rec.line_ids:
                new_state = "draft"
            else:
                line_states = set(rec.line_ids.mapped("state"))

                if line_states == {"pending"}:
                    new_state = "draft"
                elif line_states.issubset({"visited", "skipped"}):
                    new_state = "done"
                else:
                    new_state = "in_progress"

            if rec.state != new_state:
                rec.with_context(route_plan_skip_sync=True).write({"state": new_state})

    def action_view_visits(self):
        self.ensure_one()

        visits = self.line_ids.mapped("visit_id")
        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["domain"] = [("id", "in", visits.ids)]

        if len(visits) == 1:
            action["res_id"] = visits.id
            action["views"] = [(False, "form")]
        else:
            action["views"] = [(False, "list"), (False, "form")]

        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.plan") or "New"
        records = super().create(vals_list)
        records._sync_state_from_lines()
        return records

    def write(self, vals):
        protected_fields = {"date", "user_id", "vehicle_id"}

        if protected_fields.intersection(vals.keys()):
            for rec in self:
                if rec.line_ids.filtered("visit_id"):
                    raise UserError(
                        _(
                            "You cannot change Plan Date, Salesperson, or Vehicle after visits have already been created from this plan."
                        )
                    )

        result = super().write(vals)

        if self.env.context.get("route_plan_skip_sync"):
            return result

        if "state" not in vals or vals.get("state") != "cancel":
            self._sync_state_from_lines()

        return result
