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

    is_direct_sales_stop = fields.Boolean(
        string="Direct Sales Stop",
        compute="_compute_visit_amounts",
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

    direct_stop_previous_due_amount = fields.Monetary(
        string="Previous Due",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    direct_stop_previous_due_since_date = fields.Date(
        string="Previous Due Since",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    direct_stop_sales_total = fields.Monetary(
        string="Current Sale",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    direct_stop_returns_total = fields.Monetary(
        string="Current Return",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    direct_stop_current_net_amount = fields.Monetary(
        string="Net Current Stop",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    direct_stop_grand_due_amount = fields.Monetary(
        string="Grand Total Due",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    direct_stop_settlement_paid_amount = fields.Monetary(
        string="Saved / Confirmed Settlements",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    direct_stop_settlement_remaining_amount = fields.Monetary(
        string="Remaining After Saved Settlements",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    direct_stop_credit_amount = fields.Monetary(
        string="Credit Balance",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )

    direct_stop_credit_policy = fields.Selection(
        [
            ("customer_credit", "Customer Credit"),
            ("cash_refund", "Cash Refund"),
            ("next_stop", "Carry To Next Stop"),
        ],
        string="Return Credit Settlement",
    )
    direct_stop_credit_note = fields.Text(string="Credit Settlement Note")

    show_return_credit_handling = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_collection_decision = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_note_field = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_full_payment_help = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_partial_payment_help = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_defer_help = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_next_visit_help = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_credit_only_help = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_no_payment_due_help = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_close_settlement_button = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_save_draft_button = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )


    @api.depends(
        "is_direct_sales_stop",
        "collection_type",
        "direct_stop_settlement_remaining_amount",
        "direct_stop_credit_amount",
    )
    def _compute_ui_flags(self):
        for rec in self:
            has_credit = (rec.direct_stop_credit_amount or 0.0) > 0.0
            has_remaining = (rec.direct_stop_settlement_remaining_amount or 0.0) > 0.0
            no_payment_due = bool(rec.is_direct_sales_stop and (not has_remaining) and (not has_credit))
            credit_only = bool(rec.is_direct_sales_stop and (not has_remaining) and has_credit)
            rec.show_return_credit_handling = bool(rec.is_direct_sales_stop and has_credit)
            rec.show_collection_decision = bool((not rec.is_direct_sales_stop) or has_remaining)
            rec.show_note_field = bool((not rec.is_direct_sales_stop) or has_remaining)
            rec.show_full_payment_help = bool(rec.show_collection_decision and rec.collection_type == "full")
            rec.show_partial_payment_help = bool(rec.show_collection_decision and rec.collection_type == "partial")
            rec.show_defer_help = bool(rec.show_collection_decision and rec.collection_type == "defer_date")
            rec.show_next_visit_help = bool(rec.show_collection_decision and rec.collection_type == "next_visit")
            rec.show_credit_only_help = credit_only
            rec.show_no_payment_due_help = no_payment_due
            rec.show_close_settlement_button = no_payment_due
            rec.show_save_draft_button = not no_payment_due

    @api.depends("visit_id")
    def _compute_visit_amounts(self):
        for rec in self:
            visit = rec.visit_id
            is_direct = bool(visit and hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop())
            rec.is_direct_sales_stop = is_direct
            rec.visit_net_due_amount = visit.net_due_amount if visit and "net_due_amount" in visit._fields else 0.0
            rec.visit_collected_amount = visit.collected_amount if visit and "collected_amount" in visit._fields else 0.0
            rec.visit_remaining_due = visit.remaining_due_amount if visit and "remaining_due_amount" in visit._fields else 0.0

            rec.direct_stop_previous_due_amount = visit.direct_stop_previous_due_amount if is_direct and "direct_stop_previous_due_amount" in visit._fields else 0.0
            rec.direct_stop_previous_due_since_date = visit.direct_stop_previous_due_since_date if is_direct and "direct_stop_previous_due_since_date" in visit._fields else False
            rec.direct_stop_sales_total = visit.direct_stop_sales_total if is_direct and "direct_stop_sales_total" in visit._fields else 0.0
            rec.direct_stop_returns_total = visit.direct_stop_returns_total if is_direct and "direct_stop_returns_total" in visit._fields else 0.0
            rec.direct_stop_current_net_amount = visit.direct_stop_current_net_amount if is_direct and "direct_stop_current_net_amount" in visit._fields else 0.0
            rec.direct_stop_grand_due_amount = visit.direct_stop_grand_due_amount if is_direct and "direct_stop_grand_due_amount" in visit._fields else 0.0
            rec.direct_stop_settlement_paid_amount = visit.direct_stop_settlement_paid_amount if is_direct and "direct_stop_settlement_paid_amount" in visit._fields else 0.0
            rec.direct_stop_settlement_remaining_amount = visit.direct_stop_settlement_remaining_amount if is_direct and "direct_stop_settlement_remaining_amount" in visit._fields else 0.0
            rec.direct_stop_credit_amount = visit.direct_stop_credit_amount if is_direct and "direct_stop_credit_amount" in visit._fields else 0.0

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        visit_id = self.env.context.get("default_visit_id") or self.env.context.get("active_id")
        if visit_id:
            visit = self.env["route.visit"].browse(visit_id)
            vals.setdefault("visit_id", visit.id)
            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("direct_stop_credit_policy", getattr(visit, "direct_stop_credit_policy", False))
            vals.setdefault("direct_stop_credit_note", getattr(visit, "direct_stop_credit_note", False))
            if "payment_date" in fields_list:
                vals.setdefault("payment_date", fields.Datetime.now())
            if "collection_type" in fields_list:
                vals.setdefault("collection_type", "full")
            if "amount" in fields_list:
                if hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop():
                    vals["amount"] = max(getattr(visit, "direct_stop_settlement_remaining_amount", 0.0) or 0.0, 0.0)
                else:
                    vals["amount"] = max(visit.remaining_due_amount or 0.0, 0.0)
        return vals

    def _get_effective_due_amount(self):
        self.ensure_one()
        if self.is_direct_sales_stop:
            return self.direct_stop_settlement_remaining_amount or 0.0
        return self.visit_remaining_due or 0.0

    def _sync_promise_fields(self):
        for rec in self:
            due = rec._get_effective_due_amount()
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
            due = rec._get_effective_due_amount()

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
        due = self._get_effective_due_amount()
        credit_only = self.is_direct_sales_stop and due <= 0.0 and (self.direct_stop_credit_amount or 0.0) > 0.0

        if self.amount < 0:
            raise ValidationError(_("Payment amount cannot be negative."))

        if credit_only:
            if not self.direct_stop_credit_policy:
                raise ValidationError(_("Please choose how to settle the return credit."))
            return

        if self.collection_type == "full":
            if due <= 0:
                raise ValidationError(_("There is no remaining due amount on this visit."))
            if self.amount <= 0:
                raise ValidationError(_("Full payment amount must be greater than zero."))
            if self.amount > due:
                raise ValidationError(_("Full payment cannot be more than the remaining due amount."))
            if self.is_direct_sales_stop and abs((self.amount or 0.0) - due) > 0.00001:
                raise ValidationError(_("Use Partial Payment when settling less than the full direct-sales balance."))

        elif self.collection_type == "partial":
            if due <= 0:
                raise ValidationError(_("There is no remaining due amount on this visit."))
            if self.amount <= 0:
                raise ValidationError(_("Partial payment amount must be greater than zero."))
            if self.amount >= due:
                raise ValidationError(
                    _("Partial payment must be less than the remaining due amount. Use Full Payment instead.")
                )
            if not self.promise_date:
                raise ValidationError(_("Please set the promise to pay date for the carried-forward balance."))
            if (self.promise_amount or 0.0) <= 0:
                raise ValidationError(_("Please set the promise to pay amount."))
            if not self.note:
                raise ValidationError(_("Please add a note for the carried-forward balance."))

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

    def _prepare_payment_vals(self, target_visit, amount, collection_type, promise_amount=0.0, promise_date=False, due_date=False):
        return {
            "visit_id": target_visit.id,
            "settlement_visit_id": self.visit_id.id if self.is_direct_sales_stop else False,
            "payment_date": self.payment_date,
            "payment_mode": self.payment_mode,
            "collection_type": collection_type,
            "amount": amount,
            "due_date": due_date,
            "promise_date": promise_date or due_date,
            "promise_amount": promise_amount,
            "reference": self.reference,
            "bank_name": self.bank_name,
            "pos_terminal": self.pos_terminal,
            "note": self.note,
            "state": "draft",
        }

    def _create_direct_sales_cash_allocations(self):
        self.ensure_one()
        Payment = self.env["route.visit.payment"]
        visit = self.visit_id
        remaining_cash = self.amount or 0.0
        created = Payment
        targets = list(visit._get_direct_stop_previous_due_visits()) + [visit]
        last_payment = Payment
        settlement_remaining_after_payment = max((visit.direct_stop_grand_due_amount or 0.0) - (self.amount or 0.0), 0.0)

        for target in targets:
            due = target.remaining_due_amount or 0.0
            if remaining_cash <= 0.0 or due <= 0.0:
                continue
            allocation = min(remaining_cash, due)
            payment = Payment.create(self._prepare_payment_vals(target, allocation, "full"))
            created |= payment
            last_payment = payment
            remaining_cash -= allocation

        if self.collection_type == "partial" and settlement_remaining_after_payment > 0.0 and last_payment:
            last_payment.write({
                "collection_type": "partial",
                "promise_date": self.promise_date,
                "promise_amount": self.promise_amount,
                "note": self.note,
            })

        return created

    def action_close_settlement(self):
        self.ensure_one()
        if self.is_direct_sales_stop:
            self.visit_id.write({
                "direct_stop_credit_policy": self.direct_stop_credit_policy or False,
                "direct_stop_credit_note": self.direct_stop_credit_note or False,
            })
            if hasattr(self.visit_id, "_action_mark_post_collection_stage"):
                self.visit_id._action_mark_post_collection_stage()
            if hasattr(self.visit_id, "_get_pda_form_action"):
                return self.visit_id._get_pda_form_action()
        return {"type": "ir.actions.act_window_close"}

    def action_save_payment(self):
        self.ensure_one()
        self._validate_before_create()

        if self.is_direct_sales_stop:
            self.visit_id.write({
                "direct_stop_credit_policy": self.direct_stop_credit_policy or False,
                "direct_stop_credit_note": self.direct_stop_credit_note or False,
            })

            due = self.direct_stop_settlement_remaining_amount or 0.0
            credit_only = due <= 0.0 and (self.direct_stop_credit_amount or 0.0) > 0.0
            no_payment_due = due <= 0.0 and (self.direct_stop_credit_amount or 0.0) <= 0.0
            if no_payment_due:
                if hasattr(self.visit_id, "_action_mark_post_collection_stage"):
                    self.visit_id._action_mark_post_collection_stage()
                return self.visit_id._get_pda_form_action() if hasattr(self.visit_id, "_get_pda_form_action") else {"type": "ir.actions.act_window_close"}
            if credit_only:
                return self.visit_id._get_pda_form_action() if hasattr(self.visit_id, "_get_pda_form_action") else {"type": "ir.actions.act_window_close"}

            if self.collection_type in ("defer_date", "next_visit"):
                self.env["route.visit.payment"].create(
                    self._prepare_payment_vals(
                        self.visit_id,
                        0.0,
                        self.collection_type,
                        promise_amount=self.promise_amount,
                        promise_date=self.promise_date,
                        due_date=self.due_date,
                    )
                )
            else:
                self._create_direct_sales_cash_allocations()

            if hasattr(self.visit_id, "_get_pda_form_action"):
                return self.visit_id._get_pda_form_action()
            return {"type": "ir.actions.act_window_close"}

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
