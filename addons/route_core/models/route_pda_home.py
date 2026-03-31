from datetime import datetime, time, timedelta

from odoo import api, fields, models


class RoutePdaHome(models.TransientModel):
    _name = "route.pda.home"
    _description = "Route PDA Home"

    name = fields.Char(default="PDA Home", readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", default=lambda self: self.env.user, readonly=True)
    user_display_name = fields.Char(string="Salesperson Name", compute="_compute_dashboard")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)
    today_date = fields.Date(string="Today", default=fields.Date.context_today, readonly=True)
    today_display_label = fields.Char(string="Today Label", compute="_compute_dashboard")

    today_plan_count = fields.Integer(string="Today's Plans", compute="_compute_dashboard")
    today_visit_count = fields.Integer(string="Today's Visits", compute="_compute_dashboard")
    current_visit_count = fields.Integer(string="Current Visit", compute="_compute_dashboard")
    vehicle_closing_count = fields.Integer(string="Vehicle Closings", compute="_compute_dashboard")
    shortage_count = fields.Integer(string="Shortages", compute="_compute_dashboard")
    salesperson_shortage_count = fields.Integer(string="Salesperson Shortages", compute="_compute_dashboard")
    outlet_count = fields.Integer(string="Outlets", compute="_compute_dashboard")
    outlet_balance_count = fields.Integer(string="Outlet Stock", compute="_compute_dashboard")
    payment_count = fields.Integer(string="Payments Today", compute="_compute_dashboard")
    visit_collection_count = fields.Integer(string="Visit Collections Today", compute="_compute_dashboard")
    direct_sale_payment_count = fields.Integer(string="Direct Sale Payments Today", compute="_compute_dashboard")
    product_count = fields.Integer(string="Products", compute="_compute_dashboard")
    vehicle_product_count = fields.Integer(string="Vehicle Products", compute="_compute_dashboard")
    warehouse_product_count = fields.Integer(string="Main Warehouse Products", compute="_compute_dashboard")

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

    def _open_self_view(self, view_xmlid, title):
        self.ensure_one()
        view = self.env.ref(view_xmlid)
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "route.pda.home",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "current",
            "context": {"create": 0, "edit": 0, "delete": 0},
        }

    def action_back_home(self):
        return self._open_self_view("route_core.view_route_pda_home_form", "PDA Home")

    def action_open_snapshot_center_screen(self):
        return self._open_self_view("route_core.view_route_pda_snapshot_center_form", "Snapshot Center")

    def action_open_review_center_screen(self):
        return self._open_self_view("route_core.view_route_pda_review_center_form", "Alerts and Review")

    def action_open_product_center_screen(self):
        return self._open_self_view("route_core.view_route_pda_product_center_form", "Product Center")

    def action_open_sales_center_screen(self):
        return self._open_self_view("route_core.view_route_pda_sales_center_form", "Sales Center")

    def action_open_outlet_center_screen(self):
        return self._open_self_view("route_core.view_route_pda_outlet_center_form", "Outlet Center")

    def action_open_today_overview_screen(self):
        return self._open_self_view("route_core.view_route_pda_today_overview_form", "Today Overview")

    def action_open_current_visit_snapshot_screen(self):
        return self._open_self_view("route_core.view_route_pda_current_visit_snapshot_form", "Current Visit Snapshot")

    def action_open_collections_snapshot_screen(self):
        return self._open_self_view("route_core.view_route_pda_collections_snapshot_form", "Collections Snapshot")

    def action_open_reference_counts_screen(self):
        return self._open_self_view("route_core.view_route_pda_reference_counts_form", "Reference Counts")

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

    def _get_current_vehicle(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        current_visit = self.env["route.visit"].search([
            ("user_id", "=", self.env.user.id),
            ("state", "=", "in_progress"),
        ], order="start_datetime desc, id desc", limit=1)
        if current_visit and current_visit.vehicle_id:
            return current_visit.vehicle_id
        plan = self.env["route.plan"].search([
            ("user_id", "=", self.env.user.id),
            ("date", "=", today),
            ("vehicle_id", "!=", False),
        ], order="id desc", limit=1)
        return plan.vehicle_id

    def _get_main_warehouse_location(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        vehicle = self._get_current_vehicle()
        Proposal = self.env["route.loading.proposal"].sudo()

        base_domain = [
            ("company_id", "=", self.env.company.id),
            ("user_id", "=", self.env.user.id),
        ]
        if vehicle:
            base_domain.append(("vehicle_id", "=", vehicle.id))

        # First priority: the actual approved transfer source used to load the vehicle.
        approved_today = Proposal.search(
            base_domain + [("plan_date", "=", today), ("state", "=", "approved")],
            order="approval_datetime desc, id desc",
            limit=1,
        )
        if approved_today:
            picking_source = getattr(getattr(approved_today, "picking_id", False), "location_id", False)
            if picking_source:
                return picking_source
            if approved_today.source_location_id:
                return approved_today.source_location_id

        # Second priority: any latest approved proposal for this vehicle/salesperson.
        approved_any = Proposal.search(
            base_domain + [("state", "=", "approved")],
            order="approval_datetime desc, id desc",
            limit=1,
        )
        if approved_any:
            picking_source = getattr(getattr(approved_any, "picking_id", False), "location_id", False)
            if picking_source:
                return picking_source
            if approved_any.source_location_id:
                return approved_any.source_location_id

        # Third priority: latest draft for today if supervisor prepared a proposal but has not approved yet.
        draft_today = Proposal.search(
            base_domain + [("plan_date", "=", today), ("state", "=", "draft")],
            order="id desc",
            limit=1,
        )
        if draft_today and draft_today.source_location_id:
            return draft_today.source_location_id

        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)],
            order="id",
            limit=1,
        )
        return warehouse.lot_stock_id if warehouse else False

    def _open_quants_by_location(self, location, title):
        self.ensure_one()
        list_view = self.env.ref("route_core.view_route_vehicle_stock_snapshot_list")
        search_view = self.env.ref("route_core.view_route_vehicle_stock_snapshot_search")
        domain = [("quantity", ">", 0)]
        if location:
            domain.insert(0, ("location_id", "child_of", location.id))
        else:
            domain = [("id", "=", 0)]
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "views": [(list_view.id, "list"), (False, "form")],
            "search_view_id": search_view.id,
            "domain": domain,
            "target": "current",
            "context": {"search_default_filter_positive_qty": 1, "create": 0, "delete": 0},
        }

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
        Product = self.env["product.template"]
        Quant = self.env["stock.quant"]

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

            vehicle = rec._get_current_vehicle()
            warehouse_loc = rec._get_main_warehouse_location()

            rec.user_display_name = user.display_name or "-"
            rec.today_display_label = today.strftime("%b %d") if today else "-"

            rec.today_plan_count = len(today_plans)
            rec.today_visit_count = len(today_visits)
            rec.current_visit_count = 1 if current_visit else 0
            rec.vehicle_closing_count = len(today_closings)
            rec.shortage_count = len(open_shortages)
            rec.salesperson_shortage_count = len(salesperson_shortages)
            rec.outlet_count = Outlet.search_count([])
            rec.outlet_balance_count = OutletBalance.search_count([])
            rec.payment_count = len(today_payments)
            rec.visit_collection_count = len(today_payments.filtered(lambda p: p.source_type == "visit"))
            rec.direct_sale_payment_count = len(today_payments.filtered(lambda p: p.source_type == "direct_sale"))
            rec.product_count = Product.search_count([("sale_ok", "=", True), ("active", "=", True)])
            rec.vehicle_product_count = Quant.search_count([("location_id", "child_of", vehicle.stock_location_id.id), ("quantity", ">", 0)]) if vehicle and getattr(vehicle, "stock_location_id", False) else 0
            rec.warehouse_product_count = Quant.search_count([("location_id", "child_of", warehouse_loc.id), ("quantity", ">", 0)]) if warehouse_loc else 0

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

    def action_open_direct_sale_orders(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Direct Sale Orders",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("route_order_mode", "=", "direct_sale"), ("user_id", "=", self.env.user.id)],
            "context": {"search_default_my_quotations": 0, "create": 0},
            "target": "current",
        }
        tree_view = self.env.ref("sale.view_quotation_tree_with_onboarding", raise_if_not_found=False)
        form_view = self.env.ref("route_core.view_sale_order_form_route_direct_sale", raise_if_not_found=False)
        search_view = self.env.ref("sale.view_sales_order_filter", raise_if_not_found=False)
        views = []
        if tree_view:
            views.append((tree_view.id, "list"))
        if form_view:
            views.append((form_view.id, "form"))
        if views:
            action["views"] = views
        if search_view:
            action["search_view_id"] = search_view.id
        return action

    def _get_direct_sale_order_recordset(self):
        return self.env["sale.order"].search([
            ("route_order_mode", "=", "direct_sale"),
            ("user_id", "=", self.env.user.id),
        ])

    def action_open_direct_sale_deliveries(self):
        self.ensure_one()
        orders = self._get_direct_sale_order_recordset()
        pickings = self.env["stock.picking"].search([
            ("origin", "in", orders.mapped("name")),
            ("state", "!=", "cancel"),
        ], order="id desc")
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["name"] = "Direct Sale Deliveries"
        action["domain"] = [("id", "in", pickings.ids)]
        return action

    def action_open_direct_sale_returns(self):
        self.ensure_one()
        orders = self._get_direct_sale_order_recordset()
        deliveries = self.env["stock.picking"].search([
            ("origin", "in", orders.mapped("name")),
            ("state", "!=", "cancel"),
        ])
        return_moves = self.env["stock.move"].search([
            ("origin_returned_move_id", "in", deliveries.move_ids.ids),
            ("picking_id", "!=", False),
            ("state", "!=", "cancel"),
        ])
        returns = return_moves.mapped("picking_id")
        manual_returns = self.env["stock.picking"].search([
            ("route_direct_return_id.user_id", "=", self.env.user.id),
            ("state", "!=", "cancel"),
        ])
        returns |= manual_returns
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["name"] = "Direct Sale Returns"
        action["domain"] = [("id", "in", returns.ids)]
        return action

    def action_open_direct_sale_outlets(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_outlet",
            name="Direct Sale Outlets",
            domain=[("outlet_operation_mode", "=", "direct_sale"), ("active", "=", True)],
        )

    def action_create_direct_sale(self):
        self.ensure_one()
        vehicle = self._get_current_vehicle()
        source_location = vehicle.stock_location_id if vehicle and getattr(vehicle, "stock_location_id", False) else False
        default_outlet = self.env["route.outlet"].search([("outlet_operation_mode", "=", "direct_sale"), ("active", "=", True)], order="id desc", limit=1)
        action = {
            "type": "ir.actions.act_window",
            "name": "Create Direct Sale",
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_route_order_mode": "direct_sale",
                "default_user_id": self.env.user.id,
                "default_route_source_location_id": source_location.id if source_location else False,
                "default_route_payment_mode": "cash",
                "default_route_outlet_id": default_outlet.id if default_outlet else False,
                "default_partner_id": default_outlet.partner_id.id if default_outlet and default_outlet.partner_id else False,
            },
        }
        view = self.env.ref("route_core.view_sale_order_form_route_direct_sale", raise_if_not_found=False)
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_create_direct_return(self):
        self.ensure_one()
        default_outlet = self.env["route.outlet"].search([
            ("outlet_operation_mode", "=", "direct_sale"),
            ("active", "=", True),
        ], order="id desc", limit=1)
        vehicle = self._get_current_vehicle()
        action = {
            "type": "ir.actions.act_window",
            "name": "Create Direct Return",
            "res_model": "route.direct.return",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_user_id": self.env.user.id,
                "default_vehicle_id": vehicle.id if vehicle else False,
                "default_outlet_id": default_outlet.id if default_outlet else False,
            },
        }
        view = self.env.ref("route_core.view_route_direct_return_form", raise_if_not_found=False)
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_open_outlets(self):
        self.ensure_one()
        return self._prepare_action("route_core.action_route_outlet", name="Outlets")

    def action_open_outlet_balances(self):
        self.ensure_one()
        return self._prepare_action("route_core.action_outlet_stock_balance", name="Outlet Stock Balances")

    def action_open_visit_collections(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_visit_collection",
            name="My Visit Collections",
            domain=[("salesperson_id", "=", self.env.user.id), ("source_type", "=", "visit")],
        )

    def action_open_direct_sale_payments(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_direct_sale_payment",
            name="My Direct Sale Payments",
            domain=[("salesperson_id", "=", self.env.user.id), ("source_type", "=", "direct_sale")],
        )

    def action_open_payments(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_visit_payment",
            name="All Payments",
            domain=[("salesperson_id", "=", self.env.user.id)],
        )

    def action_open_products(self):
        self.ensure_one()
        return self._prepare_action("route_core.action_route_pda_products", name="All Products")

    def action_open_vehicle_products(self):
        self.ensure_one()
        vehicle = self._get_current_vehicle()
        location = vehicle.stock_location_id if vehicle and getattr(vehicle, "stock_location_id", False) else False
        return self._open_quants_by_location(location, "Vehicle Products")

    def action_open_main_warehouse_products(self):
        self.ensure_one()
        location = self._get_main_warehouse_location()
        title = "Main Warehouse Products"
        if location:
            title = f"Main Warehouse Products - {location.display_name}"
        return self._open_quants_by_location(location, title)
