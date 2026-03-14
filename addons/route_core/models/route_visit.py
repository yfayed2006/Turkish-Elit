from odoo import api, fields, models
from odoo.exceptions import UserError


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

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        readonly=True,
        copy=False,
    )
    sale_order_count = fields.Integer(
        string="Sale Orders",
        compute="_compute_sale_order_count",
    )

    @api.depends("sale_order_id")
    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

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
            if rec.sale_order_id:
                rec.write({
                    "state": "done",
                    "end_datetime": fields.Datetime.now(),
                })
            else:
                return {
                    "type": "ir.actions.act_window",
                    "name": "End Visit Options",
                    "res_model": "route.visit.end.wizard",
                    "view_mode": "form",
                    "target": "new",
                    "context": {
                        "default_route_visit_id": rec.id,
                    },
                }

    def action_force_end_visit(self):
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
                "sale_order_id": False,
            })

    def action_create_sale_order(self):
        self.ensure_one()

        if self.sale_order_id:
            return {
                "type": "ir.actions.act_window",
                "name": "Sale Order",
                "res_model": "sale.order",
                "res_id": self.sale_order_id.id,
                "view_mode": "form",
                "target": "current",
            }

        sale_order = self.env["sale.order"].create({
            "partner_id": self.partner_id.id,
        })

        self.sale_order_id = sale_order.id

        return {
            "type": "ir.actions.act_window",
            "name": "Sale Order",
            "res_model": "sale.order",
            "res_id": sale_order.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError("No Sale Order is linked to this visit yet.")
        return {
            "type": "ir.actions.act_window",
            "name": "Sale Order",
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
            "target": "current",
        }
