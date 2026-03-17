from odoo import api, models, _
from odoo.exceptions import UserError


class RoutePlan(models.Model):
    _inherit = "route.plan"

    def _prepare_visit_vals(self, line):
        vals = super()._prepare_visit_vals(line)

        partner = False
        if line.outlet_id and line.outlet_id.partner_id:
            partner = line.outlet_id.partner_id.commercial_partner_id
        elif line.partner_id:
            partner = line.partner_id.commercial_partner_id

        if partner:
            vals["partner_id"] = partner.id

        return vals


class RouteVisit(models.Model):
    _inherit = "route.visit"

    def _get_resolved_customer_partner(self):
        self.ensure_one()

        partner = self.partner_id
        if not partner and self.outlet_id and self.outlet_id.partner_id:
            partner = self.outlet_id.partner_id

        return partner.commercial_partner_id if partner else False

    def _ensure_customer_partner(self, raise_if_missing=False):
        for rec in self:
            partner = rec._get_resolved_customer_partner()

            if partner and rec.partner_id != partner:
                rec.with_context(route_visit_force_write=True).write({
                    "partner_id": partner.id,
                })

            if raise_if_missing and not partner:
                raise UserError(_(
                    "Customer is missing on this visit.\n"
                    "Please link the outlet to a customer before continuing."
                ))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("partner_id") and vals.get("outlet_id"):
                outlet = self.env["route.outlet"].browse(vals["outlet_id"])
                if outlet.exists() and outlet.partner_id:
                    vals["partner_id"] = outlet.partner_id.commercial_partner_id.id

        visits = super().create(vals_list)
        visits._ensure_customer_partner()
        return visits

    def action_start_visit(self):
        self._ensure_customer_partner(raise_if_missing=True)
        return super().action_start_visit()

    def action_create_sale_order(self):
        self._ensure_customer_partner(raise_if_missing=True)
        return super().action_create_sale_order()

    def _create_pending_refill_backorder(self):
        self._ensure_customer_partner(raise_if_missing=True)
        return super()._create_pending_refill_backorder()
