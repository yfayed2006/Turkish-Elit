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

    def _get_pda_visit_action(self, visit):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit_pda").read()[0]
        action["res_id"] = visit.id
        action["view_mode"] = "form"
        action["views"] = [(self.env.ref("route_core.view_route_visit_pda_form").id, "form")]
        action["target"] = "current"
        action["context"] = {
            **(action.get("context") or {}),
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

        return self._get_pda_visit_action(visit)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("area_id") and vals.get("plan_id"):
                plan = self.env["route.plan"].browse(vals["plan_id"])
                if plan.exists() and plan.area_id:
                    vals["area_id"] = plan.area_id.id

        records = super().create(vals_list)
        records._check_unique_outlet_per_plan()
        records._check_area_matches_outlet()
        records._sync_parent_plan_state()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._check_unique_outlet_per_plan()
        self._check_area_matches_outlet()
        if not self.env.context.get(self._plan_sync_context_key):
            self._sync_parent_plan_state()
        return result

    def unlink(self):
        plans = self.mapped("plan_id")
        result = super().unlink()
        if plans:
            plans._sync_state_from_lines()
        return result
