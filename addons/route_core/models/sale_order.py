from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        result = super().action_confirm()

        if len(self) == 1:
            visit = self.env["route.visit"].search(
                [("sale_order_id", "=", self.id)],
                limit=1,
            )
            if visit:
                visit.write({
                    "state": "done",
                    "end_datetime": fields.Datetime.now(),
                })
                return self.env.ref("route_core.action_route_visit").read()[0]

        return result
