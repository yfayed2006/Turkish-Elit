from odoo import models


class RoutePlan(models.Model):
    _inherit = "route.plan"

    def action_open_pda_screen(self):
        self.ensure_one()

        visits = self.line_ids.mapped("visit_id")

        action = self.env.ref("route_core.action_route_visit_pda").read()[0]
        action["domain"] = [("id", "in", visits.ids)]
        action["context"] = {
            "search_default_filter_my_visits": 0,
            "search_default_filter_today": 0,
            "default_user_id": self.user_id.id,
            "default_date": self.date,
            "default_vehicle_id": self.vehicle_id.id if self.vehicle_id else False,
            "default_plan_id": self.id,
            "pda_mode": True,
            "create": 0,
            "delete": 0,
        }
        action["name"] = f"PDA - {self.display_name}"
        return action
