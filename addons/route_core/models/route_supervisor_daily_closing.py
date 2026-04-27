from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteSupervisorDailyClosing(models.TransientModel):
    _name = "route.supervisor.daily.closing"
    _description = "Supervisor Daily Closing Control"
    _rec_name = "name"

    name = fields.Char(
        string="Name",
        default=lambda self: _("Supervisor Daily Closing"),
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
    )
    closing_date = fields.Date(
        string="Closing Date",
        required=True,
        default=fields.Date.context_today,
    )
    salesperson_id = fields.Many2one("res.users", string="Salesperson")
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle")
    city_id = fields.Many2one("route.city", string="City")
    area_id = fields.Many2one("route.area", string="Area")
    outlet_id = fields.Many2one("route.outlet", string="Outlet")

    total_plan_count = fields.Integer(string="Daily Plans", compute="_compute_closing_dashboard")
    finalized_plan_count = fields.Integer(string="Finalized Plans", compute="_compute_closing_dashboard")
    not_finalized_plan_count = fields.Integer(string="Not Finalized Plans", compute="_compute_closing_dashboard")

    total_visit_count = fields.Integer(string="Visits", compute="_compute_closing_dashboard")
    done_visit_count = fields.Integer(string="Done Visits", compute="_compute_closing_dashboard")
    unfinished_visit_count = fields.Integer(string="Unfinished Visits", compute="_compute_closing_dashboard")
    not_started_visit_count = fields.Integer(string="Not Started", compute="_compute_closing_dashboard")
    active_visit_count = fields.Integer(string="Active", compute="_compute_closing_dashboard")

    location_issue_count = fields.Integer(string="Location Issues", compute="_compute_closing_dashboard")
    open_due_visit_count = fields.Integer(string="Open Due Visits", compute="_compute_closing_dashboard")
    open_due_amount = fields.Monetary(string="Open Due", currency_field="currency_id", compute="_compute_closing_dashboard")
    open_promise_count = fields.Integer(string="Open Promises", compute="_compute_closing_dashboard")
    open_promise_amount = fields.Monetary(string="Promise Amount", currency_field="currency_id", compute="_compute_closing_dashboard")

    vehicle_closing_count = fields.Integer(string="Vehicle Closings", compute="_compute_closing_dashboard")
    vehicle_closing_closed_count = fields.Integer(string="Closed Vehicles", compute="_compute_closing_dashboard")
    vehicle_closing_pending_count = fields.Integer(string="Pending Vehicle Closings", compute="_compute_closing_dashboard")
    vehicle_closing_missing_count = fields.Integer(string="Missing Vehicle Closings", compute="_compute_closing_dashboard")

    loading_proposal_count = fields.Integer(string="Loading Proposals", compute="_compute_closing_dashboard")
    loading_pending_count = fields.Integer(string="Loading Pending", compute="_compute_closing_dashboard")
    pending_transfer_count = fields.Integer(string="Pending Transfers", compute="_compute_closing_dashboard")
    return_transfer_count = fields.Integer(string="Return Transfers", compute="_compute_closing_dashboard")
    refill_transfer_count = fields.Integer(string="Refill Transfers", compute="_compute_closing_dashboard")

    sale_order_count = fields.Integer(string="Sales Orders", compute="_compute_closing_dashboard")
    pending_sale_order_count = fields.Integer(string="Pending Sales Orders", compute="_compute_closing_dashboard")
    sale_order_amount = fields.Monetary(string="Sales Order Amount", currency_field="currency_id", compute="_compute_closing_dashboard")
    direct_return_count = fields.Integer(string="Return Orders", compute="_compute_closing_dashboard")
    pending_direct_return_count = fields.Integer(string="Pending Return Orders", compute="_compute_closing_dashboard")
    direct_return_amount = fields.Monetary(string="Return Order Amount", currency_field="currency_id", compute="_compute_closing_dashboard")

    blocker_count = fields.Integer(string="Closing Blockers", compute="_compute_closing_dashboard")
    ready_to_close = fields.Boolean(string="Ready to Close", compute="_compute_closing_dashboard")
    readiness_label = fields.Char(string="Readiness", compute="_compute_closing_dashboard")
    readiness_note = fields.Char(string="Readiness Note", compute="_compute_closing_dashboard")

    daily_closing_id = fields.Many2one(
        "route.daily.closing",
        string="Daily Closing Record",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    daily_closing_state = fields.Selection(
        [
            ("not_ready", "Not Ready"),
            ("ready", "Ready to Close"),
            ("closed", "Closed"),
            ("reopened", "Reopened"),
        ],
        string="Closing Status",
        compute="_compute_closing_dashboard",
    )
    daily_closing_state_label = fields.Char(string="Closing Status Label", compute="_compute_closing_dashboard")
    daily_closing_state_note = fields.Char(string="Closing Status Note", compute="_compute_closing_dashboard")
    is_day_closed = fields.Boolean(string="Day Closed", compute="_compute_closing_dashboard")
    closed_by_id = fields.Many2one("res.users", string="Closed By", compute="_compute_closing_dashboard")
    closed_at = fields.Datetime(string="Closed At", compute="_compute_closing_dashboard")
    reopened_by_id = fields.Many2one("res.users", string="Reopened By", compute="_compute_closing_dashboard")
    reopened_at = fields.Datetime(string="Reopened At", compute="_compute_closing_dashboard")
    closing_note = fields.Text(string="Closing Notes")
    reopen_reason = fields.Text(string="Reopen Reason")

    daily_visit_ids = fields.Many2many(
        "route.visit",
        string="Daily Visits",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    daily_plan_ids = fields.Many2many(
        "route.plan",
        string="Daily Plans",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    vehicle_closing_ids = fields.Many2many(
        "route.vehicle.closing",
        string="Vehicle Closings",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    loading_proposal_ids = fields.Many2many(
        "route.loading.proposal",
        string="Loading Proposals",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    open_promise_payment_ids = fields.Many2many(
        "route.visit.payment",
        string="Open Promises",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    pending_transfer_ids = fields.Many2many(
        "stock.picking",
        string="Pending Transfers",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    sale_order_ids = fields.Many2many(
        "sale.order",
        string="Sales Orders",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    direct_return_ids = fields.Many2many(
        "route.direct.return",
        string="Return Orders",
        compute="_compute_closing_dashboard",
        readonly=True,
    )
    issue_line_ids = fields.One2many(
        "route.supervisor.daily.closing.issue",
        "dashboard_id",
        string="Closing Checks",
        readonly=True,
    )

    @api.onchange("city_id")
    def _onchange_city_id(self):
        for rec in self:
            if rec.area_id and rec.area_id.city_id != rec.city_id:
                rec.area_id = False
            if rec.outlet_id and rec.outlet_id.route_city_id != rec.city_id:
                rec.outlet_id = False

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.area_id and not rec.city_id:
                rec.city_id = rec.area_id.city_id
            if rec.outlet_id and rec.outlet_id.area_id != rec.area_id:
                rec.outlet_id = False

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        for rec in self:
            if rec.outlet_id:
                rec.area_id = rec.outlet_id.area_id
                if rec.outlet_id.route_city_id:
                    rec.city_id = rec.outlet_id.route_city_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._rebuild_issue_lines()
        return records

    def write(self, vals):
        result = super().write(vals)
        watched_fields = {
            "company_id",
            "closing_date",
            "salesperson_id",
            "vehicle_id",
            "city_id",
            "area_id",
            "outlet_id",
        }
        if not self.env.context.get("skip_daily_closing_issue_rebuild") and watched_fields.intersection(vals):
            self._rebuild_issue_lines()
        return result

    @api.onchange("company_id", "closing_date", "salesperson_id", "vehicle_id", "city_id", "area_id", "outlet_id")
    def _onchange_rebuild_issue_lines(self):
        for dashboard in self:
            try:
                issue_values = dashboard._prepare_issue_line_values()
                dashboard.issue_line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in issue_values]
            except Exception:
                dashboard.issue_line_ids = [(5, 0, 0)]

    def _reset_computed_values(self):
        for rec in self:
            rec.total_plan_count = 0
            rec.finalized_plan_count = 0
            rec.not_finalized_plan_count = 0
            rec.total_visit_count = 0
            rec.done_visit_count = 0
            rec.unfinished_visit_count = 0
            rec.not_started_visit_count = 0
            rec.active_visit_count = 0
            rec.location_issue_count = 0
            rec.open_due_visit_count = 0
            rec.open_due_amount = 0.0
            rec.open_promise_count = 0
            rec.open_promise_amount = 0.0
            rec.vehicle_closing_count = 0
            rec.vehicle_closing_closed_count = 0
            rec.vehicle_closing_pending_count = 0
            rec.vehicle_closing_missing_count = 0
            rec.loading_proposal_count = 0
            rec.loading_pending_count = 0
            rec.pending_transfer_count = 0
            rec.return_transfer_count = 0
            rec.refill_transfer_count = 0
            rec.sale_order_count = 0
            rec.pending_sale_order_count = 0
            rec.sale_order_amount = 0.0
            rec.direct_return_count = 0
            rec.pending_direct_return_count = 0
            rec.direct_return_amount = 0.0
            rec.blocker_count = 0
            rec.ready_to_close = False
            rec.readiness_label = _("Not Ready")
            rec.readiness_note = _("Review the closing checks below.")
            rec.daily_closing_id = False
            rec.daily_closing_state = "not_ready"
            rec.daily_closing_state_label = _("Not Ready")
            rec.daily_closing_state_note = _("Review the closing checks below.")
            rec.is_day_closed = False
            rec.closed_by_id = False
            rec.closed_at = False
            rec.reopened_by_id = False
            rec.reopened_at = False
            rec.daily_visit_ids = [fields.Command.clear()]
            rec.daily_plan_ids = [fields.Command.clear()]
            rec.vehicle_closing_ids = [fields.Command.clear()]
            rec.loading_proposal_ids = [fields.Command.clear()]
            rec.open_promise_payment_ids = [fields.Command.clear()]
            rec.pending_transfer_ids = [fields.Command.clear()]
            rec.sale_order_ids = [fields.Command.clear()]
            rec.direct_return_ids = [fields.Command.clear()]

    def _base_visit_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("date", "=", self.closing_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.city_id:
            domain += [
                "|",
                ("area_id.city_id", "=", self.city_id.id),
                ("outlet_id.route_city_id", "=", self.city_id.id),
            ]
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        return domain

    def _plan_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("date", "=", self.closing_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.city_id:
            domain += [
                "|",
                ("area_id.city_id", "=", self.city_id.id),
                ("search_area_ids.city_id", "=", self.city_id.id),
            ]
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        return domain

    def _vehicle_closing_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("plan_date", "=", self.closing_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        return domain

    def _loading_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("plan_date", "=", self.closing_date or fields.Date.context_today(self)),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        return domain

    def _day_datetime_range(self):
        self.ensure_one()
        closing_date = self.closing_date or fields.Date.context_today(self)
        day_start = datetime.combine(closing_date, time.min)
        day_end = day_start + timedelta(days=1)
        return fields.Datetime.to_string(day_start), fields.Datetime.to_string(day_end)

    def _sale_order_domain(self, visits=None):
        self.ensure_one()
        day_start, day_end = self._day_datetime_range()
        visit_names = (visits or self.env["route.visit"]).mapped("name")
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("route_order_mode", "=", "direct_sale"),
            ("state", "!=", "cancel"),
            "|",
            "&",
            ("date_order", ">=", day_start),
            ("date_order", "<", day_end),
            ("origin", "in", visit_names or ["__no_route_visit__"]),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.outlet_id:
            domain.append(("route_outlet_id", "=", self.outlet_id.id))
        return domain

    def _direct_return_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("return_date", "=", self.closing_date or fields.Date.context_today(self)),
            ("state", "!=", "cancel"),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        return domain

    def _promise_domain_stored(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("promise_amount", ">", 0.0),
        ]
        if self.salesperson_id:
            domain.append(("salesperson_id", "=", self.salesperson_id.id))
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        return domain

    def _daily_closing_lookup_values(self):
        self.ensure_one()
        return {
            "company_id": self.company_id.id or self.env.company.id,
            "closing_date": self.closing_date or fields.Date.context_today(self),
            "salesperson_id": self.salesperson_id.id or False,
            "vehicle_id": self.vehicle_id.id or False,
            "city_id": self.city_id.id or False,
            "area_id": self.area_id.id or False,
            "outlet_id": self.outlet_id.id or False,
        }

    def _daily_closing_lookup_domain(self):
        self.ensure_one()
        vals = self._daily_closing_lookup_values()
        return [
            ("company_id", "=", vals["company_id"]),
            ("closing_date", "=", vals["closing_date"]),
            ("salesperson_id", "=", vals["salesperson_id"]),
            ("vehicle_id", "=", vals["vehicle_id"]),
            ("city_id", "=", vals["city_id"]),
            ("area_id", "=", vals["area_id"]),
            ("outlet_id", "=", vals["outlet_id"]),
        ]

    def _get_daily_closing_record(self):
        self.ensure_one()
        return self.env["route.daily.closing"].search(self._daily_closing_lookup_domain(), limit=1)

    def _filter_recordsets_for_city_area_outlet(self, visits, plans, payments, closings, proposals, sale_orders, direct_returns):
        self.ensure_one()
        if self.city_id:
            visits = visits.filtered(
                lambda visit: (visit.area_id and visit.area_id.city_id == self.city_id)
                or (visit.outlet_id and visit.outlet_id.route_city_id == self.city_id)
            )
            plans = plans.filtered(
                lambda plan: (plan.area_id and plan.area_id.city_id == self.city_id)
                or bool(plan.search_area_ids.filtered(lambda area: area.city_id == self.city_id))
            )
            payments = payments.filtered(
                lambda payment: (payment.area_id and payment.area_id.city_id == self.city_id)
                or (payment.outlet_id and payment.outlet_id.route_city_id == self.city_id)
            )
            closings = closings.filtered(
                lambda closing: closing.plan_id
                and ((closing.plan_id.area_id and closing.plan_id.area_id.city_id == self.city_id)
                     or bool(closing.plan_id.search_area_ids.filtered(lambda area: area.city_id == self.city_id)))
            )
            proposals = proposals.filtered(
                lambda proposal: proposal.plan_id
                and ((proposal.plan_id.area_id and proposal.plan_id.area_id.city_id == self.city_id)
                     or bool(proposal.plan_id.search_area_ids.filtered(lambda area: area.city_id == self.city_id)))
            )
            sale_orders = sale_orders.filtered(
                lambda order: (order.route_outlet_id and order.route_outlet_id.route_city_id == self.city_id)
                or (order.route_visit_id and ((order.route_visit_id.area_id and order.route_visit_id.area_id.city_id == self.city_id)
                    or (order.route_visit_id.outlet_id and order.route_visit_id.outlet_id.route_city_id == self.city_id)))
            )
            direct_returns = direct_returns.filtered(
                lambda direct_return: (direct_return.outlet_id and direct_return.outlet_id.route_city_id == self.city_id)
                or (direct_return.visit_id and ((direct_return.visit_id.area_id and direct_return.visit_id.area_id.city_id == self.city_id)
                    or (direct_return.visit_id.outlet_id and direct_return.visit_id.outlet_id.route_city_id == self.city_id)))
            )
        if self.area_id:
            visits = visits.filtered(lambda visit: visit.area_id == self.area_id)
            plans = plans.filtered(lambda plan: plan.area_id == self.area_id or self.area_id in plan.search_area_ids)
            payments = payments.filtered(lambda payment: payment.area_id == self.area_id)
            closings = closings.filtered(
                lambda closing: closing.plan_id and (closing.plan_id.area_id == self.area_id or self.area_id in closing.plan_id.search_area_ids)
            )
            proposals = proposals.filtered(
                lambda proposal: proposal.plan_id and (proposal.plan_id.area_id == self.area_id or self.area_id in proposal.plan_id.search_area_ids)
            )
            sale_orders = sale_orders.filtered(
                lambda order: (order.route_outlet_id and order.route_outlet_id.area_id == self.area_id)
                or (order.route_visit_id and order.route_visit_id.area_id == self.area_id)
            )
            direct_returns = direct_returns.filtered(
                lambda direct_return: (direct_return.outlet_id and direct_return.outlet_id.area_id == self.area_id)
                or (direct_return.visit_id and direct_return.visit_id.area_id == self.area_id)
            )
        if self.outlet_id:
            payments = payments.filtered(lambda payment: payment.outlet_id == self.outlet_id)
            sale_orders = sale_orders.filtered(lambda order: order.route_outlet_id == self.outlet_id)
            direct_returns = direct_returns.filtered(lambda direct_return: direct_return.outlet_id == self.outlet_id)
        return visits, plans, payments, closings, proposals, sale_orders, direct_returns

    def _collect_dashboard_data(self):
        self.ensure_one()
        Visit = self.env["route.visit"]
        Plan = self.env["route.plan"]
        Payment = self.env["route.visit.payment"]
        Closing = self.env["route.vehicle.closing"]
        Proposal = self.env["route.loading.proposal"]
        Picking = self.env["stock.picking"]
        SaleOrder = self.env["sale.order"]
        DirectReturn = self.env["route.direct.return"]

        visits = Visit.search(self._base_visit_domain(), order="date desc, start_datetime desc, id desc")
        plans = Plan.search(self._plan_domain(), order="date desc, id desc")
        closings = Closing.search(self._vehicle_closing_domain(), order="plan_date desc, id desc")
        proposals = Proposal.search(self._loading_domain(), order="plan_date desc, id desc")
        payments = Payment.search(self._promise_domain_stored(), order="promise_date asc, id desc")
        sale_orders = SaleOrder.search(self._sale_order_domain(visits), order="date_order desc, id desc")
        direct_returns = DirectReturn.search(self._direct_return_domain(), order="return_date desc, id desc")

        if self.vehicle_id:
            payments = payments.filtered(
                lambda payment: (payment.visit_id and payment.visit_id.vehicle_id == self.vehicle_id)
                or (payment.settlement_visit_id and payment.settlement_visit_id.vehicle_id == self.vehicle_id)
            )
            sale_orders = sale_orders.filtered(
                lambda order: (order.route_visit_id and order.route_visit_id.vehicle_id == self.vehicle_id)
                or bool(order.picking_ids.filtered(lambda picking: picking.location_id == self.vehicle_id.stock_location_id))
            )
        visits, plans, payments, closings, proposals, sale_orders, direct_returns = self._filter_recordsets_for_city_area_outlet(
            visits, plans, payments, closings, proposals, sale_orders, direct_returns
        )
        open_promises = payments.filtered(lambda payment: payment.promise_status in ("open", "due_today", "overdue"))

        related_picking_ids = set()
        for visit in visits:
            if visit.refill_picking_id:
                related_picking_ids.add(visit.refill_picking_id.id)
            for picking in visit.return_picking_ids:
                related_picking_ids.add(picking.id)
        for proposal in proposals:
            if proposal.picking_id:
                related_picking_ids.add(proposal.picking_id.id)
        for closing in closings:
            for picking in closing.reconciliation_picking_ids:
                related_picking_ids.add(picking.id)
        for order in sale_orders:
            for picking in order.picking_ids:
                related_picking_ids.add(picking.id)
        for direct_return in direct_returns:
            for picking in direct_return.picking_ids:
                related_picking_ids.add(picking.id)
        pending_transfers = Picking.search([
            ("id", "in", list(related_picking_ids) or [0]),
            ("state", "not in", ["done", "cancel"]),
        ])
        return visits, plans, closings, proposals, open_promises, pending_transfers, sale_orders, direct_returns

    def _promise_is_blocking_for_closing(self, payment):
        """Return True only for promises that need same-day supervisor action.

        Future promises are official follow-up commitments and must remain open,
        but they should not block the operational closing of the previous day.
        Due-today, overdue, or undated promises are kept as blockers so money is
        not forgotten or lost. A supervisor review can release the blocker only
        when it records a concrete follow-up date after the closing date.
        """
        self.ensure_one()
        closing_date = fields.Date.to_date(self.closing_date or fields.Date.context_today(self))

        review_for_date = fields.Date.to_date(payment.promise_review_for_closing_date) if getattr(payment, "promise_review_for_closing_date", False) else False
        review_followup_date = fields.Date.to_date(payment.promise_review_followup_date) if getattr(payment, "promise_review_followup_date", False) else False
        if (
            review_for_date == closing_date
            and getattr(payment, "promise_review_decision", False) in ("reschedule", "review_followup")
            and review_followup_date
            and review_followup_date > closing_date
        ):
            return False

        status = payment.promise_status or ""
        if status in ("due_today", "overdue"):
            return True
        if status != "open":
            return False

        promise_date = fields.Date.to_date(payment.promise_date) if payment.promise_date else False
        if not promise_date:
            return True
        return promise_date <= closing_date

    def _blocking_promises(self, open_promises):
        """Promises that must be resolved before Close Day."""
        return open_promises.filtered(lambda payment: self._promise_is_blocking_for_closing(payment))

    def _visit_open_promise_amount(self, visit, open_promises):
        """Return the open promise amount that covers a specific visit."""
        related_promises = open_promises.filtered(
            lambda payment: (payment.visit_id and payment.visit_id == visit)
            or (payment.settlement_visit_id and payment.settlement_visit_id == visit)
        )
        return sum(related_promises.mapped("promise_amount")) if related_promises else 0.0

    def _visit_uncovered_due_amount(self, visit, open_promises):
        """Return only the remaining due amount not covered by an open promise."""
        remaining_due = visit.remaining_due_amount or 0.0
        if remaining_due <= 0.0:
            return 0.0
        covered_by_promises = self._visit_open_promise_amount(visit, open_promises)
        uncovered_due = max(remaining_due - covered_by_promises, 0.0)

        currency = self.currency_id or self.env.company.currency_id
        if "currency_id" in visit._fields and visit.currency_id:
            currency = visit.currency_id
        if currency and currency.is_zero(uncovered_due):
            return 0.0
        return currency.round(uncovered_due) if currency else uncovered_due

    def _uncovered_due_visits(self, visits, open_promises):
        """Visits that still have due amount not covered by open promises."""
        return visits.filtered(lambda visit: self._visit_uncovered_due_amount(visit, open_promises) > 0.0)

    def _uncovered_due_amount_total(self, visits, open_promises):
        return sum(self._visit_uncovered_due_amount(visit, open_promises) for visit in visits)

    def _location_review_issue_visits(self, visits):
        """Visits that still require supervisor location review for daily closing.

        Cancelled visits without field execution should not block closing. If a
        visit was cancelled, it remains visible in visit history, but it is not
        treated as a location review blocker.
        """
        return visits.filtered(
            lambda visit: visit.visit_process_state != "cancel"
            and (
                (visit.geo_review_required and not visit.geo_review_supervisor_decision)
                or visit.geo_review_supervisor_decision == "needs_correction"
                or visit.geo_review_state == "outlet_missing"
                or (
                    visit.geo_review_state == "pending_checkin"
                    and visit.visit_process_state not in ["draft", "cancel"]
                )
            )
        )

    @api.depends("company_id", "closing_date", "salesperson_id", "vehicle_id", "city_id", "area_id", "outlet_id")
    def _compute_closing_dashboard(self):
        for dashboard in self:
            dashboard._reset_computed_values()
            try:
                visits, plans, closings, proposals, open_promises, pending_transfers, sale_orders, direct_returns = dashboard._collect_dashboard_data()
                done_visits = visits.filtered(lambda visit: visit.visit_process_state == "done")
                not_started_visits = visits.filtered(lambda visit: visit.visit_process_state == "draft")
                active_visits = visits.filtered(lambda visit: visit.visit_process_state not in ["draft", "done", "cancel"])
                unfinished_visits = visits.filtered(lambda visit: visit.visit_process_state not in ["done", "cancel"])
                location_issues = dashboard._location_review_issue_visits(visits)
                open_due_visits = dashboard._uncovered_due_visits(visits, open_promises)
                blocking_promises = dashboard._blocking_promises(open_promises)
                not_finalized_plans = plans.filtered(lambda plan: not plan.planning_finalized)
                closed_closings = closings.filtered(lambda closing: closing.state == "closed")
                pending_closings = closings.filtered(lambda closing: closing.state != "closed")
                missing_closings_count = len(plans.filtered(lambda plan: plan.vehicle_id and plan not in closings.mapped("plan_id")))
                pending_loading = proposals.filtered(
                    lambda proposal: proposal.state not in ["approved", "cancelled"]
                    or (proposal.picking_id and proposal.picking_id.state not in ["done", "cancel"])
                )
                return_pickings = (visits.mapped("return_picking_ids") | direct_returns.mapped("picking_ids")).filtered(lambda picking: picking.state != "cancel")
                refill_pickings = visits.mapped("refill_picking_id").filtered(lambda picking: picking.state != "cancel")
                pending_sale_orders = sale_orders.filtered(lambda order: order.state in ["draft", "sent"])
                pending_direct_returns = direct_returns.filtered(lambda direct_return: direct_return.state == "draft")

                blocker_count = (
                    len(unfinished_visits)
                    + len(location_issues)
                    + len(open_due_visits)
                    + len(blocking_promises)
                    + len(not_finalized_plans)
                    + len(pending_closings)
                    + missing_closings_count
                    + len(pending_loading)
                    + len(pending_transfers)
                    + len(pending_sale_orders)
                    + len(pending_direct_returns)
                )

                dashboard.daily_visit_ids = [fields.Command.set(visits.ids)]
                dashboard.daily_plan_ids = [fields.Command.set(plans.ids)]
                dashboard.vehicle_closing_ids = [fields.Command.set(closings.ids)]
                dashboard.loading_proposal_ids = [fields.Command.set(proposals.ids)]
                dashboard.open_promise_payment_ids = [fields.Command.set(open_promises.ids)]
                dashboard.pending_transfer_ids = [fields.Command.set(pending_transfers.ids)]
                dashboard.sale_order_ids = [fields.Command.set(sale_orders.ids)]
                dashboard.direct_return_ids = [fields.Command.set(direct_returns.ids)]

                dashboard.total_plan_count = len(plans)
                dashboard.finalized_plan_count = len(plans.filtered("planning_finalized"))
                dashboard.not_finalized_plan_count = len(not_finalized_plans)
                dashboard.total_visit_count = len(visits)
                dashboard.done_visit_count = len(done_visits)
                dashboard.unfinished_visit_count = len(unfinished_visits)
                dashboard.not_started_visit_count = len(not_started_visits)
                dashboard.active_visit_count = len(active_visits)
                dashboard.location_issue_count = len(location_issues)
                dashboard.open_due_visit_count = len(open_due_visits)
                dashboard.open_due_amount = dashboard._uncovered_due_amount_total(open_due_visits, open_promises) if open_due_visits else 0.0
                dashboard.open_promise_count = len(open_promises)
                dashboard.open_promise_amount = sum(open_promises.mapped("promise_amount")) if open_promises else 0.0
                dashboard.vehicle_closing_count = len(closings)
                dashboard.vehicle_closing_closed_count = len(closed_closings)
                dashboard.vehicle_closing_pending_count = len(pending_closings)
                dashboard.vehicle_closing_missing_count = missing_closings_count
                dashboard.loading_proposal_count = len(proposals)
                dashboard.loading_pending_count = len(pending_loading)
                dashboard.pending_transfer_count = len(pending_transfers)
                dashboard.return_transfer_count = len(return_pickings)
                dashboard.refill_transfer_count = len(refill_pickings)
                dashboard.sale_order_count = len(sale_orders)
                dashboard.pending_sale_order_count = len(pending_sale_orders)
                dashboard.sale_order_amount = sum(sale_orders.mapped("amount_total")) if sale_orders else 0.0
                dashboard.direct_return_count = len(direct_returns)
                dashboard.pending_direct_return_count = len(pending_direct_returns)
                dashboard.direct_return_amount = sum(direct_returns.mapped("amount_total")) if direct_returns else 0.0
                dashboard.blocker_count = blocker_count
                dashboard.ready_to_close = blocker_count == 0

                closing_record = dashboard._get_daily_closing_record()
                dashboard.daily_closing_id = closing_record
                dashboard.is_day_closed = bool(closing_record and closing_record.state == "closed")
                dashboard.closed_by_id = closing_record.closed_by_id if closing_record else False
                dashboard.closed_at = closing_record.closed_at if closing_record else False
                dashboard.reopened_by_id = closing_record.reopened_by_id if closing_record and closing_record.state == "reopened" else False
                dashboard.reopened_at = closing_record.reopened_at if closing_record and closing_record.state == "reopened" else False

                if closing_record and closing_record.state == "closed":
                    dashboard.daily_closing_state = "closed"
                    dashboard.daily_closing_state_label = _("Closed")
                    dashboard.daily_closing_state_note = _("This day is closed and linked records are locked until it is reopened.")
                    dashboard.readiness_label = _("Closed")
                    dashboard.readiness_note = _("This day was closed successfully.")
                elif closing_record and closing_record.state == "reopened":
                    dashboard.daily_closing_state = "reopened"
                    dashboard.daily_closing_state_label = _("Reopened")
                    dashboard.daily_closing_state_note = _("This day was reopened. Validate again before closing.")
                    if dashboard.ready_to_close:
                        dashboard.readiness_label = _("Ready to Close")
                        dashboard.readiness_note = _("No blocking items were found for the selected date and filters.")
                    else:
                        dashboard.readiness_label = _("Not Ready")
                        dashboard.readiness_note = _("Resolve the blocking items before closing the day.")
                elif dashboard.ready_to_close:
                    dashboard.daily_closing_state = "ready"
                    dashboard.daily_closing_state_label = _("Ready to Close")
                    dashboard.daily_closing_state_note = _("No blocking items were found. You can close the day.")
                    dashboard.readiness_label = _("Ready to Close")
                    dashboard.readiness_note = _("No blocking items were found for the selected date and filters.")
                else:
                    dashboard.daily_closing_state = "not_ready"
                    dashboard.daily_closing_state_label = _("Not Ready")
                    dashboard.daily_closing_state_note = _("Resolve the blocking items before closing the day.")
                    dashboard.readiness_label = _("Not Ready")
                    dashboard.readiness_note = _("Resolve the blocking items before closing the day.")
            except Exception:
                dashboard._reset_computed_values()

    def _prepare_issue_line_values(self):
        self.ensure_one()
        visits, plans, closings, proposals, open_promises, pending_transfers, sale_orders, direct_returns = self._collect_dashboard_data()
        lines = []

        def add(sequence, code, title, count, subtitle, severity="warning", amount=0.0, button_label="Open"):
            if not count and code != "ready":
                return
            lines.append({
                "sequence": sequence,
                "code": code,
                "title": title,
                "count": count,
                "subtitle": subtitle or "",
                "severity": severity,
                "amount": amount or 0.0,
                "button_label": button_label,
            })

        unfinished = visits.filtered(lambda visit: visit.visit_process_state not in ["done", "cancel"])
        not_started = visits.filtered(lambda visit: visit.visit_process_state == "draft")
        open_due = self._uncovered_due_visits(visits, open_promises)
        blocking_promises = self._blocking_promises(open_promises)
        location_issues = self._location_review_issue_visits(visits)
        not_finalized = plans.filtered(lambda plan: not plan.planning_finalized)
        pending_closings = closings.filtered(lambda closing: closing.state != "closed")
        missing_closings = plans.filtered(lambda plan: plan.vehicle_id and plan not in closings.mapped("plan_id"))
        pending_loading = proposals.filtered(
            lambda proposal: proposal.state not in ["approved", "cancelled"]
            or (proposal.picking_id and proposal.picking_id.state not in ["done", "cancel"])
        )
        pending_sale_orders = sale_orders.filtered(lambda order: order.state in ["draft", "sent"])
        pending_direct_returns = direct_returns.filtered(lambda direct_return: direct_return.state == "draft")

        add(10, "unfinished_visits", _("Unfinished Visits"), len(unfinished), _("Visits that are not done or cancelled."), "danger", button_label=_("Open Visits"))
        add(20, "not_started_visits", _("Not Started Visits"), len(not_started), _("Planned visits not started yet."), "warning", button_label=_("Open Visits"))
        add(30, "location_issues", _("Location Review Pending"), len(location_issues), _("Location issues need supervisor review."), "warning", button_label=_("Open Location"))
        add(40, "open_due", _("Open Due"), len(open_due), _("Visits with due amount not covered by an open promise."), "danger", self._uncovered_due_amount_total(open_due, open_promises) if open_due else 0.0, button_label=_("Open Visits"))
        add(50, "open_promises", _("Due / Overdue Promises"), len(blocking_promises), _("Promises due today, overdue, or missing a promise date must be resolved before closing."), "warning", sum(blocking_promises.mapped("promise_amount")) if blocking_promises else 0.0, button_label=_("Open Promises"))
        add(60, "pending_sale_orders", _("Pending Sales Orders"), len(pending_sale_orders), _("Direct sale orders still need confirmation."), "warning", sum(pending_sale_orders.mapped("amount_total")) if pending_sale_orders else 0.0, button_label=_("Open Orders"))
        add(70, "pending_direct_returns", _("Pending Return Orders"), len(pending_direct_returns), _("Direct return orders still need processing."), "warning", sum(pending_direct_returns.mapped("amount_total")) if pending_direct_returns else 0.0, button_label=_("Open Returns"))
        add(80, "not_finalized_plans", _("Plans Not Finalized"), len(not_finalized), _("Daily route plans still need finalization."), "warning", button_label=_("Open Plans"))
        add(90, "vehicle_closing_missing", _("Vehicle Closing Missing"), len(missing_closings), _("Daily plans have a vehicle but no closing record yet."), "danger", button_label=_("Open Plans"))
        add(100, "vehicle_closing_pending", _("Vehicle Closing Pending"), len(pending_closings), _("Vehicle closing records are still not closed."), "danger", button_label=_("Open Closings"))
        add(110, "loading_pending", _("Loading Pending"), len(pending_loading), _("Loading proposals are not fully approved or transferred."), "warning", button_label=_("Open Loading"))
        add(120, "pending_transfers", _("Transfer Pending"), len(pending_transfers), _("Related stock transfers are not fully completed."), "warning", button_label=_("Open Transfers"))
        if not lines:
            add(130, "ready", _("Ready to Close Day"), 0, _("No blocking items were found."), "success", button_label=_("Refresh"))
        return lines

    def _rebuild_issue_lines(self):
        for dashboard in self:
            try:
                issue_values = dashboard._prepare_issue_line_values()
                dashboard.with_context(skip_daily_closing_issue_rebuild=True).write({
                    "issue_line_ids": [(5, 0, 0)] + [(0, 0, vals) for vals in issue_values]
                })
            except Exception:
                dashboard.with_context(skip_daily_closing_issue_rebuild=True).write({"issue_line_ids": [(5, 0, 0)]})

    @api.model
    def action_open_daily_closing_dashboard(self):
        dashboard = self.create({
            "name": _("Supervisor Daily Closing"),
            "company_id": self.env.company.id,
            "closing_date": fields.Date.context_today(self),
        })
        view = self.env.ref("route_core.view_route_supervisor_daily_closing_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Supervisor Daily Closing"),
            "res_model": "route.supervisor.daily.closing",
            "res_id": dashboard.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": True, "delete": False},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_validate_daily_closing(self):
        self.ensure_one()
        closing_record = self._get_daily_closing_record()
        if closing_record and closing_record.state == "closed":
            return self._daily_closing_action_notification(
                _("Already Closed"),
                _("The selected day is already closed. Reopen it first if changes are required."),
                "info",
                reload=False,
            )
        issue_values = self._get_blocking_issue_values()
        if not issue_values:
            # Validate Closing is the supervisor confirmation step.
            # When no blockers remain, close the day immediately so the
            # dashboard does not stop at a passive "Ready to Close" notice.
            return self.action_close_day()
        raise UserError(self._format_blocking_issue_message(issue_values))

    def _get_blocking_issue_values(self):
        self.ensure_one()
        return [
            vals
            for vals in self._prepare_issue_line_values()
            if vals.get("code") != "ready" and vals.get("count")
        ]

    def _format_blocking_issue_message(self, issue_values):
        message_lines = ["%s: %s" % (vals.get("title"), vals.get("count")) for vals in issue_values]
        return _("The day is not ready to close. Resolve these blocking items first:\n%s") % "\n".join(message_lines)

    def _daily_closing_action_notification(self, title, message, notif_type="success", reload=True):
        params = {
            "title": title,
            "message": message,
            "type": notif_type,
            "sticky": False,
        }
        if reload:
            params["next"] = {"type": "ir.actions.client", "tag": "reload"}
        return {"type": "ir.actions.client", "tag": "display_notification", "params": params}

    def _build_daily_closing_name(self, vals):
        parts = [_('Daily Closing'), str(vals.get("closing_date") or "")]
        if vals.get("salesperson_id"):
            user = self.env["res.users"].browse(vals["salesperson_id"])
            parts.append(user.display_name)
        if vals.get("vehicle_id"):
            vehicle = self.env["route.vehicle"].browse(vals["vehicle_id"])
            parts.append(vehicle.display_name)
        if vals.get("area_id"):
            area = self.env["route.area"].browse(vals["area_id"])
            parts.append(area.display_name)
        return " - ".join([part for part in parts if part])

    def _scope_label_value(self, selected_record, record_count, all_label):
        """Return a readable scope label for Daily Closing Record cards.

        When the closing was created with an explicit filter, show the selected
        record name. When it is a full-day/company closing, show an "All ..."
        label with the number of records included in the frozen snapshot.
        """
        self.ensure_one()
        if selected_record:
            return selected_record.display_name
        if record_count:
            return _("%(label)s (%(count)s)") % {"label": all_label, "count": record_count}
        return all_label

    def _calculate_daily_closing_scope_values(self, visits, plans, closings):
        """Build readable scope labels/counts for the persisted closing record.

        The top section of the Closing Record should not show blank Salesperson,
        Vehicle, City, Area or Outlet fields for a company-wide closing. A blank
        many2one looks like missing data, while the correct meaning is usually
        "all records covered by the selected day/company". Store explicit text
        labels so the record remains clear after closing/reopening.
        """
        self.ensure_one()

        salespersons = visits.mapped("user_id") | plans.mapped("user_id")
        vehicles = visits.mapped("vehicle_id") | plans.mapped("vehicle_id") | closings.mapped("vehicle_id")
        outlets = visits.mapped("outlet_id") | plans.mapped("line_ids.outlet_id")
        areas = visits.mapped("area_id") | plans.mapped("area_id") | plans.mapped("line_ids.area_id") | outlets.mapped("area_id")
        cities = areas.mapped("city_id") | outlets.mapped("route_city_id")

        if self.salesperson_id:
            salespersons |= self.salesperson_id
        if self.vehicle_id:
            vehicles |= self.vehicle_id
        if self.outlet_id:
            outlets |= self.outlet_id
        if self.area_id:
            areas |= self.area_id
        if self.city_id:
            cities |= self.city_id

        selected_filters = []
        if self.salesperson_id:
            selected_filters.append(_("Salesperson"))
        if self.vehicle_id:
            selected_filters.append(_("Vehicle"))
        if self.city_id:
            selected_filters.append(_("City"))
        if self.area_id:
            selected_filters.append(_("Area"))
        if self.outlet_id:
            selected_filters.append(_("Outlet"))

        scope_label = _("Full Company Day Closing")
        if selected_filters:
            scope_label = _("Filtered Closing by %s") % ", ".join(selected_filters)

        return {
            "scope_label": scope_label,
            "salesperson_scope_count": len(salespersons),
            "vehicle_scope_count": len(vehicles),
            "city_scope_count": len(cities),
            "area_scope_count": len(areas),
            "outlet_scope_count": len(outlets),
            "salesperson_scope_label": self._scope_label_value(self.salesperson_id, len(salespersons), _("All Salespersons")),
            "vehicle_scope_label": self._scope_label_value(self.vehicle_id, len(vehicles), _("All Vehicles")),
            "city_scope_label": self._scope_label_value(self.city_id, len(cities), _("All Cities")),
            "area_scope_label": self._scope_label_value(self.area_id, len(areas), _("All Areas")),
            "outlet_scope_label": self._scope_label_value(self.outlet_id, len(outlets), _("All Outlets")),
        }

    def _calculate_daily_closing_snapshot_values(self):
        """Build the persisted closing snapshot from the same live data as the dashboard.

        The Daily Closing Record must be a reliable frozen snapshot of the
        selected filters at the moment of closing. Avoid copying cached
        transient/computed values here; recompute from the live recordsets so
        the record numbers match the Supervisor Daily Closing screen.
        """
        self.ensure_one()
        visits, plans, closings, proposals, open_promises, pending_transfers, sale_orders, direct_returns = self._collect_dashboard_data()

        done_visits = visits.filtered(lambda visit: visit.visit_process_state == "done")
        unfinished_visits = visits.filtered(lambda visit: visit.visit_process_state not in ["done", "cancel"])
        location_issues = self._location_review_issue_visits(visits)
        open_due_visits = self._uncovered_due_visits(visits, open_promises)
        blocking_promises = self._blocking_promises(open_promises)
        not_finalized_plans = plans.filtered(lambda plan: not plan.planning_finalized)
        closed_closings = closings.filtered(lambda closing: closing.state == "closed")
        pending_closings = closings.filtered(lambda closing: closing.state != "closed")
        missing_closings_count = len(plans.filtered(lambda plan: plan.vehicle_id and plan not in closings.mapped("plan_id")))
        pending_loading = proposals.filtered(
            lambda proposal: proposal.state not in ["approved", "cancelled"]
            or (proposal.picking_id and proposal.picking_id.state not in ["done", "cancel"])
        )
        return_pickings = (visits.mapped("return_picking_ids") | direct_returns.mapped("picking_ids")).filtered(lambda picking: picking.state != "cancel")
        refill_pickings = visits.mapped("refill_picking_id").filtered(lambda picking: picking.state != "cancel")
        pending_sale_orders = sale_orders.filtered(lambda order: order.state in ["draft", "sent"])
        pending_direct_returns = direct_returns.filtered(lambda direct_return: direct_return.state == "draft")

        blocker_count = (
            len(unfinished_visits)
            + len(location_issues)
            + len(open_due_visits)
            + len(blocking_promises)
            + len(not_finalized_plans)
            + len(pending_closings)
            + missing_closings_count
            + len(pending_loading)
            + len(pending_transfers)
            + len(pending_sale_orders)
            + len(pending_direct_returns)
        )

        scope_vals = self._calculate_daily_closing_scope_values(visits, plans, closings)

        result = {
            "blocker_count": blocker_count,
            "plan_count": len(plans),
            "not_finalized_plan_count": len(not_finalized_plans),
            "visit_count": len(visits),
            "done_visit_count": len(done_visits),
            "unfinished_visit_count": len(unfinished_visits),
            "location_issue_count": len(location_issues),
            "open_due_amount": self._uncovered_due_amount_total(open_due_visits, open_promises) if open_due_visits else 0.0,
            "open_due_visit_count": len(open_due_visits),
            "open_promise_count": len(open_promises),
            "open_promise_amount": sum(open_promises.mapped("promise_amount")) if open_promises else 0.0,
            "vehicle_closing_count": len(closings),
            "vehicle_closing_closed_count": len(closed_closings),
            "vehicle_closing_pending_count": len(pending_closings),
            "vehicle_closing_missing_count": missing_closings_count,
            "loading_proposal_count": len(proposals),
            "loading_pending_count": len(pending_loading),
            "pending_transfer_count": len(pending_transfers),
            "return_transfer_count": len(return_pickings),
            "refill_transfer_count": len(refill_pickings),
            "sale_order_count": len(sale_orders),
            "pending_sale_order_count": len(pending_sale_orders),
            "sale_order_amount": sum(sale_orders.mapped("amount_total")) if sale_orders else 0.0,
            "direct_return_count": len(direct_returns),
            "pending_direct_return_count": len(pending_direct_returns),
            "direct_return_amount": sum(direct_returns.mapped("amount_total")) if direct_returns else 0.0,
            "visit_ids": [fields.Command.set(visits.ids)],
            "plan_ids": [fields.Command.set(plans.ids)],
            "vehicle_closing_ids": [fields.Command.set(closings.ids)],
            "loading_proposal_ids": [fields.Command.set(proposals.ids)],
            "open_promise_payment_ids": [fields.Command.set(open_promises.ids)],
            "pending_transfer_ids": [fields.Command.set(pending_transfers.ids)],
            "return_transfer_ids": [fields.Command.set(return_pickings.ids)],
            "refill_transfer_ids": [fields.Command.set(refill_pickings.ids)],
            "sale_order_ids": [fields.Command.set(sale_orders.ids)],
            "direct_return_ids": [fields.Command.set(direct_returns.ids)],
        }
        result.update(scope_vals)
        return result

    def _prepare_daily_closing_record_values(self, state="closed"):
        self.ensure_one()
        vals = self._daily_closing_lookup_values()
        snapshot_vals = self._calculate_daily_closing_snapshot_values()
        vals.update(snapshot_vals)
        vals.update({
            "name": self._build_daily_closing_name(vals),
            "state": state,
            "closing_note": self.closing_note or False,
        })
        return vals

    def _link_daily_closing_to_operational_records(self, closing_record):
        self.ensure_one()
        link_vals = {"daily_closing_id": closing_record.id}
        ctx = {"bypass_daily_closing_lock": True, "route_plan_skip_locked_check": True, "route_plan_skip_sync": True, "route_visit_force_write": True}
        # Link exactly the frozen snapshot records, not potentially stale
        # transient many2many values from the dashboard cache.
        if closing_record.visit_ids:
            closing_record.visit_ids.with_context(**ctx).write(link_vals)
        if closing_record.plan_ids:
            closing_record.plan_ids.with_context(**ctx).write(link_vals)
        if closing_record.vehicle_closing_ids:
            closing_record.vehicle_closing_ids.with_context(**ctx).write(link_vals)

    def _unlink_daily_closing_from_operational_records(self, closing_record):
        self.ensure_one()
        unlink_vals = {"daily_closing_id": False}
        ctx = {"bypass_daily_closing_lock": True, "route_plan_skip_locked_check": True, "route_plan_skip_sync": True, "route_visit_force_write": True}
        linked_visits = self.env["route.visit"].search([("daily_closing_id", "=", closing_record.id)])
        linked_plans = self.env["route.plan"].search([("daily_closing_id", "=", closing_record.id)])
        linked_closings = self.env["route.vehicle.closing"].search([("daily_closing_id", "=", closing_record.id)])
        if linked_visits:
            linked_visits.with_context(**ctx).write(unlink_vals)
        if linked_plans:
            linked_plans.with_context(**ctx).write(unlink_vals)
        if linked_closings:
            linked_closings.with_context(**ctx).write(unlink_vals)

    def action_close_day(self):
        self.ensure_one()
        closing_record = self._get_daily_closing_record()
        if closing_record and closing_record.state == "closed":
            raise UserError(_("This day is already closed. Reopen it first if changes are required."))

        issue_values = self._get_blocking_issue_values()
        if issue_values:
            raise UserError(self._format_blocking_issue_message(issue_values))

        before_state = closing_record.state if closing_record else "open"
        values = self._prepare_daily_closing_record_values(state="closed")
        now = fields.Datetime.now()
        values.update({
            "closed_by_id": self.env.user.id,
            "closed_at": now,
            # Reopen details are only current while the record is reopened.
            # Historical reopen information lives in the Audit Trail.
            "reopened_by_id": False,
            "reopened_at": False,
            "reopen_reason": False,
        })
        if closing_record:
            values.update({"state": "closed"})
            closing_record.write(values)
            event_type = "close_day_again"
            audit_note = self.closing_note or _("Day closed again after reopening.")
        else:
            closing_record = self.env["route.daily.closing"].create(values)
            event_type = "close_day"
            audit_note = self.closing_note or _("Day closed from Supervisor Daily Closing.")
        closing_record._create_audit_line(
            event_type,
            audit_note,
            state_from=before_state,
            state_to="closed",
        )
        self._link_daily_closing_to_operational_records(closing_record)
        return self._daily_closing_action_notification(
            _("Day Closed"),
            _("The selected day has been closed and linked visits, daily plans, and vehicle closings are now locked."),
        )

    def _reopen_day_with_reason(self, closing_record, reopen_reason):
        self.ensure_one()
        reason = (reopen_reason or "").strip()
        if not closing_record or closing_record.state != "closed":
            raise UserError(_("There is no closed day to reopen for the selected filters."))
        if not reason:
            raise UserError(_("Please enter a Reopen Reason before reopening the day."))
        closing_record._ensure_initial_close_audit_line()
        before_state = closing_record.state
        closing_record.write({
            "state": "reopened",
            "reopened_by_id": self.env.user.id,
            "reopened_at": fields.Datetime.now(),
            "reopen_reason": reason,
        })
        closing_record._create_audit_line(
            "reopen_day",
            reason,
            state_from=before_state,
            state_to="reopened",
        )
        self._unlink_daily_closing_from_operational_records(closing_record)
        return self._daily_closing_action_notification(
            _("Day Reopened"),
            _("The selected day has been reopened. Validate and close it again after completing the required corrections."),
            "warning",
        )

    def action_open_reopen_day_wizard(self):
        self.ensure_one()
        closing_record = self._get_daily_closing_record()
        if not closing_record or closing_record.state != "closed":
            raise UserError(_("There is no closed day to reopen for the selected filters."))
        view = self.env.ref("route_core.view_route_daily_closing_reopen_wizard_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Reopen Closed Day"),
            "res_model": "route.daily.closing.reopen.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_dashboard_id": self.id,
                "default_closing_id": closing_record.id,
                "default_company_id": self.company_id.id,
                "default_closing_date": self.closing_date,
                "default_salesperson_id": self.salesperson_id.id,
                "default_vehicle_id": self.vehicle_id.id,
                "default_city_id": self.city_id.id,
                "default_area_id": self.area_id.id,
                "default_outlet_id": self.outlet_id.id,
            },
        }
        if view:
            action["views"] = [(view.id, "form")]
            action["view_id"] = view.id
        return action

    def action_reopen_day(self):
        self.ensure_one()
        closing_record = self._get_daily_closing_record()
        if not (self.reopen_reason or "").strip():
            return self.action_open_reopen_day_wizard()
        return self._reopen_day_with_reason(closing_record, self.reopen_reason)

    def action_open_daily_closing_record(self):
        self.ensure_one()
        closing_record = self._get_daily_closing_record()
        if not closing_record:
            raise UserError(_("No daily closing record exists yet for the selected filters."))
        closing_record._ensure_initial_close_audit_line()
        closing_record._ensure_scope_labels()
        action = self.env.ref("route_core.action_route_daily_closing", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Daily Closing Record"),
            "res_model": "route.daily.closing",
            "view_mode": "form",
        }
        form_view = self.env.ref("route_core.view_route_daily_closing_form", raise_if_not_found=False)
        result.update({
            "res_id": closing_record.id,
            "views": [(form_view.id, "form")] if form_view else [(False, "form")],
            "target": "current",
        })
        return result

    def action_refresh_dashboard(self):
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_open_daily_control(self):
        server_action = self.env.ref("route_core.server_action_open_route_supervisor_daily_control", raise_if_not_found=False)
        if server_action:
            return server_action.run()
        return {"type": "ir.actions.client", "tag": "reload"}

    def _action_open_visits(self, name, domain):
        self.ensure_one()
        views = []
        kanban_view = self.env.ref("route_core.view_route_supervisor_daily_visit_kanban", raise_if_not_found=False)
        list_view = self.env.ref("route_core.view_route_visit_tree", raise_if_not_found=False)
        form_view = self.env.ref("route_core.view_route_visit_form", raise_if_not_found=False)
        if kanban_view:
            views.append((kanban_view.id, "kanban"))
        if list_view:
            views.append((list_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))
        action = {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": "route.visit",
            "view_mode": "kanban,list,form",
            "domain": domain,
            "context": {"create": False, "edit": True, "delete": False},
        }
        if views:
            action["views"] = views
        search_view = self.env.ref("route_core.view_route_supervisor_daily_visit_search", raise_if_not_found=False)
        if search_view:
            action["search_view_id"] = search_view.id
        return action

    def action_open_all_visits(self):
        return self._action_open_visits(_("Daily Visits"), self._base_visit_domain())

    def action_open_unfinished_visits(self):
        return self._action_open_visits(
            _("Unfinished Visits"),
            self._base_visit_domain() + [("visit_process_state", "not in", ["done", "cancel"])],
        )

    def action_open_not_started_visits(self):
        return self._action_open_visits(
            _("Not Started Visits"),
            self._base_visit_domain() + [("visit_process_state", "=", "draft")],
        )

    def action_open_location_issues(self):
        self.ensure_one()
        visits, plans, closings, proposals, open_promises, pending_transfers, sale_orders, direct_returns = self._collect_dashboard_data()
        visits = self._location_review_issue_visits(visits)
        return self._action_open_visits(_("Location Review Pending"), [("id", "in", visits.ids or [0])])

    def action_open_open_due_visits(self):
        self.ensure_one()
        visits, plans, closings, proposals, open_promises, pending_transfers, sale_orders, direct_returns = self._collect_dashboard_data()
        visits = self._uncovered_due_visits(visits, open_promises)
        return self._action_open_visits(_("Visits With Open Due"), [("id", "in", visits.ids or [0])])

    def action_open_daily_plans(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_plan", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Daily Plans"),
            "res_model": "route.plan",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Daily Plans to Close"),
            "domain": [("id", "in", self.daily_plan_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_vehicle_closings(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_vehicle_closing", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Vehicle Closings"),
            "res_model": "route.vehicle.closing",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Vehicle Closings to Review"),
            "domain": [("id", "in", self.vehicle_closing_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_missing_vehicle_closing_plans(self):
        self.ensure_one()
        missing_plans = self.daily_plan_ids.filtered(
            lambda plan: plan.vehicle_id and plan not in self.vehicle_closing_ids.mapped("plan_id")
        )
        action = self.action_open_daily_plans()
        action.update({
            "name": _("Plans Missing Vehicle Closing"),
            "domain": [("id", "in", missing_plans.ids or [0])],
        })
        return action

    def action_open_loading_proposals(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_loading_proposal", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Loading Proposals"),
            "res_model": "route.loading.proposal",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Loading Proposals to Review"),
            "domain": [("id", "in", self.loading_proposal_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_pending_loading_proposals(self):
        self.ensure_one()
        pending_loading = self.loading_proposal_ids.filtered(
            lambda proposal: proposal.state not in ["approved", "cancelled"]
            or (proposal.picking_id and proposal.picking_id.state not in ["done", "cancel"])
        )
        action = self.action_open_loading_proposals()
        action.update({
            "name": _("Pending Loading Proposals"),
            "domain": [("id", "in", pending_loading.ids or [0])],
        })
        return action

    def action_open_pending_transfers(self):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Pending Transfers"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Pending Transfers"),
            "domain": [("id", "in", self.pending_transfer_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_promises(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit_payment", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Open Promises"),
            "res_model": "route.visit.payment",
            "view_mode": "kanban,list,form",
        }
        blocking_promises = self._blocking_promises(self.open_promise_payment_ids)
        promises_to_open = blocking_promises or self.open_promise_payment_ids
        result.update({
            "name": _("Due / Overdue Promises") if blocking_promises else _("Open Promises"),
            "domain": [("id", "in", promises_to_open.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False, "daily_closing_review_date": self.closing_date},
        })
        return result


    def action_open_sales_orders(self):
        self.ensure_one()
        action = self.env.ref("sale.action_orders", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Sales Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
        }
        result.update({
            "name": _("Sales Orders to Review"),
            "domain": [("id", "in", self.sale_order_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_direct_returns(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_direct_return", raise_if_not_found=False)
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": _("Return Orders"),
            "res_model": "route.direct.return",
            "view_mode": "kanban,list,form",
        }
        result.update({
            "name": _("Return Orders to Review"),
            "domain": [("id", "in", self.direct_return_ids.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_pending_sale_orders(self):
        self.ensure_one()
        sale_orders = self.sale_order_ids.filtered(lambda order: order.state in ["draft", "sent"])
        action = self.action_open_sales_orders()
        action.update({
            "name": _("Pending Sales Orders"),
            "domain": [("id", "in", sale_orders.ids or [0])],
        })
        return action

    def action_open_pending_direct_returns(self):
        self.ensure_one()
        direct_returns = self.direct_return_ids.filtered(lambda direct_return: direct_return.state == "draft")
        action = self.action_open_direct_returns()
        action.update({
            "name": _("Pending Return Orders"),
            "domain": [("id", "in", direct_returns.ids or [0])],
        })
        return action


class RouteDailyClosingReopenWizard(models.TransientModel):
    _name = "route.daily.closing.reopen.wizard"
    _description = "Reopen Route Daily Closing"

    dashboard_id = fields.Many2one(
        "route.supervisor.daily.closing",
        string="Dashboard",
        required=True,
        readonly=True,
    )
    closing_id = fields.Many2one(
        "route.daily.closing",
        string="Daily Closing",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    closing_date = fields.Date(string="Closing Date", readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle", readonly=True)
    city_id = fields.Many2one("route.city", string="City", readonly=True)
    area_id = fields.Many2one("route.area", string="Area", readonly=True)
    outlet_id = fields.Many2one("route.outlet", string="Outlet", readonly=True)
    reopen_reason = fields.Text(string="Reopen Reason", required=True)

    def action_confirm_reopen(self):
        self.ensure_one()
        if not (self.reopen_reason or "").strip():
            raise UserError(_("Please enter a Reopen Reason before reopening the day."))
        dashboard = self.dashboard_id.exists()
        if not dashboard:
            raise UserError(_("The daily closing dashboard is no longer available. Please refresh and try again."))
        return dashboard._reopen_day_with_reason(self.closing_id, self.reopen_reason)


class RouteDailyClosing(models.Model):
    _name = "route.daily.closing"
    _description = "Route Daily Closing"
    _order = "closing_date desc, id desc"

    name = fields.Char(string="Reference", required=True, default=lambda self: _("Daily Closing"), copy=False)
    state = fields.Selection(
        [("closed", "Closed"), ("reopened", "Reopened")],
        string="Status",
        default="closed",
        required=True,
        copy=False,
    )
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one("res.currency", string="Currency", related="company_id.currency_id", readonly=True)
    closing_date = fields.Date(string="Closing Date", required=True, default=fields.Date.context_today)
    salesperson_id = fields.Many2one("res.users", string="Salesperson")
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle")
    city_id = fields.Many2one("route.city", string="City")
    area_id = fields.Many2one("route.area", string="Area")
    outlet_id = fields.Many2one("route.outlet", string="Outlet")
    scope_label = fields.Char(string="Closing Scope", readonly=True)
    salesperson_scope_label = fields.Char(string="Salespersons", readonly=True)
    vehicle_scope_label = fields.Char(string="Vehicles", readonly=True)
    city_scope_label = fields.Char(string="Cities", readonly=True)
    area_scope_label = fields.Char(string="Areas", readonly=True)
    outlet_scope_label = fields.Char(string="Outlets", readonly=True)
    salesperson_scope_count = fields.Integer(string="Salesperson Count", readonly=True)
    vehicle_scope_count = fields.Integer(string="Vehicle Count", readonly=True)
    city_scope_count = fields.Integer(string="City Count", readonly=True)
    area_scope_count = fields.Integer(string="Area Count", readonly=True)
    outlet_scope_count = fields.Integer(string="Outlet Count", readonly=True)
    closed_by_id = fields.Many2one("res.users", string="Closed By", readonly=True, copy=False)
    closed_at = fields.Datetime(string="Closed At", readonly=True, copy=False)
    reopened_by_id = fields.Many2one("res.users", string="Reopened By", readonly=True, copy=False)
    reopened_at = fields.Datetime(string="Reopened At", readonly=True, copy=False)
    closing_note = fields.Text(string="Closing Notes")
    reopen_reason = fields.Text(string="Reopen Reason")

    blocker_count = fields.Integer(string="Blockers", readonly=True)
    plan_count = fields.Integer(string="Daily Plans", readonly=True)
    not_finalized_plan_count = fields.Integer(string="Not Finalized Plans", readonly=True)
    visit_count = fields.Integer(string="Visits", readonly=True)
    done_visit_count = fields.Integer(string="Done Visits", readonly=True)
    unfinished_visit_count = fields.Integer(string="Unfinished Visits", readonly=True)
    location_issue_count = fields.Integer(string="Location Reviews", readonly=True)
    open_due_visit_count = fields.Integer(string="Open Due Visits", readonly=True)
    open_due_amount = fields.Monetary(string="Open Due", currency_field="currency_id", readonly=True)
    open_promise_count = fields.Integer(string="Open Promises", readonly=True)
    open_promise_amount = fields.Monetary(string="Promise Amount", currency_field="currency_id", readonly=True)
    vehicle_closing_count = fields.Integer(string="Vehicle Closings", readonly=True)
    vehicle_closing_closed_count = fields.Integer(string="Closed Vehicle Closings", readonly=True)
    vehicle_closing_pending_count = fields.Integer(string="Pending Vehicle Closings", readonly=True)
    vehicle_closing_missing_count = fields.Integer(string="Missing Vehicle Closings", readonly=True)
    loading_proposal_count = fields.Integer(string="Loading Proposals", readonly=True)
    loading_pending_count = fields.Integer(string="Pending Loading", readonly=True)
    pending_transfer_count = fields.Integer(string="Pending Transfers", readonly=True)
    return_transfer_count = fields.Integer(string="Return Transfers", readonly=True)
    refill_transfer_count = fields.Integer(string="Refill Transfers", readonly=True)
    sale_order_count = fields.Integer(string="Sales Orders", readonly=True)
    pending_sale_order_count = fields.Integer(string="Pending Sales Orders", readonly=True)
    sale_order_amount = fields.Monetary(string="Sales Order Amount", currency_field="currency_id", readonly=True)
    direct_return_count = fields.Integer(string="Return Orders", readonly=True)
    pending_direct_return_count = fields.Integer(string="Pending Return Orders", readonly=True)
    direct_return_amount = fields.Monetary(string="Return Order Amount", currency_field="currency_id", readonly=True)

    visit_ids = fields.Many2many("route.visit", string="Visits", readonly=True)
    plan_ids = fields.Many2many("route.plan", string="Daily Plans", readonly=True)
    vehicle_closing_ids = fields.Many2many("route.vehicle.closing", string="Vehicle Closings", readonly=True)
    loading_proposal_ids = fields.Many2many("route.loading.proposal", string="Loading Proposals", readonly=True)
    open_promise_payment_ids = fields.Many2many(
        "route.visit.payment",
        "route_daily_closing_open_promise_payment_rel",
        "closing_id",
        "payment_id",
        string="Open Promises",
        readonly=True,
    )
    pending_transfer_ids = fields.Many2many(
        "stock.picking",
        "route_daily_closing_pending_transfer_rel",
        "closing_id",
        "picking_id",
        string="Pending Transfers",
        readonly=True,
    )
    return_transfer_ids = fields.Many2many(
        "stock.picking",
        "route_daily_closing_return_transfer_rel",
        "closing_id",
        "picking_id",
        string="Return Transfers",
        readonly=True,
    )
    refill_transfer_ids = fields.Many2many(
        "stock.picking",
        "route_daily_closing_refill_transfer_rel",
        "closing_id",
        "picking_id",
        string="Refill Transfers",
        readonly=True,
    )
    sale_order_ids = fields.Many2many("sale.order", string="Sales Orders", readonly=True)
    direct_return_ids = fields.Many2many("route.direct.return", string="Return Orders", readonly=True)
    audit_line_ids = fields.One2many(
        "route.daily.closing.audit.line",
        "closing_id",
        string="Audit Trail",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = _("Daily Closing")
        return super().create(vals_list)

    def _create_audit_line(self, event_type, note=False, state_from=False, state_to=False, event_datetime=False):
        for rec in self:
            self.env["route.daily.closing.audit.line"].sudo().create({
                "closing_id": rec.id,
                "event_type": event_type,
                "user_id": self.env.user.id,
                "event_datetime": event_datetime or fields.Datetime.now(),
                "state_from": state_from or False,
                "state_to": state_to or False,
                "note": note or False,
            })

    def _ensure_initial_close_audit_line(self):
        """Backfill the first Close Day audit row for records created by older builds."""
        for rec in self:
            has_initial_close = rec.audit_line_ids.filtered(lambda line: line.event_type in ("close_day", "closed"))
            if not has_initial_close:
                rec._create_audit_line(
                    "close_day",
                    rec.closing_note or _("Day closed from Supervisor Daily Closing."),
                    state_from="open",
                    state_to="closed",
                    event_datetime=rec.closed_at or rec.create_date or fields.Datetime.now(),
                )

    def _scope_label_value(self, selected_record, record_count, all_label):
        if selected_record:
            return selected_record.display_name
        if record_count:
            return _("%(label)s (%(count)s)") % {"label": all_label, "count": record_count}
        return all_label

    def _ensure_scope_labels(self):
        """Backfill readable scope cards for records created before this feature."""
        for rec in self:
            if rec.scope_label and rec.salesperson_scope_label and rec.vehicle_scope_label and rec.city_scope_label and rec.area_scope_label and rec.outlet_scope_label:
                continue

            salespersons = rec.visit_ids.mapped("user_id") | rec.plan_ids.mapped("user_id")
            vehicles = rec.visit_ids.mapped("vehicle_id") | rec.plan_ids.mapped("vehicle_id") | rec.vehicle_closing_ids.mapped("vehicle_id")
            outlets = rec.visit_ids.mapped("outlet_id") | rec.plan_ids.mapped("line_ids.outlet_id")
            areas = rec.visit_ids.mapped("area_id") | rec.plan_ids.mapped("area_id") | rec.plan_ids.mapped("line_ids.area_id") | outlets.mapped("area_id")
            cities = areas.mapped("city_id") | outlets.mapped("route_city_id")

            if rec.salesperson_id:
                salespersons |= rec.salesperson_id
            if rec.vehicle_id:
                vehicles |= rec.vehicle_id
            if rec.outlet_id:
                outlets |= rec.outlet_id
            if rec.area_id:
                areas |= rec.area_id
            if rec.city_id:
                cities |= rec.city_id

            selected_filters = []
            if rec.salesperson_id:
                selected_filters.append(_("Salesperson"))
            if rec.vehicle_id:
                selected_filters.append(_("Vehicle"))
            if rec.city_id:
                selected_filters.append(_("City"))
            if rec.area_id:
                selected_filters.append(_("Area"))
            if rec.outlet_id:
                selected_filters.append(_("Outlet"))

            scope_label = _("Full Company Day Closing")
            if selected_filters:
                scope_label = _("Filtered Closing by %s") % ", ".join(selected_filters)

            rec.sudo().write({
                "scope_label": scope_label,
                "salesperson_scope_count": len(salespersons),
                "vehicle_scope_count": len(vehicles),
                "city_scope_count": len(cities),
                "area_scope_count": len(areas),
                "outlet_scope_count": len(outlets),
                "salesperson_scope_label": rec._scope_label_value(rec.salesperson_id, len(salespersons), _("All Salespersons")),
                "vehicle_scope_label": rec._scope_label_value(rec.vehicle_id, len(vehicles), _("All Vehicles")),
                "city_scope_label": rec._scope_label_value(rec.city_id, len(cities), _("All Cities")),
                "area_scope_label": rec._scope_label_value(rec.area_id, len(areas), _("All Areas")),
                "outlet_scope_label": rec._scope_label_value(rec.outlet_id, len(outlets), _("All Outlets")),
            })

    def _action_open_related_records(self, name, records, res_model, view_mode="list,form", action_xmlid=False):
        self.ensure_one()
        action = self.env.ref(action_xmlid, raise_if_not_found=False) if action_xmlid else False
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "view_mode": view_mode,
        }
        result.update({
            "name": name,
            "res_model": res_model,
            "view_mode": view_mode,
            "domain": [("id", "in", records.ids or [0])],
            "context": {"create": False, "edit": True, "delete": False},
        })
        return result

    def action_open_visits(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Visits"), self.visit_ids, "route.visit", "kanban,list,form")

    def action_open_daily_plans(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Daily Plans"), self.plan_ids, "route.plan", "list,form")

    def action_open_vehicle_closings(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Vehicle Closings"), self.vehicle_closing_ids, "route.vehicle.closing", "list,form")

    def action_open_loading_proposals(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Loading Proposals"), self.loading_proposal_ids, "route.loading.proposal", "list,form")

    def action_open_location_review_visits(self):
        self.ensure_one()
        location_review_visits = self.visit_ids.filtered(
            lambda visit: visit.geo_review_required
            or visit.geo_review_supervisor_decision == "needs_correction"
            or visit.geo_review_state in ["outlet_missing", "pending_checkin"]
        )
        return self._action_open_related_records(_("Closing Location Review Visits"), location_review_visits, "route.visit", "kanban,list,form")

    def action_open_open_due_visits(self):
        self.ensure_one()
        due_visits = self.visit_ids.filtered(lambda visit: (visit.remaining_due_amount or 0.0) > 0.0)
        return self._action_open_related_records(_("Closing Open Due Visits"), due_visits, "route.visit", "kanban,list,form")

    def action_open_promises(self):
        self.ensure_one()
        action_xmlid = "route_core.action_route_visit_payment" if self.env.ref("route_core.action_route_visit_payment", raise_if_not_found=False) else False
        return self._action_open_related_records(
            _("Closing Open Promises"),
            self.open_promise_payment_ids,
            "route.visit.payment",
            "kanban,list,form",
            action_xmlid,
        )

    def action_open_pending_transfers(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Pending Transfers"), self.pending_transfer_ids, "stock.picking", "list,form")

    def action_open_return_transfers(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Return Transfers"), self.return_transfer_ids, "stock.picking", "list,form")

    def action_open_refill_transfers(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Refill Transfers"), self.refill_transfer_ids, "stock.picking", "list,form")

    def action_open_sales_orders(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Sales Orders"), self.sale_order_ids, "sale.order", "list,form", "sale.action_orders")

    def action_open_direct_returns(self):
        self.ensure_one()
        return self._action_open_related_records(_("Closing Return Orders"), self.direct_return_ids, "route.direct.return", "kanban,list,form")

    @api.model
    def _route_closed_closing_domain_for_values(self, company_id, closing_date, salesperson_id=False, vehicle_id=False, city_id=False, area_id=False, outlet_id=False):
        return [
            ("company_id", "=", company_id or self.env.company.id),
            ("closing_date", "=", closing_date),
            ("state", "=", "closed"),
            "|", ("salesperson_id", "=", False), ("salesperson_id", "=", salesperson_id or False),
            "|", ("vehicle_id", "=", False), ("vehicle_id", "=", vehicle_id or False),
            "|", ("city_id", "=", False), ("city_id", "=", city_id or False),
            "|", ("area_id", "=", False), ("area_id", "=", area_id or False),
            "|", ("outlet_id", "=", False), ("outlet_id", "=", outlet_id or False),
        ]

    @api.model
    def _find_closed_closing_for_values(self, company_id, closing_date, salesperson_id=False, vehicle_id=False, city_id=False, area_id=False, outlet_id=False):
        if not closing_date:
            return self.browse()
        # Salespeople do not need direct menu access to Route Daily Closing records,
        # but visit/plan write guards must still be able to check whether the day
        # is closed. Use sudo for the internal lock lookup only.
        closing_model = self.sudo()
        return closing_model.search(
            closing_model._route_closed_closing_domain_for_values(
                company_id=company_id,
                closing_date=closing_date,
                salesperson_id=salesperson_id,
                vehicle_id=vehicle_id,
                city_id=city_id,
                area_id=area_id,
                outlet_id=outlet_id,
            ),
            limit=1,
        )


class RouteDailyClosingAuditLine(models.Model):
    _name = "route.daily.closing.audit.line"
    _description = "Route Daily Closing Audit Line"
    _order = "event_datetime desc, id desc"

    closing_id = fields.Many2one(
        "route.daily.closing",
        string="Daily Closing",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_type = fields.Selection(
        [
            ("close_day", "Close Day"),
            ("reopen_day", "Reopen Day"),
            ("close_day_again", "Close Day Again"),
            # Kept for compatibility with audit rows created by earlier builds.
            ("closed", "Closed"),
            ("reopened", "Reopened"),
        ],
        string="Event",
        required=True,
        default="close_day",
    )
    event_label = fields.Char(string="Event Label", compute="_compute_event_label", store=True)
    user_id = fields.Many2one("res.users", string="User", required=True, default=lambda self: self.env.user)
    event_datetime = fields.Datetime(string="Date/Time", required=True, default=fields.Datetime.now)
    state_from = fields.Selection(
        [("open", "Open"), ("closed", "Closed"), ("reopened", "Reopened")],
        string="From Status",
        readonly=True,
    )
    state_to = fields.Selection(
        [("open", "Open"), ("closed", "Closed"), ("reopened", "Reopened")],
        string="To Status",
        readonly=True,
    )
    note = fields.Text(string="Note")

    @api.depends("event_type")
    def _compute_event_label(self):
        labels = {
            "close_day": _("Close Day"),
            "reopen_day": _("Reopen Day"),
            "close_day_again": _("Close Day Again"),
            "closed": _("Close Day"),
            "reopened": _("Reopen Day"),
        }
        for rec in self:
            rec.event_label = labels.get(rec.event_type, rec.event_type or "")


class RouteDailyClosingLockedRecordMixin(models.AbstractModel):
    _name = "route.daily.closing.lock.mixin"
    _description = "Route Daily Closing Lock Helper"

    daily_closing_id = fields.Many2one("route.daily.closing", string="Daily Closing", copy=False, readonly=True)
    is_daily_closed = fields.Boolean(string="Daily Closed", compute="_compute_is_daily_closed")

    @api.depends("daily_closing_id", "daily_closing_id.state")
    def _compute_is_daily_closed(self):
        for rec in self:
            closing = rec.sudo().daily_closing_id
            rec.is_daily_closed = bool(closing and closing.state == "closed")

    def _route_daily_closing_values(self, vals=None):
        self.ensure_one()
        vals = vals or {}
        company = getattr(self, "company_id", False)
        closing_date = vals.get("date") or vals.get("plan_date") or getattr(self, "date", False) or getattr(self, "plan_date", False)
        salesperson = self.env["res.users"].browse(vals["user_id"]) if vals.get("user_id") else getattr(self, "user_id", False)
        vehicle = self.env["route.vehicle"].browse(vals["vehicle_id"]) if vals.get("vehicle_id") else getattr(self, "vehicle_id", False)
        area = self.env["route.area"].browse(vals["area_id"]) if vals.get("area_id") else getattr(self, "area_id", False)
        outlet = self.env["route.outlet"].browse(vals["outlet_id"]) if vals.get("outlet_id") else getattr(self, "outlet_id", False)
        city = False
        if outlet and outlet.exists() and outlet.route_city_id:
            city = outlet.route_city_id
        elif area and area.exists() and area.city_id:
            city = area.city_id
        return {
            "company_id": company.id if company else self.env.company.id,
            "closing_date": closing_date,
            "salesperson_id": salesperson.id if salesperson else False,
            "vehicle_id": vehicle.id if vehicle else False,
            "city_id": city.id if city else False,
            "area_id": area.id if area else False,
            "outlet_id": outlet.id if outlet else False,
        }

    def _find_route_daily_closed_record(self, vals=None):
        self.ensure_one()
        linked_closing = self.sudo().daily_closing_id
        if linked_closing and linked_closing.state == "closed":
            return linked_closing
        closing_values = self._route_daily_closing_values(vals=vals)
        return self.env["route.daily.closing"].sudo()._find_closed_closing_for_values(**closing_values)

    def _ensure_not_route_daily_closed(self, vals=None):
        if self.env.context.get("bypass_daily_closing_lock"):
            return
        for rec in self:
            closing = rec._find_route_daily_closed_record(vals=vals)
            if closing:
                raise UserError(
                    _(
                        "This record is locked because the related day is closed by Supervisor Daily Closing (%s). "
                        "Reopen the day before making changes."
                    )
                    % (closing.display_name,)
                )


class RouteVisitDailyClosingLock(models.Model):
    _inherit = "route.visit"

    daily_closing_id = fields.Many2one("route.daily.closing", string="Daily Closing", copy=False, readonly=True)
    is_daily_closed = fields.Boolean(string="Daily Closed", compute="_compute_is_daily_closed")

    @api.depends("daily_closing_id", "daily_closing_id.state")
    def _compute_is_daily_closed(self):
        for rec in self:
            closing = rec.sudo().daily_closing_id
            rec.is_daily_closed = bool(closing and closing.state == "closed")

    def _route_daily_closing_values(self, vals=None):
        self.ensure_one()
        vals = vals or {}
        company = getattr(self, "company_id", False)
        closing_date = vals.get("date") or getattr(self, "date", False)
        salesperson = self.env["res.users"].browse(vals["user_id"]) if vals.get("user_id") else getattr(self, "user_id", False)
        vehicle = self.env["route.vehicle"].browse(vals["vehicle_id"]) if vals.get("vehicle_id") else getattr(self, "vehicle_id", False)
        area = self.env["route.area"].browse(vals["area_id"]) if vals.get("area_id") else getattr(self, "area_id", False)
        outlet = self.env["route.outlet"].browse(vals["outlet_id"]) if vals.get("outlet_id") else getattr(self, "outlet_id", False)
        city = False
        if outlet and outlet.exists() and outlet.route_city_id:
            city = outlet.route_city_id
        elif area and area.exists() and area.city_id:
            city = area.city_id
        return {
            "company_id": company.id if company else self.env.company.id,
            "closing_date": closing_date,
            "salesperson_id": salesperson.id if salesperson else False,
            "vehicle_id": vehicle.id if vehicle else False,
            "city_id": city.id if city else False,
            "area_id": area.id if area else False,
            "outlet_id": outlet.id if outlet else False,
        }

    def _find_route_daily_closed_record(self, vals=None):
        self.ensure_one()
        linked_closing = self.sudo().daily_closing_id
        if linked_closing and linked_closing.state == "closed":
            return linked_closing
        closing_values = self._route_daily_closing_values(vals=vals)
        return self.env["route.daily.closing"].sudo()._find_closed_closing_for_values(**closing_values)

    def _ensure_not_route_daily_closed(self, vals=None):
        if self.env.context.get("bypass_daily_closing_lock"):
            return
        for rec in self:
            closing = rec._find_route_daily_closed_record(vals=vals)
            if closing:
                raise UserError(
                    _(
                        "This record is locked because the related day is closed by Supervisor Daily Closing (%s). "
                        "Reopen the day before making changes."
                    )
                    % (closing.display_name,)
                )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("bypass_daily_closing_lock"):
            for vals in vals_list:
                outlet = self.env["route.outlet"].browse(vals.get("outlet_id")) if vals.get("outlet_id") else False
                area = self.env["route.area"].browse(vals.get("area_id")) if vals.get("area_id") else False
                city = False
                if outlet and outlet.exists() and outlet.route_city_id:
                    city = outlet.route_city_id
                elif area and area.exists() and area.city_id:
                    city = area.city_id
                closing = self.env["route.daily.closing"].sudo()._find_closed_closing_for_values(
                    company_id=vals.get("company_id") or self.env.company.id,
                    closing_date=vals.get("date"),
                    salesperson_id=vals.get("user_id") or False,
                    vehicle_id=vals.get("vehicle_id") or False,
                    city_id=city.id if city else False,
                    area_id=area.id if area else False,
                    outlet_id=outlet.id if outlet else False,
                )
                if closing:
                    raise UserError(_("You cannot create a visit for a closed day. Reopen the day first."))
        return super().create(vals_list)

    def write(self, vals):
        if set(vals.keys()) - {"daily_closing_id"}:
            self._ensure_not_route_daily_closed(vals=vals)
        return super().write(vals)

    def unlink(self):
        self._ensure_not_route_daily_closed()
        return super().unlink()


class RoutePlanDailyClosingLock(models.Model):
    _inherit = "route.plan"

    daily_closing_id = fields.Many2one("route.daily.closing", string="Daily Closing", copy=False, readonly=True)
    is_daily_closed = fields.Boolean(string="Daily Closed", compute="_compute_is_daily_closed")

    @api.depends("daily_closing_id", "daily_closing_id.state")
    def _compute_is_daily_closed(self):
        for rec in self:
            closing = rec.sudo().daily_closing_id
            rec.is_daily_closed = bool(closing and closing.state == "closed")

    def _route_daily_closing_values(self, vals=None):
        self.ensure_one()
        vals = vals or {}
        company = getattr(self, "company_id", False)
        closing_date = vals.get("date") or getattr(self, "date", False)
        salesperson = self.env["res.users"].browse(vals["user_id"]) if vals.get("user_id") else getattr(self, "user_id", False)
        vehicle = self.env["route.vehicle"].browse(vals["vehicle_id"]) if vals.get("vehicle_id") else getattr(self, "vehicle_id", False)
        area = self.env["route.area"].browse(vals["area_id"]) if vals.get("area_id") else getattr(self, "area_id", False)
        city = area.city_id if area and area.exists() and area.city_id else False
        return {
            "company_id": company.id if company else self.env.company.id,
            "closing_date": closing_date,
            "salesperson_id": salesperson.id if salesperson else False,
            "vehicle_id": vehicle.id if vehicle else False,
            "city_id": city.id if city else False,
            "area_id": area.id if area else False,
            "outlet_id": False,
        }

    def _find_route_daily_closed_record(self, vals=None):
        self.ensure_one()
        linked_closing = self.sudo().daily_closing_id
        if linked_closing and linked_closing.state == "closed":
            return linked_closing
        closing_values = self._route_daily_closing_values(vals=vals)
        return self.env["route.daily.closing"].sudo()._find_closed_closing_for_values(**closing_values)

    def _ensure_not_route_daily_closed(self, vals=None):
        if self.env.context.get("bypass_daily_closing_lock"):
            return
        for rec in self:
            closing = rec._find_route_daily_closed_record(vals=vals)
            if closing:
                raise UserError(
                    _(
                        "This record is locked because the related day is closed by Supervisor Daily Closing (%s). "
                        "Reopen the day before making changes."
                    )
                    % (closing.display_name,)
                )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("bypass_daily_closing_lock"):
            for vals in vals_list:
                closing_values = {
                    "company_id": vals.get("company_id") or self.env.company.id,
                    "closing_date": vals.get("date"),
                    "salesperson_id": vals.get("user_id") or False,
                    "vehicle_id": vals.get("vehicle_id") or False,
                    "city_id": False,
                    "area_id": vals.get("area_id") or False,
                    "outlet_id": False,
                }
                if closing_values["area_id"]:
                    area = self.env["route.area"].browse(closing_values["area_id"])
                    closing_values["city_id"] = area.city_id.id if area and area.exists() and area.city_id else False
                closing = self.env["route.daily.closing"].sudo()._find_closed_closing_for_values(**closing_values)
                if closing:
                    raise UserError(_("You cannot create a route plan for a closed day. Reopen the day first."))
        return super().create(vals_list)

    def write(self, vals):
        if set(vals.keys()) - {"daily_closing_id"}:
            self._ensure_not_route_daily_closed(vals=vals)
        return super().write(vals)

    def unlink(self):
        self._ensure_not_route_daily_closed()
        return super().unlink()


class RoutePlanLineDailyClosingLock(models.Model):
    _inherit = "route.plan.line"

    daily_closing_id = fields.Many2one(related="plan_id.daily_closing_id", string="Daily Closing", readonly=True)
    is_daily_closed = fields.Boolean(related="plan_id.is_daily_closed", string="Daily Closed", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("bypass_daily_closing_lock"):
            for vals in vals_list:
                plan = self.env["route.plan"].browse(vals.get("plan_id")) if vals.get("plan_id") else False
                if plan and plan.exists():
                    plan._ensure_not_route_daily_closed()
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("bypass_daily_closing_lock"):
            self.mapped("plan_id")._ensure_not_route_daily_closed()
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("bypass_daily_closing_lock"):
            self.mapped("plan_id")._ensure_not_route_daily_closed()
        return super().unlink()


class RouteVehicleClosingDailyClosingLock(models.Model):
    _inherit = "route.vehicle.closing"

    daily_closing_id = fields.Many2one("route.daily.closing", string="Daily Closing", copy=False, readonly=True)
    is_daily_closed = fields.Boolean(string="Daily Closed", compute="_compute_is_daily_closed")

    @api.depends("daily_closing_id", "daily_closing_id.state")
    def _compute_is_daily_closed(self):
        for rec in self:
            closing = rec.sudo().daily_closing_id
            rec.is_daily_closed = bool(closing and closing.state == "closed")

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("bypass_daily_closing_lock"):
            for vals in vals_list:
                plan = self.env["route.plan"].browse(vals.get("plan_id")) if vals.get("plan_id") else False
                if plan and plan.exists():
                    plan._ensure_not_route_daily_closed()
        return super().create(vals_list)

    def _route_daily_closing_values(self, vals=None):
        self.ensure_one()
        vals = vals or {}
        plan = self.plan_id
        if vals.get("plan_id"):
            plan = self.env["route.plan"].browse(vals["plan_id"])
        area = plan.area_id if plan else False
        city = area.city_id if area else False
        return {
            "company_id": self.company_id.id if self.company_id else self.env.company.id,
            "closing_date": vals.get("plan_date") or self.plan_date,
            "salesperson_id": plan.user_id.id if plan and plan.user_id else False,
            "vehicle_id": plan.vehicle_id.id if plan and plan.vehicle_id else False,
            "city_id": city.id if city else False,
            "area_id": area.id if area else False,
            "outlet_id": False,
        }

    def _find_route_daily_closed_record(self, vals=None):
        self.ensure_one()
        linked_closing = self.sudo().daily_closing_id
        if linked_closing and linked_closing.state == "closed":
            return linked_closing
        closing_values = self._route_daily_closing_values(vals=vals)
        return self.env["route.daily.closing"].sudo()._find_closed_closing_for_values(**closing_values)

    def _ensure_not_route_daily_closed(self, vals=None):
        if self.env.context.get("bypass_daily_closing_lock"):
            return
        for rec in self:
            closing = rec._find_route_daily_closed_record(vals=vals)
            if closing:
                raise UserError(
                    _(
                        "This record is locked because the related day is closed by Supervisor Daily Closing (%s). "
                        "Reopen the day before making changes."
                    )
                    % (closing.display_name,)
                )

    def write(self, vals):
        if set(vals.keys()) - {"daily_closing_id"}:
            self._ensure_not_route_daily_closed(vals=vals)
        return super().write(vals)

    def unlink(self):
        self._ensure_not_route_daily_closed()
        return super().unlink()


class RouteVehicleClosingLineDailyClosingLock(models.Model):
    _inherit = "route.vehicle.closing.line"

    daily_closing_id = fields.Many2one(related="closing_id.daily_closing_id", string="Daily Closing", readonly=True)
    is_daily_closed = fields.Boolean(related="closing_id.is_daily_closed", string="Daily Closed", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("bypass_daily_closing_lock"):
            for vals in vals_list:
                closing = self.env["route.vehicle.closing"].browse(vals.get("closing_id")) if vals.get("closing_id") else False
                if closing and closing.exists():
                    closing._ensure_not_route_daily_closed()
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("bypass_daily_closing_lock"):
            self.mapped("closing_id")._ensure_not_route_daily_closed()
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("bypass_daily_closing_lock"):
            self.mapped("closing_id")._ensure_not_route_daily_closed()
        return super().unlink()


class RouteVisitPaymentSupervisorPromiseReview(models.Model):
    _inherit = "route.visit.payment"

    promise_review_decision = fields.Selection(
        [
            ("reschedule", "Rescheduled by Supervisor"),
            ("review_followup", "Reviewed for Follow-up"),
            ("keep_blocking", "Keep Blocking / Escalated"),
        ],
        string="Supervisor Review Decision",
        copy=False,
        readonly=True,
    )
    promise_review_for_closing_date = fields.Date(
        string="Reviewed For Closing Date",
        copy=False,
        readonly=True,
    )
    promise_review_followup_date = fields.Date(
        string="Next Follow-up Date",
        copy=False,
        readonly=True,
    )
    promise_reviewed_by_id = fields.Many2one(
        "res.users",
        string="Reviewed By",
        copy=False,
        readonly=True,
    )
    promise_reviewed_at = fields.Datetime(
        string="Reviewed At",
        copy=False,
        readonly=True,
    )
    promise_review_note = fields.Text(
        string="Supervisor Promise Review Note",
        copy=False,
        readonly=True,
    )

    @api.constrains("amount", "collection_type", "due_date", "promise_date", "promise_amount", "visit_id", "sale_order_id", "payment_mode")
    def _check_payment_rules(self):
        """Allow supervisor promise review to update old promise records safely.

        Some historical promise rows were created before the current stricter
        route.visit.payment validations. Reviewing an overdue promise may only
        change follow-up/review metadata, but Odoo still re-runs payment
        constraints for the whole record. The explicit context flag is used
        only by the supervisor review wizard; normal payment creation and
        editing continue to use the original financial validations.
        """
        if self.env.context.get("bypass_promise_review_validation"):
            return
        return super()._check_payment_rules()

    def _ensure_can_supervise_promise_review(self):
        if not (
            self.env.user.has_group("route_core.group_route_supervisor")
            or self.env.user.has_group("route_core.group_route_management")
        ):
            raise UserError(_("Only Route Supervisors or Route Management can review overdue promises."))

    def action_open_supervisor_promise_review(self):
        self.ensure_one()
        self._ensure_can_supervise_promise_review()
        if self.state == "cancelled":
            raise UserError(_("Cancelled payments cannot be reviewed for promise follow-up."))
        if (self.promise_amount or 0.0) <= 0.0:
            raise UserError(_("This payment has no promise amount to review."))
        closing_date = self.env.context.get("daily_closing_review_date") or fields.Date.context_today(self)
        review_view = self.env.ref("route_core.view_route_promise_review_wizard_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Supervisor Promise Review"),
            "res_model": "route.promise.review.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_payment_id": self.id,
                "default_closing_date": closing_date,
                "form_view_ref": "route_core.view_route_promise_review_wizard_form",
            },
        }
        if review_view:
            action["views"] = [(review_view.id, "form")]
            action["view_id"] = review_view.id
        return action


class RoutePromiseReviewWizard(models.TransientModel):
    _name = "route.promise.review.wizard"
    _description = "Supervisor Promise Review"

    payment_id = fields.Many2one(
        "route.visit.payment",
        string="Promise",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(related="payment_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="payment_id.currency_id", readonly=True)
    closing_date = fields.Date(string="Closing Date", required=True, readonly=True)
    outlet_id = fields.Many2one(related="payment_id.outlet_id", string="Outlet", readonly=True)
    salesperson_id = fields.Many2one(related="payment_id.salesperson_id", string="Salesperson", readonly=True)
    source_document_ref = fields.Char(related="payment_id.source_document_ref", string="Source Document", readonly=True)
    current_promise_date = fields.Date(related="payment_id.promise_date", string="Current Promise Date", readonly=True)
    current_promise_amount = fields.Monetary(
        related="payment_id.promise_amount",
        string="Promise Amount",
        currency_field="currency_id",
        readonly=True,
    )
    current_promise_status = fields.Selection(
        related="payment_id.promise_status",
        string="Current Promise Status",
        readonly=True,
    )
    decision = fields.Selection(
        [
            ("reschedule", "Reschedule / New Follow-up Date"),
            ("review_followup", "Reviewed - Follow Up Later"),
            ("keep_blocking", "Keep Blocking / Escalate"),
        ],
        string="Supervisor Decision",
        required=True,
        default="reschedule",
    )
    new_promise_date = fields.Date(string="New Follow-up Date")
    note = fields.Text(string="Supervisor Review Note", required=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        closing_date = fields.Date.to_date(
            vals.get("closing_date")
            or self.env.context.get("default_closing_date")
            or fields.Date.context_today(self)
        )
        if "new_promise_date" in fields_list and not vals.get("new_promise_date"):
            vals["new_promise_date"] = closing_date + timedelta(days=1)
        return vals

    @api.onchange("decision", "closing_date")
    def _onchange_decision_set_date(self):
        for rec in self:
            if rec.decision in ("reschedule", "review_followup") and not rec.new_promise_date:
                base_date = fields.Date.to_date(rec.closing_date or fields.Date.context_today(rec))
                rec.new_promise_date = base_date + timedelta(days=1)
            elif rec.decision == "keep_blocking":
                rec.new_promise_date = False

    def action_confirm_review(self):
        self.ensure_one()
        payment = self.payment_id
        payment._ensure_can_supervise_promise_review()

        closing_date = fields.Date.to_date(self.closing_date or fields.Date.context_today(self))
        new_date = fields.Date.to_date(self.new_promise_date) if self.new_promise_date else False
        if self.decision in ("reschedule", "review_followup"):
            if not new_date:
                raise UserError(_("Please set the new follow-up date."))
            if new_date <= closing_date:
                raise UserError(_("The new follow-up date must be after the closing date."))
        if not (self.note or "").strip():
            raise UserError(_("Please add a supervisor review note."))

        decision_labels = dict(self._fields["decision"].selection)
        reviewed_at = fields.Datetime.now()
        user_label = self.env.user.display_name
        note_line = _(
            "Supervisor Promise Review: %(decision)s. Closing Date: %(closing_date)s. "
            "Next Follow-up: %(followup)s. Reviewed By: %(user)s. Note: %(note)s"
        ) % {
            "decision": decision_labels.get(self.decision, self.decision),
            "closing_date": self.closing_date or "-",
            "followup": self.new_promise_date or _("No change"),
            "user": user_label,
            "note": (self.note or "").strip(),
        }
        existing_note = payment.note or ""
        values = {
            "promise_review_decision": self.decision,
            "promise_review_for_closing_date": self.closing_date,
            "promise_review_followup_date": self.new_promise_date if self.decision in ("reschedule", "review_followup") else False,
            "promise_reviewed_by_id": self.env.user.id,
            "promise_reviewed_at": reviewed_at,
            "promise_review_note": (self.note or "").strip(),
            "note": (existing_note + "\n\n" + note_line).strip() if existing_note else note_line,
        }
        if self.decision in ("reschedule", "review_followup"):
            values.update({
                "promise_date": self.new_promise_date,
                "due_date": self.new_promise_date if payment.collection_type == "defer_date" else payment.due_date,
            })

            # Normalize older deferred promise records when supervisor review updates
            # the promise date. This keeps route.visit.payment financial validation
            # active while fixing records that were saved as Cash before the stricter
            # deferred-mode rule was introduced.
            if payment.collection_type in ("defer_date", "next_visit") and payment.payment_mode != "deferred":
                values["payment_mode"] = "deferred"
        payment.with_context(
            bypass_daily_closing_lock=True,
            bypass_promise_review_validation=True,
        ).write(values)
        return {"type": "ir.actions.act_window_close"}


class RouteSupervisorDailyClosingIssue(models.TransientModel):
    _name = "route.supervisor.daily.closing.issue"
    _description = "Daily Closing Issue Card"
    _order = "sequence, id"

    dashboard_id = fields.Many2one(
        "route.supervisor.daily.closing",
        string="Dashboard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    code = fields.Selection(
        [
            ("unfinished_visits", "Unfinished Visits"),
            ("not_started_visits", "Not Started Visits"),
            ("location_issues", "Location Issues"),
            ("open_due", "Open Due"),
            ("open_promises", "Open Promises"),
            ("pending_sale_orders", "Pending Sales Orders"),
            ("pending_direct_returns", "Pending Return Orders"),
            ("not_finalized_plans", "Plans Not Finalized"),
            ("vehicle_closing_missing", "Vehicle Closing Missing"),
            ("vehicle_closing_pending", "Vehicle Closing Pending"),
            ("loading_pending", "Loading Pending"),
            ("pending_transfers", "Pending Transfers"),
            ("ready", "Ready"),
        ],
        string="Issue Type",
        required=True,
    )
    title = fields.Char(string="Title", required=True)
    subtitle = fields.Char(string="Description")
    count = fields.Integer(string="Count")
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    currency_id = fields.Many2one(related="dashboard_id.currency_id", readonly=True)
    severity = fields.Selection(
        [
            ("success", "Success"),
            ("info", "Info"),
            ("warning", "Warning"),
            ("danger", "Danger"),
        ],
        default="warning",
        required=True,
    )
    button_label = fields.Char(string="Button", default=lambda self: _("Open"))

    def action_open_issue_details(self):
        self.ensure_one()
        dashboard = self.dashboard_id
        if self.code == "unfinished_visits":
            return dashboard.action_open_unfinished_visits()
        if self.code == "not_started_visits":
            return dashboard.action_open_not_started_visits()
        if self.code == "location_issues":
            return dashboard.action_open_location_issues()
        if self.code == "open_due":
            return dashboard.action_open_open_due_visits()
        if self.code == "open_promises":
            return dashboard.action_open_promises()
        if self.code == "pending_sale_orders":
            return dashboard.action_open_pending_sale_orders()
        if self.code == "pending_direct_returns":
            return dashboard.action_open_pending_direct_returns()
        if self.code == "not_finalized_plans":
            return dashboard.action_open_daily_plans()
        if self.code == "vehicle_closing_missing":
            return dashboard.action_open_missing_vehicle_closing_plans()
        if self.code == "vehicle_closing_pending":
            return dashboard.action_open_vehicle_closings()
        if self.code == "loading_pending":
            return dashboard.action_open_pending_loading_proposals()
        if self.code == "pending_transfers":
            return dashboard.action_open_pending_transfers()
        return dashboard.action_refresh_dashboard()

