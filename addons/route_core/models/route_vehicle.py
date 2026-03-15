from odoo import api, fields, models


class RouteVehicle(models.Model):
    _name = "route.vehicle"
    _description = "Route Vehicle"
    _order = "name"

    name = fields.Char(
        string="Vehicle Name",
        required=True,
    )
    code = fields.Char(
        string="Code",
        copy=False,
    )
    plate_no = fields.Char(
        string="Plate Number",
    )
    driver_name = fields.Char(
        string="Driver Name",
    )
    active = fields.Boolean(
        default=True,
    )
    notes = fields.Text(
        string="Notes",
    )

    _sql_constraints = [
        ("route_vehicle_name_unique", "unique(name)", "Vehicle name must be unique."),
        ("route_vehicle_code_unique", "unique(code)", "Vehicle code must be unique."),
        ("route_vehicle_plate_no_unique", "unique(plate_no)", "Plate number must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code("route.vehicle") or "/"
        return super().create(vals_list)
