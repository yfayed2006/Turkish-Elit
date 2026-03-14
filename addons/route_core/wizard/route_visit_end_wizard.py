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
    action_choice = fields.Selection(
        [
            ("create_sale_order", "Create Sale Order"),
            ("end_without_sale", "End Without Sale"),
        ],
        string="Action",
        required=True,
        default="create_sale_order",
    )
    reason = fields.Text(string="Reason")

    def action_confirm(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("No visit found."))

        if self.visit_id.state != "in_progress":
            raise UserError(_("Only visits in progress can be ended."))

        if self.action_choice == "create_sale_order":
            return self.visit_id.action_create_sale_order()

        if self.action_choice == "end_without_sale":
            if not self.reason:
                raise UserError(_("Please enter a reason for ending the visit without sale."))
            self.visit_id.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
                "no_sale_reason": self.reason,
            })
            return {"type": "ir.actions.act_window_close"}

        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
