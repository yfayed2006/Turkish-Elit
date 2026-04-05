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
    is_direct_sales_stop = fields.Boolean(compute="_compute_visit_mode_flags", store=False, readonly=True)
    is_consignment_visit = fields.Boolean(compute="_compute_visit_mode_flags", store=False, readonly=True)
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

    summary_sale_order_ref = fields.Char(compute="_compute_receipt_summary", store=False)
    summary_return_ref = fields.Char(compute="_compute_receipt_summary", store=False)
    summary_refill_ref = fields.Char(compute="_compute_receipt_summary", store=False)
    summary_previous_due_amount = fields.Monetary(compute="_compute_receipt_summary", currency_field="currency_id", store=False)
    summary_current_sale_amount = fields.Monetary(compute="_compute_receipt_summary", currency_field="currency_id", store=False)
    summary_current_return_amount = fields.Monetary(compute="_compute_receipt_summary", currency_field="currency_id", store=False)
    summary_refill_amount = fields.Monetary(compute="_compute_receipt_summary", currency_field="currency_id", store=False)
    summary_grand_due_amount = fields.Monetary(compute="_compute_receipt_summary", currency_field="currency_id", store=False)
    summary_paid_amount = fields.Monetary(compute="_compute_receipt_summary", currency_field="currency_id", store=False)
    summary_remaining_amount = fields.Monetary(compute="_compute_receipt_summary", currency_field="currency_id", store=False)
    summary_promise_amount = fields.Monetary(compute="_compute_receipt_summary", currency_field="currency_id", store=False)

    payment_ids = fields.Many2many("route.visit.payment", compute="_compute_payment_ids", string="Payments", store=False)

    sale_status_label = fields.Char(compute="_compute_status_labels", store=False)
    return_status_label = fields.Char(compute="_compute_status_labels", store=False)
    credit_policy_label = fields.Char(compute="_compute_status_labels", store=False)
    show_credit_section = fields.Boolean(compute="_compute_display_flags", store=False)
    show_return_section = fields.Boolean(compute="_compute_display_flags", store=False)
    show_previous_due = fields.Boolean(compute="_compute_display_flags", store=False)
    show_sale_orders = fields.Boolean(compute="_compute_display_flags", store=False)
    show_direct_returns = fields.Boolean(compute="_compute_display_flags", store=False)
    finish_message = fields.Html(compute="_compute_finish_message", sanitize=False, store=False)

    @api.depends("visit_id")
    def _compute_visit_mode_flags(self):
        for rec in self:
            visit = rec.visit_id
            rec.is_direct_sales_stop = bool(visit and hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop())
            rec.is_consignment_visit = bool(visit) and not rec.is_direct_sales_stop

    @api.depends("visit_id")
    def _compute_receipt_summary(self):
        for rec in self:
            summary = {}
            if rec.visit_id:
                if rec.is_direct_sales_stop and hasattr(rec.visit_id, "_get_direct_stop_receipt_summary"):
                    summary = rec.visit_id._get_direct_stop_receipt_summary()
                elif hasattr(rec.visit_id, "_get_consignment_receipt_summary"):
                    summary = rec.visit_id._get_consignment_receipt_summary()
            rec.summary_sale_order_ref = summary.get("sale_order_ref", "-")
            rec.summary_return_ref = summary.get("return_ref", "-")
            rec.summary_refill_ref = summary.get("refill_ref", "-")
            rec.summary_previous_due_amount = summary.get("previous_due", 0.0)
            rec.summary_current_sale_amount = summary.get("current_sale", 0.0)
            rec.summary_current_return_amount = summary.get("current_return", 0.0)
            rec.summary_refill_amount = summary.get("current_refill", 0.0)
            rec.summary_grand_due_amount = summary.get("grand_total_due", 0.0)
            rec.summary_paid_amount = summary.get("settled_amount", 0.0)
            rec.summary_remaining_amount = summary.get("remaining_amount", 0.0)
            rec.summary_promise_amount = summary.get("promise_amount", 0.0)

    @api.depends("visit_id")
    def _compute_payment_ids(self):
        Payment = self.env["route.visit.payment"]
        for rec in self:
            payments = Payment
            if rec.visit_id:
                if rec.is_direct_sales_stop and hasattr(rec.visit_id, "_get_direct_stop_receipt_payments"):
                    payments = rec.visit_id._get_direct_stop_receipt_payments()
                elif hasattr(rec.visit_id, "_get_consignment_receipt_payments"):
                    payments = rec.visit_id._get_consignment_receipt_payments()
            rec.payment_ids = payments

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
        "summary_previous_due_amount",
        "summary_current_return_amount",
        "summary_sale_order_ref",
        "summary_return_ref",
    )
    def _compute_display_flags(self):
        for rec in self:
            rec.show_credit_section = bool(rec.is_direct_sales_stop and (rec.direct_stop_credit_amount or 0.0) > 0.0)
            rec.show_return_section = bool(
                (rec.is_direct_sales_stop and (rec.direct_stop_returns_total or 0.0) > 0.0)
                or (rec.is_consignment_visit and (rec.summary_current_return_amount or 0.0) > 0.0)
            )
            rec.show_previous_due = bool((rec.direct_stop_previous_due_amount or rec.summary_previous_due_amount or 0.0) > 0.0)
            rec.show_sale_orders = bool(rec.is_direct_sales_stop and (rec.direct_stop_order_count or 0) > 0) or bool(rec.summary_sale_order_ref and rec.summary_sale_order_ref != "-")
            rec.show_direct_returns = bool(rec.is_direct_sales_stop and (rec.direct_stop_return_count or 0) > 0) or bool(rec.summary_return_ref and rec.summary_return_ref != "-")

    @api.depends(
        "is_direct_sales_stop",
        "is_consignment_visit",
        "outlet_id",
        "visit_date",
        "direct_stop_settlement_paid_amount",
        "direct_stop_settlement_remaining_amount",
        "direct_stop_credit_amount",
        "direct_stop_sales_total",
        "direct_stop_returns_total",
        "direct_stop_previous_due_amount",
        "direct_stop_previous_due_since_display",
        "summary_sale_order_ref",
        "summary_return_ref",
        "summary_refill_ref",
        "summary_paid_amount",
        "summary_remaining_amount",
        "summary_promise_amount",
    )
    def _compute_finish_message(self):
        for rec in self:
            if rec.is_consignment_visit:
                parts = [
                    _('<div class="alert alert-success mb-0"><strong>Consignment visit completed successfully.</strong>'),
                    _("Outlet: %s") % (rec.outlet_id.display_name if rec.outlet_id else "-"),
                    _("Date: %s") % (rec.visit_date or "-"),
                ]
                if rec.summary_sale_order_ref and rec.summary_sale_order_ref != "-":
                    parts.append(_("Sale Order: %s") % rec.summary_sale_order_ref)
                if rec.summary_return_ref and rec.summary_return_ref != "-":
                    parts.append(_("Return Transfers: %s") % rec.summary_return_ref)
                if rec.summary_refill_ref and rec.summary_refill_ref != "-":
                    parts.append(_("Refill Transfer: %s") % rec.summary_refill_ref)
                if (rec.summary_promise_amount or 0.0) > 0.0:
                    parts.append(_("Promise recorded: %s") % rec._format_currency_amount(rec.summary_promise_amount))
                elif (rec.summary_remaining_amount or 0.0) <= 0.0:
                    parts.append(_("Settlement is complete and no further action is required."))
                else:
                    parts.append(_("The visit has been closed. Review the payment summary if needed."))
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
        return self.visit_id.action_print_visit_receipt()

    def action_send_whatsapp_outlet(self):
        self.ensure_one()
        return self.visit_id.action_send_visit_whatsapp_outlet()

    def action_send_whatsapp_supervisor(self):
        self.ensure_one()
        return self.visit_id.action_send_visit_whatsapp_supervisor()

    def action_close(self):
        return {"type": "ir.actions.act_window_close"}

