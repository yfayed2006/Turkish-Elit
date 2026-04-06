from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RoutePdaHome(models.TransientModel):
    _name = "route.pda.home"
    _description = "Route Workspace"

    name = fields.Char(default="Route Workspace", readonly=True)
    user_id = fields.Many2one("res.users", string="Salesperson", default=lambda self: self.env.user, readonly=True)
    user_display_name = fields.Char(string="Salesperson Name", compute="_compute_dashboard")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", readonly=True)
    today_date = fields.Date(string="Today", default=fields.Date.context_today, readonly=True)
    today_display_label = fields.Char(string="Today Label", compute="_compute_dashboard")
    route_enable_direct_sale = fields.Boolean(related="company_id.route_enable_direct_sale", readonly=True, store=False)
    route_enable_direct_return = fields.Boolean(related="company_id.route_enable_direct_return", readonly=True, store=False)
    route_operation_mode = fields.Selection(related="company_id.route_operation_mode", readonly=True, store=False)
    route_enable_lot_serial_tracking = fields.Boolean(related="company_id.route_enable_lot_serial_tracking", readonly=True, store=False)
    route_enable_expiry_tracking = fields.Boolean(related="company_id.route_enable_expiry_tracking", readonly=True, store=False)
    route_operation_mode_label = fields.Char(string="Route Mode", compute="_compute_route_ui_mode")
    route_show_consignment_tools = fields.Boolean(string="Show Consignment Tools", compute="_compute_route_ui_mode")
    route_show_sales_center = fields.Boolean(string="Show Sales Center", compute="_compute_route_ui_mode")
    route_show_direct_sale_tools = fields.Boolean(string="Show Direct Sale Tools", compute="_compute_route_ui_mode")
    route_show_direct_return_tools = fields.Boolean(string="Show Direct Return Tools", compute="_compute_route_ui_mode")
    route_show_lot_ui = fields.Boolean(string="Show Lot and Expiry Labels", compute="_compute_route_ui_mode")

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
    direct_stop_payment_count = fields.Integer(string="Direct Stop Settlements Today", compute="_compute_dashboard")
    direct_sale_order_payment_count = fields.Integer(string="Direct Sale Order Payments Today", compute="_compute_dashboard")
    direct_sale_payment_count = fields.Integer(string="Direct Sales Settlements Today", compute="_compute_dashboard")
    product_count = fields.Integer(string="Products", compute="_compute_dashboard")
    vehicle_product_count = fields.Integer(string="Vehicle Products", compute="_compute_dashboard")
    warehouse_product_count = fields.Integer(string="Main Warehouse Products", compute="_compute_dashboard")

    direct_sale_order_today_count = fields.Integer(string="Direct Sale Orders Today", compute="_compute_dashboard")
    direct_return_today_count = fields.Integer(string="Direct Returns Today", compute="_compute_dashboard")
    direct_sale_today_amount = fields.Monetary(string="Direct Sales Today", currency_field="currency_id", compute="_compute_dashboard")
    direct_return_today_amount = fields.Monetary(string="Direct Returns Today", currency_field="currency_id", compute="_compute_dashboard")
    direct_sales_outstanding_amount = fields.Monetary(string="Outstanding After Settlement", currency_field="currency_id", compute="_compute_dashboard")

    current_visit_name = fields.Char(string="Current Visit", compute="_compute_dashboard")
    current_visit_outlet_name = fields.Char(string="Current Outlet", compute="_compute_dashboard")
    current_vehicle_name = fields.Char(string="Vehicle", compute="_compute_dashboard")
    current_visit_customer_name = fields.Char(string="Customer", compute="_compute_dashboard")
    current_visit_area_name = fields.Char(string="Area", compute="_compute_dashboard")
    current_visit_execution_mode_label = fields.Char(string="Execution Mode", compute="_compute_dashboard")
    current_visit_stage_title = fields.Char(string="Current Step", compute="_compute_dashboard")
    current_visit_stage_help = fields.Text(string="Step Help", compute="_compute_dashboard")
    current_visit_current_due_amount = fields.Monetary(string="Current Due", currency_field="currency_id", compute="_compute_dashboard")
    current_visit_net_due_amount = fields.Monetary(string="Current Visit Sale", currency_field="currency_id", compute="_compute_dashboard")
    current_visit_collected_amount = fields.Monetary(string="Collected", currency_field="currency_id", compute="_compute_dashboard")
    current_visit_remaining_due_amount = fields.Monetary(string="Remaining", currency_field="currency_id", compute="_compute_dashboard")
    current_visit_open_shortage_count = fields.Integer(string="Open Shortages", compute="_compute_dashboard")
    current_visit_near_expiry_count = fields.Integer(string="Near Expiry", compute="_compute_dashboard")
    current_visit_pending_near_expiry_count = fields.Integer(string="Pending Near Expiry", compute="_compute_dashboard")
    current_visit_payment_count = fields.Integer(string="Confirmed Payments", compute="_compute_dashboard")
    current_visit_sale_order_ref = fields.Char(string="Sale Order", compute="_compute_dashboard")
    current_visit_refill_ref = fields.Char(string="Refill Transfer", compute="_compute_dashboard")
    current_visit_return_transfer_refs = fields.Char(string="Return Transfers", compute="_compute_dashboard")

    cash_today_amount = fields.Monetary(string="Cash In Hand", currency_field="currency_id", compute="_compute_dashboard")
    bank_today_amount = fields.Monetary(string="Bank Transfer", currency_field="currency_id", compute="_compute_dashboard")
    pos_today_amount = fields.Monetary(string="POS", currency_field="currency_id", compute="_compute_dashboard")
    deferred_today_amount = fields.Monetary(string="Deferred / Promised Today", currency_field="currency_id", compute="_compute_dashboard")
    open_promise_amount = fields.Monetary(string="Open Promises", currency_field="currency_id", compute="_compute_dashboard")
    remaining_due_amount = fields.Monetary(string="Remaining Due", currency_field="currency_id", compute="_compute_dashboard")
    deferred_payment_count = fields.Integer(string="Deferred / Promise Entries Today", compute="_compute_dashboard")

    direct_sale_cash_today_amount = fields.Monetary(string="Direct Sale Cash Today", currency_field="currency_id", compute="_compute_dashboard")
    direct_sale_bank_today_amount = fields.Monetary(string="Direct Sale Bank Transfer Today", currency_field="currency_id", compute="_compute_dashboard")
    direct_sale_pos_today_amount = fields.Monetary(string="Direct Sale POS Today", currency_field="currency_id", compute="_compute_dashboard")
    direct_sale_deferred_today_amount = fields.Monetary(string="Direct Sale Deferred / Promised Today", currency_field="currency_id", compute="_compute_dashboard")
    direct_sale_open_promise_due_today_amount = fields.Monetary(string="Open Promises Due Today", currency_field="currency_id", compute="_compute_dashboard")
    direct_sale_open_promise_due_today_count = fields.Integer(string="Promise Entries Due Today", compute="_compute_dashboard")

    @api.depends("route_operation_mode", "route_enable_direct_sale", "route_enable_direct_return", "route_enable_lot_serial_tracking", "route_enable_expiry_tracking")
    def _compute_route_ui_mode(self):
        labels = {
            "consignment": _("Consignment Route"),
            "direct_sales": _("Direct Sales Route"),
            "hybrid": _("Hybrid Route"),
        }
        for rec in self:
            mode = rec.route_operation_mode or "hybrid"
            rec.route_operation_mode_label = labels.get(mode, labels["hybrid"])
            rec.route_show_consignment_tools = mode in ("consignment", "hybrid")
            rec.route_show_direct_sale_tools = bool(rec.route_enable_direct_sale) and mode in ("direct_sales", "hybrid")
            rec.route_show_direct_return_tools = bool(rec.route_enable_direct_return)
            rec.route_show_sales_center = rec.route_show_direct_sale_tools or rec.route_show_direct_return_tools
            rec.route_show_lot_ui = bool(rec.route_enable_lot_serial_tracking or rec.route_enable_expiry_tracking)

    def _ensure_consignment_tools_enabled(self):
        self.ensure_one()
        if not self.route_show_consignment_tools:
            raise UserError(_("Consignment visit tools are hidden because Route Operation Mode is Direct Sales Route."))

    def _ensure_direct_sale_mode_enabled(self):
        self.ensure_one()
        if not self.company_id.route_operation_allows_direct_sale():
            raise UserError(_("Direct Sale tools are hidden because Route Operation Mode is Consignment Route."))


    def _ensure_direct_sale_enabled(self):
        self.ensure_one()
        self._ensure_direct_sale_mode_enabled()
        if not self.company_id.route_enable_direct_sale:
            raise UserError(_("Direct Sale is disabled in Route Settings."))

    def _ensure_direct_return_enabled(self):
        self.ensure_one()
        if not self.company_id.route_enable_direct_return:
            raise UserError(_("Direct Return is disabled in Route Settings."))

    def _ensure_sales_center_enabled(self):
        self.ensure_one()
        if not self.route_show_sales_center:
            raise UserError(_("Sales Center is disabled in Route Settings."))

    @api.model
    def action_open_dashboard(self):
        rec = self.create({})
        view = self.env.ref("route_core.view_route_pda_home_form")
        return {
            "type": "ir.actions.act_window",
            "name": "Route Workspace",
            "res_model": "route.pda.home",
            "res_id": rec.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "main",
            "context": {"create": 0, "edit": 0, "delete": 0},
        }

    def _refresh_dashboard_snapshot(self):
        self.ensure_one()
        self.invalidate_recordset()
        self._compute_dashboard()
        return True

    def _open_self_view(self, view_xmlid, title, extra_context=None):
        self.ensure_one()
        self._refresh_dashboard_snapshot()
        if self.name != title:
            self.name = title
        view = self.env.ref(view_xmlid)
        context = {"create": 0, "edit": 0, "delete": 0}
        if extra_context:
            context.update(extra_context)
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "route.pda.home",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(view.id, "form")],
            "target": "main",
            "context": context,
        }

    def action_back_home(self):
        return self._open_self_view("route_core.view_route_pda_home_form", "Route Workspace")

    def action_open_snapshot_center_screen(self):
        self._ensure_consignment_tools_enabled()
        title = "Stock and Lot Snapshot" if self.route_show_lot_ui else "Snapshot Center"
        return self._open_self_view(
            "route_core.view_route_pda_snapshot_center_form",
            title,
            extra_context={"snapshot_mode": "consignment", "snapshot_origin": "consignment"},
        )

    def action_open_review_center_screen(self):
        self._ensure_consignment_tools_enabled()
        # Review Center is no longer part of the simplified salesperson consignment flow.
        # Keep this method as a safe fallback for any old buttons/actions that may still point here.
        return self.action_open_consignment_mode_screen()

    def action_back_to_consignment_mode(self):
        return self.action_open_consignment_mode_screen()

    def action_open_product_center_screen(self):
        title = "Products and Lots" if self.route_show_lot_ui else "Product Center"
        return self._open_self_view("route_core.view_route_pda_product_center_form", title)

    def action_open_sales_center_screen(self):
        self._ensure_sales_center_enabled()
        return self._open_self_view("route_core.view_route_pda_sales_center_form", "Sales Center")

    def action_open_outlet_center_screen(self):
        return self._open_self_view("route_core.view_route_pda_outlet_center_form", "Outlet Center")


    def action_open_direct_sale_mode_screen(self):
        self._ensure_sales_center_enabled()
        return self._open_self_view("route_core.view_route_pda_direct_sale_mode_form", "Direct Sale")

    def action_open_consignment_mode_screen(self):
        self._ensure_consignment_tools_enabled()
        return self._open_self_view("route_core.view_route_pda_consignment_mode_form", "Consignment")

    def action_open_today_overview_screen(self):
        return self._open_self_view("route_core.view_route_pda_today_overview_form", "Today Overview")

    def action_open_current_visit_snapshot_screen(self):
        self._ensure_consignment_tools_enabled()
        snapshot_mode = self.env.context.get("snapshot_mode") or "consignment"
        snapshot_origin = self.env.context.get("snapshot_origin") or "consignment"
        return self._open_self_view(
            "route_core.view_route_pda_current_visit_snapshot_form",
            "Current Visit Snapshot",
            extra_context={"snapshot_mode": snapshot_mode, "snapshot_origin": snapshot_origin},
        )

    def action_open_collections_snapshot_screen(self):
        return self._open_self_view(
            "route_core.view_route_pda_collections_snapshot_form",
            "Collections Snapshot",
            extra_context={"collections_snapshot_origin": "snapshot_center"},
        )

    def action_open_visit_collections_center_screen(self):
        return self._open_self_view("route_core.view_route_pda_visit_collections_center_form", "Visit Collections")

    def action_open_collections_snapshot_from_collections_center(self):
        return self._open_self_view(
            "route_core.view_route_pda_collections_snapshot_form",
            "Collections Snapshot",
            extra_context={"collections_snapshot_origin": "collections_center"},
        )

    def action_back_from_collections_snapshot(self):
        self.ensure_one()
        origin = self.env.context.get("collections_snapshot_origin")
        if origin == "collections_center":
            return self.action_open_visit_collections_center_screen()
        return self.action_open_snapshot_center_screen()

    def action_open_reference_counts_screen(self):
        return self._open_self_view("route_core.view_route_pda_reference_counts_form", "Reference Counts")

    def _today_bounds(self):
        today = fields.Date.context_today(self)
        tz_name = self.env.user.tz or self.env.context.get("tz") or "UTC"
        user_tz = pytz.timezone(tz_name)
        start_local = user_tz.localize(datetime.combine(today, time.min))
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
        end_utc = end_local.astimezone(pytz.UTC).replace(tzinfo=None)
        return today, fields.Datetime.to_string(start_utc), fields.Datetime.to_string(end_utc)

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

    def _get_payment_snapshot_mode(self, payment):
        if not payment:
            return False
        if hasattr(payment, "_get_snapshot_payment_mode"):
            return payment._get_snapshot_payment_mode()
        if payment.collection_type in ("defer_date", "next_visit"):
            return "deferred"
        return payment.payment_mode or "cash"

    def _get_payment_snapshot_promise_status(self, payment):
        if not payment or payment.state != "confirmed" or (payment.promise_amount or 0.0) <= 0.0:
            return False
        if hasattr(payment, "_get_snapshot_promise_status"):
            return payment._get_snapshot_promise_status()
        today = fields.Date.context_today(self)
        if payment.promise_date and payment.promise_date < today:
            return "overdue"
        if payment.promise_date and payment.promise_date == today:
            return "due_today"
        return "open"

    def _get_payment_business_flow(self, payment):
        if not payment:
            return False
        if getattr(payment, "payment_business_flow", False):
            return payment.payment_business_flow
        if payment.source_type == "direct_sale":
            return "direct_sale_order"
        if payment.settlement_visit_id and getattr(payment.settlement_visit_id, "visit_execution_mode", False) == "direct_sales":
            return "direct_stop"
        return "consignment_visit"

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
        SaleOrder = self.env["sale.order"]
        DirectReturn = self.env["route.direct.return"]

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
            active_visits = Visit.search([
                ("user_id", "=", user.id),
                ("state", "=", "in_progress"),
            ], order="start_datetime desc, id desc")
            snapshot_mode = self.env.context.get("snapshot_mode")
            if snapshot_mode in ("consignment", "direct_sales"):
                current_visit = active_visits.filtered(
                    lambda v: getattr(v, "visit_execution_mode", False) == snapshot_mode
                )[:1]
            else:
                current_visit = active_visits[:1]
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
            today_direct_orders = SaleOrder.search([
                ("user_id", "=", user.id),
                ("route_order_mode", "=", "direct_sale"),
                ("date_order", ">=", start_dt),
                ("date_order", "<", end_dt),
                ("state", "in", ["sale", "done"]),
            ])
            today_direct_returns = DirectReturn.search([
                ("user_id", "=", user.id),
                ("return_date", "=", today),
                ("state", "=", "done"),
            ])
            open_direct_sales_visits = today_visits.filtered(lambda v: getattr(v, "visit_execution_mode", False) == "direct_sales" and v.state != "done")

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
            visit_collections = today_payments.filtered(lambda p: rec._get_payment_business_flow(p) == "consignment_visit")
            direct_stop_payments = today_payments.filtered(lambda p: rec._get_payment_business_flow(p) == "direct_stop")
            direct_sale_order_payments = today_payments.filtered(lambda p: rec._get_payment_business_flow(p) == "direct_sale_order")
            direct_sales_today_payments = today_payments.filtered(lambda p: rec._get_payment_business_flow(p) in ("direct_stop", "direct_sale_order"))
            direct_sales_all_confirmed_payments = all_confirmed_payments.filtered(lambda p: rec._get_payment_business_flow(p) in ("direct_stop", "direct_sale_order"))
            deferred_entries = today_payments.filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
            direct_sales_deferred_entries = direct_sales_today_payments.filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
            direct_sales_due_today_promises = direct_sales_all_confirmed_payments.filtered(
                lambda p: rec._get_payment_snapshot_promise_status(p) == "due_today"
            )

            visit_collection_targets = set(visit_collections.mapped("visit_id").ids)
            direct_stop_targets = set((direct_stop_payments.mapped("settlement_visit_id") or direct_stop_payments.mapped("visit_id")).ids)
            direct_sale_order_targets = set(direct_sale_order_payments.mapped("sale_order_id").ids)

            rec.visit_collection_count = len(visit_collection_targets)
            rec.direct_stop_payment_count = len(direct_stop_targets)
            rec.direct_sale_order_payment_count = len(direct_sale_order_targets)
            rec.direct_sale_payment_count = len(direct_stop_targets) + len(direct_sale_order_targets)
            rec.product_count = Product.search_count([("sale_ok", "=", True), ("active", "=", True)])
            rec.vehicle_product_count = Quant.search_count([("location_id", "child_of", vehicle.stock_location_id.id), ("quantity", ">", 0)]) if vehicle and getattr(vehicle, "stock_location_id", False) else 0
            rec.warehouse_product_count = Quant.search_count([("location_id", "child_of", warehouse_loc.id), ("quantity", ">", 0)]) if warehouse_loc else 0
            rec.direct_sale_order_today_count = len(today_direct_orders)
            rec.direct_return_today_count = len(today_direct_returns)
            rec.direct_sale_today_amount = sum(today_direct_orders.mapped("amount_total")) if today_direct_orders else 0.0
            rec.direct_return_today_amount = sum(today_direct_returns.mapped("amount_total")) if today_direct_returns else 0.0
            rec.direct_sales_outstanding_amount = sum(open_direct_sales_visits.mapped("direct_stop_settlement_remaining_amount")) if open_direct_sales_visits else 0.0

            rec.current_visit_name = current_visit.display_name if current_visit else _("No active visit")
            rec.current_visit_outlet_name = current_visit.outlet_id.display_name if current_visit and current_visit.outlet_id else "-"
            rec.current_visit_customer_name = current_visit.partner_id.display_name if current_visit and current_visit.partner_id else "-"
            rec.current_visit_area_name = current_visit.area_id.display_name if current_visit and current_visit.area_id else "-"
            rec.current_visit_execution_mode_label = current_visit.visit_execution_mode_label if current_visit else "-"
            rec.current_visit_stage_title = current_visit.ux_stage_title if current_visit else _("No active visit in progress")
            rec.current_visit_stage_help = current_visit.ux_stage_help if current_visit else _("Open My Visits to start or continue a consignment visit.")
            rec.current_visit_current_due_amount = current_visit.outlet_current_due_amount if current_visit else 0.0
            rec.current_visit_net_due_amount = current_visit.net_due_amount if current_visit else 0.0
            rec.current_visit_collected_amount = current_visit.collected_amount if current_visit else 0.0
            rec.current_visit_remaining_due_amount = current_visit.remaining_due_amount if current_visit else 0.0
            rec.current_visit_open_shortage_count = current_visit.outlet_open_shortage_count if current_visit else 0
            rec.current_visit_near_expiry_count = current_visit.outlet_near_expiry_count if current_visit else 0
            rec.current_visit_pending_near_expiry_count = current_visit.pending_near_expiry_line_count if current_visit else 0
            rec.current_visit_payment_count = len(current_visit.display_payment_ids.filtered(lambda p: p.state == "confirmed")) if current_visit else 0
            rec.current_visit_sale_order_ref = current_visit.summary_sale_order_ref if current_visit and hasattr(current_visit, "summary_sale_order_ref") else "-"
            rec.current_visit_refill_ref = current_visit.summary_refill_transfer_ref if current_visit and hasattr(current_visit, "summary_refill_transfer_ref") else "-"
            rec.current_visit_return_transfer_refs = current_visit.summary_return_transfer_refs if current_visit and hasattr(current_visit, "summary_return_transfer_refs") else "-"
            if current_visit and current_visit.vehicle_id:
                rec.current_vehicle_name = current_visit.vehicle_id.display_name
            elif today_plans[:1].vehicle_id:
                rec.current_vehicle_name = today_plans[:1].vehicle_id.display_name
            else:
                rec.current_vehicle_name = "-"

            rec.cash_today_amount = sum((p.amount or 0.0) for p in today_payments if rec._get_payment_snapshot_mode(p) == "cash")
            rec.bank_today_amount = sum((p.amount or 0.0) for p in today_payments if rec._get_payment_snapshot_mode(p) == "bank")
            rec.pos_today_amount = sum((p.amount or 0.0) for p in today_payments if rec._get_payment_snapshot_mode(p) == "pos")
            rec.deferred_today_amount = sum((p.promise_amount or 0.0) for p in deferred_entries)
            rec.deferred_payment_count = len(deferred_entries)
            rec.open_promise_amount = sum(
                (p.promise_amount or 0.0)
                for p in all_confirmed_payments
                if rec._get_payment_snapshot_promise_status(p) in ("open", "due_today", "overdue")
            )
            rec.direct_sale_cash_today_amount = sum((p.amount or 0.0) for p in direct_sales_today_payments if rec._get_payment_snapshot_mode(p) == "cash")
            rec.direct_sale_bank_today_amount = sum((p.amount or 0.0) for p in direct_sales_today_payments if rec._get_payment_snapshot_mode(p) == "bank")
            rec.direct_sale_pos_today_amount = sum((p.amount or 0.0) for p in direct_sales_today_payments if rec._get_payment_snapshot_mode(p) == "pos")
            rec.direct_sale_deferred_today_amount = sum((p.promise_amount or 0.0) for p in direct_sales_deferred_entries)
            rec.direct_sale_open_promise_due_today_amount = sum((p.promise_amount or 0.0) for p in direct_sales_due_today_promises)
            rec.direct_sale_open_promise_due_today_count = len(direct_sales_due_today_promises)
            rec.remaining_due_amount = sum(
                (visit.direct_stop_settlement_remaining_amount or 0.0)
                if getattr(visit, "visit_execution_mode", False) == "direct_sales"
                else (visit.remaining_due_amount or 0.0)
                for visit in today_visits.filtered(lambda v: v.state not in ("done", "cancel", "cancelled"))
            )

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
            name="My Visits",
            domain=[("user_id", "=", self.env.user.id), ("date", "=", today)],
            context={"search_default_filter_my_visits": 1, "search_default_filter_today": 1, "search_default_filter_active": 1, "edit": 1},
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
            domain=[("user_id", "=", self.env.user.id), ("state", "in", ["done", "cancel", "cancelled"])],
            context={"search_default_filter_my_visits": 1, "search_default_filter_done": 1, "create": 0, "edit": 0, "delete": 0},
        )

    def action_open_my_vehicle_closing(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_vehicle_closing_salesperson",
            name="My Vehicle Closings",
            domain=[("user_id", "=", self.env.user.id), ("state", "=", "closed")],
            context={"search_default_filter_closed": 1, "create": 0, "edit": 0, "delete": 0},
        )

    def action_open_my_shortages(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_shortage",
            name="My Shortages",
            domain=[("user_id", "=", self.env.user.id)],
            context={"create": 0, "edit": 0, "delete": 0},
        )

    def action_open_my_salesperson_shortages(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_salesperson_shortage",
            name="My Salesperson Shortages",
            domain=[("salesperson_id", "=", self.env.user.id)],
        )

    def _get_consignment_visits(self):
        self.ensure_one()
        visits = self.env["route.visit"].search([("user_id", "=", self.env.user.id)], order="date desc, id desc")
        return visits.filtered(lambda v: getattr(v, "visit_execution_mode", False) != "direct_sales")

    def _get_consignment_sale_orders(self):
        self.ensure_one()
        sale_orders = self._get_consignment_visits().mapped("sale_order_id")
        return sale_orders.filtered(lambda so: so and getattr(so, "route_order_mode", "standard") != "direct_sale")

    def _get_consignment_internal_transfers(self):
        self.ensure_one()
        visits = self._get_consignment_visits()
        pickings = visits.mapped("return_picking_ids") | visits.mapped("refill_picking_id")
        return pickings.filtered(lambda p: p and p.state != "cancel")

    def action_open_consignment_sale_orders(self):
        self.ensure_one()
        self._ensure_consignment_tools_enabled()
        sale_orders = self._get_consignment_sale_orders()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Consignment Sales Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("id", "in", sale_orders.ids)],
            "context": {"create": 0, "delete": 0},
        }
        tree_view = self.env.ref("sale.view_quotation_tree_with_onboarding", raise_if_not_found=False)
        form_view = self.env.ref("sale.view_order_form", raise_if_not_found=False)
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

    def action_open_consignment_internal_transfers(self):
        self.ensure_one()
        self._ensure_consignment_tools_enabled()
        pickings = self._get_consignment_internal_transfers()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action.update({
            "name": _("Returns, Transfers and Lots") if self.route_show_lot_ui else _("Returns and Internal Transfers"),
            "domain": [("id", "in", pickings.ids)],
            "context": {"create": 0, "delete": 0},
        })
        return action

    def action_open_consignment_payments(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_visit_collection_salesperson",
            name=_("Consignment Collections"),
            domain=[("salesperson_id", "=", self.env.user.id), ("payment_business_flow", "=", "consignment_visit"), ("state", "=", "confirmed")],
            context={"search_default_filter_my_payments": 1, "search_default_filter_confirmed": 1, "create": 0, "edit": 0, "delete": 0},
        )

    def action_open_direct_sale_orders(self):
        self.ensure_one()
        self._ensure_direct_sale_enabled()
        action = {
            "type": "ir.actions.act_window",
            "name": "Direct Sale Orders",
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("route_order_mode", "=", "direct_sale"), ("user_id", "=", self.env.user.id), ("state", "!=", "cancel")],
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
        self._ensure_direct_sale_enabled()
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
        self._ensure_direct_return_enabled()
        return self._prepare_action(
            "route_core.action_route_direct_return",
            name="Direct Returns",
            domain=[("user_id", "=", self.env.user.id), ("state", "!=", "cancel")],
        )

    def action_open_direct_sale_outlets(self):
        self.ensure_one()
        self._ensure_direct_sale_enabled()
        return self._prepare_action(
            "route_core.action_route_outlet",
            name="Direct Sale Outlets",
            domain=[("outlet_operation_mode", "=", "direct_sale"), ("active", "=", True)],
        )

    def action_create_direct_sale(self):
        self.ensure_one()
        self._ensure_direct_sale_enabled()
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
        self._ensure_direct_return_enabled()
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
            "route_core.action_route_visit_collection_salesperson",
            name="All Collections",
            domain=[("salesperson_id", "=", self.env.user.id), ("state", "=", "confirmed")],
            context={"search_default_filter_my_payments": 1, "search_default_filter_confirmed": 1, "create": 0, "edit": 0, "delete": 0},
        )

    def action_open_direct_sale_payments(self):
        self.ensure_one()
        self._ensure_direct_sale_enabled()
        return self._prepare_action(
            "route_core.action_route_direct_sale_payment",
            name="Direct Sale Collections",
            domain=[("salesperson_id", "=", self.env.user.id), ("payment_business_flow", "in", ["direct_stop", "direct_sale_order"])],
        )

    def action_open_payments(self):
        self.ensure_one()
        return self._prepare_action(
            "route_core.action_route_visit_payment",
            name="All Collections",
            domain=[("salesperson_id", "=", self.env.user.id)],
        )

    def action_open_products(self):
        self.ensure_one()
        return self._prepare_action("route_core.action_route_pda_products", name="All Products and Lots" if self.route_show_lot_ui else "All Products")

    def action_open_vehicle_products(self):
        self.ensure_one()
        vehicle = self._get_current_vehicle()
        location = vehicle.stock_location_id if vehicle and getattr(vehicle, "stock_location_id", False) else False
        return self._open_quants_by_location(location, "Vehicle Products and Lots" if self.route_show_lot_ui else "Vehicle Products")

    def action_open_main_warehouse_products(self):
        self.ensure_one()
        location = self._get_main_warehouse_location()
        title = "Warehouse Products and Lots" if self.route_show_lot_ui else "Main Warehouse Products"
        if location:
            prefix = "Warehouse Products and Lots" if self.route_show_lot_ui else "Main Warehouse Products"
            title = f"{prefix} - {location.display_name}"
        return self._open_quants_by_location(location, title)
