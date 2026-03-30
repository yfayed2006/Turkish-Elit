from datetime import datetime, time, timedelta

from odoo import api, fields, models


class RoutePdaHome(models.TransientModel):
    _name = "route.pda.home"
    _description = "Route PDA Home"

    name = fields.Char(default="PDA Home", readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", default=lambda self: self.env.user, readonly=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)
    today_date = fields.Date(string="Today", default=fields.Date.context_today, readonly=True)

    today_plan_count = fields.Integer(string="Today's Plans", compute="_compute_dashboard")
    today_visit_count = fields.Integer(string="Today's Visits", compute="_compute_dashboard")
    current_visit_count = fields.Integer(string="Current Visit", compute="_compute_dashboard")
    vehicle_closing_count = fields.Integer(string="Vehicle Closings", compute="_compute_dashboard")
    shortage_count = fields.Integer(string="Shortages", compute="_compute_dashboard")
    salesperson_shortage_count = fields.Integer(string="Salesperson Shortages", compute="_compute_dashboard")
    outlet_count = fields.Integer(string="Outlets", compute="_compute_dashboard")
    outlet_balance_count = fields.Integer(string="Outlet Stock", compute="_compute_dashboard")
    payment_count = fields.Integer(string="Payments Today", compute="_compute_dashboard")

    current_visit_name = fields.Char(string="Current Visit", compute="_compute_dashboard")
    current_visit_outlet_name = fields.Char(string="Current Outlet", compute="_compute_dashboard")
    current_vehicle_name = fields.Char(string="Vehicle", compute="_compute_dashboard")

    cash_today_amount = fields.Monetary(string="Cash In Hand", currency_field="currency_id", compute="_compute_dashboard")
    bank_today_amount = fields.Monetary(string="Bank Transfer", currency_field="currency_id", compute="_compute_dashboard")
    pos_today_amount = fields.Monetary(string="POS", currency_field="currency_id", compute="_compute_dashboard")
    open_promise_amount = fields.Monetary(string="Open Promises", currency_field="currency_id", compute="_compute_dashboard")
    remaining_due_amount = fields.Monetary(string="Remaining Due", currency_field="currency_id", compute="_compute_dashboard")

    @api.model
    def action_open_dashboard(self):
        rec = self.create({})
        view = self.env.ref("route_core.view_route_pda_home_form")
        return {
            "type": "ir.actions.act_window",
            "name": "PDA Home",
            "res_model": "route.pda.home",
            "res_id": rec.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "current",
            "context": {"create": 0, "edit": 0, "delete": 0},
        }

    def _today_bounds(self):
        today = fields.Date.context_today(self)
        start = datetime.combine(today, time.min)
        end = start + timedelta(days=1)
        return today, fields.Datetime.to_string(start), fields.Datetime.to_string(end)

    def _prepare_action(self, xmlid, name=None, domain=None, context=None):
        action = self.env.ref(xmlid).read()[0]
        if name:
            action["name"] = name
        if domain is not None:
            action["domain"] = domain
        base_context = {"create": 0, "delete": 0}
        existing_context = action.get("context")
        if isinstance(existing_context, dict):
            base_context.update(existing_context)
        if context:
            base_context.update(context)
        action["context"] = base_context
        return action

    @api.depends("user_id")
    def _compute_dashboard(self):
        Visit = self.env["route.visit"]
        Plan = self.env["route.plan"]
        Closing = self.env["route.vehicle.closing"]
        Shortage = self.env["route.shortage"]
        SalespersonShortage = self.env["route.salesperson.shortage"]
        Outlet = self.env["route.outlet"]
        OutletBalance = self.env["outlet.stock.balance"]
        Payment = self.env["route.visit.payment"]

        for rec in self:
            user = rec.user_id or self.env.user
            today, start_dt, end_dt = rec._today_bounds()

            today_plans = Plan.search([
                ("user_id", "=", user.id),
                ("date", "=", today),
            ])
            today_visits = Visit.search([
                ("user_id", "=", user.id),
                ("date", "=", today),
            ])
            current_visit = Visit.search([
                ("user_id", "=", user.id),
                ("state", "=", "in_progress"),
            ], order="start_datetime desc, id desc", limit=1)
            today_closings = Closing.search([
                ("user_id", "=", user.id),
                ("plan_date", "=", today),
            ])
            open_shortages = Shortage.search([
                ("user_id", "=", user.id),
                ("state", "in", ["open", "planned"]),
            ])
            salesperson_shortages = SalespersonShortage.search([
                ("salesperson_id", "=", user.id),
                ("state", "in", ["open", "under_review"]),
            ])
            today_payments = Payment.search([
                ("salesperson_id", "=", user.id),
                ("payment_date", ">=", start_dt),
                ("payment_date", "<", end_dt),
                ("state", "=", "confirmed"),
            ])
            all_confirmed_payments = Payment.search([
                ("salesperson_id", "=", user.id),
                ("state", "=", "confirmed"),
            ])

            rec.today_plan_count = len(today_plans)
            rec.today_visit_count = len(today_visits)
            rec.current_visit_count = 1 if current_visit else 0
            rec.vehicle_closing_count = len(today_closings)
            rec.shortage_count = len(open_shortages)
            rec.salesperson_shortage_count = len(salesperson_shortages)
            rec.outlet_count = Outlet.search_count([])
            rec.outlet_balance_count = OutletBalance.search_count([])
            rec.payment_count = len(today_payments)

            rec.current_visit_name = current_visit.display_name if current_visit else "No active visit"
            rec.current_visit_outlet_name = current_visit.outlet_id.display_name if current_visit and current_visit.outlet_id else "-"
            if current_visit and current_visit.vehicle_id:
                rec.current_vehicle_name = current_visit.vehicle_id.display_name
            elif today_plans[:1].vehicle_id:
                rec.current_vehicle_name = today_plans[:1].vehicle_id.display_name
            else:
                rec.current_vehicle_name = "-"

            rec.cash_today_amount = sum(today_payments.filtered(lambda p: p.payment_mode == "cash").mapped("amount"))
            rec.bank_today_amount = sum(today_payments.filtered(lambda p: p.payment_mode == "bank").mapped("amount"))
            rec.pos_today_amount = sum(today_payments.filtered(lambda p: p.payment_mode == "pos").mapped("amount"))
            rec.open_promise_amount = sum(
                all_confirmed_payments.filtered(lambda p: (p.promise_amount or 0.0) > 0 and p.promise_status in ("open", "due_today", "overdue")).mapped("promise_amount")
            )
            rec.remaining_due_amount = sum(today_visits.filtered(lambda v: v.state != "done").mapped("remaining_due_amount"))

    def action_open_today_plans(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self._prepare_action(
            "route_core.action_route_plan",
            name="My Route Plans",
            domain=[("user_id", "=", self.env.user.id), ("date", "=", today)],
            context={"search_default_filter_my_plans": 1, "search_default_filter_today": 1},
        )

    def action_open_my_pda_visits(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self._prepare_action(
            "route_core.action_route_visit_pda",
            name="My PDA Visits",
            domain=[("user_id", "=", self.env.user.id), ("date", "=", today)],
            context={"search_default_filter_my_visits": 1, "search_default_filter_today": 1, "edit": 1},
        )

    def action_open_current_visit(self):
        self.ensure_one()
        visit = self.env["route.visit"].search([
            ("user_id", "=", self.env.user.id),
            ("state", "=", "in_progress"),
        ], order="start_datetime desc, id desc", limit=1)
        if not visit:
            return self.action_open_my_pda_visits()
        action = self._prepare_action(
            "route_core.action_route_visit_pda",
            name="Current Visit",
            context={"edit": 1},
        )
        action["view_mode"] = "form"
        action["views"] = [(self.env.ref("route_core.view_route_visit_pda_form").id, "form")]
        action["res_id"] = visit.id
        action.pop("domain", None)
        return action

    def action_open_my_history(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_visit",
            name="My Visit History",
            domain=[("user_id", "=", self.env.user.id)],
            context={"search_default_filter_my_visits": 1, "search_default_filter_today": 0},
        )

    def action_open_my_vehicle_closing(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self._prepare_action(
            "route_core.action_route_vehicle_closing",
            name="My Vehicle Closings",
            domain=[("user_id", "=", self.env.user.id), ("plan_date", "=", today)],
        )

    def action_open_my_shortages(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_shortage",
            name="My Shortages",
            domain=[("user_id", "=", self.env.user.id)],
        )

    def action_open_my_salesperson_shortages(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_salesperson_shortage",
            name="My Salesperson Shortages",
            domain=[("salesperson_id", "=", self.env.user.id)],
        )

    def action_open_outlets(self):
        self.ensure_one()
        return self._prepare_action("route_core.action_route_outlet", name="Outlets")

    def action_open_outlet_balances(self):
        self.ensure_one()
        return self._prepare_action("route_core.action_outlet_stock_balance", name="Outlet Stock Balances")

    def action_open_payments(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_visit_payment",
            name="Visit Payments",
            domain=[("salesperson_id", "=", self.env.user.id)],
        )
