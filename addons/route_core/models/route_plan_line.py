from ast import literal_eval

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
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        required=True,
        ondelete="restrict",
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        ondelete="restrict",
        domain="[('area_id', '=', area_id)]",
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
            ("in_progress", "In Progress"),
            ("visited", "Visited"),
            ("skipped", "Skipped"),
        ],
        string="Visit Status",
        default="pending",
        required=True,
    )
    button_label = fields.Char(
        string="Button Label",
        compute="_compute_button_label",
    )
    note = fields.Text(string="Line Note")
    shortage_count = fields.Integer(
        string="Open Shortages",
        compute="_compute_shortage_count",
    )

    @property
    def _plan_sync_context_key(self):
        return "route_plan_line_skip_plan_sync"

    def _ensure_line_editable(self, action_label=None):
        for rec in self:
            if rec.plan_id and rec.plan_id.planning_finalized:
                if action_label:
                    raise UserError(
                        _(
                            "You cannot %s after Finalize Daily Plan. "
                            "Please reopen the daily plan first."
                        )
                        % action_label
                    )
                raise UserError(
                    _(
                        "This route plan is locked after Finalize Daily Plan. "
                        "Please reopen the daily plan first."
                    )
                )

    @api.depends("visit_id", "visit_id.state", "state")
    def _compute_button_label(self):
        for rec in self:
            if not rec.visit_id:
                rec.button_label = "Execute Visit"
            elif rec.state in ("visited", "skipped") or rec.visit_id.state in ("done", "cancel"):
                rec.button_label = "View Visit"
            else:
                rec.button_label = "Open Visit"

    @api.depends("outlet_id")
    def _compute_shortage_count(self):
        Shortage = self.env["route.shortage"]
        for rec in self:
            rec.shortage_count = 0
            if rec.outlet_id:
                rec.shortage_count = Shortage.search_count([
                    ("outlet_id", "=", rec.outlet_id.id),
                    ("state", "in", ["open", "planned"]),
                ])

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.outlet_id and rec.outlet_id.area_id != rec.area_id:
                rec.outlet_id = False
        return {
            "domain": {
                "outlet_id": [("area_id", "=", self.area_id.id)] if self.area_id else []
            }
        }

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        for rec in self:
            if rec.outlet_id and not rec.area_id:
                rec.area_id = rec.outlet_id.area_id

    @api.constrains("plan_id", "outlet_id")
    def _check_unique_outlet_per_plan(self):
        for rec in self:
            if not rec.plan_id or not rec.outlet_id:
                continue

            duplicates = rec.plan_id.line_ids.filtered(
                lambda line: line.id != rec.id and line.outlet_id.id == rec.outlet_id.id
            )
            if duplicates:
                raise ValidationError(
                    _("You cannot add the same outlet more than once in the same route plan.")
                )

    @api.constrains("area_id", "outlet_id")
    def _check_area_matches_outlet(self):
        for rec in self:
            if rec.area_id and rec.outlet_id and rec.outlet_id.area_id != rec.area_id:
                raise ValidationError(
                    _("The selected outlet does not belong to the selected area.")
                )

    def _sync_parent_plan_state(self):
        plans = self.mapped("plan_id")
        if plans:
            plans._sync_state_from_lines()

    def _safe_action_context(self, action):
        ctx = action.get("context") or {}
        if isinstance(ctx, str):
            try:
                ctx = literal_eval(ctx)
            except Exception:
                ctx = {}
        if not isinstance(ctx, dict):
            ctx = {}
        return ctx

    def _get_pda_visit_action(self, visit):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit_pda").read()[0]
        base_context = self._safe_action_context(action)

        action["res_id"] = visit.id
        action["view_mode"] = "form"
        action["views"] = [(self.env.ref("route_core.view_route_visit_pda_form").id, "form")]
        action["target"] = "current"
        action["context"] = {
            **base_context,
            "create": 0,
            "edit": 1,
            "delete": 0,
            "pda_mode": True,
            "default_plan_id": self.plan_id.id,
            "default_user_id": self.plan_id.user_id.id if self.plan_id.user_id else False,
            "default_vehicle_id": self.plan_id.vehicle_id.id if self.plan_id.vehicle_id else False,
        }
        return action

    def action_open_or_create_visit(self):
        self.ensure_one()

        if not self.plan_id:
            raise UserError(_("Please save the route plan first."))

        visit = self.visit_id
        if not visit:
            visit = self.plan_id._create_visit_for_line(self)
        elif self.state not in ("visited", "skipped") and visit.state not in ("done", "cancel"):
            self.write({"state": "in_progress"})

        return self._get_pda_visit_action(visit)

    def action_view_outlet_shortages(self):
        self.ensure_one()
        if not self.outlet_id:
            raise UserError(_("This route plan line has no outlet."))
        action = self.env.ref("route_core.action_route_shortage").read()[0]
        action["domain"] = [
            ("outlet_id", "=", self.outlet_id.id),
            ("state", "in", ["open", "planned"]),
        ]
        action["context"] = {
            **self.env.context,
            "default_outlet_id": self.outlet_id.id,
        }
        return action

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("plan_id"):
                plan = self.env["route.plan"].browse(vals["plan_id"])
                if plan.exists() and plan.planning_finalized:
                    raise UserError(
                        _(
                            "You cannot add route plan lines after Finalize Daily Plan. "
                            "Please reopen the daily plan first."
                        )
                    )
                if not vals.get("area_id") and plan.exists() and plan.area_id:
                    vals["area_id"] = plan.area_id.id

        records = super().create(vals_list)
        records._check_unique_outlet_per_plan()
        records._check_area_matches_outlet()
        records._sync_parent_plan_state()
        return records

    def write(self, vals):
        allowed_locked_fields = {"visit_id", "state"}
        restricted_locked_fields = set(vals.keys()) - allowed_locked_fields
        if restricted_locked_fields:
            self._ensure_line_editable(_("edit planned visits"))

        result = super().write(vals)
        self._check_unique_outlet_per_plan()
        self._check_area_matches_outlet()
        if not self.env.context.get(self._plan_sync_context_key):
            self._sync_parent_plan_state()
        return result

    def unlink(self):
        self._ensure_line_editable(_("remove planned visits"))
        plans = self.mapped("plan_id")
        result = super().unlink()
        if plans:
            plans._sync_state_from_lines()
        return result
