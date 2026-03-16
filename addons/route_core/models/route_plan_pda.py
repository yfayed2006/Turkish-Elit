from odoo import models


class RoutePlan(models.Model):
    _inherit = "route.plan"

    def action_open_pda_screen(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit_pda").read()[0]
        action["domain"] = [("plan_id", "=", self.id)]
        action["context"] = {
            "default_plan_id": self.id,
            "pda_mode": True,
        }
        action["name"] = f"PDA - {self.display_name}"
        return action
