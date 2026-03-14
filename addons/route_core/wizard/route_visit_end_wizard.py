from odoo import fields, models


class RouteVisitEndWizard(models.TransientModel):
    _name = "route.visit.end.wizard"
    _description = "Route Visit End Wizard"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        required=True,
    )

    message = fields.Text(
        string="Message",
        default="No Sale Order has been created for this visit yet. Choose what you want to do.",
        readonly=True,
    )

    def action_create_sale_order(self):
        self.ensure_one()
        return self.route_visit_id.action_create_sale_order()

    def action_end_without_sale(self):
        self.ensure_one()
        self.route_visit_id.action_force_end_visit()
        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
