from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteVisitPaymentChequeFollowup(models.Model):
    _inherit = "route.visit.payment"

    cheque_followup_state = fields.Selection(
        [
            ("received", "Received"),
            ("deposited", "Deposited"),
            ("cleared", "Cleared"),
            ("bounced", "Bounced"),
            ("cancelled", "Cancelled"),
        ],
        string="Cheque Status",
        default=False,
        index=True,
        copy=False,
    )
    cheque_followup_state_label = fields.Char(
        string="Cheque Status Label",
        compute="_compute_cheque_followup_labels",
        store=False,
    )
    cheque_followup_due_label = fields.Char(
        string="Cheque Due Status",
        compute="_compute_cheque_followup_labels",
        store=False,
    )
    cheque_deposited_at = fields.Datetime(string="Deposited At", copy=False)
    cheque_cleared_at = fields.Datetime(string="Cleared At", copy=False)
    cheque_bounced_at = fields.Datetime(string="Bounced At", copy=False)
    cheque_cancelled_at = fields.Datetime(string="Cheque Cancelled At", copy=False)
    cheque_followup_updated_at = fields.Datetime(string="Cheque Last Update", copy=False)
    cheque_followup_updated_by_id = fields.Many2one(
        "res.users",
        string="Cheque Updated By",
        readonly=True,
        copy=False,
    )
    cheque_followup_note = fields.Text(string="Cheque Follow-up Note", copy=False)

    cheque_financial_state = fields.Selection(
        [
            ("pending", "Pending Clearance"),
            ("cleared", "Financially Cleared"),
            ("open_due", "Open Due"),
            ("cancelled", "Cancelled"),
        ],
        string="Financial Effect",
        compute="_compute_cheque_financial_policy",
        store=True,
        index=True,
        copy=False,
    )
    cheque_financial_state_label = fields.Char(
        string="Financial Effect Label",
        compute="_compute_cheque_financial_policy",
        store=False,
    )
    cheque_effective_collected_amount = fields.Monetary(
        string="Effective Collected",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
    )
    cheque_route_coverage_amount = fields.Monetary(
        string="Route Coverage",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
        help="Amount that still covers the route/customer balance before final bank clearance. Bounced or cancelled cheques do not cover the balance.",
    )
    cheque_pending_clearance_amount = fields.Monetary(
        string="Pending Bank Clearance",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
        help="Confirmed cheque amount waiting for bank deposit/clearance.",
    )
    cheque_financially_cleared_amount = fields.Monetary(
        string="Financially Cleared Amount",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
        help="Cheque amount that is finally cleared by the bank and can be treated as cash/bank collected for accounting integration.",
    )
    cheque_open_due_amount = fields.Monetary(
        string="Cheque Open Due",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
    )
    cheque_is_financially_cleared = fields.Boolean(
        string="Financially Cleared",
        compute="_compute_cheque_financial_policy",
        store=False,
    )
    cheque_needs_followup = fields.Boolean(
        string="Needs Follow-up",
        compute="_compute_cheque_financial_policy",
        store=True,
        index=True,
    )

    @api.depends("payment_mode", "state", "amount", "cheque_followup_state")
    def _compute_cheque_financial_policy(self):
        for rec in self:
            rec.cheque_financial_state = False
            rec.cheque_financial_state_label = False
            rec.cheque_effective_collected_amount = 0.0
            rec.cheque_route_coverage_amount = 0.0
            rec.cheque_pending_clearance_amount = 0.0
            rec.cheque_financially_cleared_amount = 0.0
            rec.cheque_open_due_amount = 0.0
            rec.cheque_is_financially_cleared = False
            rec.cheque_needs_followup = False

            if rec.payment_mode != "cheque":
                continue

            followup_state = rec.cheque_followup_state or "received"
            amount = rec.amount or 0.0

            if rec.state != "confirmed":
                rec.cheque_financial_state = "pending"
                rec.cheque_financial_state_label = _("Pending Confirmation")
                continue

            if followup_state == "cleared":
                rec.cheque_financial_state = "cleared"
                rec.cheque_financial_state_label = _("Financially Cleared")
                rec.cheque_effective_collected_amount = amount
                rec.cheque_route_coverage_amount = amount
                rec.cheque_financially_cleared_amount = amount
                rec.cheque_is_financially_cleared = True
            elif followup_state == "bounced":
                rec.cheque_financial_state = "open_due"
                rec.cheque_financial_state_label = _("Bounced - Open Due")
                rec.cheque_open_due_amount = amount
                rec.cheque_needs_followup = True
            elif followup_state == "cancelled":
                rec.cheque_financial_state = "cancelled"
                rec.cheque_financial_state_label = _("Cancelled - No Collection")
                rec.cheque_open_due_amount = amount
                rec.cheque_needs_followup = True
            else:
                rec.cheque_financial_state = "pending"
                rec.cheque_financial_state_label = _("Pending Bank Clearance")
                rec.cheque_effective_collected_amount = amount
                rec.cheque_route_coverage_amount = amount
                rec.cheque_pending_clearance_amount = amount

    def _get_route_collection_covered_amount(self):
        """Operational amount that currently covers the outlet balance.

        A received/deposited cheque may close the field visit, but it remains
        pending for bank/accounting clearance. If the cheque later bounces or
        is cancelled, it no longer covers the balance and becomes open due.
        """
        self.ensure_one()
        if self.state != "confirmed":
            return 0.0
        if self.payment_mode == "cheque":
            if (self.cheque_followup_state or "received") in ("bounced", "cancelled"):
                return 0.0
            return self.cheque_route_coverage_amount or self.amount or 0.0
        return self.amount or 0.0

    def _get_route_accounting_cleared_amount(self):
        """Amount that is final for accounting/bank collection purposes."""
        self.ensure_one()
        if self.state != "confirmed":
            return 0.0
        if self.payment_mode == "cheque":
            return self.cheque_financially_cleared_amount or 0.0
        if self.payment_mode == "deferred":
            return 0.0
        return self.amount or 0.0

    def _get_route_pending_clearance_amount(self):
        self.ensure_one()
        if self.state != "confirmed" or self.payment_mode != "cheque":
            return 0.0
        return self.cheque_pending_clearance_amount or 0.0

    def _get_route_open_due_from_cheque_amount(self):
        self.ensure_one()
        if self.state != "confirmed" or self.payment_mode != "cheque":
            return 0.0
        return self.cheque_open_due_amount or 0.0

    def _get_route_financial_collected_amount(self):
        # Kept as the existing operational collection source used by visit
        # settlement screens. Use _get_route_accounting_cleared_amount() for
        # the future accounting/journal integration.
        return self._get_route_collection_covered_amount()

    def _get_route_financial_resolved_amount(self):
        self.ensure_one()
        if self.state != "confirmed":
            return 0.0
        resolved_amount = self._get_route_financial_collected_amount()
        if (self.promise_amount or 0.0) > 0.0:
            resolved_amount += self.promise_amount or 0.0
        return resolved_amount

    def _get_target_total_amount(self):
        self.ensure_one()
        if self.source_type == "direct_sale":
            return self.sale_order_id.amount_total or 0.0
        if self.visit_id and getattr(self.visit_id, "visit_execution_mode", False) == "direct_sales":
            return getattr(self.visit_id, "direct_stop_grand_due_amount", 0.0) or getattr(self.visit_id, "net_due_amount", 0.0) or 0.0
        if self.visit_id:
            return self.visit_id.net_due_amount or 0.0
        return 0.0

    def _get_target_remaining_due(self, exclude_self=False):
        self.ensure_one()
        total_amount = self._get_target_total_amount()
        confirmed_payments = self._get_confirmed_target_payments(exclude_self=exclude_self)
        resolved_amount = 0.0
        for payment in confirmed_payments:
            if hasattr(payment, "_get_route_financial_resolved_amount"):
                resolved_amount += payment._get_route_financial_resolved_amount()
            else:
                resolved_amount += payment.amount or 0.0
                if (payment.promise_amount or 0.0) > 0.0:
                    resolved_amount += payment.promise_amount or 0.0
        return max((total_amount or 0.0) - (resolved_amount or 0.0), 0.0)

    @api.depends(
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.promise_amount",
        "visit_id.payment_ids.state",
        "visit_id.payment_ids.payment_mode",
        "visit_id.payment_ids.cheque_followup_state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.promise_amount",
        "sale_order_id.direct_sale_payment_ids.state",
        "sale_order_id.direct_sale_payment_ids.payment_mode",
        "sale_order_id.direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_visit_remaining_due(self):
        for rec in self:
            rec.visit_remaining_due = rec._get_target_remaining_due() if rec._get_target_model() else 0.0

    @api.depends(
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.promise_amount",
        "visit_id.payment_ids.state",
        "visit_id.payment_ids.payment_mode",
        "visit_id.payment_ids.cheque_followup_state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.promise_amount",
        "sale_order_id.direct_sale_payment_ids.state",
        "sale_order_id.direct_sale_payment_ids.payment_mode",
        "sale_order_id.direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_remaining_due_amount(self):
        for rec in self:
            rec.remaining_due_amount = rec._get_target_remaining_due() if rec._get_target_model() else 0.0

    @api.depends(
        "state",
        "collection_type",
        "amount",
        "promise_amount",
        "promise_date",
        "due_date",
        "payment_mode",
        "cheque_followup_state",
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.promise_amount",
        "visit_id.payment_ids.state",
        "visit_id.payment_ids.payment_mode",
        "visit_id.payment_ids.cheque_followup_state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.promise_amount",
        "sale_order_id.direct_sale_payment_ids.state",
        "sale_order_id.direct_sale_payment_ids.payment_mode",
        "sale_order_id.direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_collection_filter_buckets(self):
        today = fields.Date.context_today(self)
        for rec in self:
            remaining_due = rec._get_target_remaining_due() if rec._get_target_model() else 0.0
            if rec.payment_mode == "cheque" and rec.state == "confirmed" and (rec.cheque_followup_state or "received") in ("bounced", "cancelled"):
                remaining_due = max(remaining_due, rec.amount or 0.0)

            rec.collection_due_bucket = "remaining_due" if (remaining_due or 0.0) > 0.0001 else "fully_collected"

            if rec.state != "confirmed" or (rec.promise_amount or 0.0) <= 0.0:
                rec.collection_promise_bucket = "no_promise"
            elif remaining_due <= 0.0001 and not rec._is_direct_stop_settlement_payment():
                rec.collection_promise_bucket = "closed"
            elif rec.promise_date and rec.promise_date < today:
                rec.collection_promise_bucket = "overdue"
            elif rec.promise_date and rec.promise_date == today:
                rec.collection_promise_bucket = "due_today"
            else:
                rec.collection_promise_bucket = "open"

    @api.depends(
        "promise_amount",
        "promise_date",
        "state",
        "payment_mode",
        "cheque_followup_state",
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.promise_amount",
        "visit_id.payment_ids.state",
        "visit_id.payment_ids.payment_mode",
        "visit_id.payment_ids.cheque_followup_state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.promise_amount",
        "sale_order_id.direct_sale_payment_ids.state",
        "sale_order_id.direct_sale_payment_ids.payment_mode",
        "sale_order_id.direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_promise_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == "cancelled" or (rec.promise_amount or 0.0) <= 0:
                rec.promise_status = False
                continue

            if rec._is_direct_stop_settlement_payment():
                if rec.promise_date and rec.promise_date < today:
                    rec.promise_status = "overdue"
                elif rec.promise_date and rec.promise_date == today:
                    rec.promise_status = "due_today"
                else:
                    rec.promise_status = "open"
                continue

            remaining_due = rec._get_target_remaining_due()
            if remaining_due <= 0:
                rec.promise_status = "closed"
            elif rec.promise_date and rec.promise_date < today:
                rec.promise_status = "overdue"
            elif rec.promise_date and rec.promise_date == today:
                rec.promise_status = "due_today"
            else:
                rec.promise_status = "open"

    @api.model
    def init(self):
        """Backfill existing cheque payments after the feature is installed."""
        try:
            self.env.cr.execute(
                """
                UPDATE route_visit_payment
                   SET cheque_followup_state = 'received'
                 WHERE payment_mode = 'cheque'
                   AND (cheque_followup_state IS NULL OR cheque_followup_state = '')
                """
            )
        except Exception:
            # Keep module upgrade safe even if the column is not ready in an unusual registry phase.
            pass

    @api.depends("payment_mode", "cheque_followup_state", "cheque_date")
    def _compute_cheque_followup_labels(self):
        today = fields.Date.context_today(self)
        state_labels = dict(self._fields["cheque_followup_state"].selection)
        for rec in self:
            if rec.payment_mode != "cheque":
                rec.cheque_followup_state_label = False
                rec.cheque_followup_due_label = False
                continue

            state = rec.cheque_followup_state or "received"
            rec.cheque_followup_state_label = state_labels.get(state, state)

            if state == "cleared":
                rec.cheque_followup_due_label = _("Cleared")
            elif state == "bounced":
                rec.cheque_followup_due_label = _("Bounced")
            elif state == "cancelled":
                rec.cheque_followup_due_label = _("Cancelled")
            elif not rec.cheque_date:
                rec.cheque_followup_due_label = _("No Cheque Date")
            elif rec.cheque_date < today:
                rec.cheque_followup_due_label = _("Overdue")
            elif rec.cheque_date == today:
                rec.cheque_followup_due_label = _("Due Today")
            else:
                rec.cheque_followup_due_label = _("Upcoming")

    def _ensure_cheque_followup_payment(self):
        for rec in self:
            if rec.payment_mode != "cheque":
                raise ValidationError(_("Cheque follow-up actions are available only for cheque payments."))
            if rec.state != "confirmed":
                raise ValidationError(_("Confirm the cheque payment before using cheque follow-up actions."))

    def _cheque_followup_reload_action(self):
        """Reload the current Odoo view after a status button updates the cheque.

        Cheque follow-up buttons are used from both the kanban/list controller and
        the form view. Returning a client reload keeps the user on the same screen
        while forcing the statusbar, visible buttons, search panel counters, and
        kanban badges to refresh immediately without a manual browser refresh.
        """
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def _validate_cheque_followup_transition(self, target_state):
        allowed_transitions = {
            "deposited": (False, "received"),
            "cleared": (False, "received", "deposited"),
            "bounced": (False, "received", "deposited"),
            "cancelled": (False, "received", "deposited", "bounced"),
        }
        for rec in self:
            current_state = rec.cheque_followup_state or "received"
            if current_state == target_state:
                continue
            if target_state in ("bounced", "cancelled") and current_state == "cleared":
                raise ValidationError(
                    _("This cheque is already financially cleared. Reset it to Received first if the cleared status was entered by mistake.")
                )
            if target_state in allowed_transitions and rec.cheque_followup_state not in allowed_transitions[target_state]:
                raise ValidationError(
                    _("Cheque status cannot be changed from %(current)s to %(target)s directly. Use Reset to Received first if this status was entered by mistake.")
                    % {
                        "current": dict(rec._fields["cheque_followup_state"].selection).get(current_state, current_state),
                        "target": dict(rec._fields["cheque_followup_state"].selection).get(target_state, target_state),
                    }
                )

    def _get_cheque_followup_batch_domain(self):
        self.ensure_one()
        if not (self.cheque_number and self.bank_name and self.cheque_date):
            return [("id", "=", self.id)]

        domain = [
            ("payment_mode", "=", "cheque"),
            ("state", "=", "confirmed"),
            ("company_id", "=", self.company_id.id),
            ("cheque_number", "=", self.cheque_number),
            ("bank_name", "=", self.bank_name),
            ("cheque_date", "=", self.cheque_date),
        ]

        if self.settlement_visit_id:
            domain.append(("settlement_visit_id", "=", self.settlement_visit_id.id))
        elif self.visit_id:
            domain.extend(
                [
                    ("settlement_visit_id", "=", False),
                    ("visit_id", "=", self.visit_id.id),
                ]
            )
        elif self.sale_order_id:
            domain.extend(
                [
                    ("settlement_visit_id", "=", False),
                    ("sale_order_id", "=", self.sale_order_id.id),
                ]
            )
        else:
            domain.append(("id", "=", self.id))
        return domain

    def _get_cheque_followup_batch_records(self):
        batch_records = self.browse()
        for rec in self:
            rec._ensure_cheque_followup_payment()
            batch_records |= self.search(rec._get_cheque_followup_batch_domain())
        return batch_records

    def _write_cheque_followup_state(self, state, date_field=None):
        batch_records = self._get_cheque_followup_batch_records()
        batch_records._ensure_cheque_followup_payment()
        batch_records._validate_cheque_followup_transition(state)
        now = fields.Datetime.now()
        values = {
            "cheque_followup_state": state,
            "cheque_followup_updated_at": now,
            "cheque_followup_updated_by_id": self.env.user.id,
        }
        if date_field:
            values[date_field] = now
        batch_records.write(values)
        return self._cheque_followup_reload_action()

    def action_cheque_mark_deposited(self):
        return self._write_cheque_followup_state("deposited", "cheque_deposited_at")

    def action_cheque_mark_cleared(self):
        return self._write_cheque_followup_state("cleared", "cheque_cleared_at")

    def action_cheque_mark_bounced(self):
        return self._write_cheque_followup_state("bounced", "cheque_bounced_at")

    def action_cheque_mark_cancelled(self):
        return self._write_cheque_followup_state("cancelled", "cheque_cancelled_at")

    def action_cheque_reset_received(self):
        batch_records = self._get_cheque_followup_batch_records()
        batch_records.write(
            {
                "cheque_followup_state": "received",
                "cheque_followup_updated_at": fields.Datetime.now(),
                "cheque_followup_updated_by_id": self.env.user.id,
                "cheque_deposited_at": False,
                "cheque_cleared_at": False,
                "cheque_bounced_at": False,
                "cheque_cancelled_at": False,
            }
        )
        return self._cheque_followup_reload_action()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("payment_mode") == "cheque" and not vals.get("cheque_followup_state"):
                vals["cheque_followup_state"] = "received"
            elif vals.get("payment_mode") and vals.get("payment_mode") != "cheque":
                vals["cheque_followup_state"] = False
        records = super().create(vals_list)
        records.filtered(lambda rec: rec.payment_mode == "cheque" and not rec.cheque_followup_state).with_context(
            bypass_cheque_followup_post_create=True
        ).write({"cheque_followup_state": "received"})
        return records

    def write(self, vals):
        values = dict(vals)
        if values.get("payment_mode") == "cheque" and not values.get("cheque_followup_state"):
            values["cheque_followup_state"] = "received"
        elif values.get("payment_mode") and values.get("payment_mode") != "cheque":
            values.update(
                {
                    "cheque_followup_state": False,
                    "cheque_deposited_at": False,
                    "cheque_cleared_at": False,
                    "cheque_bounced_at": False,
                    "cheque_cancelled_at": False,
                    "cheque_followup_note": False,
                }
            )
        return super().write(values)


class RouteVisitChequeFinancialPolicy(models.Model):
    _inherit = "route.visit"

    def _route_sum_financial_collected_amount(self, payments):
        total = 0.0
        for payment in payments:
            if hasattr(payment, "_get_route_financial_collected_amount"):
                total += payment._get_route_financial_collected_amount()
            elif payment.state == "confirmed":
                total += payment.amount or 0.0
        return total

    def _route_sum_financial_resolved_amount(self, payments):
        total = 0.0
        for payment in payments:
            if hasattr(payment, "_get_route_financial_resolved_amount"):
                total += payment._get_route_financial_resolved_amount()
            elif payment.state == "confirmed":
                total += payment.amount or 0.0
                if (payment.promise_amount or 0.0) > 0.0:
                    total += payment.promise_amount or 0.0
        return total

    def _get_direct_stop_settlement_cash_amount(self, states=None):
        self.ensure_one()
        payments = self._get_direct_stop_settlement_payments(states=states)
        return self._route_sum_financial_collected_amount(payments) if payments else 0.0

    def _get_direct_stop_settlement_resolved_amount(self, states=None):
        self.ensure_one()
        payments = self._get_direct_stop_settlement_payments(states=states)
        return self._route_sum_financial_resolved_amount(payments) if payments else 0.0

    @api.depends(
        "visit_execution_mode",
        "direct_stop_skip_sale",
        "direct_stop_skip_return",
        "direct_stop_credit_policy",
        "name",
        "direct_stop_return_ids.state",
        "direct_stop_return_ids.amount_total",
        "payment_ids.state",
        "payment_ids.amount",
        "payment_ids.promise_amount",
        "payment_ids.payment_mode",
        "payment_ids.cheque_followup_state",
        "settlement_payment_ids.state",
        "settlement_payment_ids.amount",
        "settlement_payment_ids.promise_amount",
        "settlement_payment_ids.payment_mode",
        "settlement_payment_ids.cheque_followup_state",
    )
    def _compute_direct_stop_summary(self):
        for rec in self:
            orders = rec.direct_stop_order_ids.filtered(lambda o: o.state not in ("cancel",)) if rec.direct_stop_order_ids else rec.direct_stop_order_ids
            if rec.id and hasattr(rec, "_get_direct_stop_active_returns"):
                active_returns = rec._get_direct_stop_active_returns()
            elif rec.id and hasattr(rec, "_get_direct_stop_returns"):
                active_returns = rec._get_direct_stop_returns()
            else:
                active_returns = rec.direct_stop_return_ids.filtered(lambda r: r.state != "cancel") if rec.direct_stop_return_ids else rec.direct_stop_return_ids
            previous_due_visits = rec._get_direct_stop_previous_due_visits() if rec.id else self.env["route.visit"]
            settlement_payments = rec._get_direct_stop_settlement_payments() if rec.id else self.env["route.visit.payment"]

            rec.direct_stop_order_count = len(orders)
            rec.direct_stop_return_count = len(active_returns)
            rec.direct_stop_sales_total = sum(orders.filtered(lambda o: o.state in ("sale", "done")).mapped("amount_total"))
            rec.direct_stop_returns_total = sum(active_returns.mapped("amount_total"))
            rec.direct_stop_previous_due_amount = sum(previous_due_visits.mapped("remaining_due_amount")) if previous_due_visits else 0.0
            rec.direct_stop_previous_due_since_date = min(previous_due_visits.mapped("date")) if previous_due_visits else False
            rec.direct_stop_current_net_amount = (rec.direct_stop_sales_total or 0.0) - (rec.direct_stop_returns_total or 0.0)

            gross_due = (rec.direct_stop_previous_due_amount or 0.0) + (rec.direct_stop_current_net_amount or 0.0)
            rec.direct_stop_grand_due_amount = max(gross_due, 0.0)
            rec.direct_stop_credit_amount = max(-gross_due, 0.0)

            confirmed_payments = settlement_payments.filtered(lambda p: p.state == "confirmed") if settlement_payments else settlement_payments
            draft_payments = settlement_payments.filtered(lambda p: p.state == "draft") if settlement_payments else settlement_payments
            confirmed_collected_amount = rec._route_sum_financial_collected_amount(confirmed_payments) if confirmed_payments else 0.0
            confirmed_resolved_amount = rec._get_direct_stop_settlement_resolved_amount(states=["confirmed"]) if rec.id else confirmed_collected_amount
            rec.direct_stop_settlement_paid_amount = confirmed_collected_amount
            rec.direct_stop_settlement_remaining_amount = max((rec.direct_stop_grand_due_amount or 0.0) - (confirmed_resolved_amount or 0.0), 0.0)

            if rec.direct_stop_order_count:
                rec.direct_stop_sale_status = "yes"
            elif rec.direct_stop_skip_sale:
                rec.direct_stop_sale_status = "no"
            else:
                rec.direct_stop_sale_status = "pending"

            if rec.direct_stop_return_count:
                rec.direct_stop_return_status = "yes"
            elif rec.direct_stop_skip_return:
                rec.direct_stop_return_status = "no"
            else:
                rec.direct_stop_return_status = "pending"

            credit_ready = (rec.direct_stop_credit_amount or 0.0) <= 0.0 or bool(rec.direct_stop_credit_policy)
            sale_answer_complete = rec.direct_stop_sale_status != "pending"
            return_answer_complete = (not rec.route_enable_direct_return) or rec.direct_stop_return_status != "pending"
            rec.direct_stop_settlement_ready = (
                rec.visit_execution_mode != "direct_sales"
                or (
                    sale_answer_complete
                    and return_answer_complete
                    and not draft_payments
                    and (rec.direct_stop_settlement_remaining_amount or 0.0) <= 0.0
                    and credit_ready
                )
            )

    @api.depends(
        "visit_execution_mode",
        "payment_ids.state",
        "payment_ids.amount",
        "payment_ids.promise_amount",
        "payment_ids.payment_mode",
        "payment_ids.cheque_followup_state",
        "settlement_payment_ids.state",
        "settlement_payment_ids.amount",
        "settlement_payment_ids.promise_amount",
        "settlement_payment_ids.payment_mode",
        "settlement_payment_ids.cheque_followup_state",
        "line_ids.sold_amount",
        "line_ids.return_amount",
        "line_ids.route_net_payable_amount",
        "direct_stop_grand_due_amount",
    )
    def _compute_payment_totals(self):
        Payment = self.env["route.visit.payment"]
        for rec in self:
            if hasattr(rec, "_is_direct_sales_stop") and rec._is_direct_sales_stop():
                net_due = getattr(rec, "direct_stop_grand_due_amount", 0.0) or 0.0
                confirmed_payments = rec._get_direct_stop_settlement_payments(states=["confirmed"]) if rec.id and hasattr(rec, "_get_direct_stop_settlement_payments") else Payment
                total_collected = rec._route_sum_financial_collected_amount(confirmed_payments) if confirmed_payments else 0.0
                resolved_amount = rec._get_direct_stop_settlement_resolved_amount(states=["confirmed"]) if rec.id and hasattr(rec, "_get_direct_stop_settlement_resolved_amount") else total_collected
                remaining_amount = max((net_due or 0.0) - (resolved_amount or 0.0), 0.0)
            else:
                if hasattr(rec, "_get_route_consignment_financial_amounts"):
                    amounts = rec._get_route_consignment_financial_amounts()
                    net_due = amounts.get("net_payable_amount", 0.0)
                else:
                    total_sales = sum((line.sold_amount or 0.0) for line in rec.line_ids) if rec.line_ids else 0.0
                    total_returns = sum((line.return_amount or 0.0) for line in rec.line_ids) if rec.line_ids else 0.0
                    net_due = max((total_sales or 0.0) - (total_returns or 0.0), 0.0)
                confirmed_payments = rec.payment_ids.filtered(lambda p: p.state == "confirmed") if rec.payment_ids else rec.payment_ids
                total_collected = rec._route_sum_financial_collected_amount(confirmed_payments) if confirmed_payments else 0.0
                remaining_amount = max((net_due or 0.0) - (total_collected or 0.0), 0.0)

            rec.net_due_amount = net_due
            rec.collected_amount = total_collected
            rec.remaining_due_amount = remaining_amount


class SaleOrderChequeFinancialPolicy(models.Model):
    _inherit = "sale.order"

    def _get_route_payment_confirmed_amount(self, exclude_payment=None):
        self.ensure_one()
        payments = self.direct_sale_payment_ids.filtered(lambda p: p.state == "confirmed")
        if exclude_payment:
            payments = payments.filtered(lambda p: p.id != exclude_payment.id)
        total = 0.0
        for payment in payments:
            if hasattr(payment, "_get_route_financial_collected_amount"):
                total += payment._get_route_financial_collected_amount()
            else:
                total += payment.amount or 0.0
        return total

    @api.depends(
        "amount_total",
        "direct_sale_payment_ids.amount",
        "direct_sale_payment_ids.state",
        "direct_sale_payment_ids.payment_mode",
        "direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_direct_sale_payment_summary(self):
        for order in self:
            active_payments = order.direct_sale_payment_ids.filtered(lambda p: p.state != "cancelled")
            confirmed_payments = active_payments.filtered(lambda p: p.state == "confirmed")
            collected_amount = 0.0
            for payment in confirmed_payments:
                if hasattr(payment, "_get_route_financial_collected_amount"):
                    collected_amount += payment._get_route_financial_collected_amount()
                else:
                    collected_amount += payment.amount or 0.0
            order.direct_sale_payment_count = len(active_payments)
            order.direct_sale_collected_amount = collected_amount
            order.direct_sale_remaining_due = order._get_route_payment_remaining_due()
