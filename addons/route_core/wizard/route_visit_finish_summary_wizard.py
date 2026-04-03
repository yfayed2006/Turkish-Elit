from odoo import _, api, fields, models


class RouteVisitFinishSummaryWizard(models.TransientModel):
    _name = "route.visit.finish.summary.wizard"
    _description = "Route Visit Finish Summary Wizard"

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
    finish_message = fields.Html(compute="_compute_finish_message", sanitize=False, store=False)

    @api.depends("visit_id")
    def _compute_is_direct_sales_stop(self):
        for rec in self:
            visit = rec.visit_id
            rec.is_direct_sales_stop = bool(visit and hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop())

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
            rec.show_previous_due = bool(rec.is_direct_sales_stop and (rec.direct_stop_previous_due_amount or 0.0) > 0.0)
            rec.show_sale_orders = bool(rec.is_direct_sales_stop and (rec.direct_stop_order_count or 0) > 0)
            rec.show_direct_returns = bool(rec.is_direct_sales_stop and (rec.direct_stop_return_count or 0) > 0)

    @api.depends(
        "is_direct_sales_stop",
        "outlet_id",
        "visit_date",
        "direct_stop_settlement_paid_amount",
        "direct_stop_settlement_remaining_amount",
        "direct_stop_credit_amount",
        "direct_stop_sales_total",
        "direct_stop_returns_total",
    )
    def _compute_finish_message(self):
        for rec in self:
            if not rec.is_direct_sales_stop:
                rec.finish_message = _('<div class="alert alert-success mb-0"><strong>Visit finished successfully.</strong></div>')
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
            if (rec.direct_stop_sales_total or 0.0) > 0.0:
                sales_value = "%.2f %s" % ((rec.direct_stop_sales_total or 0.0), rec.currency_id.name if rec.currency_id else "")
                parts.append(_("Sales total: %s") % sales_value.strip())
            if (rec.direct_stop_returns_total or 0.0) > 0.0:
                parts.append(_("Returns total: %s") % rec.currency_id.format(rec.direct_stop_returns_total, lang_code=self.env.user.lang or None) if rec.currency_id else _("Returns total: %.2f") % (rec.direct_stop_returns_total or 0.0))
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
        return {"type": "ir.actions.act_window_close"}
