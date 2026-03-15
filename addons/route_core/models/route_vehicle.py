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

    visit_ids = fields.One2many(
        "route.visit",
        "vehicle_id",
        string="Visits",
    )
    visit_count = fields.Integer(
        string="Visits Count",
        compute="_compute_visit_stats",
    )
    last_visit_id = fields.Many2one(
        "route.visit",
        string="Last Visit",
        compute="_compute_visit_stats",
    )
    last_visit_date = fields.Date(
        string="Last Visit Date",
        compute="_compute_visit_stats",
    )
    last_sale_order_id = fields.Many2one(
        "sale.order",
        string="Last Sale Order",
        compute="_compute_visit_stats",
    )

    _sql_constraints = [
        ("route_vehicle_name_unique", "unique(name)", "Vehicle name must be unique."),
        ("route_vehicle_code_unique", "unique(code)", "Vehicle code must be unique."),
        ("route_vehicle_plate_no_unique", "unique(plate_no)", "Plate number must be unique."),
    ]

    @api.depends(
        "visit_ids",
        "visit_ids.date",
        "visit_ids.sale_order_id",
        "visit_ids.write_date",
    )
    def _compute_visit_stats(self):
        for record in self:
            visits = record.visit_ids.sorted(
                key=lambda v: ((v.date or fields.Date.today()), v.id),
                reverse=True,
            )
            record.visit_count = len(visits)
            record.last_visit_id = visits[0] if visits else False
            record.last_visit_date = visits[0].date if visits else False

            last_visit_with_sale = next((visit for visit in visits if visit.sale_order_id), False)
            record.last_sale_order_id = last_visit_with_sale.sale_order_id if last_visit_with_sale else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code("route.vehicle") or "/"
        return super().create(vals_list)
