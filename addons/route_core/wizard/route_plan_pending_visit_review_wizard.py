from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RoutePlanPendingVisitReviewWizard(models.TransientModel):
    _name = "route.plan.pending.visit.review.wizard"
    _description = "Route Plan Pending Visit Review Wizard"

    plan_id = fields.Many2one(
        "route.plan",
        string="Current Route Plan",
        required=True,
        readonly=True,
    )
    review_line_ids = fields.One2many(
        "route.plan.pending.visit.review.wizard.line",
        "wizard_id",
        string="Pending Visits",
    )
    pending_count = fields.Integer(
        string="Pending Count",
        compute="_compute_pending_count",
    )

    @api.depends("review_line_ids")
    def _compute_pending_count(self):
        for rec in self:
            rec.pending_count = len(rec.review_line_ids)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        plan_id = self.env.context.get("default_plan_id") or vals.get("plan_id")
        if not plan_id:
            return vals

        plan = self.env["route.plan"].browse(plan_id)
        if not plan.exists():
            return vals

        review_lines = []
        for source_line in plan._get_previous_pending_lines():
            review_lines.append(fields.Command.create({
                "source_line_id": source_line.id,
                "decision": "carry_forward",
            }))

        vals["plan_id"] = plan.id
        vals["review_line_ids"] = review_lines
        return vals

    def _get_or_create_target_plan(self, target_date):
        self.ensure_one()
        if not target_date:
            raise UserError(_("Please set a target date."))

        domain = [
            ("date", "=", target_date),
            ("user_id", "=", self.plan_id.user_id.id),
            ("vehicle_id", "=", self.plan_id.vehicle_id.id),
            ("state", "!=", "cancel"),
        ]
        if self.plan_id.area_id:
            domain.append(("area_id", "=", self.plan_id.area_id.id))

        target_plan = self.env["route.plan"].search(domain, limit=1)
        if not target_plan:
            target_plan = self.env["route.plan"].create({
                "date": target_date,
                "user_id": self.plan_id.user_id.id,
                "vehicle_id": self.plan_id.vehicle_id.id,
                "area_id": self.plan_id.area_id.id if self.plan_id.area_id else False,
                "notes": _("Created automatically from pending visit review."),
            })
        return target_plan

    def _prepare_destination_note(self, source_line):
        note_parts = []
        if source_line.note:
            note_parts.append((source_line.note or "").strip())
        note_parts.append(
            _("Carried from %(plan)s (%(date)s)") % {
                "plan": source_line.plan_id.display_name,
                "date": source_line.plan_id.date,
            }
        )
        return "\n".join([part for part in note_parts if part])

    def _validate_destination_duplicates(self):
        self.ensure_one()
        planned_targets = {}
        current_plan_outlets = set(self.plan_id.line_ids.mapped("outlet_id").ids)

        for line in self.review_line_ids:
            source_line = line.source_line_id
            if not source_line or source_line.state != "pending":
                continue

            if line.decision == "carry_forward":
                key = ("current", self.plan_id.id)
                planned_targets.setdefault(key, set())
                if source_line.outlet_id.id in current_plan_outlets:
                    raise UserError(
                        _("Outlet '%s' is already present in the current route plan.")
                        % source_line.outlet_id.display_name
                    )
                if source_line.outlet_id.id in planned_targets[key]:
                    raise UserError(
                        _("Outlet '%s' was selected more than once to carry forward into the current route plan.")
                        % source_line.outlet_id.display_name
                    )
                planned_targets[key].add(source_line.outlet_id.id)

            elif line.decision == "reschedule":
                if not line.reschedule_date:
                    raise UserError(
                        _("Please set a reschedule date for outlet '%s'.")
                        % source_line.outlet_id.display_name
                    )
                target_plan = self._get_or_create_target_plan(line.reschedule_date)
                if target_plan.planning_finalized:
                    raise UserError(
                        _("Target route plan '%s' is already finalized. Please choose another date.")
                        % target_plan.display_name
                    )
                key = ("date", target_plan.id)
                planned_targets.setdefault(key, set())
                existing_outlets = set(target_plan.line_ids.mapped("outlet_id").ids)
                if source_line.outlet_id.id in existing_outlets:
                    raise UserError(
                        _("Outlet '%(outlet)s' already exists in route plan '%(plan)s'.")
                        % {
                            "outlet": source_line.outlet_id.display_name,
                            "plan": target_plan.display_name,
                        }
                    )
                if source_line.outlet_id.id in planned_targets[key]:
                    raise UserError(
                        _("Outlet '%(outlet)s' was selected more than once for route plan '%(plan)s'.")
                        % {
                            "outlet": source_line.outlet_id.display_name,
                            "plan": target_plan.display_name,
                        }
                    )
                planned_targets[key].add(source_line.outlet_id.id)

    def action_confirm(self):
        self.ensure_one()

        if not self.review_line_ids:
            raise UserError(_("There are no pending visits to review."))

        self._validate_destination_duplicates()

        for line in self.review_line_ids:
            source_line = line.source_line_id
            if not source_line or source_line.state != "pending":
                continue

            if line.decision == "carry_forward":
                self.env["route.plan.line"].create({
                    "plan_id": self.plan_id.id,
                    "sequence": max(self.plan_id.line_ids.mapped("sequence") or [0]) + 10,
                    "area_id": source_line.area_id.id or (self.plan_id.area_id.id if self.plan_id.area_id else False),
                    "outlet_id": source_line.outlet_id.id,
                    "note": self._prepare_destination_note(source_line),
                })
                source_line.action_apply_pending_supervisor_decision(
                    "carry_forward",
                    note=_("Carried forward to %(plan)s.") % {"plan": self.plan_id.display_name},
                )

            elif line.decision == "reschedule":
                target_plan = self._get_or_create_target_plan(line.reschedule_date)
                self.env["route.plan.line"].create({
                    "plan_id": target_plan.id,
                    "sequence": max(target_plan.line_ids.mapped("sequence") or [0]) + 10,
                    "area_id": source_line.area_id.id or (target_plan.area_id.id if target_plan.area_id else False),
                    "outlet_id": source_line.outlet_id.id,
                    "note": self._prepare_destination_note(source_line),
                })
                source_line.action_apply_pending_supervisor_decision(
                    "reschedule",
                    note=_("Rescheduled to %(plan)s on %(date)s.") % {
                        "plan": target_plan.display_name,
                        "date": target_plan.date,
                    },
                )

            elif line.decision == "cancel":
                source_line.action_apply_pending_supervisor_decision(
                    "cancel",
                    note=line.supervisor_note or _("Cancelled by supervisor review."),
                )

        return {"type": "ir.actions.client", "tag": "reload"}


class RoutePlanPendingVisitReviewWizardLine(models.TransientModel):
    _name = "route.plan.pending.visit.review.wizard.line"
    _description = "Route Plan Pending Visit Review Wizard Line"

    wizard_id = fields.Many2one(
        "route.plan.pending.visit.review.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    source_line_id = fields.Many2one(
        "route.plan.line",
        string="Source Pending Line",
        required=True,
        readonly=True,
    )
    source_plan_id = fields.Many2one(
        "route.plan",
        string="Source Plan",
        related="source_line_id.plan_id",
        readonly=True,
        store=False,
    )
    source_plan_date = fields.Date(
        string="Source Date",
        related="source_line_id.plan_id.date",
        readonly=True,
        store=False,
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        related="source_line_id.area_id",
        readonly=True,
        store=False,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        related="source_line_id.outlet_id",
        readonly=True,
        store=False,
    )
    visit_id = fields.Many2one(
        "route.visit",
        string="Linked Visit",
        related="source_line_id.visit_id",
        readonly=True,
        store=False,
    )
    decision = fields.Selection(
        [
            ("carry_forward", "Carry Forward to Current Plan"),
            ("reschedule", "Reschedule to Specific Date"),
            ("cancel", "Cancel Pending Visit"),
        ],
        string="Supervisor Decision",
        required=True,
        default="carry_forward",
    )
    reschedule_date = fields.Date(string="Reschedule Date")
    supervisor_note = fields.Char(string="Supervisor Note")

    @api.onchange("decision")
    def _onchange_decision(self):
        for rec in self:
            if rec.decision == "reschedule" and not rec.reschedule_date and rec.wizard_id.plan_id.date:
                rec.reschedule_date = rec.wizard_id.plan_id.date
            if rec.decision != "reschedule":
                rec.reschedule_date = False
