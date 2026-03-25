from odoo import _, fields, models
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

    def _get_return_action(self):
        self.ensure_one()

        plan_line = self.env["route.plan.line"].search(
            [("visit_id", "=", self.visit_id.id)],
            limit=1,
        )

        if plan_line and plan_line.plan_id:
            plan = plan_line.plan_id

            remaining_lines = plan.line_ids.filtered(
                lambda line: line.state == "pending"
            )

            if remaining_lines:
                action = self.env.ref("route_core.action_route_plan").read()[0]
                action["res_id"] = plan.id
                action["views"] = [(False, "form")]
                return action

            return self.env.ref("route_core.action_route_plan").read()[0]

        return self.env.ref("route_core.action_route_visit").read()[0]

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
            raise UserError(
                _("Please enter a reason before ending the visit without sale.")
            )

        self.visit_id.write({
            "state": "done",
            "end_datetime": fields.Datetime.now(),
            "no_sale_reason": self.reason.strip(),
        })

        if hasattr(self.visit_id, "_sync_shortages_from_visit"):
            self.visit_id._sync_shortages_from_visit()

        return self._get_return_action()

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
