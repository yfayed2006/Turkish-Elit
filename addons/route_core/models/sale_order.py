from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def button_confirm(self):
        result = super().button_confirm()

        route_visit_id = self.env.context.get("route_visit_id")
        if route_visit_id and len(self) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": "Route Visit",
                "res_model": "route.visit",
                "res_id": route_visit_id,
                "view_mode": "form",
                "target": "current",
            }

        return result
