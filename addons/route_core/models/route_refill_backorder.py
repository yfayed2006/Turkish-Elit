from odoo import fields, models


class RouteRefillBackorder(models.Model):
    _name = "route.refill.backorder"
    _description = "Route Refill Backorder"
    _order = "create_date desc, id desc"

    name = fields.Char(string="Reference", required=True, copy=False, default="New")
    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
    )
    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        domain="[('usage', '=', 'internal')]",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="pending",
        required=True,
    )
    note = fields.Text(string="Notes")
    line_ids = fields.One2many(
        "route.refill.backorder.line",
        "backorder_id",
        string="Lines",
    )

    def action_mark_done(self):
        for rec in self:
            rec.state = "done"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"

    def action_reset_to_pending(self):
        for rec in self:
            rec.state = "pending"

    def unlink(self):
        for rec in self:
            if rec.state == "done":
                raise models.ValidationError("You cannot delete a done backorder.")
        return super().unlink()

    @models.api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = seq.next_by_code("route.refill.backorder") or "New"
        return super().create(vals_list)
