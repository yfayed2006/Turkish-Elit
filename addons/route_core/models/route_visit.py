from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Visit Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )
    date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        required=True,
        default=lambda self: self.env.user,
    )
    notes = fields.Text(string="Notes")
    no_sale_reason = fields.Text(
        string="Reason for Ending Without Sale",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    start_datetime = fields.Datetime(
        string="Start DateTime",
        readonly=True,
    )
    end_datetime = fields.Datetime(
        string="End DateTime",
        readonly=True,
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        readonly=True,
        copy=False,
    )

    sale_order_count = fields.Integer(
        string="Sale Order Count",
        compute="_compute_sale_order_count",
    )

    @api.depends("sale_order_id")
    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("route.visit") or "New"
        return super().create(vals)

    def action_start_visit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft visits can be started."))
            rec.write({
                "state": "in_progress",
                "start_datetime": fields.Datetime.now(),
                "end_datetime": False,
                "no_sale_reason": False,
            })

    def action_create_sale_order(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(_("You can only create a sale order when the visit is in progress."))

        if self.sale_order_id:
            action = self.env.ref("sale.action_orders").read()[0]
            action["res_id"] = self.sale_order_id.id
            action["views"] = [(self.env.ref("sale.view_order_form").id, "form")]
            return action

        sale_order = self.env["sale.order"].create({
            "partner_id": self.partner_id.id,
            "user_id": self.user_id.id,
            "origin": self.name,
        })

        self.sale_order_id = sale_order.id

        action = self.env.ref("sale.action_orders").read()[0]
        action["res_id"] = sale_order.id
        action["views"] = [(self.env.ref("sale.view_order_form").id, "form")]
        return action

    def action_view_sale_order(self):
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError(_("There is no sale order linked to this visit."))

        action = self.env.ref("sale.action_orders").read()[0]
        action["res_id"] = self.sale_order_id.id
        action["views"] = [(self.env.ref("sale.view_order_form").id, "form")]
        return action

    def action_end_visit(self):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only visits in progress can be ended."))
            if not rec.sale_order_id:
                raise UserError(_("You must create a sale order before ending the visit."))
            rec.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            })

    def action_force_end_visit(self):
        for rec in self:
            if rec.state != "in_progress":
                raise UserError(_("Only visits in progress can be force ended."))
            rec.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            })

    def action_cancel(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("You cannot cancel a completed visit."))
            rec.write({"state": "cancel"})

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                "state": "draft",
                "start_datetime": False,
                "end_datetime": False,
                "sale_order_id": False,
                "no_sale_reason": False,
            })
