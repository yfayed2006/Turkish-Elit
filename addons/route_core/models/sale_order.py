from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        result = super().action_confirm()

        route_visit_id = self.env.context.get("route_visit_id")
        if route_visit_id:
            return {
                "type": "ir.actions.act_window",
                "name": "Route Visit",
                "res_model": "route.visit",
                "view_mode": "form",
                "res_id": route_visit_id,
                "target": "current",
            }

        return result
