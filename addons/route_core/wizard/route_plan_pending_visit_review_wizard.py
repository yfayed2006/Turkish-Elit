from odoo import api, _, fields, models
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
    line_ids = fields.One2many(
        "route.plan.pending.visit.review.wizard.line",
        "wizard_id",
        string="Pending Visits",
    )
    pending_count = fields.Integer(
        string="Pending Visits",
        compute="_compute_pending_count",
    )

    @api.depends("line_ids")
    def _compute_pending_count(self):
        for rec in self:
            rec.pending_count = len(rec.line_ids)

    def action_apply_review(self):
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("There are no pending visits to review."))

        for line in self.line_ids:
            line.action_apply_decision()

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
        store=False,
        readonly=True,
    )
    source_plan_date = fields.Date(
        string="Source Date",
        related="source_line_id.plan_id.date",
        store=False,
        readonly=True,
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        related="source_line_id.area_id",
        store=False,
        readonly=True,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        related="source_line_id.outlet_id",
        store=False,
        readonly=True,
    )
    current_plan_has_outlet = fields.Boolean(
        string="Already in Current Plan",
        compute="_compute_current_plan_has_outlet",
    )
    decision = fields.Selection(
        [
            ("carry_forward", "Carry Forward to Current Plan"),
            ("reschedule", "Reschedule to Specific Date"),
            ("cancel", "Cancel Pending Visit"),
        ],
        string="Decision",
        required=True,
        default="carry_forward",
    )
    target_date = fields.Date(string="Target Date")
    note = fields.Text(string="Supervisor Note")

    @api.depends("wizard_id.plan_id", "source_line_id.outlet_id")
    def _compute_current_plan_has_outlet(self):
        for rec in self:
            current_plan = rec.wizard_id.plan_id
            rec.current_plan_has_outlet = bool(
                current_plan
                and rec.source_line_id.outlet_id
                and current_plan.line_ids.filtered(
                    lambda line: line.outlet_id.id == rec.source_line_id.outlet_id.id
                )
            )

    @api.onchange("decision")
    def _onchange_decision(self):
        for rec in self:
            if rec.decision == "carry_forward" and rec.wizard_id.plan_id:
                rec.target_date = rec.wizard_id.plan_id.date
            elif rec.decision == "cancel":
                rec.target_date = False

    def action_apply_decision(self):
        self.ensure_one()
        self.source_line_id.action_resolve_previous_pending(
            decision=self.decision,
            current_plan=self.wizard_id.plan_id,
            target_date=self.target_date,
            note=self.note,
        )
        return True
