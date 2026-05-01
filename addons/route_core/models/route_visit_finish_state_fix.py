from odoo import _, fields, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    def action_end_visit(self):
        """Allow the PDA Finish Visit button to close visits that already
        reached the operational finish step.

        Some consignment visits move to Collection Done before the final button
        is pressed. Older logic allowed ending only when state == in_progress,
        so the top Finish Visit button raised "Only visits in progress can be
        ended." even though the visit was ready to close.
        """
        self.ensure_one()

        if self.state == "done" and self.visit_process_state == "done":
            return True

        if self.state == "cancel" or self.visit_process_state == "cancel":
            raise UserError(_("Cancelled visits cannot be ended."))

        allowed_process_states = {
            "reconciled",
            "collection_done",
            "ready_to_close",
        }

        if self.state != "in_progress" and self.visit_process_state not in allowed_process_states:
            raise UserError(_("Only active visits that reached the finish step can be ended."))

        self.with_context(route_visit_force_write=True).write({
            "state": "done",
            "visit_process_state": "done",
            "end_datetime": fields.Datetime.now(),
        })
        return True
