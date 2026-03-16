from odoo import fields, models
from odoo.exceptions import ValidationError


class RouteVisitPayment(models.Model):
    _name = "route.visit.payment"
    _description = "Route Visit Payment"
    _order = "payment_date desc, id desc"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        ondelete="cascade",
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="visit_id.company_id",
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="visit_id.currency_id",
        store=True,
        readonly=True,
    )

    payment_date = fields.Datetime(
        string="Payment Date",
        default=fields.Datetime.now,
        required=True,
    )

    payment_mode = fields.Selection(
        [
            ("cash", "Cash"),
            ("bank", "Bank Transfer"),
            ("pos", "POS"),
        ],
        string="Payment Mode",
        required=True,
        default="cash",
    )

    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )

    reference = fields.Char(string="Reference")
    bank_name = fields.Char(string="Bank Name")
    pos_terminal = fields.Char(string="POS Terminal")
    note = fields.Text(string="Note")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    def action_confirm(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError("Payment amount cannot be negative.")
            rec.state = "confirmed"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"
