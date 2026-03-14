from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def button_confirm(self):
        result = super().button_confirm()

        if len(self) == 1 and self.origin:
            visit = self.env["route.visit"].search(
                [("name", "=", self.origin)],
                limit=1,
            )
            if visit:
                return {
                    "type": "ir.actions.act_window",
                    "name": "Route Visit",
                    "res_model": "route.visit",
                    "res_id": visit.id,
                    "view_mode": "form",
                    "target": "current",
                }

        return result
