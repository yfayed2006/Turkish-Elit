from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    route_visit_id = fields.Many2one(
        "route.visit",
        string="Route Visit",
        copy=False,
        ondelete="set null",
    )

    route_visit_state = fields.Selection(
        related="route_visit_id.state",
        string="Visit Status",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            route_visit_id = vals.get("route_visit_id")
            if route_visit_id:
                visit = self.env["route.visit"].browse(route_visit_id)
                if visit.exists() and visit.state != "in_progress":
                    raise UserError(_(
                        "You cannot create a Sales Order for a visit that is not in progress."
                    ))
        return super().create(vals_list)

    def write(self, vals):
        if "route_visit_id" in vals and vals.get("route_visit_id"):
            visit = self.env["route.visit"].browse(vals["route_visit_id"])
            if visit.exists() and visit.state != "in_progress":
                raise UserError(_(
                    "You cannot link this Sales Order to a visit that is not in progress."
                ))
        return super().write(vals)
