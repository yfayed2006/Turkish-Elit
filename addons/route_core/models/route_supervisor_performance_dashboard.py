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

    show_direct_sale_sections = fields.Boolean(compute="_compute_settings_visibility")
    show_consignment_sections = fields.Boolean(compute="_compute_settings_visibility")
    show_outlet_comparison_sections = fields.Boolean(compute="_compute_settings_visibility")
    show_direct_return_sections = fields.Boolean(compute="_compute_settings_visibility")
    show_location_sections = fields.Boolean(compute="_compute_settings_visibility")
    show_vehicle_closing_sections = fields.Boolean(compute="_compute_settings_visibility")
    show_loading_sections = fields.Boolean(compute="_compute_settings_visibility")
    show_stock_transfer_sections = fields.Boolean(compute="_compute_settings_visibility")
    show_lot_expiry_sections = fields.Boolean(compute="_compute_settings_visibility")
    dashboard_operation_mode_label = fields.Char(compute="_compute_settings_visibility")

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
    outlet_chart_html = fields.Html(
        string="Outlet Performance Analytics",
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

    @api.depends("company_id")
    def _compute_settings_visibility(self):
        for rec in self:
            settings = rec._get_dashboard_settings()
            rec.show_direct_sale_sections = settings["show_direct_sale"]
            rec.show_consignment_sections = settings["show_consignment"]
            rec.show_outlet_comparison_sections = settings["show_outlet_comparison"]
            rec.show_direct_return_sections = settings["show_direct_return"]
            rec.show_location_sections = settings["show_location"]
            rec.show_vehicle_closing_sections = settings["show_vehicle_closing"]
            rec.show_loading_sections = settings["show_loading"]
            rec.show_stock_transfer_sections = settings["show_stock_transfers"]
            rec.show_lot_expiry_sections = settings["show_lot_expiry"]
            rec.dashboard_operation_mode_label = settings["operation_mode_label"]

    def _company_field_value(self, company, field_name, default=False):
        if company and field_name in company._fields:
            return company[field_name]
        return default

    def _get_dashboard_settings(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        operation_mode = self._company_field_value(company, "route_operation_mode", "hybrid") or "hybrid"
        direct_toggle = bool(self._company_field_value(company, "route_enable_direct_sale", True))
        direct_return_toggle = bool(self._company_field_value(company, "route_enable_direct_return", True))

        show_direct_sale = operation_mode in ("direct_sales", "hybrid") and (operation_mode == "direct_sales" or direct_toggle)
        show_consignment = operation_mode in ("consignment", "hybrid")
        if not show_direct_sale and not show_consignment:
            show_consignment = True

        loading_workflow = self._company_field_value(company, "route_vehicle_loading_workflow", "optional") or "optional"
        show_loading = loading_workflow in ("optional", "required")
        show_vehicle_closing = bool(self._company_field_value(company, "route_workspace_show_vehicle_closing", True))
        geo_policy = self._company_field_value(company, "route_geo_checkin_policy", "review_only") or "review_only"
        outlet_locations_enabled = bool(self._company_field_value(company, "route_enable_outlet_geolocation", True))
        # Outlet locations can stay enabled for map/address use while Location Check-in is disabled.
        # Dashboard review/issue sections should follow the check-in policy, not the map/location master-data flag.
        show_location = bool(outlet_locations_enabled and geo_policy != "disabled")
        show_lot = bool(self._company_field_value(company, "route_enable_lot_serial_tracking", False))
        show_expiry = bool(self._company_field_value(company, "route_enable_expiry_tracking", False)) and show_lot
        show_direct_return = show_direct_sale and direct_return_toggle
        show_stock_transfers = bool(show_loading or show_consignment or show_direct_return or show_vehicle_closing)

        labels = {
            "consignment": _("Consignment Only"),
            "direct_sales": _("Direct Sale Only"),
            "hybrid": _("Direct Sale + Consignment"),
        }
        return {
            "operation_mode": operation_mode,
            "operation_mode_label": labels.get(operation_mode, labels["hybrid"]),
            "show_direct_sale": show_direct_sale,
            "show_consignment": show_consignment,
            "show_outlet_comparison": bool(show_direct_sale and show_consignment),
            "show_direct_return": show_direct_return,
            "show_location": show_location,
            "show_vehicle_closing": show_vehicle_closing,
            "show_loading": show_loading,
            "show_stock_transfers": show_stock_transfers,
            "show_lot_expiry": bool(show_lot or show_expiry),
            "loading_workflow": loading_workflow,
            "geo_policy": geo_policy,
        }

    def _visit_is_direct_sale(self, visit):
        execution_mode = getattr(visit, "visit_execution_mode", False)
        if execution_mode:
            return execution_mode == "direct_sales"
        outlet = getattr(visit, "outlet_id", False)
        return bool(outlet and getattr(outlet, "outlet_operation_mode", False) in ("direct_sale", "direct_sales"))

    def _record_allowed_by_operation_mode(self, record, settings):
        outlet = getattr(record, "outlet_id", False) or getattr(record, "route_outlet_id", False)
        visit = getattr(record, "visit_id", False) or getattr(record, "settlement_visit_id", False) or getattr(record, "route_visit_id", False)
        if visit:
            is_direct = self._visit_is_direct_sale(visit)
        else:
            is_direct = bool(outlet and getattr(outlet, "outlet_operation_mode", False) in ("direct_sale", "direct_sales"))
        if is_direct and not settings["show_direct_sale"]:
            return False
        if not is_direct and not settings["show_consignment"]:
            return False
        return True

    def _apply_operation_mode_to_visits(self, visits, settings):
        if settings["show_direct_sale"] and settings["show_consignment"]:
            return visits
        if settings["show_direct_sale"]:
            return visits.filtered(lambda visit: self._visit_is_direct_sale(visit))
        if settings["show_consignment"]:
            return visits.filtered(lambda visit: not self._visit_is_direct_sale(visit))
        return visits.browse()

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
        if not payload["settings"].get("show_location"):
            visits = self.env["route.visit"].browse()
        else:
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
        if payload["direct_returns"]:
            return self._action_open_records(_("Dashboard Return Orders"), payload["direct_returns"], "route.direct.return", "kanban,list,form")
        pickings = self.env["stock.picking"]
        if payload["settings"].get("show_consignment"):
            pickings |= payload["visits"].mapped("return_picking_ids")
        return self._action_open_records(_("Dashboard Return Transfers"), pickings, "stock.picking", "list,form")

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

    def action_open_completed_visits(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        visits = payload["visits"].filtered(lambda visit: visit.visit_process_state == "done")
        return self._action_open_records(_("Dashboard Completed Visits"), visits, "route.visit", "kanban,list,form")

    def action_open_started_visits(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        visits = payload["visits"].filtered(lambda visit: visit.visit_process_state not in ("draft", "done", "cancel"))
        return self._action_open_records(_("Dashboard Started Visits"), visits, "route.visit", "kanban,list,form")

    def action_open_not_started_visits(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        visits = payload["visits"].filtered(lambda visit: visit.visit_process_state == "draft")
        return self._action_open_records(_("Dashboard Not Started Visits"), visits, "route.visit", "kanban,list,form")

    def action_open_cancelled_visits(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        visits = payload["visits"].filtered(lambda visit: visit.visit_process_state == "cancel")
        return self._action_open_records(_("Dashboard Cancelled Visits"), visits, "route.visit", "kanban,list,form")

    def action_open_open_due_visits(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(_("Dashboard Open Due Visits"), payload["open_due_visits"], "route.visit", "kanban,list,form")

    def action_open_due_overdue_promises(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(
            _("Dashboard Due / Overdue Promises"),
            payload["due_overdue_promises"],
            "route.visit.payment",
            "kanban,list,form",
            "route_core.action_route_visit_payment",
        )

    def action_open_pending_transfers(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(_("Dashboard Pending Transfers"), payload["pending_transfers"], "stock.picking", "list,form")

    def action_open_loading_proposals(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        return self._action_open_records(_("Dashboard Loading Proposals"), payload["loading_proposals"], "route.loading.proposal", "list,form")

    def action_open_return_transfers(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        pickings = self.env["stock.picking"]
        if payload["settings"].get("show_consignment"):
            pickings |= payload["visits"].mapped("return_picking_ids")
        if payload["settings"].get("show_direct_return"):
            pickings |= payload["direct_returns"].mapped("picking_ids")
        return self._action_open_records(_("Dashboard Return Transfers"), pickings, "stock.picking", "list,form")

    def action_open_refill_transfers(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        pickings = payload["visits"].mapped("refill_picking_id") if payload["settings"].get("show_consignment") else self.env["stock.picking"]
        return self._action_open_records(_("Dashboard Refill Transfers"), pickings, "stock.picking", "list,form")

    def action_open_dashboard_products(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        products = self._products_from_product_lines(payload["product_lines"])
        return self._action_open_records(_("Dashboard Products"), products, "product.product", "kanban,list,form")

    def action_open_top_selling_products(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        lines = sorted(payload["product_lines"], key=lambda line: line.get("sales", 0.0), reverse=True)[:20]
        products = self._products_from_product_lines(lines)
        return self._action_open_records(_("Dashboard Top Selling Products"), products, "product.product", "kanban,list,form")

    def action_open_top_returned_products(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        lines = sorted(payload["product_lines"], key=lambda line: line.get("returns", 0.0), reverse=True)[:20]
        products = self._products_from_product_lines(lines)
        return self._action_open_records(_("Dashboard Top Returned Products"), products, "product.product", "kanban,list,form")

    def action_open_dashboard_outlets(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        outlets = self._outlets_from_outlet_lines(payload["outlet_lines"])
        return self._action_open_records(_("Dashboard Outlets"), outlets, "route.outlet", "kanban,list,form")

    def action_open_top_sales_outlets(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        lines = sorted(payload["outlet_lines"], key=lambda line: line.get("sales", 0.0), reverse=True)[:20]
        outlets = self._outlets_from_outlet_lines(lines)
        return self._action_open_records(_("Dashboard Top Sales Outlets"), outlets, "route.outlet", "kanban,list,form")

    def action_open_highest_due_outlets(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        lines = sorted(payload["outlet_lines"], key=lambda line: line.get("open_due", 0.0), reverse=True)[:20]
        outlets = self._outlets_from_outlet_lines(lines)
        return self._action_open_records(_("Dashboard Highest Open Due Outlets"), outlets, "route.outlet", "kanban,list,form")

    def action_open_high_risk_outlets(self):
        self.ensure_one()
        payload = self._get_dashboard_payload()
        lines = sorted(payload["outlet_lines"], key=lambda line: line.get("risk", 0.0), reverse=True)[:20]
        outlets = self._outlets_from_outlet_lines(lines)
        return self._action_open_records(_("Dashboard High Risk Outlets"), outlets, "route.outlet", "kanban,list,form")

    def _products_from_product_lines(self, lines):
        product_ids = []
        for line in lines or []:
            product_id = line.get("product_id")
            if product_id and product_id not in product_ids:
                product_ids.append(product_id)
        return self.env["product.product"].browse(product_ids)

    def _outlets_from_outlet_lines(self, lines):
        outlet_ids = []
        for line in lines or []:
            outlet_id = line.get("outlet_id")
            if outlet_id and outlet_id not in outlet_ids:
                outlet_ids.append(outlet_id)
        return self.env["route.outlet"].browse(outlet_ids)

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
            rec.outlet_chart_html = rec._render_outlet_chart_html(payload)
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
        settings = self._get_dashboard_settings()

        Visit = self.env["route.visit"]
        Payment = self.env["route.visit.payment"]
        SaleOrder = self.env["sale.order"]
        DirectReturn = self.env["route.direct.return"]
        DailyClosing = self.env["route.daily.closing"]
        VehicleClosing = self.env["route.vehicle.closing"]
        LoadingProposal = self.env["route.loading.proposal"]

        visits = self._apply_operation_mode_to_visits(
            self._filter_visits_by_city(Visit.search(self._visit_domain())), settings
        )
        payments = Payment.search(
            [
                ("company_id", "=", company_id),
                ("payment_date", ">=", fields.Datetime.to_string(dt_from)),
                ("payment_date", "<=", fields.Datetime.to_string(dt_to)),
                ("state", "!=", "cancelled"),
            ]
        ).filtered(lambda payment: self._record_in_scope(payment) and self._record_allowed_by_operation_mode(payment, settings))
        confirmed_payments = payments.filtered(lambda payment: payment.state == "confirmed")

        promise_candidates = Payment.search(
            [
                ("company_id", "=", company_id),
                ("state", "!=", "cancelled"),
                ("promise_amount", ">", 0.0),
            ]
        ).filtered(lambda payment: self._record_in_scope(payment) and self._record_allowed_by_operation_mode(payment, settings))

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

        if settings["show_direct_sale"]:
            sale_orders = SaleOrder.search(
                [
                    ("company_id", "=", company_id),
                    ("route_order_mode", "=", "direct_sale"),
                    ("date_order", ">=", fields.Datetime.to_string(dt_from)),
                    ("date_order", "<=", fields.Datetime.to_string(dt_to)),
                    ("state", "not in", ["cancel", "cancelled"]),
                ]
            ).filtered(lambda order: self._record_in_scope(order))
        else:
            sale_orders = SaleOrder.browse()

        if settings["show_direct_return"]:
            direct_returns = DirectReturn.search(
                [
                    ("company_id", "=", company_id),
                    ("return_date", ">=", date_from),
                    ("return_date", "<=", date_to),
                    ("state", "!=", "cancel"),
                ]
            ).filtered(lambda ret: self._record_in_scope(ret))
        else:
            direct_returns = DirectReturn.browse()

        closing_records = DailyClosing.search(
            [
                ("company_id", "=", company_id),
                ("closing_date", ">=", date_from),
                ("closing_date", "<=", date_to),
            ]
        ).filtered(lambda closing: self._record_in_scope(closing))

        if settings["show_vehicle_closing"]:
            vehicle_closings = VehicleClosing.search(
                [
                    ("company_id", "=", company_id),
                    ("plan_date", ">=", date_from),
                    ("plan_date", "<=", date_to),
                ]
            ).filtered(lambda closing: self._record_in_scope(closing))
        else:
            vehicle_closings = VehicleClosing.browse()

        if settings["show_loading"]:
            loading_proposals = LoadingProposal.search(
                [
                    ("company_id", "=", company_id),
                    ("plan_date", ">=", date_from),
                    ("plan_date", "<=", date_to),
                ]
            ).filtered(lambda proposal: self._record_in_scope(proposal))
        else:
            loading_proposals = LoadingProposal.browse()

        route_transfer_candidates = self.env["stock.picking"]
        if settings["show_consignment"]:
            route_transfer_candidates |= visits.mapped("return_picking_ids") | visits.mapped("refill_picking_id")
        if settings["show_direct_return"]:
            route_transfer_candidates |= direct_returns.mapped("picking_ids")
        if settings["show_loading"]:
            route_transfer_candidates |= loading_proposals.mapped("picking_id")
        if settings["show_vehicle_closing"]:
            route_transfer_candidates |= vehicle_closings.mapped("reconciliation_picking_ids")
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
        if not settings["show_location"]:
            location_missing_checkin_visits = visits.browse()
            location_missing_outlet_visits = visits.browse()
            location_outside_zone_visits = visits.browse()
            location_needs_correction_visits = visits.browse()
            location_pending_review_visits = visits.browse()
            location_accepted_visits = visits.browse()
        location_issue_visits = (
            location_missing_checkin_visits
            | location_missing_outlet_visits
            | location_outside_zone_visits
            | location_needs_correction_visits
            | location_pending_review_visits
        )
        unfinished_visits = visits.filtered(lambda visit: visit.visit_process_state not in ("done", "cancel"))
        open_due_visits = visits.filtered(lambda visit: (visit.remaining_due_amount or 0.0) > 0.0)

        consignment_visits = visits.filtered(lambda visit: not self._visit_is_direct_sale(visit)) if settings["show_consignment"] else visits.browse()
        consignment_sales = sum((line.sold_amount or 0.0) for line in consignment_visits.mapped("line_ids"))
        consignment_returns = sum((line.return_amount or 0.0) for line in consignment_visits.mapped("line_ids"))
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
        for visit in consignment_visits:
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
        product_lines, gross_profit, missing_cost_product_count = self._build_product_lines(consignment_visits, sale_orders, direct_returns)
        outlet_lines, outlet_mode_summary = self._build_outlet_lines(
            visits, confirmed_payments, open_promises, sale_orders, direct_returns, location_issue_visits
        )

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
            "settings": settings,
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
            "outlet_lines": outlet_lines,
            "outlet_mode_summary": outlet_mode_summary,
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
            "product_id": False,
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
            values["product_id"] = product.id
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
            values["product_id"] = product.id
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
            values["product_id"] = product.id
            values["name"] = product.display_name
            qty = line.quantity or 0.0
            amount = line.estimated_amount or 0.0
            values["returns"] += amount
            values["profit"] -= amount - (qty * (product.standard_price or 0.0))
            mark_missing_cost(product, qty, amount)
        lines = sorted(data.values(), key=lambda item: item["sales"], reverse=True)
        return lines, sum(line["profit"] for line in lines), len(missing_cost_product_ids)

    def _outlet_mode_key(self, outlet):
        mode = (getattr(outlet, "outlet_operation_mode", False) or "consignment") if outlet else "consignment"
        return "direct_sale" if mode in ("direct_sale", "direct_sales") else "consignment"

    def _outlet_mode_label(self, mode):
        return _("Direct Sale") if mode == "direct_sale" else _("Consignment")

    def _build_outlet_lines(self, visits, confirmed_payments, open_promises, sale_orders, direct_returns, location_issue_visits):
        data = defaultdict(lambda: {
            "outlet_id": False,
            "name": _("No Outlet"),
            "mode": "consignment",
            "mode_label": _("Consignment"),
            "visits": 0,
            "done": 0,
            "unfinished": 0,
            "sales": 0.0,
            "collection": 0.0,
            "open_due": 0.0,
            "promises": 0.0,
            "returns": 0.0,
            "location": 0,
            "risk": 0.0,
            "collection_rate": 0.0,
            "return_rate": 0.0,
        })

        def values_for(outlet):
            key = outlet.id if outlet else 0
            values = data[key]
            if outlet:
                values["outlet_id"] = outlet.id
                values["name"] = outlet.display_name
                values["mode"] = self._outlet_mode_key(outlet)
                values["mode_label"] = self._outlet_mode_label(values["mode"])
            return values

        for visit in visits:
            values = values_for(visit.outlet_id)
            values["visits"] += 1
            if visit.visit_process_state == "done":
                values["done"] += 1
            elif visit.visit_process_state != "cancel":
                values["unfinished"] += 1
            values["open_due"] += visit.remaining_due_amount or 0.0
            if values["mode"] != "direct_sale":
                values["sales"] += sum((line.sold_amount or 0.0) for line in visit.line_ids)
                values["returns"] += sum((line.return_amount or 0.0) for line in visit.line_ids)

        for visit in location_issue_visits:
            values_for(visit.outlet_id)["location"] += 1

        for order in sale_orders:
            values = values_for(order.route_outlet_id)
            values["sales"] += order.amount_total or 0.0
            if "direct_sale_remaining_due" in order._fields:
                values["open_due"] += order.direct_sale_remaining_due or 0.0

        for payment in confirmed_payments:
            values_for(payment.outlet_id)["collection"] += payment.amount or 0.0

        for payment in open_promises:
            values_for(payment.outlet_id)["promises"] += payment.effective_promise_amount or payment.promise_amount or 0.0

        for ret in direct_returns:
            values_for(ret.outlet_id)["returns"] += ret.amount_total or 0.0

        lines = []
        for values in data.values():
            if not any((values["visits"], values["sales"], values["collection"], values["open_due"], values["promises"], values["returns"], values["location"])):
                continue
            values["collection_rate"] = (values["collection"] / values["sales"] * 100.0) if values["sales"] else 0.0
            values["return_rate"] = (values["returns"] / values["sales"] * 100.0) if values["sales"] else 0.0
            values["risk"] = (
                (values["unfinished"] * 5.0)
                + (values["location"] * 3.0)
                + (1.0 if values["promises"] else 0.0)
                + (values["open_due"] / 10.0)
                + (values["returns"] / 25.0)
            )
            lines.append(values)

        summary = {
            "direct_sale": {
                "label": _("Direct Sale"),
                "outlets": 0,
                "visits": 0,
                "sales": 0.0,
                "collection": 0.0,
                "open_due": 0.0,
                "promises": 0.0,
                "returns": 0.0,
                "collection_rate": 0.0,
                "return_rate": 0.0,
            },
            "consignment": {
                "label": _("Consignment"),
                "outlets": 0,
                "visits": 0,
                "sales": 0.0,
                "collection": 0.0,
                "open_due": 0.0,
                "promises": 0.0,
                "returns": 0.0,
                "collection_rate": 0.0,
                "return_rate": 0.0,
            },
        }
        for line in lines:
            bucket = summary[line["mode"]]
            bucket["outlets"] += 1
            bucket["visits"] += line["visits"]
            bucket["sales"] += line["sales"]
            bucket["collection"] += line["collection"]
            bucket["open_due"] += line["open_due"]
            bucket["promises"] += line["promises"]
            bucket["returns"] += line["returns"]
        for bucket in summary.values():
            bucket["collection_rate"] = (bucket["collection"] / bucket["sales"] * 100.0) if bucket["sales"] else 0.0
            bucket["return_rate"] = (bucket["returns"] / bucket["sales"] * 100.0) if bucket["sales"] else 0.0

        return sorted(lines, key=lambda item: (item["risk"], item["open_due"], item["returns"], item["sales"]), reverse=True), summary


    def _dashboard_target(self):
        return "supervisor"

    def action_open_dashboard_configuration(self):
        return self.env["route.dashboard.widget"].action_open_dashboard_configuration()

    def action_customize_dashboard(self):
        self.ensure_one()
        return self.env["route.dashboard.user.preference"].action_open_my_dashboard_preferences(
            target=self._dashboard_target(),
            company=self.company_id,
            user=self.env.user,
        )

    def _dashboard_widget_enabled(self, code, target=False):
        self.ensure_one()
        target = target or self._dashboard_target()
        return self.env["route.dashboard.widget"].is_enabled(code, target, company=self.company_id)

    def _dashboard_chart_card(self, code, title, chart_html, footer="", wide=False, target=False):
        if not self._dashboard_widget_enabled(code, target=target):
            return ""
        return self._chart_card(title, chart_html, footer, wide=wide)

    def _render_executive_html(self, payload):
        if not self._dashboard_widget_enabled("command_center"):
            return ""
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
        settings = payload["settings"]
        cards = [
            self._kpi_card(_("Visits"), self._num(visit_total), _("Completed: %s") % self._num(done), "primary", f"{completion:.0f}%"),
            self._kpi_card(_("Collection"), self._money(payload["total_collected"]), _("Rate: %s%%") % f"{collection_rate:.0f}", "success"),
            self._kpi_card(_("Net Sales"), self._money(payload["net_sales"]), _("Gross: %s") % self._money(payload["gross_sales"]), "sales"),
            self._kpi_card(_("Due / Open Promises"), self._money(payload["open_promise_amount"]), _("Due/Overdue: %s") % self._num(len(payload["due_overdue_promises"])), "warning"),
            self._kpi_card(_("Open Due"), self._money(payload["open_due_amount"]), _("Visits: %s") % self._num(len(payload["open_due_visits"])), "danger"),
            self._kpi_card(_("Estimated Profit"), self._money(payload["gross_profit"]), _("Margin: %s%% | Cost data: %s%%") % (f"{margin:.0f}", f"{profit_quality:.0f}"), "profit"),
            self._kpi_card(_("Closed Operating Days"), self._num(payload["closed_day_count"]), _("Open / Not Ready: %s") % self._num(payload["open_day_count"]), "success"),
            self._kpi_card(_("Reopened Days"), self._num(payload["reopened_day_count"]), _("Operating days: %s") % self._num(payload["period_day_count"]), "warning"),
        ]
        if settings["show_vehicle_closing"]:
            cards.append(self._kpi_card(_("Vehicle Issues"), self._num(payload["pending_vehicle_issues"]), _("Vehicle closing checks"), "danger"))
        if settings["show_location"]:
            cards.append(self._kpi_card(_("Location Review"), self._num(len(payload["location_issue_visits"])), _("Outside/missing/pending review"), "warning"))
        if settings["show_stock_transfers"]:
            cards.append(self._kpi_card(_("Pending Transfers"), self._num(payload["pending_transfer_count"]), _("Stock moves not done"), "info"))
        if settings["show_consignment"] or settings["show_direct_return"]:
            cards.append(self._kpi_card(_("Returns"), self._money(payload["total_returns"]), _("Return orders/transfers"), "danger"))
        scope = self._scope_badges()
        title = self._section_title(
            _("Performance Command Center"),
            _("High-level KPIs for visits, collections, promises, stock operations, and sales performance."),
        )
        return (
            f"<div class='route_dash_block'>{title}{scope}{self._settings_badges(settings)}"
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
        settings = payload["settings"]
        insights = [
            (_("Best Collector"), best_salesperson and best_salesperson.get("name") or _("No data"), best_salesperson and self._money(best_salesperson.get("collection")) or "-", "success"),
            (_("Top Product"), top_product and top_product.get("name") or _("No data"), top_product and self._money(top_product.get("sales")) or "-", "sales"),
            (_("Highest Open Due"), highest_due and highest_due[0] or _("No open due"), highest_due and self._money(highest_due[1]) or "-", "danger"),
        ]
        if settings["show_consignment"] or settings["show_direct_return"]:
            insights.append((_("Most Returned Product"), top_return_product and top_return_product.get("name") or _("No returns"), top_return_product and self._money(top_return_product.get("returns")) or "-", "warning"))
        if settings["show_vehicle_closing"]:
            insights.append((_("Critical Vehicle"), critical_vehicle and critical_vehicle.get("name") or _("No data"), critical_vehicle and _("Issues: %s") % self._num(critical_vehicle.get("issues")) or "-", "danger"))
        insights.append((_("Collection Rate"), f"{collection_rate:.0f}%", _("Attention score: %s") % self._num(attention_score), "info"))
        return "<div class='route_dash_insight_grid'>" + "".join(
            self._insight_card(title, value, note, tone) for title, value, note, tone in insights
        ) + "</div>"

    def _render_visit_chart_html(self, payload):
        status = payload["visit_status"]
        visit_total = len(payload["visits"])
        done = status.get("done", 0)
        active = status.get("active", 0)
        not_started = status.get("not_started", 0)
        cancelled = status.get("cancelled", 0)
        started = done + active
        unfinished = len(payload["unfinished_visits"])
        completion = (done / visit_total * 100.0) if visit_total else 0.0
        start_rate = (started / visit_total * 100.0) if visit_total else 0.0
        settings = payload["settings"]

        funnel_rows = [
            (_("Planned Visits"), visit_total, "#64748b"),
            (_("Started"), started, "#0ea5e9"),
            (_("Completed"), done, "#16a34a"),
            (_("Unfinished"), unfinished, "#ef4444"),
        ]
        status_rows = [
            (_("Completed"), done, "#16a34a"),
            (_("In Progress"), active, "#0ea5e9"),
            (_("Not Started"), not_started, "#f59e0b"),
            (_("Cancelled"), cancelled, "#ef4444"),
        ]
        operations_rows = [
            (_("Unfinished Visits"), unfinished, "#ef4444"),
            (_("Due / Overdue Promises"), len(payload["due_overdue_promises"]), "#8b5cf6"),
        ]
        action_rows = [
            (_("Open Unfinished"), self._num(unfinished), _("Use Unfinished button"), "#ef4444"),
            (_("Review Promises"), self._money(payload["open_promise_amount"]), _("Use Promises button"), "#8b5cf6"),
        ]
        if settings["show_location"]:
            action_rows.append((_("Review Locations"), self._num(len(payload["location_issue_visits"])), _("Use Location Review"), "#f59e0b"))
        if settings["show_vehicle_closing"]:
            operations_rows.append((_("Vehicle Issues"), payload["pending_vehicle_issues"], "#64748b"))
            action_rows.append((_("Check Vehicles"), self._num(payload["pending_vehicle_issues"]), _("Use Vehicle Issues"), "#64748b"))
        if settings["show_stock_transfers"]:
            operations_rows.append((_("Pending Transfers"), payload["pending_transfer_count"], "#0ea5e9"))
            action_rows.append((_("Follow Transfers"), self._num(payload["pending_transfer_count"]), _("Use Transfers / Loading"), "#0ea5e9"))
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
        health_tiles = [
            (_("Start Rate"), f"{start_rate:.0f}%", _("Visits already started"), "#0ea5e9"),
            (_("Completion Rate"), f"{completion:.0f}%", _("Visits completed"), "#16a34a"),
            (_("Unfinished"), self._num(unfinished), _("Needs supervisor follow-up"), "#ef4444"),
            (_("Not Started"), self._num(not_started), _("Remaining visits"), "#f59e0b"),
        ]
        html = self._section_title(_("Visit Execution Control"), _("Operational view for route progress, exceptions, and closing readiness."))
        html += "<div class='route_dash_chart_grid route_dash_supervisor_ops route_dash_action_priority_zone'>"
        html += self._dashboard_chart_card("route_execution_funnel", _("Route Execution Funnel"), self._funnel_chart(funnel_rows), _("Planned → started → completed, with unfinished visits highlighted."), wide=True)
        html += self._dashboard_chart_card("action_priority_cards", _("Action Priority Cards"), self._spotlight_tiles(action_rows), _("Use the top toolbar buttons to open and resolve each exception."), wide=True)
        html += self._dashboard_chart_card("execution_pulse", _("Execution Pulse"), self._spotlight_tiles(health_tiles), _("Fast operational signals for the supervisor."))
        html += self._dashboard_chart_card("visit_status_chart", _("Visit Status"), self._pie_chart(status_rows), self._legend(status_rows))
        html += self._dashboard_chart_card("attention_mix", _("Attention Mix"), self._horizontal_bars(operations_rows), _("Only active blockers enabled in Route Settings are shown here."))
        if settings["show_location"]:
            html += self._dashboard_chart_card("location_review_breakdown", _("Location Review Breakdown"), self._horizontal_bars(location_rows), _("Location is split by reason to avoid one confusing total."))
        html += self._dashboard_chart_card("closing_status_chart", _("Closing Status"), self._pie_chart(closing_rows), self._legend(closing_rows) + _(" Operating days only."))
        html += "</div>"
        return f"<div class='route_dash_block route_dash_supervisor_operational'>{html}</div>"

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
        net_sales = payload["net_sales"] or 0.0
        collection_gap = max(net_sales - (payload["total_collected"] or 0.0), 0.0)
        collection_rate = (payload["total_collected"] / net_sales * 100.0) if net_sales else 0.0
        promise_count = len(payload["open_promises"])
        due_count = len(payload["due_overdue_promises"])
        workload_tiles = [
            (_("Collected"), self._money(payload["total_collected"]), _("Confirmed payments"), "#16a34a"),
            (_("Collection Rate"), f"{collection_rate:.0f}%", _("Collected vs net sales"), "#0ea5e9"),
            (_("Collection Gap"), self._money(collection_gap), _("Net sales not collected"), "#f97316"),
            (_("Open Promises"), self._money(payload["open_promise_amount"]), _("%s promises") % self._num(promise_count), "#8b5cf6"),
            (_("Due / Overdue"), self._num(due_count), self._money(payload["due_overdue_promise_amount"]), "#ef4444"),
        ]
        html = self._section_title(_("Collections and Cash Flow Control"), _("Collection workload, promise pressure, payment method mix, and trend over time."))
        html += "<div class='route_dash_chart_grid'>"
        html += self._dashboard_chart_card("collection_workload", _("Collection Workload"), self._spotlight_tiles(workload_tiles), _("Supervisor follow-up priorities for collections and promises."), wide=True)
        html += self._dashboard_chart_card("payment_method_mix", _("Payment Method Mix"), self._pie_chart(payment_rows), self._legend(payment_rows))
        html += self._dashboard_chart_card("collection_by_salesperson", _("Collection by Salesperson"), self._horizontal_bars(salesperson_rows, money=True), _("Who collected the most cash in the selected period."))
        html += self._dashboard_chart_card("sales_collection_trend", _("Sales vs Collection Trend"), line_html, _("Line compares sales and collections in the selected date range."), wide=True)
        html += "</div>"
        return f"<div class='route_dash_block route_dash_supervisor_collections'>{html}</div>"

    def _render_product_chart_html(self, payload):
        top_products = payload["product_lines"][:5]
        product_sales = [(line["name"], line["sales"], "#0ea5e9") for line in top_products]
        product_qty = [(line["name"], line["qty"], "#8b5cf6") for line in top_products]
        profit_rows = [(line["name"], line["profit"], "#16a34a" if line["profit"] >= 0 else "#ef4444") for line in top_products]
        product_returns = [
            (line["name"], line.get("returns", 0.0), "#ef4444")
            for line in sorted(payload["product_lines"], key=lambda item: item.get("returns", 0.0), reverse=True)[:5]
        ]
        settings = payload["settings"]
        sales_return_rows = [
            (_("Gross Sales"), payload["gross_sales"], "#16a34a"),
        ]
        if settings["show_consignment"] or settings["show_direct_return"]:
            sales_return_rows.append((_("Returns"), payload["total_returns"], "#ef4444"))
        sales_return_rows += [
            (_("Net Sales"), payload["net_sales"], "#0ea5e9"),
            (_("Estimated Profit"), payload["gross_profit"], "#8b5cf6"),
        ]
        product_count = len([line for line in payload["product_lines"] if line.get("sales") or line.get("qty") or line.get("returns")])
        top_product = top_products[0] if top_products else False
        top_profit = max(payload["product_lines"], key=lambda line: line.get("profit", 0.0), default=False)
        top_returned = max(payload["product_lines"], key=lambda line: line.get("returns", 0.0), default=False)
        profit_margin = (payload["gross_profit"] / payload["gross_sales"] * 100.0) if payload["gross_sales"] else 0.0
        product_tiles = [
            (_("Active Products"), self._num(product_count), _("Sold / returned in period"), "#0ea5e9"),
            (_("Top Product"), top_product and top_product.get("name") or _("No data"), top_product and self._money(top_product.get("sales")) or "-", "#16a34a"),
            (_("Profit Margin"), f"{profit_margin:.0f}%", _("Estimated from product cost"), "#8b5cf6"),
            (_("Most Returned"), top_returned and top_returned.get("name") or _("No returns"), top_returned and self._money(top_returned.get("returns")) or "-", "#ef4444"),
        ]
        quality_note = _("Missing cost products: %s. Profit is estimated from product cost.") % self._num(payload["missing_cost_product_count"])
        html = self._section_title(_("Products, Sales, and Stock Movement Signals"), quality_note)
        html += "<div class='route_dash_chart_grid'>"
        html += self._dashboard_chart_card("product_operations_pulse", _("Product Operations Pulse"), self._spotlight_tiles(product_tiles), _("Quick product signals for daily supervision."), wide=True)
        html += self._dashboard_chart_card("commercial_mix_columns", _("Sales / Returns / Profit Columns"), self._column_chart(sales_return_rows, money=True), _("Visual commercial mix for the selected period."), wide=True)
        html += self._dashboard_chart_card("top_products_sales", _("Top Products by Sales"), self._horizontal_bars(product_sales, money=True), "")
        html += self._dashboard_chart_card("top_products_quantity", _("Top Products by Quantity"), self._horizontal_bars(product_qty), "")
        if settings["show_consignment"] or settings["show_direct_return"]:
            html += self._dashboard_chart_card("top_returned_products", _("Top Returned Products"), self._horizontal_bars(product_returns, money=True), _("Return exposure by product."))
        html += self._dashboard_chart_card("estimated_product_profit", _("Estimated Product Profit"), self._horizontal_bars(profit_rows, money=True, allow_negative=True), _("Profit is safest when all products have standard cost."), wide=True)
        html += "</div>"
        return f"<div class='route_dash_block route_dash_supervisor_products'>{html}</div>"

    def _render_outlet_chart_html(self, payload):
        settings = payload["settings"]
        outlet_lines = payload.get("outlet_lines") or []
        summary = payload.get("outlet_mode_summary") or {}
        direct = summary.get("direct_sale") or {}
        consignment = summary.get("consignment") or {}

        top_sales = sorted(outlet_lines, key=lambda line: line.get("sales", 0.0), reverse=True)[:6]
        top_collection = sorted(outlet_lines, key=lambda line: line.get("collection", 0.0), reverse=True)[:6]
        top_due = sorted(outlet_lines, key=lambda line: line.get("open_due", 0.0), reverse=True)[:6]
        top_returns = sorted(outlet_lines, key=lambda line: line.get("returns", 0.0), reverse=True)[:6]
        risk_lines = sorted(outlet_lines, key=lambda line: line.get("risk", 0.0), reverse=True)[:6]

        outlet_cards_parts = []
        if settings["show_direct_sale"]:
            outlet_cards_parts.append(self._outlet_mode_card("direct", _("Direct Sale Outlets"), direct))
        if settings["show_consignment"]:
            outlet_cards_parts.append(self._outlet_mode_card("consignment", _("Consignment Outlets"), consignment))
        outlet_cards = "<div class='route_dash_outlet_mode_grid'>%s</div>" % "".join(outlet_cards_parts)

        if settings["show_outlet_comparison"]:
            title = _("Direct Sale vs Consignment Outlet Performance")
            subtitle = _("Compare direct-sale and consignment outlets by sales, collection, open due, returns, and operational risk.")
        elif settings["show_direct_sale"]:
            title = _("Direct Sale Outlet Performance")
            subtitle = _("Direct-sale outlet performance by sales orders, collections, open due, returns, and operational risk.")
        else:
            title = _("Consignment Outlet Performance")
            subtitle = _("Consignment outlet performance by visit sales, collection, returns, shelf movement, and operational risk.")

        html = self._section_title(title, subtitle)
        if self._dashboard_widget_enabled("outlet_mode_summary_cards"):
            html += outlet_cards
        html += "<div class='route_dash_chart_grid'>"
        if settings["show_outlet_comparison"]:
            comparison_rows = [
                (_("Sales"), direct.get("sales", 0.0), consignment.get("sales", 0.0), True),
                (_("Collection"), direct.get("collection", 0.0), consignment.get("collection", 0.0), True),
                (_("Open Due"), direct.get("open_due", 0.0), consignment.get("open_due", 0.0), True),
                (_("Returns"), direct.get("returns", 0.0), consignment.get("returns", 0.0), True),
                (_("Visits"), direct.get("visits", 0), consignment.get("visits", 0), False),
            ]
            html += self._dashboard_chart_card("direct_vs_consignment", _("Direct Sale vs Consignment"), self._dual_horizontal_bars(comparison_rows), _("Side-by-side comparison by outlet operation mode."), wide=True)
        else:
            active_summary = direct if settings["show_direct_sale"] else consignment
            activity_rows = [
                (_("Sales"), active_summary.get("sales", 0.0), "#0ea5e9"),
                (_("Collection"), active_summary.get("collection", 0.0), "#16a34a"),
                (_("Open Due"), active_summary.get("open_due", 0.0), "#ef4444"),
                (_("Returns"), active_summary.get("returns", 0.0), "#f97316"),
                (_("Visits"), active_summary.get("visits", 0), "#8b5cf6"),
            ]
            html += self._dashboard_chart_card("direct_vs_consignment", _("Outlet Activity Mix"), self._horizontal_bars(activity_rows), _("Displayed according to the active Route Operation Mode."), wide=True)
        html += self._dashboard_chart_card("top_outlets_sales", _("Top Outlets by Sales"), self._horizontal_bars([(line["name"], line["sales"], "#0ea5e9") for line in top_sales], money=True), _("Revenue leaders for the enabled outlet workflow."))
        html += self._dashboard_chart_card("top_outlets_collection", _("Top Outlets by Collection"), self._horizontal_bars([(line["name"], line["collection"], "#16a34a") for line in top_collection], money=True), _("Best cash collection outlets."))
        html += self._dashboard_chart_card("highest_due_outlets", _("Highest Open Due Outlets"), self._horizontal_bars([(line["name"], line["open_due"], "#ef4444") for line in top_due], money=True), _("Priority collection follow-up."))
        if settings["show_consignment"] or settings["show_direct_return"]:
            html += self._dashboard_chart_card("top_returned_outlets", _("Top Returned Outlets"), self._horizontal_bars([(line["name"], line["returns"], "#f97316") for line in top_returns], money=True), _("Helps identify slow movement, mismatch, or display issues."))
        html += self._dashboard_chart_card("outlet_risk_ranking", _("Outlet Risk Ranking"), self._outlet_risk_cards(risk_lines), _("Risk combines unfinished visits, location issues, open due, promises, and returns."), wide=True)
        html += "</div>"
        return f"<div class='route_dash_block route_dash_outlet_block'>{html}</div>"

    def _outlet_mode_card(self, tone, title, values):
        sales = values.get("sales", 0.0) or 0.0
        collection = values.get("collection", 0.0) or 0.0
        collection_rate = values.get("collection_rate", 0.0) or 0.0
        return_rate = values.get("return_rate", 0.0) or 0.0
        return (
            f"<div class='route_dash_outlet_mode route_dash_outlet_{escape(tone)}'>"
            f"<div><span>{escape(str(title))}</span><strong>{escape(self._num(values.get('outlets', 0)))}</strong><small>{escape(_('active outlets in selected period'))}</small></div>"
            "<div class='route_dash_outlet_mode_metrics'>"
            f"<span><small>{escape(_('Sales'))}</small><b>{escape(self._money(sales))}</b></span>"
            f"<span><small>{escape(_('Collection'))}</small><b>{escape(self._money(collection))}</b></span>"
            f"<span><small>{escape(_('Open Due'))}</small><b>{escape(self._money(values.get('open_due', 0.0)))}</b></span>"
            f"<span><small>{escape(_('Returns'))}</small><b>{escape(self._money(values.get('returns', 0.0)))}</b></span>"
            f"<span><small>{escape(_('Collection Rate'))}</small><b>{collection_rate:.0f}%</b></span>"
            f"<span><small>{escape(_('Return Rate'))}</small><b>{return_rate:.0f}%</b></span>"
            "</div></div>"
        )

    def _dual_horizontal_bars(self, rows):
        cleaned = [(label, float(direct or 0.0), float(consignment or 0.0), bool(money)) for label, direct, consignment, money in rows if direct or consignment]
        if not cleaned:
            return self._empty_chart()
        max_value = max(max(abs(direct), abs(consignment)) for _label, direct, consignment, _money in cleaned) or 1.0
        html = "<div class='route_dash_dual_bars'>"
        html += (
            "<div class='route_dash_dual_legend'>"
            "<span><i class='route_dash_direct_dot'></i>Direct Sale</span>"
            "<span><i class='route_dash_consignment_dot'></i>Consignment</span>"
            "</div>"
        )
        for label, direct, consignment, money in cleaned:
            direct_width = max(min(abs(direct) / max_value * 100.0, 100.0), 2.0) if direct else 0.0
            consignment_width = max(min(abs(consignment) / max_value * 100.0, 100.0), 2.0) if consignment else 0.0
            direct_display = self._money(direct) if money else self._short_num(direct)
            consignment_display = self._money(consignment) if money else self._short_num(consignment)
            html += (
                "<div class='route_dash_dual_row'>"
                f"<div class='route_dash_dual_label'>{escape(str(label))}</div>"
                "<div class='route_dash_dual_lines'>"
                f"<div class='route_dash_dual_line'><span>{escape(_('Direct Sale'))}</span><div><i class='route_dash_direct_bar' style='width:{direct_width:.2f}%'></i></div><strong>{escape(direct_display)}</strong></div>"
                f"<div class='route_dash_dual_line'><span>{escape(_('Consignment'))}</span><div><i class='route_dash_consignment_bar' style='width:{consignment_width:.2f}%'></i></div><strong>{escape(consignment_display)}</strong></div>"
                "</div></div>"
            )
        html += "</div>"
        return html

    def _outlet_risk_cards(self, lines):
        if not lines:
            return self._empty_chart()
        html = "<div class='route_dash_outlet_risk_grid'>"
        for line in lines:
            risk = line.get("risk", 0.0) or 0.0
            risk_label = _("High") if risk >= 25 else (_("Medium") if risk >= 8 else _("Low"))
            html += (
                "<div class='route_dash_outlet_risk_card'>"
                f"<div><strong>{escape(str(line.get('name') or _('No Outlet')))}</strong><span>{escape(str(line.get('mode_label') or ''))}</span></div>"
                f"<b>{escape(risk_label)}</b>"
                "<small>"
                f"{escape(_('Due'))}: {escape(self._money(line.get('open_due', 0.0)))} · "
                f"{escape(_('Returns'))}: {escape(self._money(line.get('returns', 0.0)))} · "
                f"{escape(_('Issues'))}: {escape(self._num((line.get('unfinished', 0) or 0) + (line.get('location', 0) or 0)))}"
                "</small>"
                "</div>"
            )
        html += "</div>"
        return html

    def _render_ranking_html(self, payload):
        salesperson_rows = payload["salesperson_lines"][:8]
        vehicle_rows = payload["vehicle_lines"][:8]
        settings = payload["settings"]
        focus_rows = []
        for line in salesperson_rows[:6]:
            visits = line.get("visits", 0) or 0
            done = line.get("done", 0) or 0
            completion = (done / visits * 100.0) if visits else 0.0
            focus_rows.append((line.get("name") or _("No Salesperson"), line.get("issues", 0), completion, line.get("promises", 0.0)))
        html = self._section_title(_("Team and Operations Ranking"), _("Who needs support and where operational risk is concentrated."))
        html += "<div class='route_dash_chart_grid'>"
        html += self._dashboard_chart_card("salesperson_ranking", _("Salesperson Focus Ladder"), self._salesperson_focus_ladder(focus_rows), _("Ranked by issues, with completion and promises for context."), wide=True)
        html += "</div>"
        html += "<div class='route_dash_ranking_grid'>"
        if self._dashboard_widget_enabled("salesperson_ranking"):
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
        if settings.get("show_vehicle_closing") and self._dashboard_widget_enabled("vehicle_risk_ranking"):
            html += self._ranking_table(
                _("Vehicle Issue Ranking"),
                [_('Vehicle'), _('Visits'), _('Unfinished'), _('Variance'), _('Issues')],
                [
                    [line["name"], self._num(line["visits"]), self._num(line["unfinished"]), self._num(line["variance"]), self._num(line["issues"])]
                    for line in vehicle_rows
                ],
            )
        html += "</div>"
        return f"<div class='route_dash_block route_dash_supervisor_ranking'>{html}</div>"


    def _funnel_chart(self, rows):
        rows = [(label, value, color) for label, value, color in rows if value is not None]
        if not rows or not any(float(value or 0.0) for _label, value, _color in rows):
            return self._empty_chart()
        max_value = max(float(value or 0.0) for _label, value, _color in rows) or 1.0
        base_value = float(rows[0][1] or 0.0) or max_value
        html = "<div class='route_dash_funnel'>"
        for label, value, color in rows:
            raw_value = float(value or 0.0)
            width = max(min(raw_value / max_value * 100.0, 100.0), 4.0) if raw_value else 0.0
            share = (raw_value / base_value * 100.0) if base_value else 0.0
            html += (
                "<div class='route_dash_funnel_step'>"
                "<div class='route_dash_funnel_head'>"
                f"<span>{escape(str(label))}</span>"
                f"<strong>{escape(self._num(raw_value))}</strong>"
                "</div>"
                f"<div class='route_dash_funnel_bar' style='width:{width:.2f}%; background:{escape(color)}'></div>"
                f"<small>{share:.0f}% {escape(_('of planned visits'))}</small>"
                "</div>"
            )
        html += "</div>"
        return html

    def _column_chart(self, rows, money=False, allow_negative=False):
        rows = [(label, value, color) for label, value, color in rows if value or allow_negative]
        if not rows:
            return self._empty_chart()
        max_value = max(abs(float(value or 0.0)) for _label, value, _color in rows) or 1.0
        html = "<div class='route_dash_column_chart route_dash_supervisor_columns'>"
        for label, value, color in rows:
            raw_value = float(value or 0.0)
            height = max(min(abs(raw_value) / max_value * 100.0, 100.0), 8.0) if raw_value or allow_negative else 0.0
            display = self._money(raw_value) if money else self._short_num(raw_value)
            negative_class = " route_dash_column_negative" if raw_value < 0 else ""
            html += (
                f"<div class='route_dash_column_item{negative_class}'>"
                f"<div class='route_dash_column_value'>{escape(display)}</div>"
                "<div class='route_dash_column_track'>"
                f"<div class='route_dash_column_bar' style='height:{height:.2f}%; background:{escape(color)};'></div>"
                "</div>"
                f"<div class='route_dash_column_label'>{escape(str(label))}</div>"
                "</div>"
            )
        html += "</div>"
        return html

    def _spotlight_tiles(self, rows):
        rows = [row for row in rows if row and row[1] not in (False, None, "")]
        if not rows:
            return self._empty_chart()
        html = "<div class='route_dash_spotlight_grid route_dash_supervisor_spotlights'>"
        for title, value, note, color in rows:
            html += (
                "<div class='route_dash_spotlight_tile'>"
                f"<span class='route_dash_spotlight_dot' style='background:{escape(color)}; box-shadow: 0 0 0 10px {escape(color)}22;'></span>"
                f"<strong>{escape(str(value))}</strong>"
                f"<span>{escape(str(title))}</span>"
                f"<small>{escape(str(note or ''))}</small>"
                "</div>"
            )
        html += "</div>"
        return html

    def _salesperson_focus_ladder(self, rows):
        rows = [row for row in rows if row]
        if not rows:
            return self._empty_chart()
        max_issues = max(float(row[1] or 0.0) for row in rows) or 1.0
        html = "<div class='route_dash_focus_ladder'>"
        for name, issues, completion, promises in rows:
            issues_value = float(issues or 0.0)
            width = max(min(issues_value / max_issues * 100.0, 100.0), 4.0) if issues_value else 2.0
            color = "#ef4444" if issues_value else "#16a34a"
            html += (
                "<div class='route_dash_focus_row'>"
                "<div class='route_dash_focus_name'>"
                f"<strong>{escape(str(name or _('No Salesperson')))}</strong>"
                f"<span>{escape(_('Completion'))}: {completion:.0f}% · {escape(_('Promises'))}: {escape(self._money(promises or 0.0))}</span>"
                "</div>"
                f"<div class='route_dash_focus_track'><div style='width:{width:.2f}%; background:{escape(color)}'></div></div>"
                f"<b>{escape(self._num(issues_value))}</b>"
                "</div>"
            )
        html += "</div>"
        return html

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

    def _settings_badges(self, settings):
        active = [(_("Operation Mode"), settings.get("operation_mode_label") or _("Hybrid"))]
        if settings.get("show_location"):
            active.append((_("Location Check-in"), _("Enabled")))
        if settings.get("show_vehicle_closing"):
            active.append((_("Vehicle Closing"), _("Enabled")))
        if settings.get("show_loading"):
            active.append((_("Vehicle Loading"), (settings.get("loading_workflow") or "").title()))
        if settings.get("show_lot_expiry"):
            active.append((_("Lot / Expiry"), _("Enabled")))
        return "<div class='route_dash_settings_strip'>" + "".join(
            f"<span><small>{escape(str(label))}</small>{escape(str(value))}</span>" for label, value in active
        ) + "</div>"

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


