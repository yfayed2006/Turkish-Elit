from odoo import api, fields, models


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _order = "id desc"

    name = fields.Char(
        string="Visit Reference",
        required=True,
        readonly=True,
        copy=False,
        default="New",
    )
    date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
    )
    notes = fields.Text(string="Notes")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self.env.user,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
    )
    start_datetime = fields.Datetime(string="Start Time", readonly=True)
    end_datetime = fields.Datetime(string="End Time", readonly=True)
    sale_order_count = fields.Integer(
        string="Sale Orders",
        compute="_compute_sale_order_count",
    )

    @api.depends("partner_id")
    def _compute_sale_order_count(self):
        for rec in self:
            if rec.partner_id:
                rec.sale_order_count = self.env["sale.order"].search_count([
                    ("partner_id", "=", rec.partner_id.id)
                ])
            else:
                rec.sale_order_count = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.visit.seq") or "New"
        return super().create(vals_list)

    def action_start_visit(self):
        for rec in self:
            rec.write({
                "state": "in_progress",
                "start_datetime": fields.Datetime.now(),
            })

    def action_end_visit(self):
        for rec in self:
            rec.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            })

    def action_cancel_visit(self):
        for rec in self:
            rec.state = "cancel"

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                "state": "draft",
                "start_datetime": False,
                "end_datetime": False,
            })

    def action_create_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Sale Order",
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.partner_id.id,
            },
        }

    def action_view_customer_sale_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Customer Sale Orders",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.partner_id.id)],
        }
