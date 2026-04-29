from datetime import timedelta
from html import escape

from odoo import _, api, fields, models


class RouteManagerExecutiveDashboard(models.TransientModel):
    _name = "route.manager.executive.dashboard"
    _inherit = "route.supervisor.performance.dashboard"
    _description = "Manager Executive Dashboard"
    _rec_name = "name"

    name = fields.Char(
        string="Name",
        default=lambda self: _("Manager Executive Dashboard"),
        readonly=True,
    )
    executive_overview_html = fields.Html(
        string="Executive Overview",
        compute="_compute_manager_dashboard_html",
        sanitize=False,
        readonly=True,
    )
    period_comparison_html = fields.Html(
        string="Period Comparison",
        compute="_compute_manager_dashboard_html",
        sanitize=False,
        readonly=True,
    )
    commercial_health_html = fields.Html(
        string="Commercial Health",
        compute="_compute_manager_dashboard_html",
        sanitize=False,
        readonly=True,
    )
    market_ranking_html = fields.Html(
        string="Market Ranking",
        compute="_compute_manager_dashboard_html",
        sanitize=False,
        readonly=True,
    )
    executive_risk_html = fields.Html(
        string="Executive Risk",
        compute="_compute_manager_dashboard_html",
        sanitize=False,
        readonly=True,
    )

    @api.model
    def _dashboard_target(self):
        return "manager"

    def action_customize_dashboard(self):
        self.ensure_one()
        return self.env["route.dashboard.user.preference"].action_open_my_dashboard_preferences(
            target=self._dashboard_target(),
            company=self.company_id,
            user=self.env.user,
        )

    def action_open_manager_dashboard(self):
        today = fields.Date.context_today(self)
        dashboard = self.create(
            {
                "name": _("Manager Executive Dashboard"),
                "company_id": self.env.company.id,
                "period_filter": "last_30",
                "dashboard_focus_mode": self._get_user_dashboard_focus_mode(target="manager"),
                "date_from": today - timedelta(days=29),
                "date_to": today,
            }
        )
        view = self.env.ref("route_core.view_route_manager_executive_dashboard_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Manager Executive Dashboard"),
            "res_model": "route.manager.executive.dashboard",
            "res_id": dashboard.id,
            "view_mode": "form",
            "target": "current",
            "context": {"create": False, "edit": True, "delete": False},
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_open_supervisor_dashboard(self):
        self.ensure_one()
        dashboard = self.env["route.supervisor.performance.dashboard"].create(
            {
                "name": _("Supervisor Performance Dashboard"),
                "company_id": self.company_id.id,
                "period_filter": self.period_filter,
                "dashboard_focus_mode": self._get_user_dashboard_focus_mode(target="supervisor"),
                "date_from": self.date_from,
                "date_to": self.date_to,
                "salesperson_id": self.salesperson_id.id or False,
                "vehicle_id": self.vehicle_id.id or False,
                "city_id": self.city_id.id or False,
                "area_id": self.area_id.id or False,
                "outlet_id": self.outlet_id.id or False,
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

    @api.depends(
        "company_id",
        "period_filter",
        "dashboard_focus_mode",
        "date_from",
        "date_to",
        "salesperson_id",
        "vehicle_id",
        "city_id",
        "area_id",
        "outlet_id",
    )
    def _compute_manager_dashboard_html(self):
        for rec in self:
            if not rec.date_from:
                rec.date_from = fields.Date.context_today(rec) - timedelta(days=29)
            if not rec.date_to:
                rec.date_to = fields.Date.context_today(rec)
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                rec.date_from, rec.date_to = rec.date_to, rec.date_from

            payload = rec._get_dashboard_payload()
            previous_payload = rec._get_previous_dashboard_payload()
            comparison = rec._manager_period_comparison(payload, previous_payload)
            area_lines = rec._build_manager_area_lines(payload)

            rec.executive_overview_html = rec._render_manager_overview_html(payload, previous_payload, comparison) if rec._dashboard_any_widget_enabled(rec._dashboard_section_widget_codes("executive"), target="manager") else ""
            rec.period_comparison_html = rec._render_manager_period_comparison_html(comparison) if rec._dashboard_widget_enabled("period_comparison", target="manager") else ""
            rec.commercial_health_html = rec._render_manager_commercial_html(payload) if rec._dashboard_any_widget_enabled(rec._dashboard_section_widget_codes("collections") | rec._dashboard_section_widget_codes("products"), target="manager") else ""
            rec.market_ranking_html = rec._render_manager_market_html(payload, area_lines) if rec._dashboard_any_widget_enabled(rec._dashboard_section_widget_codes("outlets"), target="manager") else ""
            rec.executive_risk_html = rec._render_manager_risk_html(payload, area_lines) if rec._dashboard_any_widget_enabled(rec._dashboard_section_widget_codes("risk") | rec._dashboard_section_widget_codes("ranking"), target="manager") else ""

    def _get_previous_dashboard_payload(self):
        self.ensure_one()
        date_from, date_to = self._get_date_range()
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        day_count = max((date_to - date_from).days + 1, 1)
        previous_to = date_from - timedelta(days=1)
        previous_from = previous_to - timedelta(days=day_count - 1)
        previous = self.new(
            {
                "name": _("Previous Period"),
                "company_id": self.company_id.id,
                "period_filter": "custom",
                "date_from": previous_from,
                "date_to": previous_to,
                "salesperson_id": self.salesperson_id.id or False,
                "vehicle_id": self.vehicle_id.id or False,
                "city_id": self.city_id.id or False,
                "area_id": self.area_id.id or False,
                "outlet_id": self.outlet_id.id or False,
            }
        )
        return previous._get_dashboard_payload()

    def _manager_period_comparison(self, payload, previous_payload):
        def metric(current, previous):
            current = float(current or 0.0)
            previous = float(previous or 0.0)
            if previous:
                change = ((current - previous) / abs(previous)) * 100.0
            else:
                change = 100.0 if current else 0.0
            return {"current": current, "previous": previous, "change": change}

        visits = len(payload.get("visits") or [])
        previous_visits = len(previous_payload.get("visits") or [])
        completion = self._completion_rate(payload)
        previous_completion = self._completion_rate(previous_payload)
        collection_rate = self._collection_rate(payload)
        previous_collection_rate = self._collection_rate(previous_payload)
        return {
            "gross_sales": metric(payload.get("gross_sales"), previous_payload.get("gross_sales")),
            "net_sales": metric(payload.get("net_sales"), previous_payload.get("net_sales")),
            "collection": metric(payload.get("total_collected"), previous_payload.get("total_collected")),
            "profit": metric(payload.get("gross_profit"), previous_payload.get("gross_profit")),
            "returns": metric(payload.get("total_returns"), previous_payload.get("total_returns")),
            "open_due": metric(payload.get("open_due_amount"), previous_payload.get("open_due_amount")),
            "visits": metric(visits, previous_visits),
            "completion": metric(completion, previous_completion),
            "collection_rate": metric(collection_rate, previous_collection_rate),
            "attention_score": metric(self._attention_score(payload), self._attention_score(previous_payload)),
        }

    def _completion_rate(self, payload):
        total = len(payload.get("visits") or [])
        if not total:
            return 0.0
        return (payload.get("visit_status", {}).get("done", 0) / total) * 100.0

    def _collection_rate(self, payload):
        net_sales = payload.get("net_sales", 0.0) or 0.0
        if not net_sales:
            return 0.0
        return (payload.get("total_collected", 0.0) or 0.0) / net_sales * 100.0

    def _attention_score(self, payload):
        return (
            len(payload.get("unfinished_visits") or [])
            + len(payload.get("location_issue_visits") or [])
            + int(payload.get("pending_vehicle_issues") or 0)
            + int(payload.get("pending_transfer_count") or 0)
            + len(payload.get("due_overdue_promises") or [])
        )

    def _build_manager_area_lines(self, payload):
        data = {}

        def area_key_from(outlet=False, area=False):
            area = area or (outlet.area_id if outlet else False)
            if not area:
                return 0, _("No Area")
            return area.id, area.display_name

        def values_for(outlet=False, area=False):
            key, label = area_key_from(outlet, area)
            if key not in data:
                data[key] = {
                    "name": label,
                    "visits": 0,
                    "done": 0,
                    "unfinished": 0,
                    "sales": 0.0,
                    "collection": 0.0,
                    "open_due": 0.0,
                    "returns": 0.0,
                    "promises": 0.0,
                    "issues": 0,
                    "collection_rate": 0.0,
                }
            return data[key]

        for visit in payload.get("visits") or []:
            values = values_for(visit.outlet_id, visit.area_id)
            values["visits"] += 1
            if visit.visit_process_state == "done":
                values["done"] += 1
            elif visit.visit_process_state != "cancel":
                values["unfinished"] += 1
            values["open_due"] += visit.remaining_due_amount or 0.0
            if not self._visit_is_direct_sale(visit):
                values["sales"] += sum((line.sold_amount or 0.0) for line in visit.line_ids)
                values["returns"] += sum((line.return_amount or 0.0) for line in visit.line_ids)

        for visit in payload.get("location_issue_visits") or []:
            values_for(visit.outlet_id, visit.area_id)["issues"] += 1

        for payment in payload.get("confirmed_payments") or []:
            values_for(payment.outlet_id)["collection"] += payment.amount or 0.0

        for payment in payload.get("open_promises") or []:
            values_for(payment.outlet_id)["promises"] += payment.effective_promise_amount or payment.promise_amount or 0.0

        for order in payload.get("sale_orders") or []:
            values = values_for(order.route_outlet_id)
            values["sales"] += order.amount_total or 0.0
            if "direct_sale_remaining_due" in order._fields:
                values["open_due"] += order.direct_sale_remaining_due or 0.0

        for ret in payload.get("direct_returns") or []:
            values_for(ret.outlet_id)["returns"] += ret.amount_total or 0.0

        lines = []
        for values in data.values():
            values["issues"] += values["unfinished"] + (1 if values["promises"] else 0)
            values["collection_rate"] = (values["collection"] / values["sales"] * 100.0) if values["sales"] else 0.0
            if any((values["visits"], values["sales"], values["collection"], values["open_due"], values["returns"], values["issues"])):
                lines.append(values)
        return sorted(lines, key=lambda line: (line["sales"], line["collection"], line["visits"]), reverse=True)

    def _render_manager_overview_html(self, payload, previous_payload, comparison):
        settings = payload.get("settings") or {}
        completion = self._completion_rate(payload)
        collection_rate = self._collection_rate(payload)
        attention_score = self._attention_score(payload)
        active_salespersons = len([line for line in payload.get("salesperson_lines", []) if line.get("visits") or line.get("sales") or line.get("collection")])
        active_outlets = len(payload.get("outlet_lines") or [])
        gross_sales = payload.get("gross_sales", 0.0) or 0.0
        net_sales = payload.get("net_sales", 0.0) or 0.0
        total_returns = payload.get("total_returns", 0.0) or 0.0
        open_due = payload.get("open_due_amount", 0.0) or 0.0
        gross_profit = payload.get("gross_profit", 0.0) or 0.0
        margin = (gross_profit / gross_sales * 100.0) if gross_sales else 0.0
        return_rate = (total_returns / gross_sales * 100.0) if gross_sales else 0.0
        open_due_ratio = (open_due / net_sales * 100.0) if net_sales else 0.0
        cards = [
            self._kpi_card(_("Total Sales"), self._money(gross_sales), self._comparison_note(comparison["gross_sales"], money=True), "sales"),
            self._kpi_card(_("Total Collection"), self._money(payload.get("total_collected")), _("Collection Rate: %s%%") % f"{collection_rate:.0f}", "success"),
            self._kpi_card(_("Net Sales"), self._money(net_sales), self._comparison_note(comparison["net_sales"], money=True), "primary"),
            self._kpi_card(_("Estimated Profit"), self._money(gross_profit), _("Margin: %s%%") % f"{margin:.0f}", "profit"),
            self._kpi_card(_("Open Due"), self._money(open_due), self._comparison_note(comparison["open_due"], money=True, inverse=True), "danger"),
            self._kpi_card(_("Returns"), self._money(total_returns), self._comparison_note(comparison["returns"], money=True, inverse=True), "warning"),
            self._kpi_card(_("Visit Completion"), f"{completion:.0f}%", _("Completed: %s / %s") % (self._num(payload.get("visit_status", {}).get("done", 0)), self._num(len(payload.get("visits") or []))), "info"),
            self._kpi_card(_("Active Outlets"), self._num(active_outlets), _("Salespersons: %s") % self._num(active_salespersons), "primary"),
            self._kpi_card(_("Reopened Days"), self._num(payload.get("reopened_day_count")), _("Closed: %s") % self._num(payload.get("closed_day_count")), "warning"),
            self._kpi_card(_("Attention Score"), self._num(attention_score), self._comparison_note(comparison["attention_score"], inverse=True), "danger"),
        ]
        if settings.get("show_location"):
            cards.append(self._kpi_card(_("Location Issues"), self._num(len(payload.get("location_issue_visits") or [])), _("Review workload"), "warning"))
        if settings.get("show_vehicle_closing"):
            cards.append(self._kpi_card(_("Vehicle Issues"), self._num(payload.get("pending_vehicle_issues")), _("Closing / variance risk"), "danger"))

        signal_cards = [
            self._gauge_card(_("Completion Rate"), completion, _("Route execution completion"), "#0ea5e9"),
            self._gauge_card(_("Collection Efficiency"), collection_rate, _("Collected vs net sales"), "#16a34a"),
            self._gauge_card(_("Gross Margin"), margin, _("Estimated profit quality"), "#8b5cf6"),
            self._gauge_card(_("Return Pressure"), return_rate, _("Returns vs gross sales"), "#ef4444"),
            self._gauge_card(_("Open Due Ratio"), open_due_ratio, _("Open due vs net sales"), "#f97316"),
        ]
        title = self._section_title(
            _("Executive Command Center"),
            _("Management-level KPIs with period comparison, commercial performance, and operational risk."),
        )
        subtitle = self._manager_period_label(payload, previous_payload)
        if not self._dashboard_widget_enabled("command_center", target="manager"):
            return ""
        signal_html = ""
        if self._dashboard_widget_enabled("executive_signal_gauges", target="manager"):
            signal_html = f"<div class='route_dash_exec_signal_grid'>{''.join(signal_cards)}</div>"
        return (
            f"<div class='route_dash_block'>{title}{self._scope_badges()}{self._settings_badges(settings)}"
            f"<div class='route_dash_scope'><span><small>{escape(_('Period Compared'))}</small>{escape(subtitle)}</span></div>"
            f"<div class='route_dash_kpi_grid'>{''.join(cards)}</div>"
            f"{signal_html}</div>"
        )

    def _render_manager_period_comparison_html(self, comparison):
        rows = [
            (_("Sales Growth"), comparison["gross_sales"], "sales", True, False),
            (_("Collection Growth"), comparison["collection"], "success", True, False),
            (_("Net Sales Growth"), comparison["net_sales"], "primary", True, False),
            (_("Profit Growth"), comparison["profit"], "profit", True, False),
            (_("Returns Change"), comparison["returns"], "warning", True, True),
            (_("Open Due Change"), comparison["open_due"], "danger", True, True),
            (_("Visit Volume"), comparison["visits"], "info", False, False),
            (_("Completion Rate Change"), comparison["completion"], "info", False, False),
            (_("Collection Rate Change"), comparison["collection_rate"], "success", False, False),
            (_("Attention Score Change"), comparison["attention_score"], "danger", False, True),
        ]
        cards = "".join(self._growth_card(title, values, tone, money, inverse) for title, values, tone, money, inverse in rows)
        html = self._section_title(
            _("This Period vs Previous Period"),
            _("Growth cards compare the selected period with the immediately preceding period of the same length."),
        )
        return f"<div class='route_dash_block'>{html}<div class='route_dash_insight_grid'>{cards}</div></div>"

    def _render_manager_commercial_html(self, payload):
        settings = payload.get("settings") or {}
        sales_return_rows = [
            (_("Gross Sales"), payload.get("gross_sales", 0.0), "#16a34a"),
            (_("Returns"), payload.get("total_returns", 0.0), "#ef4444"),
            (_("Net Sales"), payload.get("net_sales", 0.0), "#0ea5e9"),
            (_("Collection"), payload.get("total_collected", 0.0), "#22c55e"),
            (_("Open Due"), payload.get("open_due_amount", 0.0), "#f97316"),
            (_("Estimated Profit"), payload.get("gross_profit", 0.0), "#8b5cf6"),
        ]
        top_product_sales = [
            (line["name"], line.get("sales", 0.0), "#0ea5e9")
            for line in sorted(payload.get("product_lines") or [], key=lambda line: line.get("sales", 0.0), reverse=True)[:5]
        ]
        top_product_profit = [
            (line["name"], line.get("profit", 0.0), "#16a34a" if line.get("profit", 0.0) >= 0 else "#ef4444")
            for line in sorted(payload.get("product_lines") or [], key=lambda line: line.get("profit", 0.0), reverse=True)[:5]
        ]
        top_returned_products = [
            (line["name"], line.get("returns", 0.0), "#ef4444")
            for line in sorted(payload.get("product_lines") or [], key=lambda line: line.get("returns", 0.0), reverse=True)[:5]
        ]
        gross_sales = payload.get("gross_sales", 0.0) or 0.0
        net_sales = payload.get("net_sales", 0.0) or 0.0
        total_collected = payload.get("total_collected", 0.0) or 0.0
        total_returns = payload.get("total_returns", 0.0) or 0.0
        gross_profit = payload.get("gross_profit", 0.0) or 0.0
        collection_gap = max(net_sales - total_collected, 0.0)
        cash_conversion = (total_collected / net_sales * 100.0) if net_sales else 0.0
        return_impact = (total_returns / gross_sales * 100.0) if gross_sales else 0.0
        profit_margin = (gross_profit / gross_sales * 100.0) if gross_sales else 0.0
        mix_tiles = [
            (_("Cash Conversion"), f"{cash_conversion:.0f}%", _("Collected vs net sales"), "#16a34a"),
            (_("Collection Gap"), self._money(collection_gap), _("Net sales still not collected"), "#f97316"),
            (_("Return Impact"), f"{return_impact:.0f}%", _("Returns vs gross sales"), "#ef4444"),
            (_("Profit Margin"), f"{profit_margin:.0f}%", _("Estimated margin from product cost"), "#8b5cf6"),
        ]
        html = self._section_title(
            _("Commercial Performance"),
            _("Sales, returns, collections, profit, and top 5 product contribution in one executive view."),
        )
        html += "<div class='route_dash_chart_grid'>"
        html += self._dashboard_chart_card("commercial_mix_columns", _("Commercial Mix Columns"), self._column_chart(sales_return_rows, money=True), _("A more visual mix view for the main business values."), wide=True, target="manager")
        html += self._dashboard_chart_card("sales_collection_trend", _("Sales vs Collection Trend"), self._line_chart(payload.get("daily_collection", {}), payload.get("daily_sales", {}), payload.get("date_from"), payload.get("date_to")), _("Trend across the selected period."), wide=True, target="manager")
        html += self._dashboard_chart_card("commercial_pulse", _("Commercial Pulse"), self._spotlight_tiles(mix_tiles), _("Ratios and gaps that are not repeated in the main KPI cards."), target="manager")
        html += self._dashboard_chart_card("top_products_sales", _("Top Products by Sales"), self._horizontal_bars(top_product_sales, money=True), "", target="manager")
        html += self._dashboard_chart_card("top_profit_products", _("Top Profit Products"), self._horizontal_bars(top_product_profit, money=True, allow_negative=True), _("Estimated from product cost."), target="manager")
        if settings.get("show_consignment") or settings.get("show_direct_return"):
            html += self._dashboard_chart_card("top_returned_products", _("Top Returned Products"), self._horizontal_bars(top_returned_products, money=True), _("Return exposure by product."), wide=True, target="manager")
        html += "</div>"
        return f"<div class='route_dash_block'>{html}</div>"

    def _render_manager_market_html(self, payload, area_lines):
        settings = payload.get("settings") or {}
        outlet_lines = payload.get("outlet_lines") or []
        area_sales = [(line["name"], line.get("sales", 0.0), "#0ea5e9") for line in sorted(area_lines, key=lambda line: line.get("sales", 0.0), reverse=True)[:10]]
        area_collection = [(line["name"], line.get("collection", 0.0), "#16a34a") for line in sorted(area_lines, key=lambda line: line.get("collection", 0.0), reverse=True)[:10]]
        area_due = [(line["name"], line.get("open_due", 0.0), "#ef4444") for line in sorted(area_lines, key=lambda line: line.get("open_due", 0.0), reverse=True)[:10]]
        outlet_sales = [(line["name"], line.get("sales", 0.0), "#0ea5e9") for line in sorted(outlet_lines, key=lambda line: line.get("sales", 0.0), reverse=True)[:10]]
        outlet_due = [(line["name"], line.get("open_due", 0.0), "#ef4444") for line in sorted(outlet_lines, key=lambda line: line.get("open_due", 0.0), reverse=True)[:10]]
        best_area = area_sales[0][0] if area_sales else _("No Area")
        highest_due_area = area_due[0][0] if area_due else _("No Due Area")
        best_outlet = outlet_sales[0][0] if outlet_sales else _("No Outlet")
        risk_outlet = outlet_due[0][0] if outlet_due else _("No Risk Outlet")
        insight_tiles = [
            (_("Best Area"), best_area, _("Highest sales area"), "#0ea5e9"),
            (_("Highest Due Area"), highest_due_area, _("Needs collection focus"), "#ef4444"),
            (_("Best Outlet"), best_outlet, _("Top outlet by sales"), "#16a34a"),
            (_("Risk Outlet"), risk_outlet, _("Highest open due outlet"), "#f97316"),
        ]
        html = self._section_title(
            _("Market, Area, and Outlet Performance"),
            _("Compare areas and outlets by revenue, collection, open due, and customer risk."),
        )
        html += self._dashboard_chart_card("market_insight_summary", _("Market Insight Summary"), self._spotlight_tiles(insight_tiles), _("Fast executive reading before the detailed charts."), wide=True, target="manager")
        html += "<div class='route_dash_chart_grid'>"
        if settings.get("show_outlet_comparison"):
            direct = (payload.get("outlet_mode_summary") or {}).get("direct_sale") or {}
            consignment = (payload.get("outlet_mode_summary") or {}).get("consignment") or {}
            comparison_rows = [
                (_("Sales"), direct.get("sales", 0.0), consignment.get("sales", 0.0), True),
                (_("Collection"), direct.get("collection", 0.0), consignment.get("collection", 0.0), True),
                (_("Open Due"), direct.get("open_due", 0.0), consignment.get("open_due", 0.0), True),
                (_("Returns"), direct.get("returns", 0.0), consignment.get("returns", 0.0), True),
                (_("Visits"), direct.get("visits", 0), consignment.get("visits", 0), False),
            ]
            html += self._dashboard_chart_card("direct_vs_consignment", _("Direct Sale vs Consignment"), self._dual_horizontal_bars(comparison_rows), _("Shown only when both workflows are enabled."), wide=True, target="manager")
        html += self._dashboard_chart_card("area_sales", _("Sales by Area"), self._horizontal_bars(area_sales, money=True), "", target="manager")
        html += self._dashboard_chart_card("area_collection", _("Collection by Area"), self._horizontal_bars(area_collection, money=True), "", target="manager")
        html += self._dashboard_chart_card("area_open_due", _("Open Due by Area"), self._horizontal_bars(area_due, money=True), _("Priority follow-up by market."), target="manager")
        html += self._dashboard_chart_card("top_outlets_sales", _("Top Outlets by Sales"), self._horizontal_bars(outlet_sales, money=True), "", target="manager")
        html += self._dashboard_chart_card("highest_due_outlets", _("Highest Open Due Outlets"), self._horizontal_bars(outlet_due, money=True), _("Customer credit risk."), wide=True, target="manager")
        html += "</div>"
        return f"<div class='route_dash_block'>{html}</div>"

    def _render_manager_risk_html(self, payload, area_lines):
        settings = payload.get("settings") or {}
        unfinished_visits = len(payload.get("unfinished_visits") or [])
        overdue_promises = len(payload.get("due_overdue_promises") or [])
        location_issues = len(payload.get("location_issue_visits") or [])
        vehicle_issues = payload.get("pending_vehicle_issues", 0)
        pending_transfers = payload.get("pending_transfer_count", 0)

        alert_tiles = [
            (_("Unfinished Visits"), self._num(unfinished_visits), _("Execution still open"), "#ef4444"),
            (_("Open Promises"), self._num(overdue_promises), _("Due / overdue commitments"), "#8b5cf6"),
        ]
        attention_rows = [
            (_("Unfinished Visits"), unfinished_visits, "#ef4444"),
            (_("Due / Overdue Promises"), overdue_promises, "#8b5cf6"),
        ]
        if settings.get("show_location"):
            attention_rows.append((_("Location Issues"), location_issues, "#f59e0b"))
            alert_tiles.append((_("Location Issues"), self._num(location_issues), _("Location review load"), "#f59e0b"))
        if settings.get("show_vehicle_closing"):
            attention_rows.append((_("Vehicle Issues"), vehicle_issues, "#64748b"))
            alert_tiles.append((_("Vehicle Issues"), self._num(vehicle_issues), _("Vehicle closing exceptions"), "#64748b"))
        if settings.get("show_stock_transfers"):
            attention_rows.append((_("Pending Transfers"), pending_transfers, "#0ea5e9"))
            alert_tiles.append((_("Pending Transfers"), self._num(pending_transfers), _("Transfers need follow-up"), "#0ea5e9"))

        area_risk = [
            (line["name"], line.get("issues", 0) + (line.get("open_due", 0.0) / 10.0), "#ef4444")
            for line in sorted(area_lines, key=lambda line: (line.get("issues", 0) + line.get("open_due", 0.0) / 10.0), reverse=True)[:10]
        ]
        salesperson_rows = sorted(payload.get("salesperson_lines") or [], key=lambda line: line.get("issues", 0), reverse=True)[:8]
        vehicle_rows = sorted(payload.get("vehicle_lines") or [], key=lambda line: line.get("issues", 0), reverse=True)[:8]
        html = self._section_title(
            _("Executive Risk and Accountability"),
            _("Where management attention is needed: people, vehicles, areas, and unresolved operations."),
        )
        html += "<div class='route_dash_chart_grid'>"
        html += self._dashboard_chart_card("attention_counters", _("Attention Counters"), self._spotlight_tiles(alert_tiles), _("High-visibility counters for the main operational blockers."), wide=True, target="manager")
        html += self._dashboard_chart_card("attention_mix", _("Attention Mix"), self._horizontal_bars(attention_rows), _("Only enabled workflows are included."), target="manager")
        html += self._dashboard_chart_card("area_risk_ranking", _("Area Risk Ranking"), self._horizontal_bars(area_risk), _("Mix of issues and open due by area."), target="manager")
        html += "</div>"
        ranking_html = ""
        if self._dashboard_widget_enabled("salesperson_ranking", target="manager"):
            ranking_html += self._ranking_table(
                _("Salesperson Executive Ranking"),
                [_('Salesperson'), _('Sales'), _('Collected'), _('Open Promises'), _('Issues')],
                [[line.get("name"), self._money(line.get("sales")), self._money(line.get("collection")), self._money(line.get("promises")), self._num(line.get("issues"))] for line in salesperson_rows],
            )
        if settings.get("show_vehicle_closing") and self._dashboard_widget_enabled("vehicle_risk_ranking", target="manager"):
            ranking_html += self._ranking_table(
                _("Vehicle Executive Risk"),
                [_('Vehicle'), _('Visits'), _('Unfinished'), _('Variance'), _('Issues')],
                [[line.get("name"), self._num(line.get("visits")), self._num(line.get("unfinished")), self._num(line.get("variance")), self._num(line.get("issues"))] for line in vehicle_rows],
            )
        if ranking_html:
            html += f"<div class='route_dash_ranking_grid mt-2'>{ranking_html}</div>"
        return f"<div class='route_dash_block'>{html}</div>"

    def _growth_card(self, title, values, tone="primary", money=False, inverse=False):
        current = values.get("current", 0.0)
        previous = values.get("previous", 0.0)
        change = values.get("change", 0.0)
        good = change >= 0.0
        if inverse:
            good = change <= 0.0
        arrow = "▲" if change >= 0.0 else "▼"
        change_label = f"{arrow} {abs(change):.0f}%"
        change_tone = "success" if good else "danger"
        display_current = self._money(current) if money else (f"{current:.0f}%" if "Rate" in str(title) else self._num(current))
        display_previous = self._money(previous) if money else (f"{previous:.0f}%" if "Rate" in str(title) else self._num(previous))
        return (
            f"<div class='route_dash_insight route_dash_tone_{escape(tone)}'>"
            f"<span>{escape(str(title))}</span>"
            f"<strong>{escape(display_current)}</strong>"
            f"<small>{escape(_('Previous'))}: {escape(display_previous)} · "
            f"<b class='route_dash_growth_{escape(change_tone)}'>{escape(change_label)}</b></small>"
            "</div>"
        )

    def _comparison_note(self, values, money=False, inverse=False):
        change = values.get("change", 0.0)
        previous = values.get("previous", 0.0)
        good = change >= 0.0
        if inverse:
            good = change <= 0.0
        marker = "+" if change >= 0.0 else "-"
        previous_text = self._money(previous) if money else self._num(previous)
        direction = _("better") if good else _("attention")
        return _("Prev: %(previous)s | %(marker)s%(change).0f%% %(direction)s") % {
            "previous": previous_text,
            "marker": marker,
            "change": abs(change),
            "direction": direction,
        }

    def _manager_period_label(self, payload, previous_payload):
        return _("Current: %(current_from)s → %(current_to)s | Previous: %(previous_from)s → %(previous_to)s") % {
            "current_from": payload.get("date_from"),
            "current_to": payload.get("date_to"),
            "previous_from": previous_payload.get("date_from"),
            "previous_to": previous_payload.get("date_to"),
        }

    def _gauge_card(self, title, value, note, color):
        value = max(0.0, min(float(value or 0.0), 100.0))
        return (
            "<div class='route_dash_gauge_card'>"
            f"<div class='route_dash_gauge_ring' style='background: conic-gradient({escape(color)} 0 {value:.2f}%, #e2e8f0 {value:.2f}% 100%);'>"
            f"<div class='route_dash_gauge_inner'><strong>{escape(f'{value:.0f}%')}</strong><span>{escape(str(title))}</span></div>"
            "</div>"
            f"<small>{escape(str(note or ''))}</small>"
            "</div>"
        )

    def _column_chart(self, rows, money=False, allow_negative=False):
        rows = [(label, value, color) for label, value, color in rows if value or allow_negative]
        if not rows:
            return self._empty_chart()
        max_value = max(abs(float(value or 0.0)) for _label, value, _color in rows) or 1.0
        html = "<div class='route_dash_column_chart'>"
        for label, value, color in rows:
            raw_value = float(value or 0.0)
            height = max(min(abs(raw_value) / max_value * 100.0, 100.0), 8.0)
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
        html = "<div class='route_dash_spotlight_grid'>"
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


