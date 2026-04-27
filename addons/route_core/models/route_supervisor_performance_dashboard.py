from collections import defaultdict
from datetime import date as pydate
from datetime import datetime, time, timedelta
from html import escape

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class RouteSupervisorPerformanceDashboard(models.TransientModel):
    _name = "route.supervisor.performance.dashboard"
    _description = "Supervisor Performance Dashboard"
    _rec_name = "name"

    name = fields.Char(
        string="Name",
        default=lambda self: _("Supervisor Performance Dashboard"),
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
    period_filter = fields.Selection(
        [
            ("today", "Today"),
            ("week", "This Week"),
            ("month", "This Month"),
            ("last_30", "Last 30 Days"),
            ("custom", "Custom Range"),
        ],
        string="Period",
        default="last_30",
        required=True,
    )
    date_from = fields.Date(
        string="From Date",
        required=True,
        default=lambda self: fields.Date.context_today(self) - timedelta(days=29),
    )
    date_to = fields.Date(
        string="To Date",
        required=True,
        default=fields.Date.context_today,
    )
    salesperson_id = fields.Many2one("res.users", string="Salesperson")
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle")
    city_id = fields.Many2one("route.city", string="City")
    area_id = fields.Many2one("route.area", string="Area")
    outlet_id = fields.Many2one("route.outlet", string="Outlet")

    filtered_visit_count = fields.Integer(string="Filtered Visits", compute="_compute_dashboard_html")
    completed_visit_count = fields.Integer(string="Completed Visits", compute="_compute_dashboard_html")
    collection_amount = fields.Monetary(string="Collected", currency_field="currency_id", compute="_compute_dashboard_html")
    net_sales_amount = fields.Monetary(string="Net Sales", currency_field="currency_id", compute="_compute_dashboard_html")
    open_promise_amount = fields.Monetary(string="Open Promises", currency_field="currency_id", compute="_compute_dashboard_html")
    gross_profit_amount = fields.Monetary(string="Estimated Gross Profit", currency_field="currency_id", compute="_compute_dashboard_html")

    executive_html = fields.Html(
        string="Executive Snapshot",
        compute="_compute_dashboard_html",
        sanitize=False,
        readonly=True,
    )
    visit_chart_html = fields.Html(
        string="Visit Performance",
        compute="_compute_dashboard_html",
        sanitize=False,
        readonly=True,
    )
    collection_chart_html = fields.Html(
        string="Collection Performance",
        compute="_compute_dashboard_html",
        sanitize=False,
        readonly=True,
    )
    product_chart_html = fields.Html(
        string="Products and Profit",
        compute="_compute_dashboard_html",
        sanitize=False,
        readonly=True,
    )
    ranking_html = fields.Html(
        string="Team and Operations Ranking",
        compute="_compute_dashboard_html",
        sanitize=False,
        readonly=True,
    )

    @api.model
    def action_open_performance_dashboard(self):
        today = fields.Date.context_today(self)
        dashboard = self.create(
            {
                "name": _("Supervisor Performance Dashboard"),
                "company_id": self.env.company.id,
                "period_filter": "last_30",
                "date_from": today - timedelta(days=29),
                "date_to": today,
            }
        )
        view = self.env.ref("route_core.view_route_supervisor_performance_dashboard_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Supervisor Performance Dashboard"),
            "res_model": "route.supervisor.performance.dashboard",
            "res_id": dashboard.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": True, "delete": False},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    @api.onchange("period_filter")
    def _onchange_period_filter(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.period_filter == "today":
                rec.date_from = today
                rec.date_to = today
            elif rec.period_filter == "week":
                rec.date_from = today - timedelta(days=today.weekday())
                rec.date_to = today
            elif rec.period_filter == "month":
                rec.date_from = today.replace(day=1)
                rec.date_to = today
            elif rec.period_filter == "last_30":
                rec.date_from = today - timedelta(days=29)
                rec.date_to = today

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

    def action_refresh_dashboard(self):
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_open_daily_closing(self):
        self.ensure_one()
        dashboard = self.env["route.supervisor.daily.closing"].create(
            {
                "name": _("Supervisor Daily Closing"),
                "company_id": self.company_id.id,
                "closing_date": self.date_to or fields.Date.context_today(self),
                "salesperson_id": self.salesperson_id.id or False,
                "vehicle_id": self.vehicle_id.id or False,
                "city_id": self.city_id.id or False,
                "area_id": self.area_id.id or False,
                "outlet_id": self.outlet_id.id or False,
            }
        )
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

    def action_open_visits(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(_("Dashboard Visits"), payload["visits"], "route.visit", "kanban,list,form")

    def action_open_unfinished_visits(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        visits = payload["visits"].filtered(lambda visit: visit.visit_process_state not in ("done", "cancel"))
        return self._action_open_records(_("Dashboard Unfinished Visits"), visits, "route.visit", "kanban,list,form")

    def action_open_location_review(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        visits = payload["location_issue_visits"]
        return self._action_open_records(_("Dashboard Location Review"), visits, "route.visit", "kanban,list,form")

    def action_open_collections(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(
            _("Dashboard Collections"),
            payload["payments"],
            "route.visit.payment",
            "kanban,list,form",
            "route_core.action_route_visit_payment",
        )

    def action_open_promises(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(
            _("Dashboard Open Promises"),
            payload["open_promises"],
            "route.visit.payment",
            "kanban,list,form",
            "route_core.action_route_visit_payment",
        )

    def action_open_sales_orders(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(_("Dashboard Sales Orders"), payload["sale_orders"], "sale.order", "list,form", "sale.action_orders")

    def action_open_returns(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(_("Dashboard Return Orders"), payload["direct_returns"], "route.direct.return", "kanban,list,form")

    def action_open_vehicle_issues(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        closings = payload["vehicle_closings"].filtered(
            lambda closing: closing.state != "closed" or (closing.pending_variance_line_count or 0) > 0 or (closing.pending_execution_line_count or 0) > 0
        )
        return self._action_open_records(_("Dashboard Vehicle Issues"), closings, "route.vehicle.closing", "list,form")

    def action_open_closing_records(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(_("Dashboard Closing Records"), payload["closing_records"], "route.daily.closing", "list,form")

    def _action_open_records(self, name, records, res_model, view_mode="list,form", action_xmlid=False):
        action = self.env.ref(action_xmlid, raise_if_not_found=False) if action_xmlid else False
        result = action.read()[0] if action else {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "view_mode": view_mode,
        }
        result.update(
            {
                "name": name,
                "res_model": res_model,
                "view_mode": view_mode,
                "domain": [("id", "in", records.ids or [0])],
                "context": {"create": False, "edit": True, "delete": False},
            }
        )
        if res_model == "route.visit.payment" and "kanban" in (view_mode or ""):
            kanban_view = self.env.ref("route_core.view_route_visit_collection_kanban", raise_if_not_found=False)
            list_view = self.env.ref("route_core.view_route_visit_payment_list", raise_if_not_found=False)
            form_view = self.env.ref("route_core.view_route_visit_payment_form", raise_if_not_found=False)
            if kanban_view and list_view and form_view:
                result["views"] = [(kanban_view.id, "kanban"), (list_view.id, "list"), (form_view.id, "form")]
                result["view_id"] = kanban_view.id
        return result

    @api.depends(
        "company_id",
        "period_filter",
        "date_from",
        "date_to",
        "salesperson_id",
        "vehicle_id",
        "city_id",
        "area_id",
        "outlet_id",
    )
    def _compute_dashboard_html(self):
        for rec in self:
            if not rec.date_from:
                rec.date_from = fields.Date.context_today(rec)
            if not rec.date_to:
                rec.date_to = rec.date_from
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                rec.date_from, rec.date_to = rec.date_to, rec.date_from

            payload = rec._get_dashboard_payload()
            rec.filtered_visit_count = len(payload["visits"])
            rec.completed_visit_count = payload["visit_status"].get("done", 0)
            rec.collection_amount = payload["total_collected"]
            rec.net_sales_amount = payload["net_sales"]
            rec.open_promise_amount = payload["open_promise_amount"]
            rec.gross_profit_amount = payload["gross_profit"]
            rec.executive_html = rec._render_executive_html(payload)
            rec.visit_chart_html = rec._render_visit_chart_html(payload)
            rec.collection_chart_html = rec._render_collection_chart_html(payload)
            rec.product_chart_html = rec._render_product_chart_html(payload)
            rec.ranking_html = rec._render_ranking_html(payload)

    def _get_date_range(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        date_from = self.date_from or today
        date_to = self.date_to or date_from
        if self.period_filter == "today":
            date_from = date_to = today
        elif self.period_filter == "week" and not self.date_from:
            date_from = today - timedelta(days=today.weekday())
            date_to = today
        elif self.period_filter == "month" and not self.date_from:
            date_from = today.replace(day=1)
            date_to = today
        elif self.period_filter == "last_30" and not self.date_from:
            date_from = today - timedelta(days=29)
            date_to = today
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        return date_from, date_to

    def _datetime_bounds(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()
        start = datetime.combine(fields.Date.to_date(date_from), time.min)
        end = datetime.combine(fields.Date.to_date(date_to), time.max)
        return start, end

    def _visit_domain(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()
        domain = [
            ("company_id", "=", self.company_id.id or self.env.company.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
        if self.salesperson_id:
            domain.append(("user_id", "=", self.salesperson_id.id))
        if self.vehicle_id:
            domain.append(("vehicle_id", "=", self.vehicle_id.id))
        if self.area_id:
            domain.append(("area_id", "=", self.area_id.id))
        if self.outlet_id:
            domain.append(("outlet_id", "=", self.outlet_id.id))
        return domain

    def _filter_visits_by_city(self, visits):
        self.ensure_one()
        if not self.city_id:
            return visits
        return visits.filtered(
            lambda visit: (visit.area_id and visit.area_id.city_id == self.city_id)
            or (visit.outlet_id and visit.outlet_id.route_city_id == self.city_id)
        )

    def _record_in_scope(self, record):
        self.ensure_one()
        outlet = getattr(record, "outlet_id", False) or getattr(record, "route_outlet_id", False)
        area = getattr(record, "area_id", False) or (outlet.area_id if outlet else False)
        city = area.city_id if area else (outlet.route_city_id if outlet else False)
        salesperson = getattr(record, "salesperson_id", False) or getattr(record, "user_id", False)
        vehicle = getattr(record, "vehicle_id", False)
        visit = getattr(record, "visit_id", False) or getattr(record, "settlement_visit_id", False) or getattr(record, "route_visit_id", False)
        if visit:
            outlet = outlet or visit.outlet_id
            area = area or visit.area_id
            city = city or (area.city_id if area else False) or (outlet.route_city_id if outlet else False)
            salesperson = salesperson or visit.user_id
            vehicle = vehicle or visit.vehicle_id
        if self.salesperson_id and salesperson != self.salesperson_id:
            return False
        if self.vehicle_id and vehicle != self.vehicle_id:
            return False
        if self.city_id and city != self.city_id:
            return False
        if self.area_id and area != self.area_id:
            return False
        if self.outlet_id and outlet != self.outlet_id:
            return False
        return True

    def _date_labels(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()
        labels = []
        current = fields.Date.to_date(date_from)
        end = fields.Date.to_date(date_to)
        while current <= end:
            labels.append(current)
            current += timedelta(days=1)
            if len(labels) > 366:
                break
        return labels

    def _get_dashboard_payload(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()
        dt_from, dt_to = self._datetime_bounds()
        company_id = self.company_id.id or self.env.company.id

        Visit = self.env["route.visit"]
        Payment = self.env["route.visit.payment"]
        SaleOrder = self.env["sale.order"]
        DirectReturn = self.env["route.direct.return"]
        DailyClosing = self.env["route.daily.closing"]
        VehicleClosing = self.env["route.vehicle.closing"]
        LoadingProposal = self.env["route.loading.proposal"]

        visits = self._filter_visits_by_city(Visit.search(self._visit_domain()))
        payments = Payment.search(
            [
                ("company_id", "=", company_id),
                ("payment_date", ">=", fields.Datetime.to_string(dt_from)),
                ("payment_date", "<=", fields.Datetime.to_string(dt_to)),
                ("state", "!=", "cancelled"),
            ]
        ).filtered(lambda payment: self._record_in_scope(payment))
        confirmed_payments = payments.filtered(lambda payment: payment.state == "confirmed")

        promise_candidates = Payment.search(
            [
                ("company_id", "=", company_id),
                ("state", "!=", "cancelled"),
                ("promise_amount", ">", 0.0),
            ]
        ).filtered(lambda payment: self._record_in_scope(payment))

        def _promise_in_period(payment):
            promise_date = payment.promise_date or payment.due_date
            if not promise_date and payment.payment_date:
                promise_date = fields.Date.to_date(payment.payment_date)
            if not promise_date:
                return True
            return promise_date <= date_to and (
                promise_date >= date_from or payment.promise_status in ("due_today", "overdue")
            )

        open_promises = promise_candidates.filtered(
            lambda payment: payment.promise_status in ("open", "due_today", "overdue")
            and _promise_in_period(payment)
        )

        sale_orders = SaleOrder.search(
            [
                ("company_id", "=", company_id),
                ("route_order_mode", "=", "direct_sale"),
                ("date_order", ">=", fields.Datetime.to_string(dt_from)),
                ("date_order", "<=", fields.Datetime.to_string(dt_to)),
                ("state", "not in", ["cancel", "cancelled"]),
            ]
        ).filtered(lambda order: self._record_in_scope(order))

        direct_returns = DirectReturn.search(
            [
                ("company_id", "=", company_id),
                ("return_date", ">=", date_from),
                ("return_date", "<=", date_to),
                ("state", "!=", "cancel"),
            ]
        ).filtered(lambda ret: self._record_in_scope(ret))

        closing_records = DailyClosing.search(
            [
                ("company_id", "=", company_id),
                ("closing_date", ">=", date_from),
                ("closing_date", "<=", date_to),
            ]
        ).filtered(lambda closing: self._record_in_scope(closing))

        vehicle_closings = VehicleClosing.search(
            [
                ("company_id", "=", company_id),
                ("plan_date", ">=", date_from),
                ("plan_date", "<=", date_to),
            ]
        ).filtered(lambda closing: self._record_in_scope(closing))

        loading_proposals = LoadingProposal.search(
            [
                ("company_id", "=", company_id),
                ("plan_date", ">=", date_from),
                ("plan_date", "<=", date_to),
            ]
        ).filtered(lambda proposal: self._record_in_scope(proposal))

        route_transfer_candidates = (
            visits.mapped("return_picking_ids")
            | visits.mapped("refill_picking_id")
            | direct_returns.mapped("picking_ids")
            | loading_proposals.mapped("picking_id")
            | vehicle_closings.mapped("reconciliation_picking_ids")
        )
        pending_transfers = route_transfer_candidates.filtered(lambda picking: picking and picking.state not in ("done", "cancel"))

        visit_status = {
            "done": len(visits.filtered(lambda visit: visit.visit_process_state == "done")),
            "active": len(visits.filtered(lambda visit: visit.visit_process_state not in ("draft", "done", "cancel"))),
            "not_started": len(visits.filtered(lambda visit: visit.visit_process_state == "draft")),
            "cancelled": len(visits.filtered(lambda visit: visit.visit_process_state == "cancel")),
        }
        location_missing_checkin_visits = visits.filtered(lambda visit: visit.geo_review_state == "pending_checkin")
        location_missing_outlet_visits = visits.filtered(lambda visit: visit.geo_review_state == "outlet_missing")
        location_outside_zone_visits = visits.filtered(
            lambda visit: visit.geo_review_state in ("outside_no_reason", "outside_with_reason")
        )
        location_needs_correction_visits = visits.filtered(
            lambda visit: visit.geo_review_supervisor_decision == "needs_correction"
        )
        location_pending_review_visits = visits.filtered(
            lambda visit: visit.geo_review_required
            and visit.geo_review_supervisor_decision not in ("accepted", "needs_correction")
        )
        location_accepted_visits = visits.filtered(
            lambda visit: visit.geo_review_supervisor_decision == "accepted"
        )
        location_issue_visits = (
            location_missing_checkin_visits
            | location_missing_outlet_visits
            | location_outside_zone_visits
            | location_needs_correction_visits
            | location_pending_review_visits
        )
        unfinished_visits = visits.filtered(lambda visit: visit.visit_process_state not in ("done", "cancel"))
        open_due_visits = visits.filtered(lambda visit: (visit.remaining_due_amount or 0.0) > 0.0)

        consignment_sales = sum((line.sold_amount or 0.0) for line in visits.mapped("line_ids"))
        consignment_returns = sum((line.return_amount or 0.0) for line in visits.mapped("line_ids"))
        direct_sales = sum(sale_orders.mapped("amount_total"))
        direct_return_amount = sum(direct_returns.mapped("amount_total"))
        total_collected = sum(confirmed_payments.mapped("amount"))
        period_promises = payments.filtered(lambda payment: (payment.promise_amount or 0.0) > 0.0)
        due_overdue_promises = open_promises.filtered(lambda payment: payment.promise_status in ("due_today", "overdue"))
        period_promise_amount = sum((payment.effective_promise_amount or payment.promise_amount or 0.0) for payment in period_promises)
        open_promise_amount = sum((payment.effective_promise_amount or payment.promise_amount or 0.0) for payment in open_promises)
        due_overdue_promise_amount = sum((payment.effective_promise_amount or payment.promise_amount or 0.0) for payment in due_overdue_promises)
        open_due_amount = sum(open_due_visits.mapped("remaining_due_amount"))
        gross_sales = consignment_sales + direct_sales
        total_returns = consignment_returns + direct_return_amount
        net_sales = max(gross_sales - total_returns, 0.0)

        payment_modes = defaultdict(float)
        for payment in confirmed_payments:
            payment_modes[payment.payment_mode or _("Other")] += payment.amount or 0.0

        daily_collection = defaultdict(float)
        daily_sales = defaultdict(float)
        daily_returns = defaultdict(float)
        for payment in confirmed_payments:
            pay_date = fields.Date.to_date(payment.payment_date) if payment.payment_date else date_from
            daily_collection[pay_date] += payment.amount or 0.0
        for visit in visits:
            visit_date = visit.date or date_from
            daily_sales[visit_date] += sum((line.sold_amount or 0.0) for line in visit.line_ids)
            daily_returns[visit_date] += sum((line.return_amount or 0.0) for line in visit.line_ids)
        for order in sale_orders:
            order_date = fields.Date.to_date(order.date_order) if order.date_order else date_from
            daily_sales[order_date] += order.amount_total or 0.0
        for ret in direct_returns:
            ret_date = ret.return_date or date_from
            daily_returns[ret_date] += ret.amount_total or 0.0

        salesperson_lines = self._build_salesperson_lines(visits, payments, sale_orders, direct_returns, location_issue_visits)
        vehicle_lines = self._build_vehicle_lines(visits, vehicle_closings)
        product_lines, gross_profit, missing_cost_product_count = self._build_product_lines(visits, sale_orders, direct_returns)

        operation_dates = self._operation_dates(
            visits, payments, sale_orders, direct_returns, closing_records, vehicle_closings, loading_proposals
        )
        closed_dates = set(closing_records.filtered(lambda rec: rec.state == "closed").mapped("closing_date"))
        reopened_dates = set(
            closing_records.filtered(
                lambda rec: rec.state == "reopened"
                or rec.audit_line_ids.filtered(lambda line: line.event_type == "reopen_day")
            ).mapped("closing_date")
        )
        closed_day_count = len(operation_dates & closed_dates)
        reopened_day_count = len(operation_dates & reopened_dates)
        period_day_count = len(operation_dates)
        open_day_count = max(len(operation_dates - closed_dates), 0)
        pending_vehicle_issues = len(vehicle_closings.filtered(lambda closing: closing.state != "closed" or (closing.pending_variance_line_count or 0) > 0 or (closing.pending_execution_line_count or 0) > 0))

        return {
            "date_from": date_from,
            "date_to": date_to,
            "visits": visits,
            "payments": payments,
            "confirmed_payments": confirmed_payments,
            "open_promises": open_promises,
            "period_promises": period_promises,
            "due_overdue_promises": due_overdue_promises,
            "sale_orders": sale_orders,
            "direct_returns": direct_returns,
            "closing_records": closing_records,
            "vehicle_closings": vehicle_closings,
            "loading_proposals": loading_proposals,
            "pending_transfers": pending_transfers,
            "visit_status": visit_status,
            "unfinished_visits": unfinished_visits,
            "location_issue_visits": location_issue_visits,
            "location_missing_checkin_visits": location_missing_checkin_visits,
            "location_missing_outlet_visits": location_missing_outlet_visits,
            "location_outside_zone_visits": location_outside_zone_visits,
            "location_needs_correction_visits": location_needs_correction_visits,
            "location_pending_review_visits": location_pending_review_visits,
            "location_accepted_visits": location_accepted_visits,
            "open_due_visits": open_due_visits,
            "consignment_sales": consignment_sales,
            "direct_sales": direct_sales,
            "gross_sales": gross_sales,
            "consignment_returns": consignment_returns,
            "direct_return_amount": direct_return_amount,
            "total_returns": total_returns,
            "net_sales": net_sales,
            "total_collected": total_collected,
            "period_promise_amount": period_promise_amount,
            "open_promise_amount": open_promise_amount,
            "due_overdue_promise_amount": due_overdue_promise_amount,
            "open_due_amount": open_due_amount,
            "payment_modes": dict(payment_modes),
            "daily_collection": dict(daily_collection),
            "daily_sales": dict(daily_sales),
            "daily_returns": dict(daily_returns),
            "salesperson_lines": salesperson_lines,
            "vehicle_lines": vehicle_lines,
            "product_lines": product_lines,
            "gross_profit": gross_profit,
            "missing_cost_product_count": missing_cost_product_count,
            "closed_day_count": closed_day_count,
            "reopened_day_count": reopened_day_count,
            "open_day_count": open_day_count,
            "period_day_count": period_day_count,
            "pending_vehicle_issues": pending_vehicle_issues,
            "loading_pending_count": len(loading_proposals.filtered(lambda prop: prop.state not in ("approved", "done", "cancel"))),
            "pending_transfer_count": len(pending_transfers),
        }

    def _operation_dates(self, visits, payments, sale_orders, direct_returns, closing_records, vehicle_closings, loading_proposals):
        operation_dates = set()

        def add_date(value):
            if not value:
                return
            try:
                operation_dates.add(fields.Date.to_date(value))
            except Exception:
                return

        for visit in visits:
            add_date(visit.date)
        for payment in payments:
            add_date(payment.payment_date)
        for order in sale_orders:
            add_date(order.date_order)
        for ret in direct_returns:
            add_date(ret.return_date)
        for closing in closing_records:
            add_date(closing.closing_date)
        for closing in vehicle_closings:
            add_date(closing.plan_date)
        for proposal in loading_proposals:
            add_date(proposal.plan_date)
        return operation_dates

    def _build_salesperson_lines(self, visits, payments, sale_orders, direct_returns, location_issue_visits):
        data = defaultdict(lambda: {
            "name": _("Unassigned"),
            "sales": 0.0,
            "collection": 0.0,
            "promises": 0.0,
            "visits": 0,
            "done": 0,
            "unfinished": 0,
            "location": 0,
            "issues": 0,
        })
        for visit in visits:
            user = visit.user_id
            key = user.id or 0
            data[key]["name"] = user.display_name if user else _("Unassigned")
            data[key]["visits"] += 1
            data[key]["sales"] += sum((line.sold_amount or 0.0) for line in visit.line_ids)
            if visit.visit_process_state == "done":
                data[key]["done"] += 1
            elif visit.visit_process_state != "cancel":
                data[key]["unfinished"] += 1
        for visit in location_issue_visits:
            user = visit.user_id
            key = user.id or 0
            data[key]["location"] += 1
        for payment in payments:
            user = payment.salesperson_id
            key = user.id or 0
            data[key]["name"] = user.display_name if user else data[key]["name"]
            if payment.state == "confirmed":
                data[key]["collection"] += payment.amount or 0.0
            if (payment.promise_amount or 0.0) > 0.0 and payment.promise_status in ("open", "due_today", "overdue"):
                data[key]["promises"] += payment.effective_promise_amount or payment.promise_amount or 0.0
        for order in sale_orders:
            user = order.user_id
            key = user.id or 0
            data[key]["name"] = user.display_name if user else data[key]["name"]
            data[key]["sales"] += order.amount_total or 0.0
        for ret in direct_returns:
            user = ret.user_id
            key = user.id or 0
            data[key]["sales"] -= ret.amount_total or 0.0
        lines = []
        for values in data.values():
            values["issues"] = values["unfinished"] + values["location"] + (1 if values["promises"] else 0)
            lines.append(values)
        return sorted(lines, key=lambda item: (item["issues"], item["promises"], item["sales"]), reverse=True)

    def _build_vehicle_lines(self, visits, vehicle_closings):
        data = defaultdict(lambda: {
            "name": _("Unassigned"),
            "visits": 0,
            "unfinished": 0,
            "variance": 0,
            "pending": 0,
            "issues": 0,
        })
        for visit in visits:
            vehicle = visit.vehicle_id
            key = vehicle.id or 0
            data[key]["name"] = vehicle.display_name if vehicle else _("Unassigned")
            data[key]["visits"] += 1
            if visit.visit_process_state not in ("done", "cancel"):
                data[key]["unfinished"] += 1
        for closing in vehicle_closings:
            vehicle = closing.vehicle_id
            key = vehicle.id or 0
            data[key]["name"] = vehicle.display_name if vehicle else data[key]["name"]
            data[key]["variance"] += closing.variance_line_count or 0
            if closing.state != "closed" or (closing.pending_variance_line_count or 0) > 0 or (closing.pending_execution_line_count or 0) > 0:
                data[key]["pending"] += 1
        lines = []
        for values in data.values():
            values["issues"] = values["unfinished"] + values["variance"] + values["pending"]
            lines.append(values)
        return sorted(lines, key=lambda item: item["issues"], reverse=True)

    def _build_product_lines(self, visits, sale_orders, direct_returns):
        data = defaultdict(lambda: {
            "name": "",
            "qty": 0.0,
            "sales": 0.0,
            "returns": 0.0,
            "profit": 0.0,
            "missing_cost": False,
        })
        missing_cost_product_ids = set()

        def mark_missing_cost(product, qty, amount):
            if product and qty and amount and (product.standard_price or 0.0) <= 0.0:
                missing_cost_product_ids.add(product.id)
                data[product.id]["missing_cost"] = True

        for line in visits.mapped("line_ids"):
            product = line.product_id
            if not product:
                continue
            values = data[product.id]
            values["name"] = product.display_name
            sold_qty = line.sold_qty or 0.0
            sold_amount = line.sold_amount or 0.0
            return_qty = getattr(line, "return_qty", 0.0) or 0.0
            return_amount = line.return_amount or 0.0
            values["qty"] += sold_qty
            values["sales"] += sold_amount
            values["returns"] += return_amount
            values["profit"] += sold_amount - return_amount - ((sold_qty - return_qty) * (product.standard_price or 0.0))
            mark_missing_cost(product, sold_qty, sold_amount)
        for line in sale_orders.mapped("order_line"):
            product = line.product_id
            if not product:
                continue
            values = data[product.id]
            values["name"] = product.display_name
            qty = getattr(line, "product_uom_qty", 0.0) or 0.0
            amount = getattr(line, "price_subtotal", 0.0) or 0.0
            values["qty"] += qty
            values["sales"] += amount
            values["profit"] += amount - (qty * (product.standard_price or 0.0))
            mark_missing_cost(product, qty, amount)
        for line in direct_returns.mapped("line_ids"):
            product = line.product_id
            if not product:
                continue
            values = data[product.id]
            values["name"] = product.display_name
            qty = line.quantity or 0.0
            amount = line.estimated_amount or 0.0
            values["returns"] += amount
            values["profit"] -= amount - (qty * (product.standard_price or 0.0))
            mark_missing_cost(product, qty, amount)
        lines = sorted(data.values(), key=lambda item: item["sales"], reverse=True)
        return lines, sum(line["profit"] for line in lines), len(missing_cost_product_ids)

    def _render_executive_html(self, payload):
        visit_total = len(payload["visits"])
        done = payload["visit_status"].get("done", 0)
        completion = (done / visit_total * 100.0) if visit_total else 0.0
        collection_rate = (payload["total_collected"] / payload["net_sales"] * 100.0) if payload["net_sales"] else 0.0
        margin = (payload["gross_profit"] / payload["gross_sales"] * 100.0) if payload["gross_sales"] else 0.0
        profit_quality = 100.0
        if payload["product_lines"]:
            profit_quality = max(
                0.0,
                100.0 - ((payload["missing_cost_product_count"] / len(payload["product_lines"])) * 100.0),
            )
        attention_score = (
            len(payload["unfinished_visits"])
            + len(payload["location_issue_visits"])
            + payload["pending_vehicle_issues"]
            + payload["pending_transfer_count"]
            + len(payload["due_overdue_promises"])
        )
        cards = [
            self._kpi_card(_("Visits"), self._num(visit_total), _("Completed: %s") % self._num(done), "primary", f"{completion:.0f}%"),
            self._kpi_card(_("Collection"), self._money(payload["total_collected"]), _("Rate: %s%%") % f"{collection_rate:.0f}", "success"),
            self._kpi_card(_("Net Sales"), self._money(payload["net_sales"]), _("Gross: %s") % self._money(payload["gross_sales"]), "sales"),
            self._kpi_card(_("Due / Open Promises"), self._money(payload["open_promise_amount"]), _("Due/Overdue: %s") % self._num(len(payload["due_overdue_promises"])), "warning"),
            self._kpi_card(_("Open Due"), self._money(payload["open_due_amount"]), _("Visits: %s") % self._num(len(payload["open_due_visits"])), "danger"),
            self._kpi_card(_("Estimated Profit"), self._money(payload["gross_profit"]), _("Margin: %s%% | Cost data: %s%%") % (f"{margin:.0f}", f"{profit_quality:.0f}"), "profit"),
            self._kpi_card(_("Closed Operating Days"), self._num(payload["closed_day_count"]), _("Open / Not Ready: %s") % self._num(payload["open_day_count"]), "success"),
            self._kpi_card(_("Reopened Days"), self._num(payload["reopened_day_count"]), _("Operating days: %s") % self._num(payload["period_day_count"]), "warning"),
            self._kpi_card(_("Vehicle Issues"), self._num(payload["pending_vehicle_issues"]), _("Vehicle closing checks"), "danger"),
            self._kpi_card(_("Location Review"), self._num(len(payload["location_issue_visits"])), _("Outside/missing/pending review"), "warning"),
            self._kpi_card(_("Pending Transfers"), self._num(payload["pending_transfer_count"]), _("Stock moves not done"), "info"),
            self._kpi_card(_("Returns"), self._money(payload["total_returns"]), _("Return orders/transfers"), "danger"),
        ]
        scope = self._scope_badges()
        title = self._section_title(
            _("Performance Command Center"),
            _("High-level KPIs for visits, collections, promises, stock operations, and sales performance."),
        )
        return (
            f"<div class='route_dash_block'>{title}{scope}"
            f"{self._render_insight_cards(payload, collection_rate, attention_score)}"
            f"<div class='route_dash_kpi_grid'>{''.join(cards)}</div></div>"
        )

    def _render_insight_cards(self, payload, collection_rate, attention_score):
        best_salesperson = max(payload["salesperson_lines"], key=lambda line: line.get("collection", 0.0), default=False)
        top_product = max(payload["product_lines"], key=lambda line: line.get("sales", 0.0), default=False)
        top_return_product = max(payload["product_lines"], key=lambda line: line.get("returns", 0.0), default=False)
        critical_vehicle = max(payload["vehicle_lines"], key=lambda line: line.get("issues", 0), default=False)
        due_by_outlet = defaultdict(float)
        for visit in payload["open_due_visits"]:
            label = visit.outlet_id.display_name if visit.outlet_id else _("No Outlet")
            due_by_outlet[label] += visit.remaining_due_amount or 0.0
        highest_due = max(due_by_outlet.items(), key=lambda item: item[1], default=False)
        insights = [
            (_("Best Collector"), best_salesperson and best_salesperson.get("name") or _("No data"), best_salesperson and self._money(best_salesperson.get("collection")) or "-", "success"),
            (_("Top Product"), top_product and top_product.get("name") or _("No data"), top_product and self._money(top_product.get("sales")) or "-", "sales"),
            (_("Highest Open Due"), highest_due and highest_due[0] or _("No open due"), highest_due and self._money(highest_due[1]) or "-", "danger"),
            (_("Most Returned Product"), top_return_product and top_return_product.get("name") or _("No returns"), top_return_product and self._money(top_return_product.get("returns")) or "-", "warning"),
            (_("Critical Vehicle"), critical_vehicle and critical_vehicle.get("name") or _("No data"), critical_vehicle and _("Issues: %s") % self._num(critical_vehicle.get("issues")) or "-", "danger"),
            (_("Collection Rate"), f"{collection_rate:.0f}%", _("Attention score: %s") % self._num(attention_score), "info"),
        ]
        return "<div class='route_dash_insight_grid'>" + "".join(
            self._insight_card(title, value, note, tone) for title, value, note, tone in insights
        ) + "</div>"

    def _render_visit_chart_html(self, payload):
        status = payload["visit_status"]
        status_rows = [
            (_("Completed"), status.get("done", 0), "#16a34a"),
            (_("In Progress"), status.get("active", 0), "#0ea5e9"),
            (_("Not Started"), status.get("not_started", 0), "#f59e0b"),
            (_("Cancelled"), status.get("cancelled", 0), "#ef4444"),
        ]
        operations_rows = [
            (_("Unfinished Visits"), len(payload["unfinished_visits"]), "#ef4444"),
            (_("Due / Overdue Promises"), len(payload["due_overdue_promises"]), "#8b5cf6"),
            (_("Vehicle Issues"), payload["pending_vehicle_issues"], "#64748b"),
            (_("Pending Transfers"), payload["pending_transfer_count"], "#0ea5e9"),
        ]
        location_rows = [
            (_("Missing Check-in"), len(payload["location_missing_checkin_visits"]), "#ef4444"),
            (_("Missing Outlet GPS"), len(payload["location_missing_outlet_visits"]), "#64748b"),
            (_("Outside Zone"), len(payload["location_outside_zone_visits"]), "#f59e0b"),
            (_("Needs Correction"), len(payload["location_needs_correction_visits"]), "#dc2626"),
            (_("Pending Review"), len(payload["location_pending_review_visits"]), "#0ea5e9"),
            (_("Accepted"), len(payload["location_accepted_visits"]), "#16a34a"),
        ]
        closing_rows = [
            (_("Closed"), payload["closed_day_count"], "#16a34a"),
            (_("Open / Not Ready"), payload["open_day_count"], "#f59e0b"),
            (_("Reopened"), payload["reopened_day_count"], "#ef4444"),
        ]
        html = self._section_title(_("Visit and Closing Health"), _("Visual status instead of repeated operational lists."))
        html += "<div class='route_dash_chart_grid'>"
        html += self._chart_card(_("Visit Status"), self._pie_chart(status_rows), self._legend(status_rows))
        html += self._chart_card(_("Attention Mix"), self._horizontal_bars(operations_rows), _("Only active blockers are shown here."))
        html += self._chart_card(_("Location Review Breakdown"), self._horizontal_bars(location_rows), _("Location is split by reason to avoid one confusing total."))
        html += self._chart_card(_("Closing Status"), self._pie_chart(closing_rows), self._legend(closing_rows) + _(" Operating days only."))
        html += "</div>"
        return f"<div class='route_dash_block'>{html}</div>"

    def _render_collection_chart_html(self, payload):
        payment_labels = {
            "cash": _("Cash"),
            "bank": _("Bank"),
            "pos": _("POS"),
            "deferred": _("Deferred"),
        }
        colors = ["#16a34a", "#0ea5e9", "#8b5cf6", "#f59e0b", "#64748b"]
        payment_rows = []
        for index, (mode, amount) in enumerate(sorted(payload["payment_modes"].items(), key=lambda item: item[1], reverse=True)):
            payment_rows.append((payment_labels.get(mode, mode), amount, colors[index % len(colors)]))
        salesperson_rows = [
            (line["name"], line["collection"], "#16a34a")
            for line in sorted(payload["salesperson_lines"], key=lambda item: item["collection"], reverse=True)[:8]
        ]
        line_html = self._line_chart(payload["daily_collection"], payload["daily_sales"], payload["date_from"], payload["date_to"])
        html = self._section_title(_("Collections and Cash Flow"), _("Collections, promises, payment method mix, and trend over time."))
        html += "<div class='route_dash_chart_grid'>"
        html += self._chart_card(_("Payment Method Mix"), self._pie_chart(payment_rows), self._legend(payment_rows))
        html += self._chart_card(_("Collection by Salesperson"), self._horizontal_bars(salesperson_rows, money=True), "")
        html += self._chart_card(_("Sales vs Collection Trend"), line_html, _("Line compares sales and collections in the selected date range."), wide=True)
        html += "</div>"
        return f"<div class='route_dash_block'>{html}</div>"

    def _render_product_chart_html(self, payload):
        top_products = payload["product_lines"][:10]
        product_sales = [(line["name"], line["sales"], "#0ea5e9") for line in top_products]
        product_qty = [(line["name"], line["qty"], "#8b5cf6") for line in top_products]
        profit_rows = [(line["name"], line["profit"], "#16a34a" if line["profit"] >= 0 else "#ef4444") for line in top_products]
        product_returns = [
            (line["name"], line.get("returns", 0.0), "#ef4444")
            for line in sorted(payload["product_lines"], key=lambda item: item.get("returns", 0.0), reverse=True)[:10]
        ]
        sales_return_rows = [
            (_("Gross Sales"), payload["gross_sales"], "#16a34a"),
            (_("Returns"), payload["total_returns"], "#ef4444"),
            (_("Net Sales"), payload["net_sales"], "#0ea5e9"),
            (_("Estimated Profit"), payload["gross_profit"], "#8b5cf6"),
        ]
        quality_note = _("Missing cost products: %s. Profit is estimated from product cost.") % self._num(payload["missing_cost_product_count"])
        html = self._section_title(_("Products, Sales, and Estimated Profit"), quality_note)
        html += "<div class='route_dash_chart_grid'>"
        html += self._chart_card(_("Sales / Returns / Profit"), self._horizontal_bars(sales_return_rows, money=True), "")
        html += self._chart_card(_("Top Products by Sales"), self._horizontal_bars(product_sales, money=True), "")
        html += self._chart_card(_("Top Products by Quantity"), self._horizontal_bars(product_qty), "")
        html += self._chart_card(_("Top Returned Products"), self._horizontal_bars(product_returns, money=True), "")
        html += self._chart_card(_("Estimated Product Profit"), self._horizontal_bars(profit_rows, money=True, allow_negative=True), _("Profit is safest when all products have standard cost."), wide=True)
        html += "</div>"
        return f"<div class='route_dash_block'>{html}</div>"

    def _render_ranking_html(self, payload):
        salesperson_rows = payload["salesperson_lines"][:8]
        vehicle_rows = payload["vehicle_lines"][:8]
        html = self._section_title(_("Team and Operations Ranking"), _("Highlights who needs support and where operational risk is concentrated."))
        html += "<div class='route_dash_ranking_grid'>"
        html += self._ranking_table(
            _("Salesperson Performance"),
            [_('Salesperson'), _('Sales'), _('Collected'), _('Promises'), _('Issues')],
            [
                [
                    line["name"],
                    self._money(line["sales"]),
                    self._money(line["collection"]),
                    self._money(line["promises"]),
                    self._num(line["issues"]),
                ]
                for line in salesperson_rows
            ],
        )
        html += self._ranking_table(
            _("Vehicle Issue Ranking"),
            [_('Vehicle'), _('Visits'), _('Unfinished'), _('Variance'), _('Issues')],
            [
                [line["name"], self._num(line["visits"]), self._num(line["unfinished"]), self._num(line["variance"]), self._num(line["issues"])]
                for line in vehicle_rows
            ],
        )
        html += "</div>"
        return f"<div class='route_dash_block'>{html}</div>"

    def _insight_card(self, title, value, note, tone="primary"):
        return (
            f"<div class='route_dash_insight route_dash_tone_{escape(tone)}'>"
            f"<span>{escape(str(title))}</span>"
            f"<strong>{escape(str(value))}</strong>"
            f"<small>{escape(str(note or ''))}</small>"
            f"</div>"
        )

    def _kpi_card(self, title, value, note, tone="primary", corner=False):
        corner_html = f"<span class='route_dash_kpi_corner'>{escape(str(corner))}</span>" if corner else ""
        return (
            f"<div class='route_dash_kpi route_dash_tone_{escape(tone)}'>"
            f"{corner_html}"
            f"<span class='route_dash_kpi_label'>{escape(str(title))}</span>"
            f"<strong>{escape(str(value))}</strong>"
            f"<span class='route_dash_kpi_note'>{escape(str(note or ''))}</span>"
            f"</div>"
        )

    def _section_title(self, title, subtitle):
        return (
            "<div class='route_dash_section_title'>"
            f"<div><span>{escape(str(title))}</span><p>{escape(str(subtitle or ''))}</p></div>"
            "</div>"
        )

    def _scope_badges(self):
        badges = []
        if self.salesperson_id:
            badges.append((_("Salesperson"), self.salesperson_id.display_name))
        if self.vehicle_id:
            badges.append((_("Vehicle"), self.vehicle_id.display_name))
        if self.city_id:
            badges.append((_("City"), self.city_id.display_name))
        if self.area_id:
            badges.append((_("Area"), self.area_id.display_name))
        if self.outlet_id:
            badges.append((_("Outlet"), self.outlet_id.display_name))
        if not badges:
            badges.append((_("Scope"), _("All Operations")))
        return "<div class='route_dash_scope'>" + "".join(
            f"<span><small>{escape(str(label))}</small>{escape(str(value))}</span>" for label, value in badges
        ) + "</div>"

    def _chart_card(self, title, chart_html, footer, wide=False):
        wide_class = " route_dash_chart_wide" if wide else ""
        return (
            f"<div class='route_dash_chart_card{wide_class}'>"
            f"<h3>{escape(str(title))}</h3>"
            f"<div class='route_dash_chart_body'>{chart_html}</div>"
            f"<div class='route_dash_chart_footer'>{footer or ''}</div>"
            f"</div>"
        )

    def _empty_chart(self):
        return (
            "<div class='route_dash_empty_chart'>"
            "<strong>No activity for this period</strong>"
            "<small>Try Last 30 Days, This Month, or widen the filters.</small>"
            "</div>"
        )

    def _pie_chart(self, rows):
        total = sum(float(value or 0.0) for _label, value, _color in rows)
        if not total:
            return self._empty_chart()
        start = 0.0
        parts = []
        for _label, value, color in rows:
            pct = (float(value or 0.0) / total) * 100.0 if total else 0.0
            end = start + pct
            parts.append(f"{color} {start:.2f}% {end:.2f}%")
            start = end
        return (
            f"<div class='route_dash_pie' style='background: conic-gradient({', '.join(parts)});'>"
            f"<span>{escape(self._num(total))}</span>"
            "</div>"
        )

    def _legend(self, rows):
        if not rows:
            return ""
        return "<div class='route_dash_legend'>" + "".join(
            f"<span><i style='background:{escape(color)}'></i>{escape(str(label))}: <b>{escape(self._short_num(value))}</b></span>"
            for label, value, color in rows
        ) + "</div>"

    def _horizontal_bars(self, rows, money=False, allow_negative=False):
        rows = [(label, value, color) for label, value, color in rows if value or allow_negative]
        if not rows:
            return self._empty_chart()
        max_value = max(abs(float(value or 0.0)) for _label, value, _color in rows) or 1.0
        html = "<div class='route_dash_bars'>"
        for label, value, color in rows:
            raw_value = float(value or 0.0)
            width = max(min(abs(raw_value) / max_value * 100.0, 100.0), 3.0)
            display = self._money(raw_value) if money else self._short_num(raw_value)
            sign_class = " route_dash_bar_negative" if raw_value < 0 else ""
            html += (
                f"<div class='route_dash_bar_row{sign_class}'>"
                f"<div class='route_dash_bar_meta'><span>{escape(str(label))}</span><strong>{escape(display)}</strong></div>"
                f"<div class='route_dash_bar_track'><div style='width:{width:.2f}%; background:{escape(color)}'></div></div>"
                f"</div>"
            )
        html += "</div>"
        return html

    def _line_chart(self, collection_by_date, sales_by_date, date_from, date_to):
        labels = []
        current = fields.Date.to_date(date_from)
        end = fields.Date.to_date(date_to)
        while current <= end:
            labels.append(current)
            current += timedelta(days=1)
            if len(labels) > 60:
                break
        if not labels:
            return self._empty_chart()
        sales_values = [float(sales_by_date.get(day, 0.0) or 0.0) for day in labels]
        collection_values = [float(collection_by_date.get(day, 0.0) or 0.0) for day in labels]
        if not any(sales_values) and not any(collection_values):
            return self._empty_chart()
        max_value = max(sales_values + collection_values + [1.0])
        width = 520
        height = 180
        pad = 24
        def points(values):
            if len(values) == 1:
                x_positions = [width / 2]
            else:
                x_positions = [pad + (width - 2 * pad) * idx / (len(values) - 1) for idx in range(len(values))]
            pts = []
            for x, value in zip(x_positions, values):
                y = height - pad - ((height - 2 * pad) * value / max_value)
                pts.append(f"{x:.1f},{y:.1f}")
            return " ".join(pts)
        return (
            "<div class='route_dash_line_wrap'>"
            f"<svg viewBox='0 0 {width} {height}' preserveAspectRatio='none' class='route_dash_line_svg'>"
            f"<polyline points='{points(sales_values)}' fill='none' stroke='#0ea5e9' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/>"
            f"<polyline points='{points(collection_values)}' fill='none' stroke='#16a34a' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/>"
            "</svg>"
            "<div class='route_dash_line_legend'><span><i style='background:#0ea5e9'></i>Sales</span><span><i style='background:#16a34a'></i>Collection</span></div>"
            "</div>"
        )

    def _ranking_table(self, title, headers, rows):
        if not rows:
            body = f"<tr><td colspan='{len(headers)}' class='route_dash_empty_cell'>No data</td></tr>"
        else:
            body = "".join(
                "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>"
                for row in rows
            )
        return (
            "<div class='route_dash_table_card'>"
            f"<h3>{escape(str(title))}</h3>"
            "<div class='table-responsive'><table class='table table-sm route_dash_table'>"
            "<thead><tr>" + "".join(f"<th>{escape(str(header))}</th>" for header in headers) + "</tr></thead>"
            f"<tbody>{body}</tbody>"
            "</table></div></div>"
        )

    def _num(self, value):
        try:
            if isinstance(value, float) and not value.is_integer():
                return f"{value:,.2f}"
            return f"{int(value):,}"
        except Exception:
            return str(value or 0)

    def _short_num(self, value):
        try:
            value = float(value or 0.0)
        except Exception:
            return str(value or 0)
        abs_value = abs(value)
        if abs_value >= 1000000:
            return f"{value / 1000000:.1f}M"
        if abs_value >= 1000:
            return f"{value / 1000:.1f}K"
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"

    def _money(self, amount):
        amount = amount or 0.0
        currency = self.currency_id or self.env.company.currency_id
        formatted = f"{amount:,.2f}"
        symbol = currency.symbol or ""
        if currency.position == "after":
            return f"{formatted} {symbol}".strip()
        return f"{symbol} {formatted}".strip()
