from odoo import _, api, fields, models


class RouteVisitFinishSummaryWizard(models.TransientModel):
    _name = "route.visit.finish.summary.wizard"
    _description = "Route Visit Finish Summary Wizard"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="visit_id.company_id",
        readonly=True,
        store=False,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
        store=False,
    )
    is_direct_sales_stop = fields.Boolean(
        compute="_compute_is_direct_sales_stop",
        store=False,
        readonly=True,
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        related="visit_id.outlet_id",
        readonly=True,
        store=False,
    )
    partner_id = fields.Many2one(
        "res.partner",
        related="visit_id.partner_id",
        readonly=True,
        store=False,
    )
    user_id = fields.Many2one(
        "res.users",
        related="visit_id.user_id",
        readonly=True,
        store=False,
    )
    visit_date = fields.Date(
        related="visit_id.date",
        readonly=True,
        store=False,
    )
    end_datetime = fields.Datetime(
        related="visit_id.end_datetime",
        readonly=True,
        store=False,
    )

    direct_stop_sale_status = fields.Selection(
        related="visit_id.direct_stop_sale_status",
        readonly=True,
        store=False,
    )
    direct_stop_return_status = fields.Selection(
        related="visit_id.direct_stop_return_status",
        readonly=True,
        store=False,
    )
    direct_stop_order_count = fields.Integer(
        related="visit_id.direct_stop_order_count",
        readonly=True,
        store=False,
    )
    direct_stop_return_count = fields.Integer(
        related="visit_id.direct_stop_return_count",
        readonly=True,
        store=False,
    )
    direct_stop_previous_due_amount = fields.Monetary(
        related="visit_id.direct_stop_previous_due_amount",
        currency_field="currency_id",
        readonly=True,
        store=False,
    )
    direct_stop_sales_total = fields.Monetary(
        related="visit_id.direct_stop_sales_total",
        currency_field="currency_id",
        readonly=True,
        store=False,
    )
    direct_stop_returns_total = fields.Monetary(
        related="visit_id.direct_stop_returns_total",
        currency_field="currency_id",
        readonly=True,
        store=False,
    )
    direct_stop_current_net_amount = fields.Monetary(
        related="visit_id.direct_stop_current_net_amount",
        currency_field="currency_id",
        readonly=True,
        store=False,
    )
    direct_stop_grand_due_amount = fields.Monetary(
        related="visit_id.direct_stop_grand_due_amount",
        currency_field="currency_id",
        readonly=True,
        store=False,
    )
    direct_stop_settlement_paid_amount = fields.Monetary(
        related="visit_id.direct_stop_settlement_paid_amount",
        currency_field="currency_id",
        readonly=True,
        store=False,
    )
    direct_stop_settlement_remaining_amount = fields.Monetary(
        related="visit_id.direct_stop_settlement_remaining_amount",
        currency_field="currency_id",
        readonly=True,
        store=False,
    )
    direct_stop_credit_amount = fields.Monetary(
        related="visit_id.direct_stop_credit_amount",
        currency_field="currency_id",
        readonly=True,
        store=False,
    )
    direct_stop_credit_policy = fields.Selection(
        related="visit_id.direct_stop_credit_policy",
        readonly=True,
        store=False,
    )

    sale_status_label = fields.Char(compute="_compute_status_labels", store=False)
    return_status_label = fields.Char(compute="_compute_status_labels", store=False)
    credit_policy_label = fields.Char(compute="_compute_status_labels", store=False)
    finish_message = fields.Html(compute="_compute_finish_message", sanitize=False, store=False)

    @api.depends("visit_id")
    def _compute_is_direct_sales_stop(self):
        for rec in self:
            visit = rec.visit_id
            rec.is_direct_sales_stop = bool(visit and hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop())

    @api.depends("direct_stop_sale_status", "direct_stop_return_status", "direct_stop_credit_policy")
    def _compute_status_labels(self):
        sale_map = {
            "pending": _("Pending"),
            "yes": _("Yes"),
            "no": _("No"),
        }
        return_map = {
            "pending": _("Pending"),
            "yes": _("Yes"),
            "no": _("No"),
        }

        credit_map = {}
        try:
            credit_map = dict(
                self.env["route.visit"].fields_get(["direct_stop_credit_policy"])["direct_stop_credit_policy"].get("selection", [])
            )
        except Exception:
            credit_map = {
                "customer_credit": _("Customer Credit"),
                "cash_refund": _("Cash Refund"),
                "next_stop": _("Carry to Next Stop"),
            }

        for rec in self:
            rec.sale_status_label = sale_map.get(rec.direct_stop_sale_status, "")
            rec.return_status_label = return_map.get(rec.direct_stop_return_status, "")
            rec.credit_policy_label = credit_map.get(rec.direct_stop_credit_policy, "") if rec.direct_stop_credit_policy else _("Not Required")

    @api.depends(
        "is_direct_sales_stop",
        "outlet_id",
        "visit_date",
        "direct_stop_settlement_paid_amount",
        "direct_stop_settlement_remaining_amount",
        "direct_stop_credit_amount",
    )
    def _compute_finish_message(self):
        for rec in self:
            if not rec.is_direct_sales_stop:
                rec.finish_message = _('<div class="alert alert-success mb-0">Visit finished successfully.</div>')
                continue

            if (rec.direct_stop_credit_amount or 0.0) > 0.0:
                extra = _("Customer credit has been captured for this stop.")
            elif (rec.direct_stop_settlement_remaining_amount or 0.0) <= 0.0:
                extra = _("Settlement is complete and the stop is fully closed.")
            else:
                extra = _("The stop has been closed. Please review the saved settlement records if needed.")

            rec.finish_message = _(
                '<div class="alert alert-success mb-0"><strong>Direct sales stop completed.</strong><br/>Outlet: %(outlet)s<br/>Date: %(date)s<br/>%(extra)s</div>'
            ) % {
                "outlet": rec.outlet_id.display_name if rec.outlet_id else "-",
                "date": rec.visit_date or "-",
                "extra": extra,
            }

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

