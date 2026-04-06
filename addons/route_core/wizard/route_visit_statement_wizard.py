from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisitStatementWizard(models.TransientModel):
    _name = "route.visit.statement.wizard"
    _description = "Route Visit Mini Statement Of Account"

    visit_id = fields.Many2one("route.visit", string="Visit", required=True, readonly=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True, readonly=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)

    is_direct_sales_stop = fields.Boolean(string="Direct Sales Stop", compute="_compute_statement", readonly=True)
    outlet_id = fields.Many2one("route.outlet", string="Outlet", compute="_compute_statement", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Customer", compute="_compute_statement", readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", compute="_compute_statement", readonly=True)
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle", compute="_compute_statement", readonly=True)
    visit_date = fields.Date(string="Visit Date", compute="_compute_statement", readonly=True)

    previous_due_amount = fields.Monetary(string="Previous Due", currency_field="currency_id", compute="_compute_statement", readonly=True)
    current_visit_sale_amount = fields.Monetary(string="Current Visit Sale", currency_field="currency_id", compute="_compute_statement", readonly=True)
    current_visit_return_amount = fields.Monetary(string="Current Visit Returns", currency_field="currency_id", compute="_compute_statement", readonly=True)
    net_amount_for_visit = fields.Monetary(string="Net Amount For This Visit", currency_field="currency_id", compute="_compute_statement", readonly=True)
    amount_due_now = fields.Monetary(string="Amount Due Now", currency_field="currency_id", compute="_compute_statement", readonly=True)
    suggested_collection_now = fields.Monetary(string="Suggested Collection Now", currency_field="currency_id", compute="_compute_statement", readonly=True)
    expected_remaining_after_payment = fields.Monetary(string="Expected Remaining After Payment", currency_field="currency_id", compute="_compute_statement", readonly=True)

    previous_confirmed_payment_count = fields.Integer(string="Previous Confirmed Payments", compute="_compute_statement", readonly=True)
    previous_confirmed_payment_amount = fields.Monetary(string="Previous Confirmed Payments Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)
    open_promise_count = fields.Integer(string="Open Promises", compute="_compute_statement", readonly=True)
    open_promise_amount = fields.Monetary(string="Open Promise Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)
    overdue_promise_count = fields.Integer(string="Overdue Promises", compute="_compute_statement", readonly=True)
    overdue_promise_amount = fields.Monetary(string="Overdue Promise Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)

    last_payment_date = fields.Datetime(string="Last Payment Date", compute="_compute_statement", readonly=True)
    last_payment_amount = fields.Monetary(string="Last Payment Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)
    next_promise_date = fields.Date(string="Next Promise Date", compute="_compute_statement", readonly=True)
    next_promise_amount = fields.Monetary(string="Next Promise Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)

    def _get_outlet_confirmed_payments(self, visit):
        Payment = self.env["route.visit.payment"]
        if not visit or not visit.outlet_id:
            return Payment
        return Payment.search([
            ("outlet_id", "=", visit.outlet_id.id),
            ("state", "=", "confirmed"),
        ], order="payment_date desc, id desc")

    def _get_previous_confirmed_payments(self, visit):
        payments = self._get_outlet_confirmed_payments(visit)
        if not visit:
            return payments
        return payments.filtered(lambda p: p.visit_id != visit and p.settlement_visit_id != visit)

    def _get_open_promises(self, visit):
        payments = self._get_outlet_confirmed_payments(visit).filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
        if not payments:
            return payments

        def _status(payment):
            if hasattr(payment, "_get_snapshot_promise_status"):
                return payment._get_snapshot_promise_status()
            return payment.promise_status

        return payments.filtered(lambda p: _status(p) in ("open", "due_today", "overdue"))

    @api.depends("visit_id")
    def _compute_statement(self):
        Payment = self.env["route.visit.payment"]
        for rec in self:
            visit = rec.visit_id
            rec.is_direct_sales_stop = bool(visit and hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop())
            rec.outlet_id = visit.outlet_id if visit else False
            rec.partner_id = visit.partner_id if visit else False
            rec.user_id = visit.user_id if visit else False
            rec.vehicle_id = visit.vehicle_id if visit else False
            rec.visit_date = visit.date if visit else False

            rec.previous_due_amount = 0.0
            rec.current_visit_sale_amount = 0.0
            rec.current_visit_return_amount = 0.0
            rec.net_amount_for_visit = 0.0
            rec.amount_due_now = 0.0
            rec.suggested_collection_now = 0.0
            rec.expected_remaining_after_payment = 0.0
            rec.previous_confirmed_payment_count = 0
            rec.previous_confirmed_payment_amount = 0.0
            rec.open_promise_count = 0
            rec.open_promise_amount = 0.0
            rec.overdue_promise_count = 0
            rec.overdue_promise_amount = 0.0
            rec.last_payment_date = False
            rec.last_payment_amount = 0.0
            rec.next_promise_date = False
            rec.next_promise_amount = 0.0
            if not visit:
                continue

            if rec.is_direct_sales_stop:
                rec.previous_due_amount = visit.direct_stop_previous_due_amount or 0.0
                rec.current_visit_sale_amount = visit.direct_stop_sales_total or 0.0
                rec.current_visit_return_amount = visit.direct_stop_returns_total or 0.0
                rec.net_amount_for_visit = visit.direct_stop_current_net_amount or 0.0
                rec.amount_due_now = visit.direct_stop_grand_due_amount or 0.0
                rec.suggested_collection_now = visit.direct_stop_settlement_remaining_amount or rec.net_amount_for_visit or 0.0
                rec.expected_remaining_after_payment = max((rec.amount_due_now or 0.0) - (rec.suggested_collection_now or 0.0), 0.0)
            else:
                sale_amount = sum((line.sold_amount or 0.0) for line in visit.line_ids) if visit.line_ids else (visit.net_due_amount or 0.0)
                return_amount = sum((line.return_amount or 0.0) for line in visit.line_ids) if visit.line_ids else 0.0
                net_amount = sale_amount - return_amount
                rec.current_visit_sale_amount = sale_amount
                rec.current_visit_return_amount = return_amount
                rec.net_amount_for_visit = net_amount
                rec.amount_due_now = visit.outlet_current_due_amount or 0.0
                rec.suggested_collection_now = visit.remaining_due_amount or visit.net_due_amount or max(net_amount, 0.0)
                rec.previous_due_amount = max((rec.amount_due_now or 0.0) - max(net_amount, 0.0), 0.0)
                rec.expected_remaining_after_payment = max((rec.amount_due_now or 0.0) - (rec.suggested_collection_now or 0.0), 0.0)

            previous_confirmed = rec._get_previous_confirmed_payments(visit)
            open_promises = rec._get_open_promises(visit)
            overdue_promises = open_promises.filtered(lambda p: (p._get_snapshot_promise_status() if hasattr(p, "_get_snapshot_promise_status") else p.promise_status) == "overdue")

            rec.previous_confirmed_payment_count = len(previous_confirmed)
            rec.previous_confirmed_payment_amount = sum(previous_confirmed.mapped("amount")) if previous_confirmed else 0.0
            rec.open_promise_count = len(open_promises)
            rec.open_promise_amount = sum((p.promise_amount or 0.0) for p in open_promises) if open_promises else 0.0
            rec.overdue_promise_count = len(overdue_promises)
            rec.overdue_promise_amount = sum((p.promise_amount or 0.0) for p in overdue_promises) if overdue_promises else 0.0

            last_payment = previous_confirmed[:1] if previous_confirmed else Payment
            next_promise = open_promises.sorted(lambda p: p.promise_date or fields.Date.to_date("2099-12-31"))[:1] if open_promises else Payment

            rec.last_payment_date = last_payment.payment_date if last_payment else False
            rec.last_payment_amount = last_payment.amount if last_payment else 0.0
            rec.next_promise_date = next_promise.promise_date if next_promise else False
            rec.next_promise_amount = next_promise.promise_amount if next_promise else 0.0

    def action_print_statement_pdf(self):
        self.ensure_one()
        return self.env.ref("route_core.action_report_route_visit_statement_of_account").report_action(self)

    def action_continue_to_collection(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit:
            raise UserError(_("Visit is required."))
        if hasattr(visit, "action_ux_collect_payment"):
            return visit.action_ux_collect_payment()
        return {"type": "ir.actions.act_window_close"}
