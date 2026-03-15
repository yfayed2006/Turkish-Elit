from odoo import api, fields, models


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

    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def _sync_state_from_lines(self):
        for rec in self:
            if rec.state == "cancel":
                continue

            if not rec.line_ids:
                rec.state = "draft"
                continue

            line_states = set(rec.line_ids.mapped("state"))

            if line_states == {"pending"}:
                rec.state = "draft"
            elif line_states.issubset({"visited", "skipped"}):
                rec.state = "done"
            else:
                rec.state = "in_progress"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.plan") or "New"
        records = super().create(vals_list)
        records._sync_state_from_lines()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "state" not in vals or vals.get("state") != "cancel":
            self._sync_state_from_lines()
        return result
