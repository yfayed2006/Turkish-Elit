import json

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
    current_visit_commission_amount = fields.Monetary(string="Current Visit Commission", currency_field="currency_id", compute="_compute_statement", readonly=True)
    amount_due_now = fields.Monetary(string="Total Outlet Due", currency_field="currency_id", compute="_compute_statement", readonly=True)
    suggested_collection_now = fields.Monetary(string="Suggested Cash Collection Now", currency_field="currency_id", compute="_compute_statement", readonly=True)
    expected_remaining_after_payment = fields.Monetary(string="Expected Remaining After Collection", currency_field="currency_id", compute="_compute_statement", readonly=True)

    previous_confirmed_payment_count = fields.Integer(string="Previous Confirmed Payments", compute="_compute_statement", readonly=True)
    previous_confirmed_payment_amount = fields.Monetary(string="Previous Confirmed Payments Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)
    open_promise_count = fields.Integer(string="Open Promises", compute="_compute_statement", readonly=True)
    open_promise_amount = fields.Monetary(string="Open Promise Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)
    overdue_promise_count = fields.Integer(string="Overdue Promises", compute="_compute_statement", readonly=True)
    overdue_promise_amount = fields.Monetary(string="Overdue Promise Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)

    cheque_pending_clearance_count = fields.Integer(string="Pending Cheques", compute="_compute_statement", readonly=True)
    cheque_pending_clearance_amount = fields.Monetary(string="Pending Cheque Clearance", currency_field="currency_id", compute="_compute_statement", readonly=True)
    cheque_open_due_count = fields.Integer(string="Cheque Open Due Entries", compute="_compute_statement", readonly=True)
    cheque_open_due_amount = fields.Monetary(string="Cheque Open Due", currency_field="currency_id", compute="_compute_statement", readonly=True)
    cheque_financially_cleared_count = fields.Integer(string="Cleared Cheques", compute="_compute_statement", readonly=True)
    cheque_financially_cleared_amount = fields.Monetary(string="Financially Cleared Cheques", currency_field="currency_id", compute="_compute_statement", readonly=True)

    last_payment_date = fields.Datetime(string="Last Payment Date", compute="_compute_statement", readonly=True)
    last_payment_amount = fields.Monetary(string="Last Payment Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)
    next_promise_date = fields.Date(string="Next Promise Date", compute="_compute_statement", readonly=True)
    next_promise_amount = fields.Monetary(string="Next Promise Amount", currency_field="currency_id", compute="_compute_statement", readonly=True)
    can_continue_to_collection = fields.Boolean(string="Can Continue To Collection", compute="_compute_statement", readonly=True)

    return_to_collection = fields.Boolean(string="Return To Collection", readonly=True)
    return_settlement_mode = fields.Selection(
        [
            ("single", "Single Payment"),
            ("split", "Split Payment"),
        ],
        string="Return Payment Structure",
        readonly=True,
    )
    return_collection_type = fields.Selection(
        [
            ("full", "Full Payment"),
            ("partial", "Partial Payment + Carry Forward"),
            ("defer_date", "Defer To Specific Date"),
            ("next_visit", "Carry To Next Visit"),
        ],
        string="Return Collection Scenario",
        readonly=True,
    )
    return_payment_mode = fields.Selection(
        [
            ("cash", "Cash"),
            ("bank", "Bank Transfer"),
            ("pos", "POS"),
            ("cheque", "Cheque"),
            ("deferred", "Deferred"),
        ],
        string="Return Payment Mode",
        readonly=True,
    )
    return_payment_date = fields.Datetime(string="Return Payment Date", readonly=True)
    return_amount = fields.Monetary(string="Return Amount", currency_field="currency_id", readonly=True)
    return_promise_date = fields.Date(string="Return Promise Date", readonly=True)
    return_promise_amount = fields.Monetary(string="Return Promise Amount", currency_field="currency_id", readonly=True)
    return_due_date = fields.Date(string="Return Due Date", readonly=True)
    return_reference = fields.Char(string="Return Reference", readonly=True)
    return_bank_name = fields.Char(string="Return Bank Name", readonly=True)
    return_pos_terminal = fields.Char(string="Return POS Terminal", readonly=True)
    return_cheque_number = fields.Char(string="Return Cheque Number", readonly=True)
    return_cheque_date = fields.Date(string="Return Cheque Date", readonly=True)
    return_cheque_holder_name = fields.Char(string="Return Cheque Holder", readonly=True)
    return_cheque_note = fields.Text(string="Return Cheque Details", readonly=True)
    return_note = fields.Text(string="Return Collection Note", readonly=True)
    return_direct_stop_credit_policy = fields.Selection(
        [
            ("customer_credit", "Customer Credit"),
            ("cash_refund", "Cash Refund"),
            ("next_stop", "Carry To Next Stop"),
        ],
        string="Return Credit Settlement",
        readonly=True,
    )
    return_direct_stop_credit_note = fields.Text(string="Return Credit Settlement Note", readonly=True)
    return_payment_line_payload = fields.Text(string="Return Split Payment Snapshot", readonly=True)

    def _get_statement_reference_date(self, visit):
        self.ensure_one()
        return (visit.date if visit and visit.date else fields.Date.context_today(self))

    def _get_statement_reference_datetime(self, visit):
        self.ensure_one()
        if not visit:
            return fields.Datetime.now()
        if visit.start_datetime:
            return visit.start_datetime
        ref_date = self._get_statement_reference_date(visit)
        return fields.Datetime.to_datetime(f"{ref_date} 23:59:59")

    def _get_statement_promise_status(self, payment, visit):
        self.ensure_one()
        if not payment or (payment.promise_amount or 0.0) <= 0.0 or payment.state != "confirmed":
            return False
        reference_date = self._get_statement_reference_date(visit)
        promise_date = payment.promise_date
        if promise_date and promise_date < reference_date:
            return "overdue"
        if promise_date and promise_date == reference_date:
            return "due_today"
        return "open"

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
        reference_dt = self._get_statement_reference_datetime(visit)
        return payments.filtered(
            lambda p: p.visit_id != visit
            and p.settlement_visit_id != visit
            and (not p.payment_date or p.payment_date <= reference_dt)
        )

    def _get_open_promises(self, visit):
        payments = self._get_previous_confirmed_payments(visit).filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
        if not payments:
            return payments
        return payments.filtered(lambda p: self._get_statement_promise_status(p, visit) in ("open", "due_today", "overdue"))

    @api.model
    def _first_defined_amount(self, *values):
        for value in values:
            if value is not False and value is not None:
                return value
        return 0.0

    def _get_statement_draft_payments(self, visit):
        Payment = self.env["route.visit.payment"]
        if not visit:
            return Payment
        if (
            hasattr(visit, "_is_direct_sales_stop")
            and visit._is_direct_sales_stop()
            and hasattr(visit, "_get_direct_stop_settlement_payments")
        ):
            return visit._get_direct_stop_settlement_payments(states=["draft"])
        return visit.payment_ids.filtered(lambda payment: payment.state == "draft") if visit.payment_ids else Payment

    def _is_statement_collection_closed(self, visit):
        if not visit:
            return True
        return bool(
            visit.state == "done"
            or getattr(visit, "visit_process_state", False) in ("collection_done", "ready_to_close", "done")
        )

    def _get_statement_visit_action(self, visit):
        if visit and hasattr(visit, "_get_pda_form_action"):
            return visit._get_pda_form_action()
        if visit:
            return {
                "type": "ir.actions.act_window",
                "name": _("Visit"),
                "res_model": "route.visit",
                "res_id": visit.id,
                "view_mode": "form",
                "target": "current",
            }
        return {"type": "ir.actions.act_window_close"}

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
            rec.current_visit_commission_amount = 0.0
            rec.amount_due_now = 0.0
            rec.suggested_collection_now = 0.0
            rec.expected_remaining_after_payment = 0.0
            rec.previous_confirmed_payment_count = 0
            rec.previous_confirmed_payment_amount = 0.0
            rec.open_promise_count = 0
            rec.open_promise_amount = 0.0
            rec.overdue_promise_count = 0
            rec.overdue_promise_amount = 0.0
            rec.cheque_pending_clearance_count = 0
            rec.cheque_pending_clearance_amount = 0.0
            rec.cheque_open_due_count = 0
            rec.cheque_open_due_amount = 0.0
            rec.cheque_financially_cleared_count = 0
            rec.cheque_financially_cleared_amount = 0.0
            rec.last_payment_date = False
            rec.last_payment_amount = 0.0
            rec.next_promise_date = False
            rec.next_promise_amount = 0.0
            rec.can_continue_to_collection = False
            if not visit:
                continue

            if rec.is_direct_sales_stop:
                rec.previous_due_amount = visit.direct_stop_previous_due_amount or 0.0
                rec.current_visit_sale_amount = visit.direct_stop_sales_total or 0.0
                rec.current_visit_return_amount = visit.direct_stop_returns_total or 0.0
                rec.net_amount_for_visit = visit.direct_stop_current_net_amount or 0.0
                rec.current_visit_commission_amount = 0.0
                rec.amount_due_now = visit.direct_stop_grand_due_amount or 0.0
                current_immediate_remaining = max(
                    rec._first_defined_amount(
                        visit.direct_stop_immediate_remaining_amount,
                        rec.amount_due_now,
                    ),
                    0.0,
                )
                rec.suggested_collection_now = current_immediate_remaining
                rec.expected_remaining_after_payment = max(
                    current_immediate_remaining - rec.suggested_collection_now,
                    0.0,
                )
            else:
                if hasattr(visit, "_get_consignment_receipt_summary"):
                    summary = visit._get_consignment_receipt_summary()
                    sale_amount = summary.get("visit_sale_amount", 0.0)
                    return_amount = summary.get("returned_value", 0.0)
                    commission_amount = summary.get("commission_amount", getattr(visit, "consignment_commission_amount", 0.0) or 0.0)
                    net_amount = summary.get("current_visit_net", max((sale_amount or 0.0) - (return_amount or 0.0) - (commission_amount or 0.0), 0.0))
                    amount_due_now = summary.get("total_outlet_due", summary.get("current_due", 0.0))
                    balance_after_collection = summary.get("total_outstanding_after_collection", getattr(visit, "remaining_due_amount", 0.0) or 0.0)
                    previous_due = summary.get("previous_due", max((amount_due_now or 0.0) - max(net_amount, 0.0), 0.0))
                else:
                    sale_amount = sum((line.sold_amount or 0.0) for line in visit.line_ids) if visit.line_ids else (visit.net_due_amount or 0.0)
                    return_amount = sum((line.return_amount or 0.0) for line in visit.line_ids) if visit.line_ids else 0.0
                    commission_amount = getattr(visit, "consignment_commission_amount", 0.0) or 0.0
                    net_amount = max((sale_amount or 0.0) - (return_amount or 0.0) - (commission_amount or 0.0), 0.0)
                    amount_due_now = visit.outlet_current_due_amount or 0.0
                    balance_after_collection = max(getattr(visit, "remaining_due_amount", 0.0) or 0.0, amount_due_now)
                    previous_due = max((amount_due_now or 0.0) - max(net_amount, 0.0), 0.0)

                rec.current_visit_sale_amount = sale_amount
                rec.current_visit_return_amount = return_amount
                rec.net_amount_for_visit = net_amount
                rec.current_visit_commission_amount = commission_amount
                rec.amount_due_now = amount_due_now
                current_immediate_remaining = max(
                    rec._first_defined_amount(
                        getattr(visit, "remaining_due_amount", False),
                        rec.amount_due_now,
                    ),
                    0.0,
                )
                rec.suggested_collection_now = current_immediate_remaining if getattr(visit, "ux_can_collect_payment", False) else 0.0
                rec.previous_due_amount = previous_due
                rec.expected_remaining_after_payment = (
                    max((rec.amount_due_now or 0.0) - (rec.suggested_collection_now or 0.0), 0.0)
                    if getattr(visit, "ux_can_collect_payment", False)
                    else max(balance_after_collection or 0.0, 0.0)
                )

            previous_confirmed = rec._get_previous_confirmed_payments(visit)
            open_promises = rec._get_open_promises(visit)
            overdue_promises = open_promises.filtered(lambda p: rec._get_statement_promise_status(p, visit) == "overdue")

            rec.previous_confirmed_payment_count = len(previous_confirmed)
            rec.previous_confirmed_payment_amount = sum(previous_confirmed.mapped("amount")) if previous_confirmed else 0.0
            rec.open_promise_count = len(open_promises)
            rec.open_promise_amount = sum((p.promise_amount or 0.0) for p in open_promises) if open_promises else 0.0
            rec.overdue_promise_count = len(overdue_promises)
            rec.overdue_promise_amount = sum((p.promise_amount or 0.0) for p in overdue_promises) if overdue_promises else 0.0

            cheque_payments = previous_confirmed.filtered(lambda p: p.payment_mode == "cheque")
            pending_cheques = cheque_payments.filtered(
                lambda p: (p._get_route_pending_clearance_amount() if hasattr(p, "_get_route_pending_clearance_amount") else (p.amount or 0.0 if (p.cheque_followup_state or "received") in ("received", "deposited") else 0.0)) > 0.0
            )
            open_due_cheques = cheque_payments.filtered(
                lambda p: (p._get_route_open_due_from_cheque_amount() if hasattr(p, "_get_route_open_due_from_cheque_amount") else (p.amount or 0.0 if (p.cheque_followup_state or "received") in ("bounced", "cancelled") else 0.0)) > 0.0
            )
            cleared_cheques = cheque_payments.filtered(
                lambda p: (p._get_route_accounting_cleared_amount() if hasattr(p, "_get_route_accounting_cleared_amount") else (p.amount or 0.0 if (p.cheque_followup_state or "received") == "cleared" else 0.0)) > 0.0
            )
            rec.cheque_pending_clearance_count = len(pending_cheques)
            rec.cheque_pending_clearance_amount = sum(
                p._get_route_pending_clearance_amount() if hasattr(p, "_get_route_pending_clearance_amount") else (p.amount or 0.0)
                for p in pending_cheques
            ) if pending_cheques else 0.0
            rec.cheque_open_due_count = len(open_due_cheques)
            rec.cheque_open_due_amount = sum(
                p._get_route_open_due_from_cheque_amount() if hasattr(p, "_get_route_open_due_from_cheque_amount") else (p.amount or 0.0)
                for p in open_due_cheques
            ) if open_due_cheques else 0.0
            rec.cheque_financially_cleared_count = len(cleared_cheques)
            rec.cheque_financially_cleared_amount = sum(
                p._get_route_accounting_cleared_amount() if hasattr(p, "_get_route_accounting_cleared_amount") else (p.amount or 0.0)
                for p in cleared_cheques
            ) if cleared_cheques else 0.0

            last_payment = previous_confirmed[:1] if previous_confirmed else Payment
            reference_date = rec._get_statement_reference_date(visit)
            candidate_promises = open_promises.filtered(lambda p: p.promise_date and p.promise_date >= reference_date)
            next_promise = candidate_promises.sorted(lambda p: p.promise_date)[:1] if candidate_promises else Payment

            rec.last_payment_date = last_payment.payment_date if last_payment else False
            rec.last_payment_amount = last_payment.amount if last_payment else 0.0
            rec.next_promise_date = next_promise.promise_date if next_promise else False
            rec.next_promise_amount = next_promise.promise_amount if next_promise else 0.0
            draft_payments = rec._get_statement_draft_payments(visit)
            rec.can_continue_to_collection = bool(
                getattr(visit, "ux_can_collect_payment", False)
                and not draft_payments
                and not rec._is_statement_collection_closed(visit)
            )

    def action_print_statement_pdf(self):
        self.ensure_one()
        return self.env.ref("route_core.action_report_route_visit_statement_of_account").report_action(self)

    def _get_restore_collection_context(self):
        self.ensure_one()
        context = {"default_visit_id": self.visit_id.id}
        if not self.return_to_collection:
            return context

        restored_values = {
            "settlement_mode": self.return_settlement_mode or "single",
            "collection_type": self.return_collection_type or "full",
            "payment_mode": self.return_payment_mode or "cash",
            "payment_date": fields.Datetime.to_string(self.return_payment_date) if self.return_payment_date else False,
            "amount": self.return_amount or 0.0,
            "promise_date": fields.Date.to_string(self.return_promise_date) if self.return_promise_date else False,
            "promise_amount": self.return_promise_amount or 0.0,
            "due_date": fields.Date.to_string(self.return_due_date) if self.return_due_date else False,
            "reference": self.return_reference or False,
            "bank_name": self.return_bank_name or False,
            "pos_terminal": self.return_pos_terminal or False,
            "cheque_number": self.return_cheque_number or False,
            "cheque_date": fields.Date.to_string(self.return_cheque_date) if self.return_cheque_date else False,
            "cheque_holder_name": self.return_cheque_holder_name or False,
            "cheque_note": self.return_cheque_note or False,
            "note": self.return_note or False,
            "direct_stop_credit_policy": self.return_direct_stop_credit_policy or False,
            "direct_stop_credit_note": self.return_direct_stop_credit_note or False,
        }
        context.update({f"default_{field_name}": value for field_name, value in restored_values.items()})

        if self.return_payment_line_payload:
            try:
                payment_lines = json.loads(self.return_payment_line_payload)
            except Exception:
                payment_lines = []
            if payment_lines:
                context["default_payment_line_ids"] = [(0, 0, line) for line in payment_lines]

        return context

    def _get_collect_payment_action(self, visit):
        self.ensure_one()
        view = self.env.ref("route_core.view_route_visit_collect_payment_wizard_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Collect Payment"),
            "res_model": "route.visit.collect.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": self._get_restore_collection_context(),
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_continue_to_collection(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit:
            raise UserError(_("Visit is required."))

        # Do not open a new Collect Payment wizard when the visit already has
        # draft settlement entries, or when collection is already closed.
        # In those cases we return to the visit so the salesperson can confirm
        # payments, finish the visit, or just review the closed settlement.
        if self._get_statement_draft_payments(visit):
            return self._get_statement_visit_action(visit)

        if self._is_statement_collection_closed(visit):
            return self._get_statement_visit_action(visit)

        if getattr(visit, "ux_can_confirm_payments", False):
            return self._get_statement_visit_action(visit)

        if not getattr(visit, "ux_can_collect_payment", False):
            return self._get_statement_visit_action(visit)

        return self._get_collect_payment_action(visit)
