from odoo import _, fields, models
from odoo.exceptions import UserError


class RoutePlanSkipVisitWizard(models.TransientModel):
    _name = "route.plan.skip.visit.wizard"
    _description = "Skip Route Plan Visit"

    def _skip_reason_selection(self):
        return [
            ("outlet_closed", "Outlet Closed"),
            ("customer_unavailable", "Customer Not Available"),
            ("access_problem", "Delivery/Access Problem"),
            ("postponed_by_supervisor", "Postponed by Supervisor"),
            ("other", "Other"),
        ]

    line_id = fields.Many2one(
        "route.plan.line",
        string="Route Plan Line",
        required=True,
        readonly=True,
    )
    plan_id = fields.Many2one(
        "route.plan",
        string="Route Plan",
        related="line_id.plan_id",
        readonly=True,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        related="line_id.outlet_id",
        readonly=True,
    )
    reason = fields.Selection(
        selection=_skip_reason_selection,
        string="Skip Reason",
        required=True,
    )
    note = fields.Text(string="Note")

    def action_confirm_skip(self):
        self.ensure_one()

        if not self.line_id:
            raise UserError(_("Route plan line is required."))
        if not self.reason:
            raise UserError(_("Please select a skip reason."))

        self.line_id.action_skip_visit(self.reason, self.note)
        return {"type": "ir.actions.act_window_close"}
