from odoo import api, _, fields, models
from odoo.exceptions import UserError, ValidationError


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
    button_label = fields.Char(
        string="Button Label",
        compute="_compute_button_label",
    )
    note = fields.Text(string="Line Note")

    _sql_constraints = [
        (
            "route_plan_line_unique_outlet_per_plan",
            "unique(plan_id, outlet_id)",
            "You cannot add the same outlet more than once in the same route plan.",
        ),
    ]

    @property
    def _plan_sync_context_key(self):
        return "route_plan_line_skip_plan_sync"

    @api.depends("visit_id", "visit_id.state", "state")
    def _compute_button_label(self):
        for rec in self:
            if not rec.visit_id:
                rec.button_label = "Execute Visit"
            elif rec.state in ("visited", "skipped") or rec.visit_id.state in ("done", "cancel"):
                rec.button_label = "View Visit"
            else:
                rec.button_label = "Open Visit"

    @api.constrains("plan_id", "outlet_id")
    def _check_unique_outlet_per_plan(self):
        for rec in self:
            if not rec.plan_id or not rec.outlet_id:
                continue

            duplicate = self.search(
                [
                    ("id", "!=", rec.id),
                    ("plan_id", "=", rec.plan_id.id),
                    ("outlet_id", "=", rec.outlet_id.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "This outlet is already added in the same route plan. Duplicate outlets are not allowed."
                    )
                )

    def _sync_parent_plan_state(self):
        plans = self.mapped("plan_id")
        if plans:
            plans._sync_state_from_lines()

    def action_open_or_create_visit(self):
        self.ensure_one()

        if not self.plan_id:
            raise UserError(_("Please save the route plan first."))

        other_in_progress_line = self.plan_id.line_ids.filtered(
            lambda line: line.id != self.id
            and line.visit_id
            and line.visit_id.state == "in_progress"
        )[:1]

        if other_in_progress_line:
            raise UserError(
                _(
                    "Another visit is already in progress in this route plan: %s. Please finish it before starting a new visit."
                )
                % (other_in_progress_line.outlet_id.display_name or other_in_progress_line.visit_id.name)
            )

        if self.visit_id:
            action = self.env.ref("route_core.action_route_visit").read()[0]
            action["res_id"] = self.visit_id.id
            action["views"] = [(False, "form")]
            return action

        visit = self.plan_id._create_visit_for_line(self)

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
