from odoo import fields, models, _
from odoo.exceptions import ValidationError


class RouteVisitEndWizard(models.TransientModel):
    _name = "route.visit.end.wizard"
    _description = "Route Visit End Wizard"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )
    no_sale_reason = fields.Text(
        string="Reason for Ending Without Sale",
    )

    def action_create_sale_order(self):
        self.ensure_one()
        return self.visit_id.action_create_sale_order()

    def action_end_without_sale(self):
        self.ensure_one()

        if not self.no_sale_reason or not self.no_sale_reason.strip():
            raise ValidationError(_("You must enter a reason before ending the visit without sale."))

        self.visit_id.action_end_without_sale(self.no_sale_reason)
        return self.env.ref("route_core.action_route_visit").read()[0]
