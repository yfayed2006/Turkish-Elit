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

    def _compute_stock_locations(self):
        for rec in self:
            rec.vehicle_stock_location_id = rec.vehicle_id.stock_location_id
            rec.outlet_stock_location_id = rec.outlet_id.stock_location_id

    def _get_vehicle_stock_location(self):
        self.ensure_one()
        return self.vehicle_id.stock_location_id

    def _get_outlet_stock_location(self):
        self.ensure_one()
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
                    _(
                        "Vehicle '%s' does not have a Vehicle Stock Location."
                    )
                    % (rec.vehicle_id.display_name,)
                )

            if getattr(rec, "_is_direct_sales_stop", False) and rec._is_direct_sales_stop():
                continue

            if not rec.outlet_id.stock_location_id:
                raise UserError(
                    _(
                        "Outlet '%s' does not have an Outlet Stock Location."
                    )
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
        for rec in self:
            if getattr(rec, "_is_direct_sales_stop", False) and rec._is_direct_sales_stop():
                rec.with_context(route_visit_force_write=True).write({
                    "source_location_id": rec.vehicle_id.stock_location_id.id if rec.vehicle_id and rec.vehicle_id.stock_location_id else False,
                    "destination_location_id": False,
                })
        return result
