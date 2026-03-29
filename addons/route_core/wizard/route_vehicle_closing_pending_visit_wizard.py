from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError


class RouteVehicleClosingPendingVisitWizard(models.TransientModel):
    _name = "route.vehicle.closing.pending.visit.wizard"
    _description = "Resolve Pending Visits Before Vehicle Closing"

    closing_id = fields.Many2one(
        "route.vehicle.closing",
        string="Vehicle Closing",
        required=True,
        readonly=True,
    )
    plan_id = fields.Many2one(
        "route.plan",
        string="Route Plan",
        related="closing_id.plan_id",
        readonly=True,
    )
    plan_date = fields.Date(
        string="Plan Date",
        related="closing_id.plan_date",
        readonly=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        related="closing_id.vehicle_id",
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        related="closing_id.user_id",
        readonly=True,
    )
    line_ids = fields.One2many(
        "route.vehicle.closing.pending.visit.wizard.line",
        "wizard_id",
        string="Pending Visits",
    )
    pending_count = fields.Integer(
        string="Pending Visits",
        compute="_compute_pending_count",
    )

    def _compute_pending_count(self):
        for rec in self:
            rec.pending_count = len(rec.line_ids)

    def _get_next_day_date(self):
        self.ensure_one()
        base_date = fields.Date.to_date(self.plan_date or fields.Date.context_today(self))
        return base_date + timedelta(days=1)

    def _get_target_plan_domain(self, source_plan, source_line, target_date):
        target_area = source_plan.area_id or source_line.area_id
        domain = [
            ("date", "=", target_date),
            ("vehicle_id", "=", source_plan.vehicle_id.id),
            ("user_id", "=", source_plan.user_id.id),
            ("state", "!=", "cancel"),
        ]
        if target_area:
            domain.append(("area_id", "=", target_area.id))
        return domain

    def _get_or_create_target_plan(self, source_line, target_date):
        self.ensure_one()
        source_plan = self.plan_id
        target_plan = self.env["route.plan"].search(
            self._get_target_plan_domain(source_plan, source_line, target_date),
            order="id desc",
            limit=1,
        )
        if target_plan:
            if target_plan.planning_finalized:
                raise UserError(
                    _(
                        "The target route plan for %(date)s is already finalized. "
                        "Please reopen it first or choose another date."
                    )
                    % {"date": target_date}
                )
            return target_plan

        return self.env["route.plan"].create({
            "date": target_date,
            "user_id": source_plan.user_id.id,
            "vehicle_id": source_plan.vehicle_id.id,
            "area_id": (source_plan.area_id.id if source_plan.area_id else (source_line.area_id.id if source_line.area_id else False)),
            "notes": _("Auto-created from vehicle day closing resolution for pending visits."),
        })

    def _build_target_line_note(self, source_line, decision, target_date):
        self.ensure_one()
        base_note = (source_line.note or "").strip()
        if decision == "carry_forward":
            resolution_note = _(
                "Carried forward from %(plan)s dated %(date)s during vehicle day closing."
            ) % {
                "plan": self.plan_id.display_name,
                "date": self.plan_date,
            }
        else:
            resolution_note = _(
                "Rescheduled from %(plan)s dated %(date)s to %(target)s during vehicle day closing."
            ) % {
                "plan": self.plan_id.display_name,
                "date": self.plan_date,
                "target": target_date,
            }

        if not base_note:
            return resolution_note
        if resolution_note in base_note:
            return base_note
        return "%s\n%s" % (base_note, resolution_note)

    def _close_source_line(self, source_line):
        self.ensure_one()
        visit = source_line.visit_id
        if visit and visit.state not in ("done", "cancel"):
            visit.with_context(route_visit_force_write=True).write({
                "state": "cancel",
                "visit_process_state": "cancel",
            })

        source_line.with_context(route_plan_line_skip_plan_sync=True).write({
            "state": "skipped",
            "visit_id": False,
        })

    def _upsert_target_line(self, target_plan, source_line, decision, target_date):
        self.ensure_one()
        target_line = target_plan.line_ids.filtered(
            lambda line: line.outlet_id.id == source_line.outlet_id.id
        )[:1]

        target_note = self._build_target_line_note(source_line, decision, target_date)

        if target_line:
            if target_line.state in ("visited", "skipped") or (
                target_line.visit_id and target_line.visit_id.state in ("done", "cancel")
            ):
                raise UserError(
                    _(
                        "Outlet '%(outlet)s' already has a completed line on route plan %(plan)s. "
                        "Please choose another date or reopen the target line first."
                    )
                    % {
                        "outlet": source_line.outlet_id.display_name,
                        "plan": target_plan.display_name,
                    }
                )

            vals = {}
            if target_line.state != "pending":
                vals["state"] = "pending"
            if target_line.visit_id:
                vals["visit_id"] = False
            if target_note and "note" in target_line._fields:
                current_note = (target_line.note or "").strip()
                if target_note not in current_note:
                    vals["note"] = (current_note + "\n" + target_note).strip() if current_note else target_note

            if vals:
                target_line.write(vals)
            return target_line

        next_sequence = max(target_plan.line_ids.mapped("sequence") or [0]) + 10
        return self.env["route.plan.line"].create({
            "plan_id": target_plan.id,
            "sequence": next_sequence,
            "area_id": source_line.area_id.id if source_line.area_id else (target_plan.area_id.id if target_plan.area_id else False),
            "outlet_id": source_line.outlet_id.id,
            "note": target_note or source_line.note or False,
        })

    def action_apply_resolution(self):
        self.ensure_one()

        closing = self.closing_id
        if not closing or closing.state != "draft":
            raise UserError(_("Vehicle closing must still be in draft before resolving pending visits."))

        active_lines = closing._get_in_progress_plan_lines()
        if active_lines:
            outlet_names = ", ".join(active_lines.mapped("outlet_id.display_name"))
            raise UserError(
                _(
                    "You still have visit(s) in progress for: %(outlets)s. "
                    "Please finish them before closing the vehicle day."
                )
                % {"outlets": outlet_names}
            )

        for wizard_line in self.line_ids:
            source_line = wizard_line.plan_line_id
            if not source_line or source_line.plan_id != closing.plan_id:
                continue
            if source_line.state != "pending":
                continue

            if wizard_line.decision == "skip_today":
                self._close_source_line(source_line)
                continue

            if wizard_line.decision == "carry_forward":
                target_date = self._get_next_day_date()
            else:
                target_date = wizard_line.target_date

            if not target_date:
                raise UserError(
                    _("Please set a target date for outlet '%s'.")
                    % (source_line.outlet_id.display_name,)
                )

            target_plan = self._get_or_create_target_plan(source_line, target_date)
            self._upsert_target_line(target_plan, source_line, wizard_line.decision, target_date)

            self._close_source_line(source_line)

        closing.plan_id._sync_state_from_lines()

        result = closing.with_context(route_vehicle_closing_pending_resolved=True).action_close_day()
        if isinstance(result, dict):
            return result
        return closing._open_form_action()


class RouteVehicleClosingPendingVisitWizardLine(models.TransientModel):
    _name = "route.vehicle.closing.pending.visit.wizard.line"
    _description = "Pending Visit Resolution Line"

    wizard_id = fields.Many2one(
        "route.vehicle.closing.pending.visit.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    plan_line_id = fields.Many2one(
        "route.plan.line",
        string="Route Plan Line",
        required=True,
        readonly=True,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        related="plan_line_id.outlet_id",
        readonly=True,
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        related="plan_line_id.area_id",
        readonly=True,
    )
    existing_visit_id = fields.Many2one(
        "route.visit",
        string="Existing Visit",
        related="plan_line_id.visit_id",
        readonly=True,
    )
    note = fields.Text(
        string="Current Note",
        related="plan_line_id.note",
        readonly=True,
    )
    decision = fields.Selection(
        [
            ("carry_forward", "Carry Forward to Next Day"),
            ("reschedule", "Reschedule to Specific Date"),
            ("skip_today", "Skip for Today"),
        ],
        string="Resolution",
        required=True,
        default="carry_forward",
    )
    target_date = fields.Date(
        string="Target Date",
    )

    @api.onchange("decision")
    def _onchange_decision(self):
        for rec in self:
            if rec.decision == "carry_forward" and rec.wizard_id:
                rec.target_date = rec.wizard_id._get_next_day_date()
            elif rec.decision == "skip_today":
                rec.target_date = False

    @api.constrains("decision", "target_date")
    def _check_target_date(self):
        for rec in self:
            if rec.decision == "reschedule" and not rec.target_date:
                raise UserError(
                    _("Please choose a target date when you use 'Reschedule to Specific Date'.")
                )
