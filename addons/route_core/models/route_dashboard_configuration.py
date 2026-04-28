from odoo import _, api, fields, models


class RouteDashboardWidget(models.Model):
    _name = "route.dashboard.widget"
    _description = "Route Dashboard Widget Configuration"
    _order = "company_id, target_sequence, category, sequence, name, id"
    _rec_name = "name"

    name = fields.Char(string="Widget Name", required=True, translate=True)
    code = fields.Char(string="Technical Code", required=True, readonly=True)
    category = fields.Selection(
        [
            ("executive", "Executive KPIs"),
            ("visits", "Visit Execution"),
            ("collections", "Collections and Cash Flow"),
            ("products", "Products and Stock"),
            ("outlets", "Outlets and Market"),
            ("risk", "Risk and Accountability"),
        ],
        string="Category",
        required=True,
        default="executive",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    target_sequence = fields.Integer(string="Target Sequence", compute="_compute_target_sequence", store=True)
    active = fields.Boolean(string="Active", default=True)
    show_on_manager = fields.Boolean(string="Manager Dashboard", default=False)
    show_on_supervisor = fields.Boolean(string="Supervisor Dashboard", default=False)
    default_manager = fields.Boolean(string="Default Manager", readonly=True)
    default_supervisor = fields.Boolean(string="Default Supervisor", readonly=True)
    description = fields.Char(string="Description", translate=True)

    @api.depends("show_on_manager", "show_on_supervisor", "sequence")
    def _compute_target_sequence(self):
        for rec in self:
            if rec.show_on_manager and rec.show_on_supervisor:
                rec.target_sequence = 10
            elif rec.show_on_manager:
                rec.target_sequence = 20
            elif rec.show_on_supervisor:
                rec.target_sequence = 30
            else:
                rec.target_sequence = 40

    @api.model
    def _default_widget_definitions(self):
        return [
            self._w("command_center", _("Command Center KPIs"), "executive", 10, True, True, _("Main KPI cards and top signals.")),
            self._w("executive_signal_gauges", _("Executive Signal Gauges"), "executive", 20, True, False, _("Circular gauges for completion, collection, margin, returns, and due ratio.")),
            self._w("period_comparison", _("Period Comparison"), "executive", 30, True, False, _("Current period compared with previous period.")),
            self._w("route_execution_funnel", _("Route Execution Funnel"), "visits", 40, False, True, _("Planned, started, completed, and unfinished visit funnel.")),
            self._w("action_priority_cards", _("Action Priority Cards"), "visits", 50, False, True, _("Supervisor action cards for open exceptions.")),
            self._w("execution_pulse", _("Execution Pulse"), "visits", 60, False, True, _("Fast execution indicators for supervisors.")),
            self._w("visit_status_chart", _("Visit Status Chart"), "visits", 70, False, True, _("Visit status pie chart.")),
            self._w("attention_mix", _("Attention Mix"), "risk", 80, True, True, _("Open operational blockers by type.")),
            self._w("location_review_breakdown", _("Location Review Breakdown"), "visits", 90, False, True, _("Location check-in review breakdown.")),
            self._w("closing_status_chart", _("Closing Status Chart"), "visits", 100, False, True, _("Daily closing status pie chart.")),
            self._w("collection_workload", _("Collection Workload"), "collections", 110, False, True, _("Collection workload and promise pressure.")),
            self._w("payment_method_mix", _("Payment Method Mix"), "collections", 120, False, True, _("Payment method distribution.")),
            self._w("collection_by_salesperson", _("Collection by Salesperson"), "collections", 130, False, True, _("Cash collected by salesperson.")),
            self._w("sales_collection_trend", _("Sales vs Collection Trend"), "collections", 140, True, True, _("Line chart comparing sales and collection.")),
            self._w("commercial_mix_columns", _("Commercial Mix Columns"), "collections", 150, True, True, _("Column chart for sales, returns, collection, and profit.")),
            self._w("commercial_pulse", _("Commercial Pulse"), "collections", 160, True, False, _("Commercial ratios and gaps for managers.")),
            self._w("product_operations_pulse", _("Product Operations Pulse"), "products", 170, False, True, _("Product signals for daily supervision.")),
            self._w("top_products_sales", _("Top Products by Sales"), "products", 180, True, True, _("Top product revenue ranking.")),
            self._w("top_products_quantity", _("Top Products by Quantity"), "products", 190, False, True, _("Top sold quantity ranking.")),
            self._w("top_profit_products", _("Top Profit Products"), "products", 200, True, False, _("Top product profit ranking.")),
            self._w("estimated_product_profit", _("Estimated Product Profit"), "products", 210, False, True, _("Product profit estimate based on cost.")),
            self._w("top_returned_products", _("Top Returned Products"), "products", 220, True, True, _("Products with the highest return exposure.")),
            self._w("outlet_mode_summary_cards", _("Outlet Mode Summary Cards"), "outlets", 230, False, True, _("Direct sale and consignment outlet summary cards.")),
            self._w("market_insight_summary", _("Market Insight Summary"), "outlets", 240, True, False, _("Best area, highest due area, best outlet, and risk outlet.")),
            self._w("direct_vs_consignment", _("Direct Sale vs Consignment"), "outlets", 250, True, True, _("Side-by-side comparison when both workflows are enabled.")),
            self._w("area_sales", _("Sales by Area"), "outlets", 260, True, False, _("Sales ranking by market area.")),
            self._w("area_collection", _("Collection by Area"), "outlets", 270, True, False, _("Collection ranking by market area.")),
            self._w("area_open_due", _("Open Due by Area"), "outlets", 280, True, False, _("Open due ranking by area.")),
            self._w("top_outlets_sales", _("Top Outlets by Sales"), "outlets", 290, True, True, _("Outlet sales ranking.")),
            self._w("top_outlets_collection", _("Top Outlets by Collection"), "outlets", 300, False, True, _("Outlet collection ranking.")),
            self._w("highest_due_outlets", _("Highest Open Due Outlets"), "outlets", 310, True, True, _("Outlets with highest open due.")),
            self._w("top_returned_outlets", _("Top Returned Outlets"), "outlets", 320, False, True, _("Outlets with the highest returns.")),
            self._w("outlet_risk_ranking", _("Outlet Risk Ranking"), "outlets", 330, False, True, _("Risk by outlet from due, returns, promises, and issues.")),
            self._w("attention_counters", _("Attention Counters"), "risk", 340, True, False, _("High visibility risk counters.")),
            self._w("area_risk_ranking", _("Area Risk Ranking"), "risk", 350, True, False, _("Operational risk by area.")),
            self._w("salesperson_ranking", _("Salesperson Ranking"), "risk", 360, True, True, _("Salesperson performance and accountability ranking.")),
            self._w("vehicle_risk_ranking", _("Vehicle Risk Ranking"), "risk", 370, True, True, _("Vehicle variance and issue ranking.")),
        ]

    @api.model
    def _w(self, code, name, category, sequence, manager, supervisor, description):
        return {
            "code": code,
            "name": name,
            "category": category,
            "sequence": sequence,
            "show_on_manager": bool(manager),
            "show_on_supervisor": bool(supervisor),
            "default_manager": bool(manager),
            "default_supervisor": bool(supervisor),
            "description": description,
        }

    @api.model
    def _ensure_default_widgets(self, company=False):
        company = company or self.env.company
        if not company:
            return self.browse()
        created = self.browse()
        for vals in self._default_widget_definitions():
            existing = self.with_context(active_test=False).search([("company_id", "=", company.id), ("code", "=", vals["code"])], limit=1)
            if existing:
                update_vals = {
                    "name": vals["name"],
                    "category": vals["category"],
                    "sequence": vals["sequence"],
                    "default_manager": vals["default_manager"],
                    "default_supervisor": vals["default_supervisor"],
                    "description": vals["description"],
                }
                changed_vals = {key: value for key, value in update_vals.items() if existing[key] != value}
                if changed_vals:
                    existing.write(changed_vals)
            else:
                created |= self.create(dict(vals, company_id=company.id, active=True))
        return created

    @api.model
    def _default_lookup(self):
        return {vals["code"]: vals for vals in self._default_widget_definitions()}

    @api.model
    def is_enabled(self, code, target, company=False):
        company = company or self.env.company
        if not company or not code or target not in ("manager", "supervisor"):
            return True
        # Ensure defaults lazily so existing databases are immediately usable after upgrade.
        default_count = len(self._default_widget_definitions())
        existing_count = self.sudo().with_context(active_test=False).search_count([("company_id", "=", company.id)])
        if existing_count < default_count:
            self.sudo()._ensure_default_widgets(company)
        widget = self.sudo().with_context(active_test=False).search([("company_id", "=", company.id), ("code", "=", code)], limit=1)
        if not widget:
            defaults = self._default_lookup().get(code)
            if not defaults:
                return True
            return bool(defaults.get("show_on_%s" % target))
        return bool(widget.active and widget[("show_on_%s" % target)])

    def action_reset_to_default_visibility(self):
        defaults = self._default_lookup()
        for rec in self:
            vals = defaults.get(rec.code)
            if vals:
                rec.write(
                    {
                        "active": True,
                        "show_on_manager": vals.get("show_on_manager", False),
                        "show_on_supervisor": vals.get("show_on_supervisor", False),
                    }
                )
        return True

    @api.model
    def action_open_dashboard_configuration(self):
        self._ensure_default_widgets(self.env.company)
        list_view = self.env.ref("route_core.view_route_dashboard_widget_list", raise_if_not_found=False)
        form_view = self.env.ref("route_core.view_route_dashboard_widget_form", raise_if_not_found=False)
        views = []
        if list_view:
            views.append((list_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Dashboard Configuration"),
            "res_model": "route.dashboard.widget",
            "view_mode": "list,form",
            "views": views or False,
            "domain": [("company_id", "=", self.env.company.id)],
            "context": {"default_company_id": self.env.company.id, "search_default_group_category": 1, "active_test": False},
            "target": "current",
        }
