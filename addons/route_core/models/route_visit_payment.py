from odoo import api, fields, models
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

    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        related="visit_id.outlet_id",
        store=True,
        readonly=True,
    )

    area_id = fields.Many2one(
        "route.area",
        string="Area",
        related="visit_id.area_id",
        store=True,
        readonly=True,
    )

    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        related="visit_id.user_id",
        store=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
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

    collection_type = fields.Selection(
        [
            ("full", "Full Payment"),
            ("partial", "Partial Payment + Carry Forward"),
            ("defer_date", "Defer To Specific Date"),
            ("next_visit", "Carry To Next Visit"),
        ],
        string="Collection Scenario",
        required=True,
        default="full",
    )

    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )

    remaining_due_amount = fields.Monetary(
        string="Unpaid Amount",
        currency_field="currency_id",
        compute="_compute_remaining_due_amount",
        store=False,
    )

    due_date = fields.Date(string="Deferred Due Date")

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

    visit_remaining_due = fields.Monetary(
        string="Visit Remaining Due",
        currency_field="currency_id",
        compute="_compute_visit_remaining_due",
        store=False,
    )

    @api.depends("visit_id.remaining_due_amount")
    def _compute_visit_remaining_due(self):
        for rec in self:
            rec.visit_remaining_due = rec.visit_id.remaining_due_amount or 0.0

    @api.depends("visit_id.remaining_due_amount")
    def _compute_remaining_due_amount(self):
        for rec in self:
            rec.remaining_due_amount = rec.visit_id.remaining_due_amount or 0.0

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        visit_id = self.env.context.get("default_visit_id")
        if visit_id:
            visit = self.env["route.visit"].browse(visit_id)
            vals.setdefault("visit_id", visit_id)
            if "amount" in fields_list:
                vals["amount"] = max(visit.remaining_due_amount or 0.0, 0.0)
            if "collection_type" in fields_list:
                vals.setdefault("collection_type", "full")
        return vals

    @api.onchange("visit_id")
    def _onchange_visit_id_set_amount(self):
        for rec in self:
            due = max(rec.visit_id.remaining_due_amount, 0.0) if rec.visit_id else 0.0
            if rec.collection_type == "full":
                rec.amount = due
            elif rec.collection_type == "partial":
                if due > 0 and (rec.amount <= 0 or rec.amount >= due):
                    rec.amount = due / 2.0

    @api.onchange("collection_type")
    def _onchange_collection_type(self):
        for rec in self:
            due = max(rec.visit_id.remaining_due_amount, 0.0) if rec.visit_id else 0.0

            if rec.collection_type == "full":
                rec.amount = due
                rec.due_date = False

            elif rec.collection_type == "partial":
                rec.due_date = False
                if due <= 0:
                    rec.amount = 0.0
                elif rec.amount <= 0 or rec.amount >= due:
                    rec.amount = due / 2.0

            elif rec.collection_type == "defer_date":
                rec.amount = 0.0

            elif rec.collection_type == "next_visit":
                rec.amount = 0.0
                rec.due_date = False

    @api.constrains("amount", "collection_type", "due_date", "visit_id")
    def _check_payment_rules(self):
        for rec in self:
            due = rec.visit_id.remaining_due_amount or 0.0

            if rec.amount < 0:
                raise ValidationError("Payment amount cannot be negative.")

            if rec.collection_type == "full":
                if due <= 0:
                    raise ValidationError("There is no remaining due amount on this visit.")
                if rec.amount <= 0:
                    raise ValidationError("Full payment amount must be greater than zero.")
                if rec.amount > due:
                    raise ValidationError("Full payment cannot be more than the remaining due amount.")

            elif rec.collection_type == "partial":
                if due <= 0:
                    raise ValidationError("There is no remaining due amount on this visit.")
                if rec.amount <= 0:
                    raise ValidationError("Partial payment amount must be greater than zero.")
                if rec.amount >= due:
                    raise ValidationError(
                        "Partial payment must be less than the remaining due amount. Use Full Payment instead."
                    )

            elif rec.collection_type == "defer_date":
                if rec.amount != 0:
                    raise ValidationError("Deferred payment to a specific date must have amount = 0.")
                if not rec.due_date:
                    raise ValidationError("Please set the deferred due date.")

            elif rec.collection_type == "next_visit":
                if rec.amount != 0:
                    raise ValidationError("Carry to next visit must have amount = 0.")
                if rec.due_date:
                    raise ValidationError("Do not set a due date when carrying payment to the next visit.")

    def action_confirm(self):
        for rec in self:
            rec._check_payment_rules()
            rec.state = "confirmed"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"

    def unlink(self):
        for rec in self:
            if rec.state == "confirmed":
                raise ValidationError("You cannot delete a confirmed payment.")
        return super().unlink()

