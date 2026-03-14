from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Visit Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
        tracking=True,
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
        tracking=True,
    )

    date = fields.Date(
        string="Visit Date",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    start_datetime = fields.Datetime(
        string="Start Time",
        tracking=True,
    )

    end_datetime = fields.Datetime(
        string="End Time",
        tracking=True,
    )

    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        tracking=True,
    )

    notes = fields.Text(string="Notes")

    sale_order_ids = fields.One2many(
        "sale.order",
        "route_visit_id",
        string="Sale Orders",
    )

    sale_order_count = fields.Integer(
        string="Sale Orders Count",
        compute="_compute_sale_order_count",
    )

    has_sale_order = fields.Boolean(
        string="Has Sale Order",
        compute="_compute_has_sale_order",
        store=True,
    )

    can_create_sale_order = fields.Boolean(
        string="Can Create Sale Order",
        compute="_compute_can_create_sale_order",
    )

    @api.depends("sale_order_ids")
    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = len(rec.sale_order_ids)

    @api.depends("sale_order_ids")
    def _compute_has_sale_order(self):
        for rec in self:
            rec.has_sale_order = bool(rec.sale_order_ids)

    def _compute_can_create_sale_order(self):
        for rec in self:
            rec.can_create_sale_order = rec.state == "in_progress"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("route.visit.seq") or _("New")
        return super().create(vals_list)

    def action_start_visit(self):
        for rec in self:
            if rec.state != "draft":
                continue
            rec.write({
                "state": "in_progress",
                "start_datetime": fields.Datetime.now(),
            })

    def action_create_sale_order(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(_("You can only create a sales order while the visit is in progress."))

        if not self.partner_id:
            raise UserError(_("Please select a customer first."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Sale Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_route_visit_id": self.id,
            },
        }

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sale Orders"),
            "res_model": "sale.order",
            "view_mode": "tree,form",
            "domain": [("route_visit_id", "=", self.id)],
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_route_visit_id": self.id,
            },
        }

    def action_end_visit(self):
        for rec in self:
            if rec.state != "in_progress":
                continue

            if not rec.sale_order_ids:
                raise UserError(_(
                    "No Sale Order has been created for this visit yet.\n\n"
                    "If you want to create a Sale Order, use 'Create Sale Order'.\n"
                    "If you really want to close the visit without a sale, use 'Force End Visit'."
                ))

            rec.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            })

    def action_force_end_visit(self):
        for rec in self:
            if rec.state != "in_progress":
                continue

            rec.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            })

    def action_cancel_visit(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("You cannot cancel a completed visit."))
            rec.state = "cancel"

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                "state": "draft",
                "start_datetime": False,
                "end_datetime": False,
            })

    @api.constrains("start_datetime", "end_datetime")
    def _check_start_end_datetime(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime < rec.start_datetime:
                raise ValidationError(_("End Time cannot be earlier than Start Time."))
