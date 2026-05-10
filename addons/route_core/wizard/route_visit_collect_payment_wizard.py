from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RouteVisitCollectPaymentWizardLine(models.TransientModel):
    _name = "route.visit.collect.payment.wizard.line"
    _description = "Route Visit Collect Payment Wizard Line"
    _order = "id"

    wizard_id = fields.Many2one(
        "route.visit.collect.payment.wizard",
        string="Payment Wizard",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="wizard_id.company_id",
        store=False,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="wizard_id.currency_id",
        store=False,
        readonly=True,
    )
    payment_mode = fields.Selection(
        [
            ("cash", "Cash"),
            ("bank", "Bank Transfer"),
            ("pos", "POS"),
            ("cheque", "Cheque"),
        ],
        string="Payment Mode",
        required=True,
        default="cash",
    )
    payment_date = fields.Datetime(
        string="Payment Date",
        default=fields.Datetime.now,
        required=True,
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
    cheque_number = fields.Char(string="Cheque Number")
    cheque_date = fields.Date(string="Cheque Date")
    cheque_holder_name = fields.Char(string="Cheque Holder")
    cheque_note = fields.Text(string="Cheque Details")

    def _get_remaining_amount_excluding_self(self):
        self.ensure_one()
        wizard = self.wizard_id
        if not wizard:
            return 0.0

        due = wizard._get_effective_due_amount() if wizard.visit_id else 0.0
        other_total = 0.0
        for line in wizard.payment_line_ids:
            if line == self:
                continue
            other_total += line.amount or 0.0

        remaining = max((due or 0.0) - (other_total or 0.0), 0.0)
        currency = wizard.currency_id or self.currency_id
        return currency.round(remaining) if currency else remaining

    def _auto_fill_remaining_amount(self):
        for rec in self:
            wizard = rec.wizard_id
            if not wizard or wizard.settlement_mode != "split" or wizard.collection_type != "full":
                continue
            if (rec.amount or 0.0) <= 0.0:
                rec.amount = rec._get_remaining_amount_excluding_self()

    @api.onchange("payment_mode", "wizard_id")
    def _onchange_payment_mode(self):
        for rec in self:
            if rec.payment_mode == "cash":
                rec.bank_name = False
                rec.pos_terminal = False
                rec.reference = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "bank":
                rec.pos_terminal = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "pos":
                rec.bank_name = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "cheque":
                rec.pos_terminal = False
                if rec.cheque_number and not rec.reference:
                    rec.reference = rec.cheque_number

            rec._auto_fill_remaining_amount()

    @api.onchange("amount")
    def _onchange_amount(self):
        for rec in self:
            rec._auto_fill_remaining_amount()

    @api.onchange("cheque_number")
    def _onchange_cheque_number(self):
        for rec in self:
            if rec.payment_mode == "cheque" and rec.cheque_number and not rec.reference:
                rec.reference = rec.cheque_number

    def _validate_payment_line(self):
        self.ensure_one()
        if (self.amount or 0.0) <= 0.0:
            raise ValidationError(_("Each split payment line must have an amount greater than zero."))
        if self.payment_mode == "cheque":
            if not self.cheque_number:
                raise ValidationError(_("Please enter the cheque number on every cheque payment line."))
            if not self.bank_name:
                raise ValidationError(_("Please enter the cheque bank name on every cheque payment line."))
            if not self.cheque_date:
                raise ValidationError(_("Please enter the cheque date on every cheque payment line."))

    def _payment_data(self):
        self.ensure_one()
        return {
            "payment_mode": self.payment_mode,
            "payment_date": self.payment_date,
            "amount": self.amount,
            "reference": self.cheque_number if self.payment_mode == "cheque" and self.cheque_number else self.reference,
            "bank_name": self.bank_name,
            "pos_terminal": self.pos_terminal,
            "cheque_number": self.cheque_number,
            "cheque_date": self.cheque_date,
            "cheque_holder_name": self.cheque_holder_name,
            "cheque_note": self.cheque_note,
        }


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
            ("cheque", "Cheque"),
            ("deferred", "Deferred"),
        ],
        string="Payment Mode",
        required=True,
        default="cash",
    )

    settlement_mode = fields.Selection(
        [
            ("single", "Single Payment"),
            ("split", "Split Payment"),
        ],
        string="Payment Structure",
        required=True,
        default="single",
        help="Use Split Payment when the outlet pays the same settlement with more than one instrument, such as Cash + Cheque or multiple cheques.",
    )

    payment_line_ids = fields.One2many(
        "route.visit.collect.payment.wizard.line",
        "wizard_id",
        string="Payment Lines",
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
    cheque_number = fields.Char(string="Cheque Number")
    cheque_date = fields.Date(string="Cheque Date")
    cheque_holder_name = fields.Char(string="Cheque Holder")
    cheque_note = fields.Text(string="Cheque Details")
    note = fields.Text(string="Note")

    visit_net_due_amount = fields.Monetary(
        string="Current Visit Net",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    visit_gross_sale_amount = fields.Monetary(
        string="Gross Sold Value",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    visit_return_amount = fields.Monetary(
        string="Returns Value",
        currency_field="currency_id",
        compute="_compute_visit_amounts",
        store=False,
        readonly=True,
    )
    visit_commission_amount = fields.Monetary(
        string="Commission",
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
        string="Current Visit Remaining",
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
        string="Total Due Now",
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
        string="Remaining After Collection",
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
    show_single_payment_fields = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    show_split_payment_lines = fields.Boolean(
        compute="_compute_ui_flags",
        store=False,
        readonly=True,
    )
    payment_line_total = fields.Monetary(
        string="Payment Lines Total",
        currency_field="currency_id",
        compute="_compute_payment_line_totals",
        store=False,
        readonly=True,
    )
    payment_line_remaining = fields.Monetary(
        string="Remaining After Lines",
        currency_field="currency_id",
        compute="_compute_payment_line_totals",
        store=False,
        readonly=True,
    )


    @api.depends(
        "is_direct_sales_stop",
        "collection_type",
        "settlement_mode",
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

            split_is_available = bool(
                rec.show_collection_decision
                and rec.collection_type == "full"
                and rec.settlement_mode == "split"
            )
            rec.show_split_payment_lines = split_is_available
            rec.show_single_payment_fields = bool(rec.show_collection_decision and not split_is_available)

            rec.show_full_payment_help = bool(rec.show_collection_decision and rec.collection_type == "full" and not split_is_available)
            rec.show_partial_payment_help = bool(rec.show_collection_decision and rec.collection_type == "partial")
            rec.show_defer_help = bool(rec.show_collection_decision and rec.collection_type == "defer_date")
            rec.show_next_visit_help = bool(rec.show_collection_decision and rec.collection_type == "next_visit")
            rec.show_credit_only_help = credit_only
            rec.show_no_payment_due_help = no_payment_due
            rec.show_close_settlement_button = no_payment_due
            rec.show_save_draft_button = not no_payment_due

    @api.depends(
        "settlement_mode",
        "amount",
        "payment_line_ids",
        "payment_line_ids.amount",
        "direct_stop_settlement_remaining_amount",
        "visit_remaining_due",
    )
    def _compute_payment_line_totals(self):
        for rec in self:
            if rec.settlement_mode == "split":
                total = sum(rec.payment_line_ids.mapped("amount")) if rec.payment_line_ids else 0.0
            else:
                total = rec.amount or 0.0
            due = rec._get_effective_due_amount() if rec.visit_id else 0.0
            rec.payment_line_total = total
            rec.payment_line_remaining = max((due or 0.0) - (total or 0.0), 0.0)

    @api.depends("visit_id")
    def _compute_visit_amounts(self):
        for rec in self:
            visit = rec.visit_id
            is_direct = bool(visit and hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop())
            rec.is_direct_sales_stop = is_direct
            rec.visit_net_due_amount = visit.net_due_amount if visit and "net_due_amount" in visit._fields else 0.0
            rec.visit_gross_sale_amount = 0.0
            rec.visit_return_amount = 0.0
            rec.visit_commission_amount = getattr(visit, "consignment_commission_amount", 0.0) if visit else 0.0
            if visit and not is_direct and hasattr(visit, "_get_route_consignment_financial_amounts"):
                consignment_amounts = visit._get_route_consignment_financial_amounts()
                rec.visit_gross_sale_amount = consignment_amounts.get("gross_sale_amount", 0.0)
                rec.visit_return_amount = consignment_amounts.get("return_amount", 0.0)
                rec.visit_commission_amount = consignment_amounts.get("commission_amount", 0.0)
                rec.visit_net_due_amount = consignment_amounts.get("net_payable_amount", rec.visit_net_due_amount)
            elif visit and not is_direct:
                rec.visit_gross_sale_amount = sum((line.sold_amount or 0.0) for line in visit.line_ids) if visit.line_ids else 0.0
                rec.visit_return_amount = sum((line.return_amount or 0.0) for line in visit.line_ids) if visit.line_ids else 0.0
            rec.visit_collected_amount = visit.collected_amount if visit and "collected_amount" in visit._fields else 0.0
            rec.visit_remaining_due = visit.remaining_due_amount if visit and "remaining_due_amount" in visit._fields else 0.0

            rec.direct_stop_previous_due_amount = visit.direct_stop_previous_due_amount if is_direct and "direct_stop_previous_due_amount" in visit._fields else 0.0
            rec.direct_stop_previous_due_since_date = visit.direct_stop_previous_due_since_date if is_direct and "direct_stop_previous_due_since_date" in visit._fields else False
            rec.direct_stop_sales_total = visit.direct_stop_sales_total if is_direct and "direct_stop_sales_total" in visit._fields else 0.0
            rec.direct_stop_returns_total = visit.direct_stop_returns_total if is_direct and "direct_stop_returns_total" in visit._fields else 0.0
            rec.direct_stop_current_net_amount = visit.direct_stop_current_net_amount if is_direct and "direct_stop_current_net_amount" in visit._fields else 0.0
            rec.direct_stop_grand_due_amount = visit.direct_stop_grand_due_amount if is_direct and "direct_stop_grand_due_amount" in visit._fields else 0.0
            if is_direct and visit and hasattr(visit, "_get_direct_stop_settlement_payments"):
                settlement_payments = visit._get_direct_stop_settlement_payments(states=["draft", "confirmed"])
                saved_or_confirmed = 0.0
                if settlement_payments:
                    for payment in settlement_payments:
                        saved_or_confirmed += payment.amount or 0.0
                        if (payment.promise_amount or 0.0) > 0.0:
                            saved_or_confirmed += payment.promise_amount or 0.0
                gross_due = visit.direct_stop_grand_due_amount if "direct_stop_grand_due_amount" in visit._fields else 0.0
                rec.direct_stop_settlement_paid_amount = saved_or_confirmed
                rec.direct_stop_settlement_remaining_amount = max((gross_due or 0.0) - (saved_or_confirmed or 0.0), 0.0)
            else:
                rec.direct_stop_settlement_paid_amount = visit.direct_stop_settlement_paid_amount if is_direct and "direct_stop_settlement_paid_amount" in visit._fields else 0.0
                rec.direct_stop_settlement_remaining_amount = visit.direct_stop_settlement_remaining_amount if is_direct and "direct_stop_settlement_remaining_amount" in visit._fields else 0.0
            rec.direct_stop_credit_amount = visit.direct_stop_credit_amount if is_direct and "direct_stop_credit_amount" in visit._fields else 0.0

    def _get_direct_stop_existing_draft_payments(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit or not hasattr(visit, "_get_direct_stop_settlement_payments"):
            return self.env["route.visit.payment"]
        return visit._get_direct_stop_settlement_payments(states=["draft"])

    def _get_direct_stop_latest_draft_payment(self):
        self.ensure_one()
        drafts = self._get_direct_stop_existing_draft_payments()
        if not drafts:
            return self.env["route.visit.payment"]
        return drafts.sorted(key=lambda p: (p.payment_date or fields.Datetime.now(), p.id or 0))[-1]

    def _clear_direct_stop_existing_drafts(self):
        self.ensure_one()
        drafts = self._get_direct_stop_existing_draft_payments()
        if drafts:
            drafts.unlink()

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

            is_direct = hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop()
            existing_drafts = visit._get_direct_stop_settlement_payments(states=["draft"]) if is_direct and hasattr(visit, "_get_direct_stop_settlement_payments") else self.env["route.visit.payment"]
            latest_draft = existing_drafts.sorted(key=lambda p: (p.payment_date or fields.Datetime.now(), p.id or 0))[-1] if existing_drafts else self.env["route.visit.payment"]
            special_draft = existing_drafts.filtered(lambda p: p.collection_type in ("partial", "defer_date", "next_visit"))
            draft_template = special_draft.sorted(key=lambda p: (p.payment_date or fields.Datetime.now(), p.id or 0))[-1] if special_draft else latest_draft

            if latest_draft and latest_draft.id:
                vals.setdefault("payment_date", latest_draft.payment_date or fields.Datetime.now())
                vals.setdefault("payment_mode", latest_draft.payment_mode or "cash")
                vals.setdefault("reference", latest_draft.reference or False)
                vals.setdefault("bank_name", latest_draft.bank_name or False)
                vals.setdefault("pos_terminal", latest_draft.pos_terminal or False)
                vals.setdefault("cheque_number", latest_draft.cheque_number or False)
                vals.setdefault("cheque_date", latest_draft.cheque_date or False)
                vals.setdefault("cheque_holder_name", latest_draft.cheque_holder_name or False)
                vals.setdefault("cheque_note", latest_draft.cheque_note or False)
                vals.setdefault("note", draft_template.note or latest_draft.note or False)
                vals.setdefault("collection_type", draft_template.collection_type or "full")
                vals.setdefault("promise_date", draft_template.promise_date or False)
                vals.setdefault("promise_amount", draft_template.promise_amount or 0.0)
                vals.setdefault("due_date", draft_template.due_date or False)
                vals.setdefault("amount", sum(existing_drafts.mapped("amount")) if existing_drafts else 0.0)
            else:
                if "payment_date" in fields_list:
                    vals.setdefault("payment_date", fields.Datetime.now())
                if "collection_type" in fields_list:
                    vals.setdefault("collection_type", "full")
                if "amount" in fields_list:
                    if is_direct:
                        vals["amount"] = max(getattr(visit, "direct_stop_settlement_remaining_amount", 0.0) or 0.0, 0.0)
                    else:
                        vals["amount"] = max(visit.remaining_due_amount or 0.0, 0.0)
        return vals

    def _get_effective_due_amount(self):
        self.ensure_one()
        if self.is_direct_sales_stop:
            return self.direct_stop_settlement_remaining_amount or 0.0
        return self.visit_remaining_due or 0.0

    def _get_split_payment_total(self):
        self.ensure_one()
        return sum(self.payment_line_ids.mapped("amount")) if self.payment_line_ids else 0.0

    def _get_active_collection_amount(self):
        self.ensure_one()
        if self.settlement_mode == "split" and self.collection_type == "full":
            return self._get_split_payment_total()
        return self.amount or 0.0

    def _single_payment_data(self):
        self.ensure_one()
        return {
            "payment_mode": self.payment_mode,
            "payment_date": self.payment_date,
            "amount": self.amount,
            "reference": self.cheque_number if self.payment_mode == "cheque" and self.cheque_number else self.reference,
            "bank_name": self.bank_name,
            "pos_terminal": self.pos_terminal,
            "cheque_number": self.cheque_number,
            "cheque_date": self.cheque_date,
            "cheque_holder_name": self.cheque_holder_name,
            "cheque_note": self.cheque_note,
        }

    def _get_active_payment_splits(self):
        self.ensure_one()
        if self.settlement_mode == "split" and self.collection_type == "full":
            return [line._payment_data() for line in self.payment_line_ids]
        return [self._single_payment_data()]

    def _sync_promise_fields(self):
        for rec in self:
            due = rec._get_effective_due_amount()
            active_collection_amount = rec._get_active_collection_amount()
            if rec.collection_type == "full":
                rec.promise_date = False
                rec.promise_amount = 0.0
            elif rec.collection_type == "partial":
                rec.promise_amount = max(due - (active_collection_amount or 0.0), 0.0)
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
                if rec.payment_mode == "deferred":
                    rec.payment_mode = "cash"
            elif rec.collection_type == "partial":
                rec.settlement_mode = "single"
                rec.due_date = False
                if rec.payment_mode == "deferred":
                    rec.payment_mode = "cash"
                if due <= 0:
                    rec.amount = 0.0
                elif rec.amount <= 0 or rec.amount >= due:
                    rec.amount = due / 2.0
            elif rec.collection_type == "defer_date":
                rec.settlement_mode = "single"
                rec.amount = 0.0
                rec.payment_mode = "deferred"
            elif rec.collection_type == "next_visit":
                rec.settlement_mode = "single"
                rec.amount = 0.0
                rec.due_date = False
                rec.payment_mode = "deferred"
            if rec.settlement_mode == "split" and rec.collection_type == "full" and not rec.payment_line_ids and due > 0.0:
                rec.payment_line_ids = [(0, 0, {"payment_mode": "cash", "payment_date": rec.payment_date or fields.Datetime.now(), "amount": due})]
            rec._sync_promise_fields()

    def _auto_fill_zero_split_payment_lines(self):
        for rec in self:
            if rec.settlement_mode != "split" or rec.collection_type != "full":
                continue

            due = rec._get_effective_due_amount()
            if due <= 0.0 or not rec.payment_line_ids:
                continue

            running_total = 0.0
            currency = rec.currency_id
            for line in rec.payment_line_ids:
                line_amount = line.amount or 0.0
                if line_amount <= 0.0:
                    remaining = max((due or 0.0) - (running_total or 0.0), 0.0)
                    line.amount = currency.round(remaining) if currency else remaining
                    line_amount = line.amount or 0.0
                running_total += line_amount

    @api.onchange("settlement_mode")
    def _onchange_settlement_mode(self):
        for rec in self:
            due = rec._get_effective_due_amount()
            if rec.settlement_mode == "split" and rec.collection_type != "full":
                rec.settlement_mode = "single"
            elif rec.settlement_mode == "split" and not rec.payment_line_ids and due > 0.0:
                rec.payment_line_ids = [(0, 0, {"payment_mode": "cash", "payment_date": rec.payment_date or fields.Datetime.now(), "amount": due})]
            rec._auto_fill_zero_split_payment_lines()
            rec._sync_promise_fields()

    @api.onchange("payment_line_ids", "payment_line_ids.amount", "payment_line_ids.payment_mode")
    def _onchange_payment_lines(self):
        self._auto_fill_zero_split_payment_lines()
        self._sync_promise_fields()

    @api.onchange("payment_mode")
    def _onchange_payment_mode(self):
        for rec in self:
            if rec.payment_mode in ("cash", "deferred"):
                rec.bank_name = False
                rec.pos_terminal = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "bank":
                rec.pos_terminal = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "pos":
                rec.bank_name = False
                rec.cheque_number = False
                rec.cheque_date = False
                rec.cheque_holder_name = False
                rec.cheque_note = False
            elif rec.payment_mode == "cheque":
                rec.pos_terminal = False
                if rec.cheque_number and not rec.reference:
                    rec.reference = rec.cheque_number

            if rec.payment_mode == "deferred" and rec.collection_type in ("full", "partial"):
                rec.collection_type = "defer_date"
                rec.amount = 0.0
            elif rec.payment_mode != "deferred" and rec.collection_type in ("defer_date", "next_visit"):
                rec.payment_mode = "deferred"

    @api.onchange("cheque_number")
    def _onchange_cheque_number(self):
        for rec in self:
            if rec.payment_mode == "cheque" and rec.cheque_number and not rec.reference:
                rec.reference = rec.cheque_number

    def _validate_cheque_details(self):
        self.ensure_one()
        if self.payment_mode != "cheque" or self.collection_type in ("defer_date", "next_visit"):
            return
        if not self.cheque_number:
            raise ValidationError(_("Please enter the cheque number."))
        if not self.bank_name:
            raise ValidationError(_("Please enter the cheque bank name."))
        if not self.cheque_date:
            raise ValidationError(_("Please enter the cheque date."))

    def _validate_split_payment_lines(self, due):
        self.ensure_one()
        if self.collection_type != "full":
            raise ValidationError(_("Split Payment is available only with Full Payment in this first stable rollout. Use the single-payment partial or deferred options for carried-forward balances."))
        if due <= 0.0:
            raise ValidationError(_("There is no remaining due amount to split."))

        lines = self.payment_line_ids
        if not lines:
            raise ValidationError(_("Please add at least one split payment line."))

        for line in lines:
            line._validate_payment_line()

        total = sum(lines.mapped("amount"))
        precision = self.currency_id.rounding if self.currency_id and self.currency_id.rounding else 0.01
        if total > due + precision:
            raise ValidationError(_("Split payment lines cannot be more than the remaining due amount."))
        if abs((total or 0.0) - (due or 0.0)) > precision:
            raise ValidationError(_("For Full Payment, the split payment lines total must exactly match the remaining due amount."))

    def _validate_before_create(self):
        self.ensure_one()
        due = self._get_effective_due_amount()
        credit_only = self.is_direct_sales_stop and due <= 0.0 and (self.direct_stop_credit_amount or 0.0) > 0.0

        if self.amount < 0:
            raise ValidationError(_("Payment amount cannot be negative."))

        if self.collection_type in ("defer_date", "next_visit") and self.payment_mode != "deferred":
            raise ValidationError(_("Deferred scenarios must use payment mode Deferred."))

        if self.collection_type in ("full", "partial") and self.payment_mode == "deferred":
            raise ValidationError(_("Deferred payment mode is only allowed for defer-to-date or next-visit scenarios."))

        self._validate_cheque_details()

        if credit_only:
            if not self.direct_stop_credit_policy:
                raise ValidationError(_("Please choose how to settle the return credit."))
            return

        if self.settlement_mode == "split":
            self._validate_split_payment_lines(due)
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

    def _prepare_payment_vals(self, target_visit, amount, collection_type, promise_amount=0.0, promise_date=False, due_date=False, payment_data=None):
        payment_data = payment_data or self._single_payment_data()
        payment_mode = "deferred" if collection_type in ("defer_date", "next_visit") else (payment_data.get("payment_mode") or "cash")
        return {
            "visit_id": target_visit.id,
            "settlement_visit_id": self.visit_id.id if self.is_direct_sales_stop else False,
            "payment_date": payment_data.get("payment_date") or self.payment_date,
            "payment_mode": payment_mode,
            "collection_type": collection_type,
            "amount": amount,
            "due_date": due_date,
            "promise_date": promise_date or due_date,
            "promise_amount": promise_amount,
            "reference": payment_data.get("cheque_number") if payment_mode == "cheque" and payment_data.get("cheque_number") else payment_data.get("reference"),
            "bank_name": payment_data.get("bank_name"),
            "pos_terminal": payment_data.get("pos_terminal"),
            "cheque_number": payment_data.get("cheque_number"),
            "cheque_date": payment_data.get("cheque_date"),
            "cheque_holder_name": payment_data.get("cheque_holder_name"),
            "cheque_note": payment_data.get("cheque_note"),
            "note": self.note,
            "state": "draft",
        }

    def _get_direct_stop_target_due(self, target_visit):
        self.ensure_one()
        if not target_visit:
            return 0.0
        if target_visit.id == self.visit_id.id:
            confirmed_payments = target_visit.payment_ids.filtered(lambda p: p.state == "confirmed") if target_visit.payment_ids else target_visit.payment_ids
            confirmed_amount = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0
            current_total = 0.0
            if hasattr(target_visit, "direct_stop_current_net_amount"):
                current_total = target_visit.direct_stop_current_net_amount or 0.0
            if not current_total and hasattr(target_visit, "net_due_amount"):
                current_total = target_visit.net_due_amount or 0.0
            return max((current_total or 0.0) - (confirmed_amount or 0.0), 0.0)
        return target_visit.remaining_due_amount or 0.0

    def _create_direct_sales_payment_allocations(self, payment_splits=None):
        self.ensure_one()
        Payment = self.env["route.visit.payment"]
        visit = self.visit_id
        payment_splits = payment_splits or self._get_active_payment_splits()
        created = Payment
        targets = list(visit._get_direct_stop_previous_due_visits()) + [visit]
        allocated_by_target = {}
        last_payment = Payment
        total_collection_amount = sum(split.get("amount") or 0.0 for split in payment_splits)
        settlement_remaining_after_payment = max((visit.direct_stop_grand_due_amount or 0.0) - (total_collection_amount or 0.0), 0.0)

        for split in payment_splits:
            remaining_amount = split.get("amount") or 0.0
            if remaining_amount <= 0.0:
                continue
            for target in targets:
                already_allocated = allocated_by_target.get(target.id, 0.0)
                due = max((self._get_direct_stop_target_due(target) or 0.0) - already_allocated, 0.0)
                if remaining_amount <= 0.0 or due <= 0.0:
                    continue
                allocation = min(remaining_amount, due)
                payment = Payment.create(self._prepare_payment_vals(target, allocation, "full", payment_data=split))
                created |= payment
                last_payment = payment
                allocated_by_target[target.id] = already_allocated + allocation
                remaining_amount -= allocation

        if self.collection_type == "partial" and settlement_remaining_after_payment > 0.0 and last_payment:
            last_payment.write({
                "collection_type": "partial",
                "promise_date": self.promise_date,
                "promise_amount": self.promise_amount,
                "note": self.note,
            })

        return created

    def _create_direct_sales_cash_allocations(self):
        self.ensure_one()
        return self._create_direct_sales_payment_allocations([self._single_payment_data()])

    def _create_standard_payment_lines(self, payment_splits=None):
        self.ensure_one()
        Payment = self.env["route.visit.payment"]
        payment_splits = payment_splits or self._get_active_payment_splits()
        created = Payment
        last_payment = Payment
        for split in payment_splits:
            amount = split.get("amount") or 0.0
            if amount <= 0.0:
                continue
            payment = Payment.create(self._prepare_payment_vals(self.visit_id, amount, "full", payment_data=split))
            created |= payment
            last_payment = payment

        if self.collection_type == "partial" and last_payment:
            last_payment.write({
                "collection_type": "partial",
                "promise_date": self.promise_date,
                "promise_amount": self.promise_amount,
                "note": self.note,
            })
        return created

    def action_open_statement_of_account(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit:
            raise ValidationError(_("Visit is required."))
        return visit.action_open_statement_of_account() if hasattr(visit, "action_open_statement_of_account") else {"type": "ir.actions.act_window_close"}

    def _ensure_collection_is_open(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit:
            raise ValidationError(_("Visit is required."))

        if visit.state == "done" or getattr(visit, "visit_process_state", False) in ("collection_done", "ready_to_close", "done"):
            raise ValidationError(_("Collection is already closed for this visit. You cannot save another payment decision."))

        if self.is_direct_sales_stop:
            draft_payments = visit._get_direct_stop_settlement_payments(states=["draft"]) if hasattr(visit, "_get_direct_stop_settlement_payments") else self.env["route.visit.payment"]
        else:
            draft_payments = visit.payment_ids.filtered(lambda p: p.state == "draft")

        if draft_payments:
            raise ValidationError(_("There are draft payments waiting for confirmation. Please confirm them before saving a new collection decision."))

        if not getattr(visit, "ux_can_collect_payment", False):
            raise ValidationError(_("Collect Payment is not available for this visit at the current stage."))

    def action_close_settlement(self):
        self.ensure_one()
        if self.is_direct_sales_stop:
            self.visit_id.write({
                "direct_stop_credit_policy": self.direct_stop_credit_policy or False,
                "direct_stop_credit_note": self.direct_stop_credit_note or False,
                "direct_stop_settlement_reviewed": True,
            })
            if hasattr(self.visit_id, "_action_mark_post_collection_stage"):
                self.visit_id._action_mark_post_collection_stage()
            if hasattr(self.visit_id, "_get_pda_form_action"):
                return self.visit_id._get_pda_form_action()
        return {"type": "ir.actions.act_window_close"}

    def action_save_payment(self):
        self.ensure_one()
        self._ensure_collection_is_open()
        self._validate_before_create()

        if self.is_direct_sales_stop:
            self.visit_id.write({
                "direct_stop_credit_policy": self.direct_stop_credit_policy or False,
                "direct_stop_credit_note": self.direct_stop_credit_note or False,
            })

            due = self.direct_stop_settlement_remaining_amount or 0.0
            credit_only = due <= 0.0 and (self.direct_stop_credit_amount or 0.0) > 0.0
            no_payment_due = due <= 0.0 and (self.direct_stop_credit_amount or 0.0) <= 0.0

            # A direct-sales stop must keep only one active draft settlement decision.
            # When the salesperson changes the scenario and saves again, replace the old draft(s)
            # instead of creating duplicate/conflicting lines.
            self._clear_direct_stop_existing_drafts()

            if no_payment_due:
                self.visit_id.write({"direct_stop_settlement_reviewed": True})
                if hasattr(self.visit_id, "_action_mark_post_collection_stage"):
                    self.visit_id._action_mark_post_collection_stage()
                return self.visit_id._get_pda_form_action() if hasattr(self.visit_id, "_get_pda_form_action") else {"type": "ir.actions.act_window_close"}
            if credit_only:
                self.visit_id.write({"direct_stop_settlement_reviewed": True})
                if hasattr(self.visit_id, "_action_mark_post_collection_stage"):
                    self.visit_id._action_mark_post_collection_stage()
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
                self._create_direct_sales_payment_allocations(self._get_active_payment_splits())

            if hasattr(self.visit_id, "_get_pda_form_action"):
                return self.visit_id._get_pda_form_action()
            return {"type": "ir.actions.act_window_close"}

        if self.settlement_mode == "split" and self.collection_type == "full":
            self._create_standard_payment_lines(self._get_active_payment_splits())
        else:
            self.env["route.visit.payment"].create(
                self._prepare_payment_vals(
                    self.visit_id,
                    self.amount,
                    self.collection_type,
                    promise_amount=self.promise_amount,
                    promise_date=self.promise_date,
                    due_date=self.due_date,
                    payment_data=self._single_payment_data(),
                )
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



