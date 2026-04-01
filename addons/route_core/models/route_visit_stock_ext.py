from odoo import fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    vehicle_stock_location_id = fields.Many2one(
        "stock.location",
        string="Vehicle Stock Location",
        compute="_compute_stock_locations",
        store=False,
    )

    outlet_stock_location_id = fields.Many2one(
        "stock.location",
        string="Outlet Stock Location",
        compute="_compute_stock_locations",
        store=False,
    )

    def _route_uses_outlet_stock_location(self):
        """Direct-sale stops deliver from vehicle stock and do not require an
        outlet stock location distinct from the vehicle location.
        """
        self.ensure_one()

        if self.outlet_id and getattr(self.outlet_id, "outlet_operation_mode", False) == "direct_sale":
            return False

        direct_sales_checker = getattr(self, "_is_direct_sales_stop", None)
        if callable(direct_sales_checker):
            try:
                if direct_sales_checker():
                    return False
            except Exception:
                # Keep this helper safe even if the direct-sales workflow layer
                # is not installed yet on the current code branch.
                pass

        return True

    def _compute_stock_locations(self):
        for rec in self:
            rec.vehicle_stock_location_id = rec.vehicle_id.stock_location_id
            rec.outlet_stock_location_id = (
                rec.outlet_id.stock_location_id if rec._route_uses_outlet_stock_location() else False
            )

    def _get_vehicle_stock_location(self):
        self.ensure_one()
        return self.vehicle_id.stock_location_id

    def _get_outlet_stock_location(self):
        self.ensure_one()
        if not self._route_uses_outlet_stock_location():
            return self.env["stock.location"]
        return self.outlet_id.stock_location_id

    def _get_route_stock_locations(self):
        self.ensure_one()
        return {
            "source_location": self._get_vehicle_stock_location(),
            "destination_location": self._get_outlet_stock_location(),
        }

    def _check_route_stock_locations_ready(self):
        for rec in self:
            if not rec.outlet_id:
                raise UserError(_("Please select an outlet before continuing."))

            if not rec.vehicle_id:
                raise UserError(_("Please select a vehicle before continuing."))

            if not rec.vehicle_id.stock_location_id:
                raise UserError(
                    _("Vehicle '%s' does not have a Vehicle Stock Location.")
                    % (rec.vehicle_id.display_name,)
                )

            if not rec._route_uses_outlet_stock_location():
                continue

            if not rec.outlet_id.stock_location_id:
                raise UserError(
                    _("Outlet '%s' does not have an Outlet Stock Location.")
                    % (rec.outlet_id.display_name,)
                )

            if rec.vehicle_id.stock_location_id == rec.outlet_id.stock_location_id:
                raise UserError(
                    _(
                        "Vehicle Stock Location and Outlet Stock Location cannot be the same on visit '%s'."
                    )
                    % (rec.display_name,)
                )

    def action_start_visit(self):
        self._check_route_stock_locations_ready()
        result = super().action_start_visit()

        direct_sales_visits = self.filtered(lambda rec: not rec._route_uses_outlet_stock_location())
        if direct_sales_visits:
            direct_sales_visits.with_context(route_visit_force_write=True).write({
                "destination_location_id": False,
            })

        return result
