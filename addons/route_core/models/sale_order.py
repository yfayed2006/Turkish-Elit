from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_route_return_action(self, visit):
        plan_line = self.env["route.plan.line"].search(
            [("visit_id", "=", visit.id)],
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
                return self._get_route_return_action(visit)

        return result
