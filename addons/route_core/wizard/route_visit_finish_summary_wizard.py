from odoo import _, api, fields, models


class RouteVisitFinishSummaryWizard(models.TransientModel):
    _name = "route.visit.finish.summary.wizard"
    _description = "Route Visit Finish Summary Wizard"

    def _format_currency_amount(self, amount):
        self.ensure_one()
        amount = amount or 0.0
        currency = self.currency_id
        if not currency:
            return "%.2f" % amount

        precision = currency.decimal_places or 2
        formatted = f"{amount:,.{precision}f}"
        symbol = currency.symbol or currency.name or ""
        if not symbol:
            return formatted
        if currency.position == "before":
            return "%s %s" % (symbol, formatted)
        return "%s %s" % (formatted, symbol)

    def _get_credit_policy_selection_map(self):
        selection = []
        try:
            selection = self.env["route.visit"].fields_get(["direct_stop_credit_policy"])["direct_stop_credit_policy"].get("selection", [])
        except Exception:
            selection = []
        return dict(selection or [
            ("customer_credit", _("Customer Credit")),
            ("cash_refund", _("Cash Refund")),
            ("next_stop", _("Carry to Next Stop")),
        ])

    visit_id = fields.Many2one("route.visit", string="Visit", required=True, readonly=True)
    company_id = fields.Many2one("res.company", related="visit_id.company_id", readonly=True, store=False)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True, store=False)
    is_direct_sales_stop = fields.Boolean(compute="_compute_is_direct_sales_stop", store=False, readonly=True)
    outlet_id = fields.Many2one("route.outlet", related="visit_id.outlet_id", readonly=True, store=False)
    partner_id = fields.Many2one("res.partner", related="visit_id.partner_id", readonly=True, store=False)
    user_id = fields.Many2one("res.users", related="visit_id.user_id", readonly=True, store=False)
    visit_date = fields.Date(related="visit_id.date", readonly=True, store=False)
    end_datetime = fields.Datetime(related="visit_id.end_datetime", readonly=True, store=False)

    direct_stop_sale_status = fields.Selection(related="visit_id.direct_stop_sale_status", readonly=True, store=False)
    direct_stop_return_status = fields.Selection(related="visit_id.direct_stop_return_status", readonly=True, store=False)
    direct_stop_order_count = fields.Integer(related="visit_id.direct_stop_order_count", readonly=True, store=False)
    direct_stop_return_count = fields.Integer(related="visit_id.direct_stop_return_count", readonly=True, store=False)
    direct_stop_previous_due_amount = fields.Monetary(related="visit_id.direct_stop_previous_due_amount", currency_field="currency_id", readonly=True, store=False)
    direct_stop_previous_due_since_date = fields.Date(related="visit_id.direct_stop_previous_due_since_date", readonly=True, store=False)
    direct_stop_previous_due_since_display = fields.Char(compute="_compute_previous_due_since_display", store=False)
    direct_stop_sales_total = fields.Monetary(related="visit_id.direct_stop_sales_total", currency_field="currency_id", readonly=True, store=False)
    direct_stop_returns_total = fields.Monetary(related="visit_id.direct_stop_returns_total", currency_field="currency_id", readonly=True, store=False)
    direct_stop_current_net_amount = fields.Monetary(related="visit_id.direct_stop_current_net_amount", currency_field="currency_id", readonly=True, store=False)
    direct_stop_grand_due_amount = fields.Monetary(related="visit_id.direct_stop_grand_due_amount", currency_field="currency_id", readonly=True, store=False)
    direct_stop_settlement_paid_amount = fields.Monetary(related="visit_id.direct_stop_settlement_paid_amount", currency_field="currency_id", readonly=True, store=False)
    direct_stop_settlement_remaining_amount = fields.Monetary(related="visit_id.direct_stop_settlement_remaining_amount", currency_field="currency_id", readonly=True, store=False)
    direct_stop_credit_amount = fields.Monetary(related="visit_id.direct_stop_credit_amount", currency_field="currency_id", readonly=True, store=False)
    direct_stop_credit_policy = fields.Selection(related="visit_id.direct_stop_credit_policy", readonly=True, store=False)
    direct_stop_open_promise_amount = fields.Monetary(currency_field="currency_id", compute="_compute_direct_stop_balance_breakdown", store=False)
    direct_stop_immediate_remaining_amount = fields.Monetary(currency_field="currency_id", compute="_compute_direct_stop_balance_breakdown", store=False)
    direct_stop_latest_promise_date = fields.Date(compute="_compute_direct_stop_balance_breakdown", store=False)
    direct_stop_latest_promise_status = fields.Char(compute="_compute_direct_stop_balance_breakdown", store=False)


    sale_status_label = fields.Char(compute="_compute_status_labels", store=False)
    return_status_label = fields.Char(compute="_compute_status_labels", store=False)
    credit_policy_label = fields.Char(compute="_compute_status_labels", store=False)
    show_credit_section = fields.Boolean(compute="_compute_display_flags", store=False)
    show_return_section = fields.Boolean(compute="_compute_display_flags", store=False)
    show_previous_due = fields.Boolean(compute="_compute_display_flags", store=False)
    show_sale_orders = fields.Boolean(compute="_compute_display_flags", store=False)
    show_direct_returns = fields.Boolean(compute="_compute_display_flags", store=False)
    show_consignment_section = fields.Boolean(compute="_compute_display_flags", store=False)
    consignment_sale_order_ref = fields.Char(compute="_compute_consignment_summary", store=False)
    consignment_refill_ref = fields.Char(compute="_compute_consignment_summary", store=False)
    consignment_return_refs = fields.Char(compute="_compute_consignment_summary", store=False)
    consignment_execution_mode_label = fields.Char(compute="_compute_consignment_summary", store=False)
    consignment_previous_due_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_current_visit_sale_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_current_visit_return_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_net_amount_for_visit = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_current_due_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_collected_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_remaining_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_promise_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_total_outstanding_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_payment_count = fields.Integer(compute="_compute_consignment_summary", store=False)
    show_consignment_payments_section = fields.Boolean(compute="_compute_consignment_summary", store=False)
    consignment_payment_summary_html = fields.Html(compute="_compute_consignment_summary", sanitize=False, store=False)
    finish_message = fields.Html(compute="_compute_finish_message", sanitize=False, store=False)

    @api.depends("visit_id")
    def _compute_is_direct_sales_stop(self):
        for rec in self:
            visit = rec.visit_id
            rec.is_direct_sales_stop = bool(visit and hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop())

    @api.depends("direct_stop_previous_due_since_date")
    def _compute_previous_due_since_display(self):
        for rec in self:
            rec.direct_stop_previous_due_since_display = str(rec.direct_stop_previous_due_since_date) if rec.direct_stop_previous_due_since_date else "0"

    @api.depends("visit_id", "direct_stop_grand_due_amount", "direct_stop_settlement_paid_amount")
    def _compute_direct_stop_balance_breakdown(self):
        for rec in self:
            if not rec.is_direct_sales_stop or not rec.visit_id:
                rec.direct_stop_open_promise_amount = 0.0
                rec.direct_stop_immediate_remaining_amount = 0.0
                rec.direct_stop_latest_promise_date = False
                rec.direct_stop_latest_promise_status = False
                continue
            payments = rec.visit_id._get_direct_stop_settlement_payments(states=["confirmed"]) if hasattr(rec.visit_id, "_get_direct_stop_settlement_payments") else rec.env["route.visit.payment"]
            promise_payments = payments.filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
            latest_promise = promise_payments.sorted(
                key=lambda p: (p.payment_date or fields.Datetime.to_datetime("1900-01-01 00:00:00"), p.id or 0),
                reverse=True,
            )[:1] if promise_payments else promise_payments
            rec.direct_stop_open_promise_amount = sum(promise_payments.mapped("promise_amount")) if promise_payments else 0.0
            rec.direct_stop_immediate_remaining_amount = max((rec.direct_stop_grand_due_amount or 0.0) - (rec.direct_stop_settlement_paid_amount or 0.0), 0.0)
            rec.direct_stop_latest_promise_date = latest_promise.promise_date if latest_promise else False
            if latest_promise:
                rec.direct_stop_latest_promise_status = latest_promise._get_snapshot_promise_status() if hasattr(latest_promise, "_get_snapshot_promise_status") else latest_promise.promise_status
            else:
                rec.direct_stop_latest_promise_status = False

    @api.depends("direct_stop_sale_status", "direct_stop_return_status", "direct_stop_credit_policy")
    def _compute_status_labels(self):
        sale_map = {"pending": _("Pending"), "yes": _("Sale Created"), "no": _("No Sale")}
        return_map = {"pending": _("Pending"), "yes": _("Return Created"), "no": _("No Return")}
        credit_map = self._get_credit_policy_selection_map()

        for rec in self:
            rec.sale_status_label = sale_map.get(rec.direct_stop_sale_status, "")
            rec.return_status_label = return_map.get(rec.direct_stop_return_status, "")
            rec.credit_policy_label = credit_map.get(rec.direct_stop_credit_policy, "") if rec.direct_stop_credit_policy else _("Not Required")

    @api.depends(
        "is_direct_sales_stop",
        "direct_stop_credit_amount",
        "direct_stop_returns_total",
        "direct_stop_previous_due_amount",
        "direct_stop_order_count",
        "direct_stop_return_count",
    )
    def _compute_display_flags(self):
        for rec in self:
            rec.show_credit_section = bool(rec.is_direct_sales_stop and (rec.direct_stop_credit_amount or 0.0) > 0.0)
            rec.show_return_section = bool(rec.is_direct_sales_stop and (rec.direct_stop_returns_total or 0.0) > 0.0)
            rec.show_previous_due = bool(rec.is_direct_sales_stop)
            rec.show_sale_orders = bool(rec.is_direct_sales_stop and (rec.direct_stop_order_count or 0) > 0)
            rec.show_direct_returns = bool(rec.is_direct_sales_stop and (rec.direct_stop_return_count or 0) > 0)
            rec.show_consignment_section = not rec.is_direct_sales_stop

    @api.depends("visit_id")
    def _compute_consignment_summary(self):
        for rec in self:
            if rec.is_direct_sales_stop or not rec.visit_id:
                rec.consignment_sale_order_ref = False
                rec.consignment_refill_ref = False
                rec.consignment_return_refs = False
                rec.consignment_execution_mode_label = False
                rec.consignment_previous_due_amount = 0.0
                rec.consignment_current_visit_sale_amount = 0.0
                rec.consignment_current_visit_return_amount = 0.0
                rec.consignment_net_amount_for_visit = 0.0
                rec.consignment_current_due_amount = 0.0
                rec.consignment_collected_amount = 0.0
                rec.consignment_remaining_amount = 0.0
                rec.consignment_promise_amount = 0.0
                rec.consignment_total_outstanding_amount = 0.0
                rec.consignment_payment_count = 0
                rec.show_consignment_payments_section = False
                rec.consignment_payment_summary_html = False
                continue
            summary = rec.visit_id._get_consignment_receipt_summary() if hasattr(rec.visit_id, "_get_consignment_receipt_summary") else {}
            rec.consignment_sale_order_ref = summary.get("sale_order_ref") or "-"
            rec.consignment_refill_ref = summary.get("refill_ref") or "-"
            rec.consignment_return_refs = summary.get("return_refs") or "-"
            rec.consignment_execution_mode_label = rec.visit_id.visit_execution_mode_label or "-"
            rec.consignment_previous_due_amount = summary.get("previous_due", 0.0)
            rec.consignment_current_visit_sale_amount = summary.get("visit_sale_amount", 0.0)
            rec.consignment_current_visit_return_amount = summary.get("returned_value", 0.0)
            rec.consignment_net_amount_for_visit = summary.get("current_visit_net", 0.0)
            rec.consignment_current_due_amount = summary.get("total_outlet_due", summary.get("current_due", 0.0))
            rec.consignment_collected_amount = summary.get("settled_amount", 0.0)
            rec.consignment_remaining_amount = summary.get("current_visit_remaining", summary.get("remaining_amount", 0.0))
            rec.consignment_promise_amount = summary.get("promise_amount", 0.0)
            rec.consignment_total_outstanding_amount = summary.get("total_outstanding_after_collection", 0.0)
            payments = rec.visit_id._get_consignment_receipt_payments() if hasattr(rec.visit_id, "_get_consignment_receipt_payments") else self.env["route.visit.payment"]
            rec.consignment_payment_count = len(payments)
            rec.show_consignment_payments_section = bool(payments)
            rec.consignment_payment_summary_html = rec.visit_id._build_payment_cards_html(
                payments,
                empty_message=_("<div class='alert alert-info mb-0'>No confirmed payments were found for this visit.</div>"),
                show_source=False,
                show_settlement=False,
                show_notes=True,
            )

    @api.depends(
        "is_direct_sales_stop",
        "outlet_id",
        "visit_date",
        "direct_stop_settlement_paid_amount",
        "direct_stop_settlement_remaining_amount",
        "direct_stop_open_promise_amount",
        "direct_stop_immediate_remaining_amount",
        "direct_stop_credit_amount",
        "direct_stop_sales_total",
        "direct_stop_returns_total",
        "direct_stop_previous_due_amount",
        "direct_stop_previous_due_since_display",
        "visit_id",
    )
    def _compute_finish_message(self):
        for rec in self:
            if not rec.is_direct_sales_stop:
                extra = _("This is the final visit summary. Completed documents, receipt, WhatsApp, and review actions are available below.")
                rec.finish_message = "".join([
                    '<div class="alert alert-success mb-0 route_pda_finish_alert">',
                    f"<strong>{_('Visit completed successfully.')}</strong><br/>",
                    extra,
                    "</div>",
                ])
                continue

            if (rec.direct_stop_credit_amount or 0.0) > 0.0:
                extra = _("Customer credit has been recorded for this stop.")
            elif (rec.direct_stop_open_promise_amount or 0.0) > 0.0:
                extra = _("Immediate cash collection is complete and the remaining balance is covered by an open promise.")
            elif (rec.direct_stop_immediate_remaining_amount or 0.0) <= 0.0:
                extra = _("Settlement is complete and no further action is required.")
            else:
                extra = _("The stop has been closed. Review the saved settlement records if needed.")

            rec.finish_message = "".join([
                '<div class="alert alert-success mb-0 route_pda_finish_alert">',
                f"<strong>{_('Visit completed successfully.')}</strong><br/>",
                extra,
                "</div>",
            ])

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        visit_id = self.env.context.get("default_visit_id") or self.env.context.get("active_id")
        if visit_id:
            vals.setdefault("visit_id", visit_id)
        return vals

    def action_print_receipt(self):
        self.ensure_one()
        return self.visit_id.action_print_direct_stop_settlement_receipt()

    def action_send_whatsapp_outlet(self):
        self.ensure_one()
        return self.visit_id.action_send_direct_stop_whatsapp_outlet()

    def action_send_whatsapp_supervisor(self):
        self.ensure_one()
        return self.visit_id.action_send_direct_stop_whatsapp_supervisor()

    def action_close(self):
        self.ensure_one()
        if self.visit_id and hasattr(self.visit_id, '_get_pda_form_action'):
            return self.visit_id._get_pda_form_action()
        return {"type": "ir.actions.act_window_close"}



