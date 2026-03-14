from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisitEndWizard(models.TransientModel):
    _name = "route.visit.end.wizard"
    _description = "Route Visit End Wizard"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Reason for Ending Without Sale",
    )

    def action_create_sale_order(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("No visit found."))

        if self.visit_id.state != "in_progress":
            raise UserError(_("Only visits in progress can be processed."))

        return self.visit_id.action_create_sale_order()

    def action_end_without_sale(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("No visit found."))

        if self.visit_id.state != "in_progress":
            raise UserError(_("Only visits in progress can be ended."))

        if not self.reason or not self.reason.strip():
            raise UserError(_("Please enter a reason before ending the visit without sale."))

        self.visit_id.write({
            "state": "done",
            "end_datetime": fields.Datetime.now(),
            "no_sale_reason": self.reason.strip(),
        })

        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
