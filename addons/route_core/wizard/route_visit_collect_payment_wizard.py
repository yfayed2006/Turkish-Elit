from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RouteVisitCollectPaymentWizard(models.TransientModel):
    _name = "route.visit.collect.payment.wizard"
    _description = "Route Visit Collect Payment Wizard"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=False,
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

    promise_date = fields.Date(string="Promise To Pay Date")
    promise_amount = fields.Monetary(
        string="Promise To Pay Amount",
        currency_field="currency_id",
        default=0.0,
    )

    due_date = fields.Date(string="Deferred Due Date")
    reference = fields.Char(string="Reference")
    bank_name = fields.Char(string="Bank Name")
    pos_terminal = fields.Char(string="POS Terminal")
    note = fields.Text(string="Note")

    visit_net_due_amount = fields.Monetary(
        string="Net Due",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    visit_collected_amount = fields.Monetary(
        string="Collected",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    visit_remaining_due = fields.Monetary(
        string="Remaining Due",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )

    @api.depends("visit_id")
    def _compute_visit_amounts(self):
        for rec in self:
            visit = rec.visit_id
            rec.visit_net_due_amount = (
                visit.net_due_amount
                if visit and "net_due_amount" in visit._fields
                else 0.0
            )
            rec.visit_collected_amount = (
                visit.collected_amount
                if visit and "collected_amount" in visit._fields
                else 0.0
            )
            rec.visit_remaining_due = (
                visit.remaining_due_amount
                if visit and "remaining_due_amount" in visit._fields
                else 0.0
            )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        visit_id = self.env.context.get("default_visit_id") or self.env.context.get("active_id")
        if visit_id:
            visit = self.env["route.visit"].browse(visit_id)
            vals.setdefault("visit_id", visit.id)
            vals.setdefault("company_id", self.env.company.id)
            if "payment_date" in fields_list:
                vals.setdefault("payment_date", fields.Datetime.now())
            if "collection_type" in fields_list:
                vals.setdefault("collection_type", "full")
            if "amount" in fields_list:
                remaining_due = (
                    visit.remaining_due_amount
                    if "remaining_due_amount" in visit._fields
                    else 0.0
                )
                vals["amount"] = max(remaining_due or 0.0, 0.0)
        return vals

    def _sync_promise_fields(self):
        for rec in self:
            due = rec.visit_remaining_due or 0.0
            if rec.collection_type == "full":
                rec.promise_date = False
                rec.promise_amount = 0.0
            elif rec.collection_type == "partial":
                rec.promise_amount = max(due - (rec.amount or 0.0), 0.0)
            elif rec.collection_type == "defer_date":
                rec.promise_date = rec.due_date or rec.promise_date
                rec.promise_amount = due
            elif rec.collection_type == "next_visit":
                rec.promise_amount = due

    @api.onchange("collection_type", "visit_id", "amount", "due_date", "promise_date")
    def _onchange_collection_type(self):
        for rec in self:
            due = rec.visit_remaining_due or 0.0

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
            rec._sync_promise_fields()

    @api.onchange("payment_mode")
    def _onchange_payment_mode(self):
        for rec in self:
            if rec.payment_mode == "cash":
                rec.bank_name = False
                rec.pos_terminal = False
            elif rec.payment_mode == "bank":
                rec.pos_terminal = False
            elif rec.payment_mode == "pos":
                rec.bank_name = False

    def _validate_before_create(self):
        self.ensure_one()
        due = self.visit_remaining_due or 0.0

        if self.amount < 0:
            raise ValidationError(_("Payment amount cannot be negative."))

        if self.collection_type == "full":
            if due <= 0:
                raise ValidationError(_("There is no remaining due amount on this visit."))
            if self.amount <= 0:
                raise ValidationError(_("Full payment amount must be greater than zero."))
            if self.amount > due:
                raise ValidationError(_("Full payment cannot be more than the remaining due amount."))

        elif self.collection_type == "partial":
            if due <= 0:
                raise ValidationError(_("There is no remaining due amount on this visit."))
            if self.amount <= 0:
                raise ValidationError(_("Partial payment amount must be greater than zero."))
            if self.amount >= due:
                raise ValidationError(
                    _("Partial payment must be less than the remaining due amount. Use Full Payment instead.")
                )
            if not self.note:
                raise ValidationError(_("Please add a note for the remaining carried-forward balance."))

        elif self.collection_type == "defer_date":
            if self.amount != 0:
                raise ValidationError(_("Deferred payment to a specific date must have amount = 0."))
            if not self.due_date:
                raise ValidationError(_("Please set the deferred due date."))
            if not (self.promise_date or self.due_date):
                raise ValidationError(_("Please set the promise to pay date."))
            if (self.promise_amount or 0.0) <= 0:
                raise ValidationError(_("Please set the promise to pay amount."))
            if not self.note:
                raise ValidationError(_("Please add a note explaining the deferment."))

        elif self.collection_type == "next_visit":
            if self.amount != 0:
                raise ValidationError(_("Carry to next visit must have amount = 0."))
            if self.due_date:
                raise ValidationError(_("Do not set a due date when carrying payment to the next visit."))
            if not self.promise_date:
                raise ValidationError(_("Please set the promise to pay date for the next visit."))
            if (self.promise_amount or 0.0) <= 0:
                raise ValidationError(_("Please set the promise to pay amount for the next visit."))
            if not self.note:
                raise ValidationError(_("Please add a note explaining why payment is carried to next visit."))

    def action_save_payment(self):
        self.ensure_one()
        self._validate_before_create()

        self.env["route.visit.payment"].create(
            {
                "visit_id": self.visit_id.id,
                "payment_date": self.payment_date,
                "payment_mode": self.payment_mode,
                "collection_type": self.collection_type,
                "amount": self.amount,
                "due_date": self.due_date,
                "promise_date": self.promise_date or self.due_date,
                "promise_amount": self.promise_amount,
                "reference": self.reference,
                "bank_name": self.bank_name,
                "pos_terminal": self.pos_terminal,
                "note": self.note,
                "state": "draft",
            }
        )

        if hasattr(self.visit_id, "_get_pda_form_action"):
            return self.visit_id._get_pda_form_action()

        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.visit_id.id,
            "view_mode": "form",
            "target": "current",
        }
