from odoo import api, fields, models
from odoo.exceptions import ValidationError


class RouteOutlet(models.Model):
    _name = "route.outlet"
    _description = "Route Outlet"
    _order = "name"

    name = fields.Char(string="Outlet Name", required=True)
    code = fields.Char(string="Code", copy=False)
    active = fields.Boolean(default=True)

    area_id = fields.Many2one(
        "route.area",
        string="Area",
        required=True,
        ondelete="restrict",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Related Contact",
        ondelete="set null",
        help="Optional link to an existing contact/customer.",
    )

    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street 2")
    city = fields.Char(string="City")
    state_id = fields.Many2one("res.country.state", string="State")
    country_id = fields.Many2one("res.country", string="Country")
    zip = fields.Char(string="ZIP")
    note = fields.Text(string="Notes")

    visit_ids = fields.One2many(
        "route.visit",
        "outlet_id",
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

    display_address = fields.Text(
        string="Address",
        compute="_compute_display_address",
    )

    _sql_constraints = [
        ("route_outlet_name_unique", "unique(name)", "Outlet name must be unique."),
        ("route_outlet_code_unique", "unique(code)", "Outlet code must be unique."),
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

    @api.depends("street", "street2", "city", "state_id", "country_id", "zip")
    def _compute_display_address(self):
        for record in self:
            parts = [
                record.street or "",
                record.street2 or "",
                record.city or "",
                record.state_id.name or "",
                record.zip or "",
                record.country_id.name or "",
            ]
            record.display_address = ", ".join([part for part in parts if part])

    @api.constrains("partner_id")
    def _check_partner_company_type(self):
        for record in self:
            if record.partner_id and record.partner_id.company_type == "person":
                raise ValidationError("Related Contact should preferably be a company/customer record.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code("route.outlet") or "/"
        return super().create(vals_list)

    def action_view_visits(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["domain"] = [("outlet_id", "=", self.id)]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
            default_area_id=self.area_id.id,
            default_partner_id=self.partner_id.id if self.partner_id else False,
        )
        return action
