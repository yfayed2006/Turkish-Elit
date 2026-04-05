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
    consignment_current_due_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_collected_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_remaining_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_promise_amount = fields.Monetary(currency_field="currency_id", compute="_compute_consignment_summary", store=False)
    consignment_payment_count = fields.Integer(compute="_compute_consignment_summary", store=False)
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
        payment_mode_map = dict(self.env["route.visit.payment"]._fields["payment_mode"].selection)
        collection_type_map = dict(self.env["route.visit.payment"]._fields["collection_type"].selection)
        for rec in self:
            if rec.is_direct_sales_stop or not rec.visit_id:
                rec.consignment_sale_order_ref = False
                rec.consignment_refill_ref = False
                rec.consignment_return_refs = False
                rec.consignment_execution_mode_label = False
                rec.consignment_current_due_amount = 0.0
                rec.consignment_collected_amount = 0.0
                rec.consignment_remaining_amount = 0.0
                rec.consignment_promise_amount = 0.0
                rec.consignment_payment_count = 0
                rec.consignment_payment_summary_html = False
                continue
            summary = rec.visit_id._get_consignment_receipt_summary() if hasattr(rec.visit_id, "_get_consignment_receipt_summary") else {}
            rec.consignment_sale_order_ref = summary.get("sale_order_ref") or "-"
            rec.consignment_refill_ref = summary.get("refill_ref") or "-"
            rec.consignment_return_refs = summary.get("return_refs") or "-"
            rec.consignment_execution_mode_label = rec.visit_id.visit_execution_mode_label or "-"
            rec.consignment_current_due_amount = summary.get("current_due", 0.0)
            rec.consignment_collected_amount = summary.get("settled_amount", 0.0)
            rec.consignment_remaining_amount = summary.get("remaining_amount", 0.0)
            rec.consignment_promise_amount = summary.get("promise_amount", 0.0)
            payments = rec.visit_id._get_consignment_receipt_payments() if hasattr(rec.visit_id, "_get_consignment_receipt_payments") else self.env["route.visit.payment"]
            rec.consignment_payment_count = len(payments)
            rows = []
            for payment in payments:
                promise_text = "-"
                if payment.promise_date or payment.promise_amount:
                    bits = []
                    if payment.promise_date:
                        bits.append(str(payment.promise_date))
                    if payment.promise_amount:
                        bits.append(rec._format_currency_amount(payment.promise_amount))
                    promise_text = " / ".join(bits)
                rows.append(
                    "<tr>"
                    f"<td style='padding:6px 8px; border-bottom:1px solid #eee;'>{payment.payment_date or '-'}</td>"
                    f"<td style='padding:6px 8px; border-bottom:1px solid #eee;'>{payment_mode_map.get(payment.payment_mode, payment.payment_mode or '-')}</td>"
                    f"<td style='padding:6px 8px; border-bottom:1px solid #eee;'>{collection_type_map.get(payment.collection_type, payment.collection_type or '-')}</td>"
                    f"<td style='padding:6px 8px; border-bottom:1px solid #eee; text-align:right;'>{rec._format_currency_amount(payment.amount)}</td>"
                    f"<td style='padding:6px 8px; border-bottom:1px solid #eee;'>{promise_text}</td>"
                    "</tr>"
                )
            if rows:
                rec.consignment_payment_summary_html = (
                    "<table style='width:100%; border-collapse:collapse;'>"
                    "<thead><tr>"
                    "<th style='text-align:left; padding:6px 8px; border-bottom:1px solid #ddd;'>Date</th>"
                    "<th style='text-align:left; padding:6px 8px; border-bottom:1px solid #ddd;'>Mode</th>"
                    "<th style='text-align:left; padding:6px 8px; border-bottom:1px solid #ddd;'>Collection</th>"
                    "<th style='text-align:right; padding:6px 8px; border-bottom:1px solid #ddd;'>Amount</th>"
                    "<th style='text-align:left; padding:6px 8px; border-bottom:1px solid #ddd;'>Promise</th>"
                    "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
                )
            else:
                rec.consignment_payment_summary_html = _("<div class='alert alert-info mb-0'>No confirmed payments were found for this visit.</div>")

    @api.depends(
        "is_direct_sales_stop",
        "outlet_id",
        "visit_date",
        "direct_stop_settlement_paid_amount",
        "direct_stop_settlement_remaining_amount",
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
                summary = rec.visit_id._get_consignment_receipt_summary() if rec.visit_id and hasattr(rec.visit_id, "_get_consignment_receipt_summary") else {}
                parts = [
                    _('<div class="alert alert-success mb-0"><strong>Consignment visit finished successfully.</strong>'),
                    _("Outlet: %s") % (rec.outlet_id.display_name if rec.outlet_id else "-"),
                    _("Date: %s") % (rec.visit_date or "-"),
                    _("Sale Order: %s") % (summary.get("sale_order_ref") or "-"),
                    _("Refill Transfer: %s") % (summary.get("refill_ref") or "-"),
                    _("Return Transfer: %s") % (summary.get("return_refs") or "-"),
                    _("Current Due: %s") % rec._format_currency_amount(summary.get("current_due", 0.0)),
                    _("Collected: %s") % rec._format_currency_amount(summary.get("settled_amount", 0.0)),
                    _("Remaining: %s") % rec._format_currency_amount(summary.get("remaining_amount", 0.0)),
                ]
                if summary.get("promise_amount"):
                    parts.append(_("Promise: %s") % rec._format_currency_amount(summary.get("promise_amount", 0.0)))
                    if summary.get("latest_promise_date"):
                        parts.append(_("Promise Date: %s") % summary.get("latest_promise_date"))
                parts.append("</div>")
                rec.finish_message = "<br/>".join(parts)
                continue

            if (rec.direct_stop_credit_amount or 0.0) > 0.0:
                extra = _("Customer credit has been recorded for this stop.")
            elif (rec.direct_stop_settlement_remaining_amount or 0.0) <= 0.0:
                extra = _("Settlement is complete and no further action is required.")
            else:
                extra = _("The stop has been closed. Review the saved settlement records if needed.")

            parts = [
                _('<div class="alert alert-success mb-0"><strong>Direct sales stop completed successfully.</strong>'),
                _("Outlet: %s") % (rec.outlet_id.display_name if rec.outlet_id else "-"),
                _("Date: %s") % (rec.visit_date or "-"),
            ]
            parts.append(_("Previous due: %s") % rec._format_currency_amount(rec.direct_stop_previous_due_amount))
            parts.append(_("Previous due since: %s") % (rec.direct_stop_previous_due_since_display or "0"))
            if (rec.direct_stop_sales_total or 0.0) > 0.0:
                parts.append(_("Sales total: %s") % rec._format_currency_amount(rec.direct_stop_sales_total))
            if (rec.direct_stop_returns_total or 0.0) > 0.0:
                parts.append(_("Returns total: %s") % rec._format_currency_amount(rec.direct_stop_returns_total))
            parts.append(extra)
            parts.append("</div>")
            rec.finish_message = "<br/>".join(parts)

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
