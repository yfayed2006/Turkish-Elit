from ast import literal_eval

from odoo import api, _, fields, models
from odoo.exceptions import UserError, ValidationError


class RoutePlanLine(models.Model):
    _name = "route.plan.line"
    _description = "Route Plan Line"
    _order = "sequence, id"

    def _skip_reason_selection(self):
        return [
            ("outlet_closed", "Outlet Closed"),
            ("customer_unavailable", "Customer Not Available"),
            ("access_problem", "Delivery/Access Problem"),
            ("postponed_by_supervisor", "Postponed by Supervisor"),
            ("carried_forward", "Carried Forward"),
            ("rescheduled", "Rescheduled"),
            ("cancelled_by_supervisor", "Cancelled by Supervisor"),
            ("other", "Other"),
        ]

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
    plan_date = fields.Date(
        string="Plan Date",
        related="plan_id.date",
        store=True,
        readonly=True,
    )
    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        related="plan_id.user_id",
        store=True,
        readonly=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        related="plan_id.vehicle_id",
        store=True,
        readonly=True,
    )
    weekly_schedule_id = fields.Many2one(
        "route.weekly.schedule",
        string="Weekly Schedule",
        related="plan_id.weekly_schedule_id",
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
    skip_reason = fields.Selection(
        selection=_skip_reason_selection,
        string="Skip Reason",
        readonly=True,
        copy=False,
    )
    skip_note = fields.Text(
        string="Skip Note",
        readonly=True,
        copy=False,
    )
    skipped_by_id = fields.Many2one(
        "res.users",
        string="Skipped By",
        readonly=True,
        copy=False,
    )
    skipped_datetime = fields.Datetime(
        string="Skipped On",
        readonly=True,
        copy=False,
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

    def _get_skip_reason_label(self, reason):
        return dict(self._skip_reason_selection()).get(reason, reason or "")

    def _build_skip_reason_text(self, reason, note=None):
        label = self._get_skip_reason_label(reason)
        if note:
            return "%s - %s" % (label, note)
        return label

    def _ensure_can_skip(self):
        for rec in self:
            if not rec.plan_id:
                raise UserError(_("Please save the route plan first."))
            if rec.state == "skipped":
                raise UserError(_("This route plan line is already skipped."))
            if rec.state == "visited" or (rec.visit_id and rec.visit_id.state == "done"):
                raise UserError(_("You cannot skip a visit line that is already completed."))

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
        for rec in self:
            rec.shortage_count = 0

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
        is_completed_line = self.state in ("visited", "skipped") or (
            visit and visit.state in ("done", "cancel")
        )

        if is_completed_line and visit:
            return self._get_pda_visit_action(visit)

        self.plan_id._ensure_single_active_visit(current_line=self)

        if not visit:
            visit = self.plan_id._create_visit_for_line(self)
        elif visit.state not in ("done", "cancel"):
            self.write({"state": "in_progress"})

        return self._get_pda_visit_action(visit)

    def action_view_outlet_shortages(self):
        return False

    def action_open_skip_visit_wizard(self):
        self.ensure_one()
        self._ensure_can_skip()
        return {
            "type": "ir.actions.act_window",
            "name": _("Skip Visit"),
            "res_model": "route.plan.skip.visit.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_line_id": self.id,
            },
        }

    def action_skip_visit(self, reason, note=False):
        self.ensure_one()
        self._ensure_can_skip()

        if not reason:
            raise UserError(_("Please select a skip reason."))

        now = fields.Datetime.now()
        if self.visit_id and self.visit_id.state not in ("done", "cancel"):
            self.visit_id.with_context(route_visit_force_write=True).write({
                "state": "cancel",
                "visit_process_state": "cancel",
                "end_datetime": now,
                "no_sale_reason": self._build_skip_reason_text(reason, note),
            })

        self.write({
            "state": "skipped",
            "skip_reason": reason,
            "skip_note": note or False,
            "skipped_by_id": self.env.user.id,
            "skipped_datetime": now,
        })
        return True

    def _get_matching_line_in_plan(self, plan):
        self.ensure_one()
        if not plan:
            return self.env["route.plan.line"]
        return plan.line_ids.filtered(lambda line: line.outlet_id.id == self.outlet_id.id)[:1]

    def _ensure_current_plan_line_can_be_reworked(self, current_line):
        self.ensure_one()
        if not current_line:
            return

        if current_line.state == "visited" or (current_line.visit_id and current_line.visit_id.state == "done"):
            raise UserError(
                _(
                    "Outlet '%s' is already completed in the current route plan. "
                    "You cannot cancel or reschedule it from pending review."
                )
                % (current_line.outlet_id.display_name,)
            )

        if current_line.state == "in_progress" or (current_line.visit_id and current_line.visit_id.state == "in_progress"):
            raise UserError(
                _(
                    "Outlet '%s' is already in progress in the current route plan. "
                    "Please finish or cancel the current visit first."
                )
                % (current_line.outlet_id.display_name,)
            )

    def _build_resolution_note(self, auto_note, note=False):
        if note:
            return (auto_note + "\n" + note) if auto_note else note
        return auto_note or False

    def _apply_supervisor_skip_to_current_line(self, current_line, reason, note=False, now=False):
        self.ensure_one()
        current_line.ensure_one()
        now = now or fields.Datetime.now()

        combined_note = self._build_resolution_note(
            _("Resolved from previous pending review of %s.") % (self.outlet_id.display_name,),
            note,
        )

        if current_line.visit_id and current_line.visit_id.state not in ("done", "cancel"):
            current_line.visit_id.with_context(route_visit_force_write=True).write({
                "state": "cancel",
                "visit_process_state": "cancel",
                "end_datetime": now,
                "no_sale_reason": current_line._build_skip_reason_text(reason, combined_note),
            })

        current_line.write({
            "state": "skipped",
            "visit_id": False,
            "skip_reason": reason,
            "skip_note": combined_note,
            "skipped_by_id": self.env.user.id,
            "skipped_datetime": now,
        })

    def action_resolve_previous_pending(
        self,
        decision,
        current_plan,
        target_date=False,
        note=False,
        apply_current_plan_effect=True,
    ):
        self.ensure_one()

        if self.state != "pending":
            return False

        if not current_plan:
            raise UserError(_("A target route plan is required."))

        now = fields.Datetime.now()
        target_plan = False
        auto_note = False
        skip_reason = False
        current_line = self._get_matching_line_in_plan(current_plan) if apply_current_plan_effect else self.env["route.plan.line"]

        if decision == "carry_forward":
            target_plan = current_plan
            auto_note = _("Carried forward to plan %s.") % (target_plan.name,)
            skip_reason = "carried_forward"
        elif decision == "reschedule":
            if not target_date:
                raise UserError(_("Please select a target date for rescheduling."))
            target_plan = current_plan._get_or_create_plan_for_date(target_date, area=self.area_id)
            auto_note = _("Rescheduled to %s (%s).") % (
                fields.Date.to_string(target_plan.date),
                target_plan.name,
            )
            skip_reason = "rescheduled"
        elif decision == "cancel":
            auto_note = _("Cancelled by supervisor.")
            skip_reason = "cancelled_by_supervisor"
        else:
            raise UserError(_("Unsupported pending visit decision."))

        if apply_current_plan_effect and current_line and decision in ("cancel", "reschedule"):
            self._ensure_current_plan_line_can_be_reworked(current_line)

        if self.visit_id and self.visit_id.state not in ("done", "cancel"):
            self.visit_id.with_context(route_visit_force_write=True).write({
                "state": "cancel",
                "visit_process_state": "cancel",
                "end_datetime": now,
                "no_sale_reason": self._build_skip_reason_text(skip_reason, note),
            })

        if target_plan and apply_current_plan_effect:
            existing_target_line = self._get_matching_line_in_plan(target_plan)
            if not existing_target_line:
                target_plan._ensure_plan_editable(_("load pending visits into this route plan"))
                next_sequence = max(target_plan.line_ids.mapped("sequence") or [0]) + 10
                self.env["route.plan.line"].create({
                    "plan_id": target_plan.id,
                    "sequence": next_sequence,
                    "area_id": self.area_id.id,
                    "outlet_id": self.outlet_id.id,
                    "note": self.note or False,
                })

        if apply_current_plan_effect and current_line:
            if decision == "cancel":
                self._apply_supervisor_skip_to_current_line(
                    current_line=current_line,
                    reason="cancelled_by_supervisor",
                    note=note,
                    now=now,
                )
            elif decision == "reschedule":
                if current_line.plan_id.planning_finalized or current_line.visit_id:
                    self._apply_supervisor_skip_to_current_line(
                        current_line=current_line,
                        reason="rescheduled",
                        note=note,
                        now=now,
                    )
                else:
                    current_line.unlink()

        combined_note = self._build_resolution_note(auto_note, note)

        vals = {
            "state": "skipped",
            "visit_id": False,
            "skip_reason": skip_reason,
            "skip_note": combined_note,
            "skipped_by_id": self.env.user.id,
            "skipped_datetime": now,
        }
        self.write(vals)
        return target_plan

    def action_reopen_line(self):
        self.ensure_one()

        if self.state != "skipped":
            raise UserError(_("Only skipped lines can be reopened."))

        vals = {
            "state": "pending",
            "skip_reason": False,
            "skip_note": False,
            "skipped_by_id": False,
            "skipped_datetime": False,
        }
        if self.visit_id and self.visit_id.state == "cancel":
            vals["visit_id"] = False

        self.write(vals)
        return {"type": "ir.actions.client", "tag": "reload"}

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
        allowed_locked_fields = {
            "visit_id",
            "state",
            "skip_reason",
            "skip_note",
            "skipped_by_id",
            "skipped_datetime",
        }
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

