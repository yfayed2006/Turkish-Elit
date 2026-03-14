from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


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
    no_sale_reason = fields.Text(string="Reason for Ending Without Sale", readonly=True)

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
        tracking=True,
    )

    start_datetime = fields.Datetime(string="Start DateTime", readonly=True)
    end_datetime = fields.Datetime(string="End DateTime", readonly=True)

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.visit") or "New"
        return super().create(vals_list)

    def action_start_visit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only a draft visit can be started."))
            rec.write({
                "state": "in_progress",
                "start_datetime": fields.Datetime.now(),
            })
        return True

    def action_create_sale_order(self):
        self.ensure_one()

        if self.state not in ("in_progress", "done"):
            raise UserError(_("You can only create a sale order for a visit that is in progress or done."))

        if not self.sale_order_id:
            sale_order = self.env["sale.order"].create({
                "partner_id": self.partner_id.id,
                "user_id": self.user_id.id,
                "origin": self.name,
                "note": self.notes or "",
            })
            self.sale_order_id = sale_order.id

        return {
            "type": "ir.actions.act_window",
            "name": _("Sale Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
            "target": "current",
        }

    def action_view_sale_order(self):
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError(_("There is no sale order linked to this visit yet."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Sale Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": self.sale_order_id.id,
            "target": "current",
        }

    def action_end_visit(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(_("Only a visit in progress can be ended."))

        if self.sale_order_id:
            self.write({
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            })
            return True

        return {
            "type": "ir.actions.act_window",
            "name": _("End Visit"),
            "res_model": "route.visit.end.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
            },
        }

    def action_end_without_sale(self, reason):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(_("Only a visit in progress can be ended without sale."))

        if not reason or not reason.strip():
            raise ValidationError(_("Reason is required to end the visit without sale."))

        self.write({
            "state": "done",
            "end_datetime": fields.Datetime.now(),
            "no_sale_reason": reason.strip(),
        })
        return True

    def action_cancel(self):
        for rec in self:
            rec.write({"state": "cancel"})
        return True

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                "state": "draft",
                "start_datetime": False,
                "end_datetime": False,
                "no_sale_reason": False,
            })
        return True
