from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Visit Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )
    date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=False,
        readonly=True,
    )

    route_operation_mode = fields.Selection(
        related="company_id.route_operation_mode",
        readonly=True,
        store=False,
    )
    route_enable_direct_sale = fields.Boolean(
        related="company_id.route_enable_direct_sale",
        readonly=True,
        store=False,
    )
    route_enable_direct_return = fields.Boolean(
        related="company_id.route_enable_direct_return",
        readonly=True,
        store=False,
    )
    route_enable_lot_serial_tracking = fields.Boolean(
        related="company_id.route_enable_lot_serial_tracking",
        readonly=True,
        store=False,
    )
    route_enable_expiry_tracking = fields.Boolean(
        related="company_id.route_enable_expiry_tracking",
        readonly=True,
        store=False,
    )
    outlet_operation_mode = fields.Selection(
        related="outlet_id.outlet_operation_mode",
        readonly=True,
        store=False,
    )
    visit_execution_mode = fields.Selection(
        [("consignment", "Consignment Visit"), ("direct_sales", "Direct Sales Stop")],
        string="Visit Execution Mode",
        compute="_compute_visit_execution_mode",
        store=False,
    )
    visit_execution_mode_label = fields.Char(
        string="Execution Mode",
        compute="_compute_visit_execution_mode",
        store=False,
    )
    route_show_consignment_workflow = fields.Boolean(
        string="Show Consignment Workflow",
        compute="_compute_visit_execution_mode",
        store=False,
    )
    route_show_direct_sales_workflow = fields.Boolean(
        string="Show Direct Sales Workflow",
        compute="_compute_visit_execution_mode",
        store=False,
    )
    direct_stop_skip_sale = fields.Boolean(string="Skip Sale", default=False, copy=False)
    direct_stop_skip_return = fields.Boolean(string="Skip Return", default=False, copy=False)
    direct_stop_sale_status = fields.Selection(
        [("pending", "Pending"), ("yes", "Sale Created"), ("no", "No Sale")],
        string="Sale Decision",
        compute="_compute_direct_stop_summary",
        store=False,
    )
    direct_stop_return_status = fields.Selection(
        [("pending", "Pending"), ("yes", "Return Created"), ("no", "No Return")],
        string="Return Decision",
        compute="_compute_direct_stop_summary",
        store=False,
    )
    direct_stop_order_ids = fields.Many2many(
        "sale.order",
        string="Direct Sale Orders",
        compute="_compute_direct_stop_order_ids",
        store=False,
    )
    direct_stop_return_ids = fields.One2many("route.direct.return", "visit_id", string="Direct Returns")
    direct_stop_order_count = fields.Integer(string="Direct Sale Orders", compute="_compute_direct_stop_summary", store=False)
    direct_stop_return_count = fields.Integer(string="Direct Returns", compute="_compute_direct_stop_summary", store=False)
    direct_stop_sales_total = fields.Monetary(string="Direct Sales Total", currency_field="currency_id", compute="_compute_direct_stop_summary", store=False)
    direct_stop_returns_total = fields.Monetary(string="Direct Returns Total", currency_field="currency_id", compute="_compute_direct_stop_summary", store=False)
    direct_stop_previous_due_amount = fields.Monetary(string="Previous Due", currency_field="currency_id", compute="_compute_direct_stop_summary", store=False)
    direct_stop_previous_due_since_date = fields.Date(string="Previous Due Since", compute="_compute_direct_stop_summary", store=False)
    direct_stop_current_net_amount = fields.Monetary(string="Current Stop Net", currency_field="currency_id", compute="_compute_direct_stop_summary", store=False)
    direct_stop_grand_due_amount = fields.Monetary(string="Grand Total Due", currency_field="currency_id", compute="_compute_direct_stop_summary", store=False)
    direct_stop_settlement_paid_amount = fields.Monetary(string="Settlement Paid", currency_field="currency_id", compute="_compute_direct_stop_summary", store=False)
    direct_stop_settlement_remaining_amount = fields.Monetary(string="Settlement Remaining", currency_field="currency_id", compute="_compute_direct_stop_summary", store=False)
    direct_stop_credit_amount = fields.Monetary(string="Return Credit", currency_field="currency_id", compute="_compute_direct_stop_summary", store=False)
    direct_stop_credit_policy = fields.Selection(
        [("customer_credit", "Customer Credit"), ("cash_refund", "Cash Refund"), ("next_stop", "Carry to Next Stop")],
        string="Return Credit Settlement",
        copy=False,
    )
    direct_stop_credit_note = fields.Text(string="Credit Settlement Note", copy=False)
    direct_stop_settlement_ready = fields.Boolean(string="Direct Stop Settlement Ready", compute="_compute_direct_stop_summary", store=False)

    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        tracking=True,
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        tracking=True,
    )
    vehicle_id = fields.Many2one(
        "route.vehicle",
        string="Vehicle",
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    notes = fields.Text(string="Notes")

    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        tracking=True,
        copy=False,
    )
    destination_location_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        tracking=True,
        copy=False,
    )

    near_expiry_threshold_days = fields.Integer(
        string="Near Expiry Threshold Days",
        default=60,
        tracking=True,
        help="If expiry is within this number of days, the line is treated as near expiry.",
    )

    collection_skip_reason = fields.Text(
        string="Collection Skip Reason",
        tracking=True,
        copy=False,
    )
    no_sale_reason = fields.Text(
        string="Reason for Ending Without Sale",
        readonly=True,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    visit_process_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("checked_in", "Checked In"),
            ("counting", "Counting"),
            ("reconciled", "Reconciled"),
            ("collection_done", "Collection Done"),
            ("ready_to_close", "Ready To Close"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Visit Process State",
        default="draft",
        tracking=True,
        copy=False,
    )

    start_datetime = fields.Datetime(
        string="Start DateTime",
        readonly=True,
        tracking=True,
    )
    end_datetime = fields.Datetime(
        string="End DateTime",
        readonly=True,
        tracking=True,
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Sale Order",
        readonly=True,
        copy=False,
        tracking=True,
    )
    sale_order_count = fields.Integer(
        string="Sale Order Count",
        compute="_compute_sale_order_count",
    )

    line_ids = fields.One2many(
        "route.visit.line",
        "visit_id",
        string="Visit Lines",
    )
    payment_ids = fields.One2many(
        "route.visit.payment",
        "visit_id",
        string="Payments",
    )
    settlement_payment_ids = fields.One2many(
        "route.visit.payment",
        "settlement_visit_id",
        string="Settlement Payments",
    )
    display_payment_ids = fields.Many2many(
        "route.visit.payment",
        string="Displayed Payments",
        compute="_compute_display_payment_ids",
        store=False,
    )

    net_due_amount = fields.Monetary(
        string="Net Due Amount",
        currency_field="currency_id",
        compute="_compute_payment_totals",
        store=False,
    )
    collected_amount = fields.Monetary(
        string="Collected Amount",
        currency_field="currency_id",
        compute="_compute_payment_totals",
        store=False,
    )
    remaining_due_amount = fields.Monetary(
        string="Remaining Due Amount",
        currency_field="currency_id",
        compute="_compute_payment_totals",
        store=False,
    )
    promise_to_pay_count = fields.Integer(
        string="Open Promises",
        compute="_compute_promise_to_pay_summary",
        store=False,
    )
    next_promise_to_pay_date = fields.Date(
        string="Next Promise Date",
        compute="_compute_promise_to_pay_summary",
        store=False,
    )
    latest_promise_to_pay_date = fields.Date(
        string="Latest Promise Date",
        compute="_compute_promise_to_pay_summary",
        store=False,
    )
    latest_promise_to_pay_amount = fields.Monetary(
        string="Latest Promise Amount",
        currency_field="currency_id",
        compute="_compute_promise_to_pay_summary",
        store=False,
    )
    latest_promise_status = fields.Selection(
        [("open", "Open"), ("due_today", "Due Today"), ("overdue", "Overdue"), ("closed", "Closed")],
        string="Latest Promise Status",
        compute="_compute_promise_to_pay_summary",
        store=False,
    )

    collection_priority_score = fields.Integer(
        string="Collection Priority Score",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_open_promise_count = fields.Integer(
        string="Open Promises",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_overdue_promise_count = fields.Integer(
        string="Overdue Promises",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_unpaid_visit_count = fields.Integer(
        string="Unpaid Visits",
        compute="_compute_visit_command_header",
        store=False,
    )
    collection_trend_status = fields.Selection(
        [
            ("good", "Good"),
            ("warning", "Warning"),
            ("weak", "Weak"),
            ("no_basis", "No Basis"),
        ],
        string="Collection Trend",
        compute="_compute_visit_command_header",
        store=False,
    )
    collection_priority_reason = fields.Char(
        string="Collection Priority Basis",
        compute="_compute_visit_command_header",
        store=False,
    )
    debt_risk_level = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Debt Risk Level",
        compute="_compute_visit_command_header",
        store=False,
    )
    debt_policy_action = fields.Selection(
        [
            ("allow", "Allow Refill"),
            ("warning", "Warning"),
            ("supervisor", "Supervisor Approval"),
            ("block", "Block Refill"),
        ],
        string="Refill Restriction Hint",
        compute="_compute_visit_command_header",
        store=False,
    )
    collection_first_required = fields.Boolean(
        string="Collection First Required",
        compute="_compute_visit_command_header",
        store=False,
    )
    debt_policy_reason = fields.Char(
        string="Debt Policy Basis",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_aging_0_30_amount = fields.Monetary(
        string="Aging 0-30",
        currency_field="currency_id",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_aging_31_60_amount = fields.Monetary(
        string="Aging 31-60",
        currency_field="currency_id",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_aging_61_90_amount = fields.Monetary(
        string="Aging 61-90",
        currency_field="currency_id",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_aging_90_plus_amount = fields.Monetary(
        string="Aging 90+",
        currency_field="currency_id",
        compute="_compute_visit_command_header",
        store=False,
    )

    has_returns = fields.Boolean(
        string="Has Returns",
        default=False,
        tracking=True,
        copy=False,
    )
    returns_step_done = fields.Boolean(
        string="Returns Step Done",
        default=False,
        tracking=True,
        copy=False,
    )
    has_refill = fields.Boolean(
        string="Has Refill",
        default=False,
        tracking=True,
        copy=False,
    )
    has_pending_refill = fields.Boolean(
        string="Has Pending Refill",
        default=False,
        tracking=True,
        copy=False,
    )
    no_refill = fields.Boolean(
        string="No Refill",
        default=False,
        tracking=True,
        copy=False,
    )

    refill_datetime = fields.Datetime(
        string="Refill Datetime",
        tracking=True,
        copy=False,
    )
    refill_backorder_id = fields.Many2one(
        "route.refill.backorder",
        string="Refill Backorder",
        copy=False,
    )
    refill_picking_id = fields.Many2one(
        "stock.picking",
        string="Refill Transfer",
        copy=False,
    )
    refill_picking_count = fields.Integer(
        string="Refill Transfer Count",
        compute="_compute_refill_picking_count",
        store=False,
    )

    return_picking_ids = fields.One2many(
        "stock.picking",
        "route_visit_id",
        string="Return Transfers",
    )
    return_picking_count = fields.Integer(
        string="Return Pickings",
        compute="_compute_return_picking_count",
        store=False,
    )

    near_expiry_line_count = fields.Integer(
        string="Near Expiry Lines",
        compute="_compute_near_expiry_status",
        store=True,
    )
    pending_near_expiry_line_count = fields.Integer(
        string="Pending Near Expiry Lines",
        compute="_compute_near_expiry_status",
        store=True,
    )
    has_pending_near_expiry = fields.Boolean(
        string="Has Pending Near Expiry",
        compute="_compute_near_expiry_status",
        store=True,
    )


    visit_mode = fields.Selection(
        [
            ("regular", "Regular Visit"),
            ("collection_first", "Collection First"),
            ("refill_first", "Refill First"),
            ("audit_only", "Audit Only"),
        ],
        string="Visit Mode",
        default="regular",
        required=True,
        tracking=True,
        copy=False,
    )
    visit_mode_recommendation = fields.Selection(
        [
            ("regular", "Regular Visit"),
            ("collection_first", "Collection First"),
            ("refill_first", "Refill First"),
            ("audit_only", "Audit Only"),
        ],
        string="Recommended Visit Mode",
        compute="_compute_visit_command_header",
        store=False,
    )
    collection_priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Collection Priority",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_current_due_amount = fields.Monetary(
        string="Current Due",
        currency_field="currency_id",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_open_shortage_count = fields.Integer(
        string="Open Shortages",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_near_expiry_count = fields.Integer(
        string="Near Expiry",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_summary_alert_level = fields.Selection(
        [("normal", "Normal"), ("warning", "Needs Follow-up"), ("critical", "Critical")],
        string="Outlet Alert Level",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_decision_flags_html = fields.Html(
        string="Decision Flags",
        compute="_compute_visit_command_header",
        sanitize=False,
    )
    recommended_visit_frequency = fields.Selection(
        [
            ("daily", "Daily"),
            ("every_2_days", "Every 2 Days"),
            ("twice_weekly", "Twice Weekly"),
            ("weekly", "Weekly"),
            ("on_demand", "On Demand"),
        ],
        string="Visit Frequency",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_health_score = fields.Integer(
        string="Outlet Health Score",
        compute="_compute_visit_command_header",
        store=False,
    )
    outlet_health_status = fields.Selection(
        [
            ("healthy", "Healthy"),
            ("attention", "Needs Attention"),
            ("critical", "Critical"),
        ],
        string="Outlet Health Status",
        compute="_compute_visit_command_header",
        store=False,
    )
    visit_regularity_days = fields.Integer(
        string="Days Since Last Visit",
        compute="_compute_visit_command_header",
        store=False,
    )
    visit_regularity_status = fields.Selection(
        [
            ("on_track", "On Track"),
            ("follow_up", "Follow-up Due"),
            ("overdue", "Overdue"),
            ("unknown", "Unknown"),
        ],
        string="Visit Regularity",
        compute="_compute_visit_command_header",
        store=False,
    )
    visit_planning_reason = fields.Char(
        string="Visit Planning Basis",
        compute="_compute_visit_command_header",
        store=False,
    )


    slow_moving_line_count = fields.Integer(
        string="Slow Moving Lines",
        compute="_compute_slow_moving_snapshot",
        store=False,
    )
    very_slow_line_count = fields.Integer(
        string="Very Slow Lines",
        compute="_compute_slow_moving_snapshot",
        store=False,
    )
    no_sale_history_line_count = fields.Integer(
        string="No Sale History Lines",
        compute="_compute_slow_moving_snapshot",
        store=False,
    )
    average_days_on_shelf = fields.Float(
        string="Avg Days On Shelf",
        compute="_compute_slow_moving_snapshot",
        store=False,
    )
    oldest_days_on_shelf = fields.Integer(
        string="Oldest Shelf Days",
        compute="_compute_slow_moving_snapshot",
        store=False,
    )


    def _get_outlet_collection_promise_metrics(self, outlet):
        Payment = self.env["route.visit.payment"]
        if not outlet:
            return {"open_promises": 0, "overdue_promises": 0}

        promise_payments = Payment.search([
            ("outlet_id", "=", outlet.id),
            ("state", "!=", "cancelled"),
            ("promise_amount", ">", 0.0),
        ])
        open_promises = promise_payments.filtered(
            lambda p: p.promise_status in ("open", "due_today", "overdue")
        )
        overdue_promises = open_promises.filtered(lambda p: p.promise_status == "overdue")
        return {
            "open_promises": len(open_promises),
            "overdue_promises": len(overdue_promises),
        }

    def _get_collection_priority_context(self, outlet):
        if not outlet:
            return {
                "priority": "low",
                "score": 0,
                "open_promises": 0,
                "overdue_promises": 0,
                "unpaid_visits": 0,
                "collection_trend": "no_basis",
                "reason": "No outlet linked",
            }

        current_due = getattr(outlet, "current_due_amount", 0.0) or 0.0
        aging_31_60 = getattr(outlet, "aging_31_60_amount", 0.0) or 0.0
        aging_61_90 = getattr(outlet, "aging_61_90_amount", 0.0) or 0.0
        aging_90_plus = getattr(outlet, "aging_90_plus_amount", 0.0) or 0.0
        unpaid_visits = getattr(outlet, "unpaid_visit_count", 0) or 0
        collection_trend = getattr(outlet, "collection_status", "no_basis") or "no_basis"
        sales_average = getattr(outlet, "sales_last_3_months_average", 0.0) or 0.0

        promise_metrics = self._get_outlet_collection_promise_metrics(outlet)
        open_promises = promise_metrics["open_promises"]
        overdue_promises = promise_metrics["overdue_promises"]

        score = 0
        reasons = []

        # Current due pressure
        if current_due > 0:
            if current_due >= max(sales_average * 3.0, 5000.0):
                score += 25
                reasons.append("very high due")
            elif current_due >= max(sales_average * 1.5, 1500.0):
                score += 18
                reasons.append("high due")
            elif current_due >= 500.0:
                score += 10
                reasons.append("due outstanding")
            else:
                score += 5
                reasons.append("small due")

        # Aging pressure
        if aging_90_plus > 0:
            score += 40
            reasons.append("90+ aging")
        elif aging_61_90 > 0:
            score += 25
            reasons.append("61-90 aging")
        elif aging_31_60 > 0:
            score += 10
            reasons.append("31-60 aging")

        # Promise pressure
        if overdue_promises >= 3:
            score += 25
            reasons.append("multiple overdue promises")
        elif overdue_promises > 0:
            score += min(15 + ((overdue_promises - 1) * 5), 25)
            reasons.append("overdue promises")

        if open_promises >= 3:
            score += 10
            reasons.append("many open promises")
        elif open_promises > 0:
            score += 5
            reasons.append("open promise")

        # Unpaid visits pressure
        if unpaid_visits >= 5:
            score += 15
            reasons.append("many unpaid visits")
        elif unpaid_visits >= 2:
            score += 8
            reasons.append("multiple unpaid visits")
        elif unpaid_visits >= 1:
            score += 4
            reasons.append("unpaid visit")

        # Collection trend pressure
        if collection_trend == "weak":
            score += 20
            reasons.append("weak collection trend")
        elif collection_trend == "warning":
            score += 10
            reasons.append("warning collection trend")

        if score >= 70:
            priority = "critical"
        elif score >= 40:
            priority = "high"
        elif score >= 15:
            priority = "medium"
        else:
            priority = "low"

        return {
            "priority": priority,
            "score": int(score),
            "open_promises": open_promises,
            "overdue_promises": overdue_promises,
            "unpaid_visits": unpaid_visits,
            "collection_trend": collection_trend,
            "reason": ", ".join(reasons[:4]) if reasons else "healthy collection profile",
        }

    def _get_debt_policy_context(self, outlet, priority_ctx=None):
        if not outlet:
            return {
                "risk": "low",
                "action": "allow",
                "collection_first": False,
                "reason": "No outlet linked",
                "aging_0_30": 0.0,
                "aging_31_60": 0.0,
                "aging_61_90": 0.0,
                "aging_90_plus": 0.0,
            }

        if priority_ctx is None:
            priority_ctx = self._get_collection_priority_context(outlet)

        current_due = getattr(outlet, "current_due_amount", 0.0) or 0.0
        sales_average = getattr(outlet, "sales_last_3_months_average", 0.0) or 0.0
        aging_0_30 = getattr(outlet, "aging_0_30_amount", 0.0) or 0.0
        aging_31_60 = getattr(outlet, "aging_31_60_amount", 0.0) or 0.0
        aging_61_90 = getattr(outlet, "aging_61_90_amount", 0.0) or 0.0
        aging_90_plus = getattr(outlet, "aging_90_plus_amount", 0.0) or 0.0
        overdue_promises = priority_ctx.get("overdue_promises", 0)
        open_promises = priority_ctx.get("open_promises", 0)
        unpaid_visits = priority_ctx.get("unpaid_visits", 0)
        collection_trend = priority_ctx.get("collection_trend", "no_basis")
        priority = priority_ctx.get("priority", "low")

        reasons = []
        risk = "low"
        action = "allow"
        collection_first = False

        if aging_90_plus > 0:
            risk = "critical"
            action = "block"
            collection_first = True
            reasons.append("90+ aging outstanding")
        elif aging_61_90 > 0:
            risk = "high"
            action = "supervisor"
            collection_first = True
            reasons.append("61-90 aging outstanding")
        elif aging_31_60 > 0:
            risk = "medium"
            action = "warning"
            reasons.append("31-60 aging present")

        if overdue_promises > 0:
            collection_first = True
            if overdue_promises >= 2:
                reasons.append("multiple overdue promises")
            else:
                reasons.append("overdue promise")
            if risk == "low":
                risk = "high"
                action = "supervisor"
            elif risk == "medium":
                risk = "high"
                action = "supervisor"

        if priority == "critical":
            collection_first = True
            if risk != "critical":
                risk = "critical"
            if action != "block":
                action = "block"
            reasons.append("critical collection priority")
        elif priority == "high":
            collection_first = True
            if risk == "low":
                risk = "high"
                action = "supervisor"
            elif risk == "medium":
                risk = "high"
                action = "supervisor"
            reasons.append("high collection priority")
        elif priority == "medium" and risk == "low":
            risk = "medium"
            action = "warning"
            reasons.append("medium collection priority")

        if collection_trend == "weak":
            collection_first = True
            if risk in ("low", "medium"):
                risk = "high"
                if action == "allow":
                    action = "supervisor"
            reasons.append("weak collection trend")
        elif collection_trend == "warning" and risk == "low":
            risk = "medium"
            action = "warning"
            reasons.append("warning collection trend")

        if current_due >= max(sales_average * 3.0, 5000.0):
            if risk != "critical":
                if risk in ("low", "medium"):
                    risk = "high"
            if action == "allow":
                action = "warning"
            reasons.append("very high due outstanding")
        elif current_due >= max(sales_average * 1.5, 1500.0) and risk == "low":
            risk = "medium"
            action = "warning"
            reasons.append("high due outstanding")

        if open_promises >= 3 and action == "allow":
            action = "warning"
            reasons.append("many open promises")

        if unpaid_visits >= 5 and action in ("allow", "warning"):
            action = "supervisor"
            reasons.append("many unpaid visits")

        if not reasons:
            reasons.append("healthy debt profile")

        # normalize risk/action combinations
        if risk == "critical":
            action = "block"
            collection_first = True
        elif risk == "high" and action == "allow":
            action = "supervisor"
        elif risk == "medium" and action == "allow":
            action = "warning"

        return {
            "risk": risk,
            "action": action,
            "collection_first": collection_first,
            "reason": ", ".join(reasons[:4]),
            "aging_0_30": aging_0_30,
            "aging_31_60": aging_31_60,
            "aging_61_90": aging_61_90,
            "aging_90_plus": aging_90_plus,
        }

    def _get_collection_priority_value(self, outlet):
        return self._get_collection_priority_context(outlet)["priority"]

    def _get_recommended_visit_mode_value(self, outlet, collection_priority):
        if not outlet:
            return "regular"

        refill_needed_count = getattr(outlet, "refill_needed_count", 0) or 0
        open_shortage_count = getattr(outlet, "open_shortage_count", 0) or 0
        near_expiry_count = getattr(outlet, "near_expiry_product_count", 0) or 0
        expired_count = getattr(outlet, "expired_product_count", 0) or 0

        if collection_priority in ("high", "critical"):
            return "collection_first"
        if refill_needed_count > 0 or open_shortage_count > 0:
            return "refill_first"
        if near_expiry_count > 0 or expired_count > 0:
            return "audit_only"
        return "regular"

    def _get_visit_planning_context(self, rec, outlet, priority_ctx, debt_policy_ctx):
        if not outlet:
            return {
                "frequency": "weekly",
                "health_score": 50,
                "health_status": "attention",
                "regularity_days": 0,
                "regularity_status": "unknown",
                "reason": "No outlet linked",
            }

        current_due = getattr(outlet, "current_due_amount", 0.0) or 0.0
        sales_average = getattr(outlet, "sales_last_3_months_average", 0.0) or 0.0
        open_shortages = getattr(outlet, "open_shortage_count", 0) or 0
        near_expiry = getattr(outlet, "near_expiry_product_count", 0) or 0
        refill_needed = getattr(outlet, "refill_needed_count", 0) or 0
        collection_trend = getattr(outlet, "collection_status", "no_basis") or "no_basis"
        summary_alert = getattr(outlet, "summary_alert_level", "normal") or "normal"
        last_visit_date = getattr(outlet, "last_visit_date", False)

        slow_count = rec.slow_moving_line_count or 0
        very_slow_count = rec.very_slow_line_count or 0
        no_history_count = rec.no_sale_history_line_count or 0

        score = 100
        reasons = []

        risk = debt_policy_ctx.get("risk", "low")
        priority = priority_ctx.get("priority", "low")

        risk_penalty = {"low": 0, "medium": 12, "high": 25, "critical": 40}
        priority_penalty = {"low": 0, "medium": 8, "high": 18, "critical": 28}
        score -= risk_penalty.get(risk, 0)
        score -= priority_penalty.get(priority, 0)
        if risk_penalty.get(risk, 0):
            reasons.append(f"debt risk {risk}")
        if priority_penalty.get(priority, 0):
            reasons.append(f"collection priority {priority}")

        if open_shortages:
            score -= min(open_shortages * 5, 15)
            reasons.append("open shortages")
        if near_expiry:
            score -= min(near_expiry * 4, 12)
            reasons.append("near expiry")
        if refill_needed:
            score -= min(refill_needed * 3, 12)
            reasons.append("refill needed")
        if slow_count:
            score -= min(slow_count * 4, 12)
            reasons.append("slow moving lines")
        if very_slow_count:
            score -= min(very_slow_count * 6, 18)
            reasons.append("very slow lines")
        if no_history_count:
            score -= min(no_history_count * 2, 8)
            reasons.append("no sale history")

        if collection_trend == "weak":
            score -= 12
            reasons.append("weak collection trend")
        elif collection_trend == "warning":
            score -= 6
            reasons.append("warning collection trend")

        if current_due >= max(sales_average * 3.0, 5000.0):
            score -= 12
            reasons.append("very high outstanding")
        elif current_due >= max(sales_average * 1.5, 1500.0):
            score -= 6
            reasons.append("high outstanding")

        regularity_days = 0
        if last_visit_date:
            try:
                regularity_days = max((fields.Date.context_today(rec) - last_visit_date).days, 0)
            except Exception:
                regularity_days = 0

        if summary_alert == "critical" or risk == "critical" or priority == "critical":
            frequency = "daily"
        elif debt_policy_ctx.get("collection_first") or open_shortages >= 2 or refill_needed >= 2:
            frequency = "every_2_days"
        elif near_expiry > 0 or slow_count > 0 or very_slow_count > 0 or priority == "medium" or risk == "medium":
            frequency = "twice_weekly"
        elif current_due <= 0 and open_shortages == 0 and refill_needed == 0 and sales_average < 500:
            frequency = "on_demand"
        else:
            frequency = "weekly"

        thresholds = {
            "daily": (1, 3),
            "every_2_days": (2, 5),
            "twice_weekly": (4, 8),
            "weekly": (7, 14),
            "on_demand": (14, 30),
        }
        on_track_limit, overdue_limit = thresholds.get(frequency, (7, 14))
        if not last_visit_date:
            regularity_status = "unknown"
        elif regularity_days <= on_track_limit:
            regularity_status = "on_track"
        elif regularity_days <= overdue_limit:
            regularity_status = "follow_up"
        else:
            regularity_status = "overdue"
            reasons.append("visit overdue")

        score = max(min(int(round(score)), 100), 0)
        if score >= 75:
            health_status = "healthy"
        elif score >= 45:
            health_status = "attention"
        else:
            health_status = "critical"

        if not reasons:
            reasons.append("healthy operating profile")

        return {
            "frequency": frequency,
            "health_score": score,
            "health_status": health_status,
            "regularity_days": regularity_days,
            "regularity_status": regularity_status,
            "reason": ", ".join(reasons[:4]),
        }

    def _build_visit_command_flags_html(self, outlet, collection_priority, open_shortages, near_expiry, pending_decisions, debt_policy_ctx=None, planning_ctx=None):
        def _badge(label, style):
            return (
                '<span style="display:inline-flex;align-items:center;white-space:nowrap;'
                'margin:0 6px 6px 0;padding:4px 10px;border-radius:999px;'
                'font-weight:600;font-size:13px;line-height:1.35;%s">%s</span>'
            ) % (style, label)

        badges = []
        alert_level = getattr(outlet, "summary_alert_level", "normal") if outlet else "normal"

        promise_metrics = self._get_outlet_collection_promise_metrics(outlet) if outlet else {"open_promises": 0, "overdue_promises": 0}
        debt_policy_ctx = debt_policy_ctx or self._get_debt_policy_context(outlet)

        if collection_priority == "critical":
            badges.append(_badge("Critical Debt", "background:#f8d7da;color:#b02a37;"))
        elif collection_priority == "high":
            badges.append(_badge("Collect First", "background:#fde2e4;color:#b02a37;"))
        elif collection_priority == "medium":
            badges.append(_badge("Collection Follow-up", "background:#fff3cd;color:#8a6d1d;"))

        if promise_metrics.get("overdue_promises", 0) > 0:
            badges.append(_badge("Overdue Promise", "background:#fde2e4;color:#b02a37;"))
        elif promise_metrics.get("open_promises", 0) > 0:
            badges.append(_badge("Open Promise", "background:#e2f0ff;color:#1d4ed8;"))

        if (debt_policy_ctx.get("aging_90_plus", 0.0) or 0.0) > 0:
            badges.append(_badge("90+ Aging", "background:#fde2e4;color:#b02a37;"))
        elif (debt_policy_ctx.get("aging_61_90", 0.0) or 0.0) > 0:
            badges.append(_badge("61-90 Aging", "background:#fff3cd;color:#8a6d1d;"))
        elif (debt_policy_ctx.get("aging_31_60", 0.0) or 0.0) > 0:
            badges.append(_badge("31-60 Aging", "background:#fff3cd;color:#8a6d1d;"))

        action = debt_policy_ctx.get("action")
        if action == "block":
            badges.append(_badge("Block Refill", "background:#fde2e4;color:#b02a37;"))
        elif action == "supervisor":
            badges.append(_badge("Supervisor Approval", "background:#ffe5d0;color:#b54708;"))
        elif action == "warning":
            badges.append(_badge("Refill Warning", "background:#fff3cd;color:#8a6d1d;"))

        if debt_policy_ctx.get("collection_first") and collection_priority not in ("critical", "high"):
            badges.append(_badge("Collection First", "background:#fde2e4;color:#b02a37;"))

        if open_shortages > 0:
            badges.append(_badge("Open Shortages", "background:#e2e3ff;color:#3d3d9b;"))

        if near_expiry > 0:
            badges.append(_badge("Near Expiry Risk", "background:#f6e7b0;color:#8a6d1d;"))

        if pending_decisions > 0:
            badges.append(_badge("Pending Expiry Decision", "background:#ffe5d0;color:#b54708;"))

        if alert_level == "critical":
            badges.append(_badge("Visit Now", "background:#f8d7da;color:#b02a37;"))
        elif alert_level == "warning":
            badges.append(_badge("Needs Follow-up", "background:#fff3cd;color:#8a6d1d;"))

        if planning_ctx:
            if planning_ctx.get("health_status") == "critical":
                badges.append(_badge("Critical Outlet", "background:#f8d7da;color:#b02a37;"))
            elif planning_ctx.get("health_status") == "attention":
                badges.append(_badge("Needs Attention", "background:#fff3cd;color:#8a6d1d;"))

            freq = planning_ctx.get("frequency")
            if freq == "daily":
                badges.append(_badge("Daily Route", "background:#e2f0ff;color:#1d4ed8;"))
            elif freq == "every_2_days":
                badges.append(_badge("Every 2 Days", "background:#e2f0ff;color:#1d4ed8;"))
            elif freq == "twice_weekly":
                badges.append(_badge("Twice Weekly", "background:#e2f0ff;color:#1d4ed8;"))

        if not badges:
            badges.append(_badge("Normal", "background:#d1f7d6;color:#1e7e34;"))

        return "".join(badges)

    @api.depends(
        "outlet_id",
        "outlet_id.current_due_amount",
        "outlet_id.open_shortage_count",
        "outlet_id.near_expiry_product_count",
        "outlet_id.summary_alert_level",
        "outlet_id.aging_0_30_amount",
        "outlet_id.aging_31_60_amount",
        "outlet_id.aging_61_90_amount",
        "outlet_id.aging_90_plus_amount",
        "outlet_id.collection_status",
        "outlet_id.unpaid_visit_count",
        "outlet_id.sales_last_3_months_average",
        "outlet_id.deferred_payment_count",
        "outlet_id.refill_needed_count",
        "outlet_id.expired_product_count",
        "outlet_id.last_visit_date",
        "outlet_id.sales_last_3_months_average",
        "line_ids.movement_status",
        "line_ids.days_on_shelf",
        "outlet_id.visit_ids.payment_ids.promise_date",
        "outlet_id.visit_ids.payment_ids.promise_amount",
        "outlet_id.visit_ids.payment_ids.state",
        "pending_near_expiry_line_count",
        "has_pending_near_expiry",
    )
    def _compute_visit_command_header(self):
        for rec in self:
            outlet = rec.outlet_id
            current_due = (getattr(outlet, "current_due_amount", 0.0) or 0.0) if outlet else 0.0
            open_shortages = (getattr(outlet, "open_shortage_count", 0) or 0) if outlet else 0
            near_expiry = (getattr(outlet, "near_expiry_product_count", 0) or 0) if outlet else 0

            priority_ctx = rec._get_collection_priority_context(outlet)
            debt_policy_ctx = rec._get_debt_policy_context(outlet, priority_ctx)
            priority = priority_ctx["priority"]
            recommendation = rec._get_recommended_visit_mode_value(outlet, priority)
            planning_ctx = rec._get_visit_planning_context(rec, outlet, priority_ctx, debt_policy_ctx)

            rec.collection_priority = priority
            rec.collection_priority_score = priority_ctx["score"]
            rec.outlet_open_promise_count = priority_ctx["open_promises"]
            rec.outlet_overdue_promise_count = priority_ctx["overdue_promises"]
            rec.outlet_unpaid_visit_count = priority_ctx["unpaid_visits"]
            rec.collection_trend_status = priority_ctx["collection_trend"]
            rec.collection_priority_reason = priority_ctx["reason"]
            rec.debt_risk_level = debt_policy_ctx["risk"]
            rec.debt_policy_action = debt_policy_ctx["action"]
            rec.collection_first_required = debt_policy_ctx["collection_first"]
            rec.debt_policy_reason = debt_policy_ctx["reason"]
            rec.recommended_visit_frequency = planning_ctx["frequency"]
            rec.outlet_health_score = planning_ctx["health_score"]
            rec.outlet_health_status = planning_ctx["health_status"]
            rec.visit_regularity_days = planning_ctx["regularity_days"]
            rec.visit_regularity_status = planning_ctx["regularity_status"]
            rec.visit_planning_reason = planning_ctx["reason"]
            rec.outlet_aging_0_30_amount = debt_policy_ctx["aging_0_30"]
            rec.outlet_aging_31_60_amount = debt_policy_ctx["aging_31_60"]
            rec.outlet_aging_61_90_amount = debt_policy_ctx["aging_61_90"]
            rec.outlet_aging_90_plus_amount = debt_policy_ctx["aging_90_plus"]
            rec.visit_mode_recommendation = recommendation
            rec.outlet_current_due_amount = current_due
            rec.outlet_open_shortage_count = open_shortages
            rec.outlet_near_expiry_count = near_expiry
            rec.outlet_summary_alert_level = getattr(outlet, "summary_alert_level", "normal") if outlet else "normal"
            rec.outlet_decision_flags_html = rec._build_visit_command_flags_html(
                outlet,
                priority,
                open_shortages,
                near_expiry,
                rec.pending_near_expiry_line_count or 0,
                debt_policy_ctx,
                planning_ctx,
            )

    @api.depends("sale_order_id")
    @api.depends(
        "line_ids.movement_status",
        "line_ids.days_on_shelf",
        "line_ids.product_id",
    )
    def _compute_slow_moving_snapshot(self):
        for rec in self:
            lines = rec.line_ids.filtered(lambda l: l.product_id)
            slow_lines = lines.filtered(lambda l: l.movement_status == "slow")
            very_slow_lines = lines.filtered(lambda l: l.movement_status == "very_slow")
            no_history_lines = lines.filtered(lambda l: l.movement_status == "no_sale_history")
            shelf_days = [l.days_on_shelf for l in lines if (l.days_on_shelf or 0) > 0]

            rec.slow_moving_line_count = len(slow_lines)
            rec.very_slow_line_count = len(very_slow_lines)
            rec.no_sale_history_line_count = len(no_history_lines)
            rec.average_days_on_shelf = round(sum(shelf_days) / len(shelf_days), 1) if shelf_days else 0.0
            rec.oldest_days_on_shelf = max(shelf_days) if shelf_days else 0

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

    @api.depends("name")
    def _compute_direct_stop_order_ids(self):
        SaleOrder = self.env["sale.order"]
        empty_orders = SaleOrder.browse()
        names = [name for name in self.mapped("name") if name]
        orders_by_origin = {}
        if names:
            for order in SaleOrder.search([("route_order_mode", "=", "direct_sale"), ("origin", "in", names)]):
                orders_by_origin.setdefault(order.origin, empty_orders)
                orders_by_origin[order.origin] |= order
        for rec in self:
            rec.direct_stop_order_ids = orders_by_origin.get(rec.name, empty_orders)

    def _get_direct_stop_previous_due_visits(self):
        self.ensure_one()
        Visit = self.env["route.visit"]
        if not self.outlet_id:
            return Visit
        visits = Visit.search(
            [
                ("outlet_id", "=", self.outlet_id.id),
                ("id", "!=", self.id or 0),
                ("state", "!=", "cancel"),
            ],
            order="date asc, id asc",
        )
        return visits.filtered(
            lambda v: getattr(v, "visit_execution_mode", False) == "direct_sales"
            and (v.remaining_due_amount or 0.0) > 0.0
        )

    def _get_direct_stop_settlement_payments(self, states=None):
        self.ensure_one()
        Payment = self.env["route.visit.payment"]
        if not self.id:
            return Payment
        domain = [
            "|",
            ("settlement_visit_id", "=", self.id),
            ("visit_id", "=", self.id),
        ]
        if states:
            domain.append(("state", "in", states))
        payments = Payment.search(domain, order="payment_date asc, id asc")
        return payments.filtered(
            lambda p: (p.settlement_visit_id and p.settlement_visit_id.id == self.id)
            or (p.visit_id and p.visit_id.id == self.id and not p.settlement_visit_id)
        )

    def _get_direct_stop_settlement_cash_amount(self, states=None):
        self.ensure_one()
        payments = self._get_direct_stop_settlement_payments(states=states)
        return sum(payments.mapped("amount")) if payments else 0.0

    def _get_direct_stop_settlement_resolved_amount(self, states=None):
        self.ensure_one()
        payments = self._get_direct_stop_settlement_payments(states=states)
        resolved_amount = 0.0
        for payment in payments:
            resolved_amount += payment.amount or 0.0
            if (payment.promise_amount or 0.0) > 0.0:
                resolved_amount += payment.promise_amount or 0.0
        return resolved_amount

    def _get_direct_stop_active_returns(self):
        self.ensure_one()
        DirectReturn = self.env["route.direct.return"]
        if not self.outlet_id:
            return DirectReturn
        returns = DirectReturn.search(
            [
                ("outlet_id", "=", self.outlet_id.id),
                ("state", "!=", "cancel"),
            ],
            order="id desc",
        )
        if self.user_id:
            returns = returns.filtered(lambda r: r.user_id == self.user_id)
        sale_orders = self.direct_stop_order_ids
        return returns.filtered(
            lambda r: (r.visit_id and r.visit_id.id == self.id)
            or (r.sale_order_id and r.sale_order_id in sale_orders)
            or (self.name and self.name in (r.note or ""))
        )

    @api.depends(
        "visit_execution_mode",
        "direct_stop_skip_sale",
        "direct_stop_skip_return",
        "direct_stop_credit_policy",
        "direct_stop_order_ids.state",
        "direct_stop_order_ids.amount_total",
        "direct_stop_return_ids.state",
        "direct_stop_return_ids.amount_total",
        "payment_ids.state",
        "payment_ids.amount",
        "settlement_payment_ids.state",
        "settlement_payment_ids.amount",
        "settlement_payment_ids.promise_amount",
    )
    def _compute_direct_stop_summary(self):
        for rec in self:
            orders = rec.direct_stop_order_ids.filtered(lambda o: o.state not in ("cancel",)) if rec.direct_stop_order_ids else rec.direct_stop_order_ids
            active_returns = rec._get_direct_stop_active_returns() if rec.id else self.env["route.direct.return"]
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
            confirmed_cash_amount = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0
            confirmed_resolved_amount = 0.0
            if rec.id:
                confirmed_resolved_amount = rec._get_direct_stop_settlement_resolved_amount(states=["confirmed"])
            rec.direct_stop_settlement_paid_amount = confirmed_cash_amount
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
        "settlement_payment_ids.state",
        "settlement_payment_ids.payment_date",
        "settlement_payment_ids.promise_date",
        "settlement_payment_ids.promise_amount",
        "settlement_payment_ids.amount",
    )
    def _compute_display_payment_ids(self):
        Payment = self.env["route.visit.payment"]
        for rec in self:
            if rec.visit_execution_mode == "direct_sales":
                payments = rec._get_direct_stop_settlement_payments() if rec.id else Payment
                rec.display_payment_ids = payments.filtered(lambda p: p.state != "cancelled")
            else:
                rec.display_payment_ids = rec.payment_ids.filtered(lambda p: p.state != "cancelled")

    def _compute_payment_totals(self):
        Payment = self.env["route.visit.payment"]
        for rec in self:
            if rec.visit_execution_mode == "direct_sales":
                net_due = rec.direct_stop_grand_due_amount or 0.0
                confirmed_payments = rec._get_direct_stop_settlement_payments(states=["confirmed"]) if rec.id else Payment
                total_collected = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0
                resolved_amount = rec._get_direct_stop_settlement_resolved_amount(states=["confirmed"]) if rec.id else 0.0
                remaining_amount = max((net_due or 0.0) - (resolved_amount or 0.0), 0.0)
            else:
                total_sales = 0.0
                for line in rec.line_ids:
                    sold_qty = getattr(line, "sold_qty", 0.0) or 0.0
                    unit_price = getattr(line, "unit_price", 0.0) or 0.0
                    total_sales += sold_qty * unit_price
                net_due = total_sales
                confirmed_payments = rec.payment_ids.filtered(lambda p: p.state == "confirmed") if rec.payment_ids else rec.payment_ids
                total_collected = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0
                remaining_amount = max((net_due or 0.0) - (total_collected or 0.0), 0.0)

            rec.net_due_amount = net_due
            rec.collected_amount = total_collected
            rec.remaining_due_amount = remaining_amount


    @api.depends(
        "payment_ids.promise_date",
        "payment_ids.promise_amount",
        "payment_ids.promise_status",
        "payment_ids.state",
        "payment_ids.payment_date",
    )
    def _compute_promise_to_pay_summary(self):
        today = fields.Date.context_today(self)
        Payment = self.env["route.visit.payment"]
        for rec in self:
            if rec.visit_execution_mode == "direct_sales":
                promise_payments = rec._get_direct_stop_settlement_payments(states=["draft", "confirmed"]) if rec.id else Payment
                promise_payments = promise_payments.filtered(
                    lambda p: p.state != "cancelled" and (p.promise_amount or 0.0) > 0.0
                )

                def _local_promise_status(payment):
                    if payment.promise_date and payment.promise_date < today:
                        return "overdue"
                    if payment.promise_date and payment.promise_date == today:
                        return "due_today"
                    return "open"

                open_promises = promise_payments.filtered(lambda p: _local_promise_status(p) in ("open", "due_today", "overdue"))

                next_promise = False
                if open_promises:
                    next_promise = open_promises.sorted(
                        key=lambda p: (
                            p.promise_date or fields.Date.to_date("9999-12-31"),
                            p.payment_date or fields.Datetime.to_datetime("1900-01-01 00:00:00"),
                            p.id or 0,
                        )
                    )[0]

                latest = False
                if promise_payments:
                    latest = promise_payments.sorted(
                        key=lambda p: (
                            p.payment_date or fields.Datetime.to_datetime("1900-01-01 00:00:00"),
                            p.id or 0,
                        ),
                        reverse=True,
                    )[0]

                rec.promise_to_pay_count = len(open_promises)
                rec.next_promise_to_pay_date = next_promise.promise_date if next_promise else False
                rec.latest_promise_to_pay_date = latest.promise_date if latest else False
                rec.latest_promise_to_pay_amount = latest.promise_amount if latest else 0.0
                rec.latest_promise_status = _local_promise_status(latest) if latest else False
                continue

            promise_payments = rec.payment_ids.filtered(
                lambda p: p.state != "cancelled" and (p.promise_amount or 0.0) > 0.0
            )
            open_promises = promise_payments.filtered(
                lambda p: p.promise_status in ("open", "due_today", "overdue")
            )

            next_promise = False
            if open_promises:
                next_promise = open_promises.sorted(
                    key=lambda p: (
                        p.promise_date or fields.Date.to_date("9999-12-31"),
                        p.payment_date or fields.Datetime.to_datetime("1900-01-01 00:00:00"),
                        p.id or 0,
                    )
                )[0]

            latest = False
            if promise_payments:
                latest = promise_payments.sorted(
                    key=lambda p: (
                        p.payment_date or fields.Datetime.to_datetime("1900-01-01 00:00:00"),
                        p.id or 0,
                    ),
                    reverse=True,
                )[0]

            rec.promise_to_pay_count = len(open_promises)
            rec.next_promise_to_pay_date = next_promise.promise_date if next_promise else False
            rec.latest_promise_to_pay_date = latest.promise_date if latest else False
            rec.latest_promise_to_pay_amount = latest.promise_amount if latest else 0.0
            rec.latest_promise_status = latest.promise_status if latest else False

    def _compute_refill_picking_count(self):
        for rec in self:
            rec.refill_picking_count = 1 if rec.refill_picking_id else 0

    def _compute_return_picking_count(self):
        for rec in self:
            rec.return_picking_count = len(rec.return_picking_ids)

    @api.depends(
        "line_ids.is_near_expiry",
        "line_ids.near_expiry_action_state",
    )
    def _compute_near_expiry_status(self):
        for rec in self:
            near_lines = rec.line_ids.filtered(lambda l: l.is_near_expiry)
            pending_lines = near_lines.filtered(
                lambda l: l.near_expiry_action_state == "pending"
            )

            rec.near_expiry_line_count = len(near_lines)
            rec.pending_near_expiry_line_count = len(pending_lines)
            rec.has_pending_near_expiry = bool(pending_lines)

    def _get_outlet_commission_rate_value(self, outlet):
        if not outlet:
            return 0.0

        if "commission_rate" in outlet._fields:
            return outlet.commission_rate or 0.0

        if "default_commission_rate" in outlet._fields:
            return outlet.default_commission_rate or 0.0

        return 0.0

    @api.onchange("outlet_id")
    def _onchange_outlet_id(self):
        for rec in self:
            if rec.outlet_id:
                rec.area_id = rec.outlet_id.area_id
                if rec.outlet_id.partner_id:
                    rec.partner_id = rec.outlet_id.partner_id
                if hasattr(rec.vehicle_id, "stock_location_id") and rec.vehicle_id.stock_location_id:
                    rec.source_location_id = rec.vehicle_id.stock_location_id
                if hasattr(rec.outlet_id, "stock_location_id") and rec.outlet_id.stock_location_id:
                    rec.destination_location_id = rec.outlet_id.stock_location_id

                if "commission_rate" in rec._fields:
                    rec.commission_rate = rec._get_outlet_commission_rate_value(rec.outlet_id)

                recommended_mode = rec._get_recommended_visit_mode_value(
                    rec.outlet_id,
                    rec._get_collection_priority_value(rec.outlet_id),
                )
                if not rec.visit_mode or rec.visit_mode == "regular":
                    rec.visit_mode = recommended_mode

    @api.onchange("vehicle_id")
    def _onchange_vehicle_id_set_source_location(self):
        for rec in self:
            if rec.vehicle_id and hasattr(rec.vehicle_id, "stock_location_id"):
                rec.source_location_id = rec.vehicle_id.stock_location_id

    def _sync_plan_line_state(self):
        plan_lines = self.env["route.plan.line"].search([("visit_id", "in", self.ids)])
        force_pending_line = self.env.context.get("route_visit_force_pending_line")
        for line in plan_lines:
            visit_state = line.visit_id.state
            if visit_state == "done":
                new_state = "visited"
            elif visit_state == "cancel":
                new_state = "skipped"
            elif visit_state == "in_progress":
                new_state = "in_progress"
            elif visit_state == "draft" and line.state == "in_progress" and not force_pending_line:
                new_state = "in_progress"
            else:
                new_state = "pending"

            if line.state != new_state:
                line.write({"state": new_state})

    def _get_plan_line(self):
        self.ensure_one()
        return self.env["route.plan.line"].search([("visit_id", "=", self.id)], limit=1)

    def _ensure_single_active_plan_visit(self):
        for rec in self:
            plan_line = rec._get_plan_line()
            if plan_line and plan_line.plan_id:
                plan_line.plan_id._ensure_single_active_visit(current_line=plan_line)

    def _raise_pending_near_expiry_error(self):
        self.ensure_one()

        pending_lines = self.line_ids.filtered(
            lambda l: l.near_expiry_action_state == "pending"
        )
        if not pending_lines:
            return

        product_names = pending_lines.mapped("product_id.display_name")
        product_lines = "\n- " + "\n- ".join(product_names[:10])

        raise UserError(_(
            "You still have Near Expiry items pending a decision.\n"
            "Please either:\n"
            "- set Return Route = Near Expiry Stock with return quantity, or\n"
            "- mark the line as Keep Near Expiry.\n"
            "\nPending items:%s"
        ) % product_lines)

    def _phase0_notification(self, title, message, notif_type="success", sticky=False):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notif_type,
                "sticky": sticky,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("route_plan_allow_visit_create"):
            raise UserError(
                _(
                    "Route Visits cannot be created manually. "
                    "They must be generated from Route Plan."
                )
            )

        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.visit") or "New"

            outlet_id = vals.get("outlet_id")
            vehicle_id = vals.get("vehicle_id")

            if outlet_id:
                outlet = self.env["route.outlet"].browse(outlet_id)
                if outlet.exists():
                    if not vals.get("area_id") and outlet.area_id:
                        vals["area_id"] = outlet.area_id.id
                    if not vals.get("partner_id") and outlet.partner_id:
                        vals["partner_id"] = outlet.partner_id.id
                    if not vals.get("company_id") and outlet.company_id:
                        vals["company_id"] = outlet.company_id.id
                    if not vals.get("destination_location_id") and hasattr(outlet, "stock_location_id") and outlet.stock_location_id:
                        vals["destination_location_id"] = outlet.stock_location_id.id

                    if "commission_rate" in self._fields and not vals.get("commission_rate"):
                        vals["commission_rate"] = self._get_outlet_commission_rate_value(outlet)

            if vehicle_id:
                vehicle = self.env["route.vehicle"].browse(vehicle_id)
                if vehicle.exists():
                    if not vals.get("source_location_id") and hasattr(vehicle, "stock_location_id") and vehicle.stock_location_id:
                        vals["source_location_id"] = vehicle.stock_location_id.id

            vals.setdefault("company_id", self.env.company.id)
            vals.setdefault("visit_process_state", "draft")
            vals.setdefault("near_expiry_threshold_days", 60)
            vals.setdefault("has_returns", False)
            vals.setdefault("returns_step_done", False)
            vals.setdefault("has_refill", False)
            vals.setdefault("has_pending_refill", False)
            vals.setdefault("no_refill", False)

        records = super().create(vals_list)
        records._sync_plan_line_state()
        return records

    def write(self, vals):
        if self.env.context.get("route_visit_force_write"):
            result = super().write(vals)
            self._sync_plan_line_state()
            return result

        allowed_when_locked = {
            "message_follower_ids",
            "message_partner_ids",
            "message_ids",
            "activity_ids",
            "activity_state",
            "activity_type_id",
            "activity_user_id",
            "activity_date_deadline",
            "message_main_attachment_id",
            "__last_update",
            "write_date",
            "write_uid",
        }

        for rec in self:
            if rec.state in ("done", "cancel"):
                disallowed_keys = set(vals.keys()) - allowed_when_locked
                if disallowed_keys:
                    raise UserError(
                        _(
                            "You cannot modify a visit that is Done or Cancelled. "
                            "Please reset it first if changes are needed."
                        )
                    )

        if vals.get("outlet_id"):
            outlet = self.env["route.outlet"].browse(vals["outlet_id"])
            if outlet.exists():
                if not vals.get("area_id") and outlet.area_id:
                    vals["area_id"] = outlet.area_id.id
                if not vals.get("partner_id") and outlet.partner_id:
                    vals["partner_id"] = outlet.partner_id.id
                if not vals.get("company_id") and outlet.company_id:
                    vals["company_id"] = outlet.company_id.id
                if not vals.get("destination_location_id") and hasattr(outlet, "stock_location_id") and outlet.stock_location_id:
                    vals["destination_location_id"] = outlet.stock_location_id.id

                if "commission_rate" in self._fields and not vals.get("commission_rate"):
                    vals["commission_rate"] = self._get_outlet_commission_rate_value(outlet)

        if vals.get("vehicle_id"):
            vehicle = self.env["route.vehicle"].browse(vals["vehicle_id"])
            if vehicle.exists():
                if not vals.get("source_location_id") and hasattr(vehicle, "stock_location_id") and vehicle.stock_location_id:
                    vals["source_location_id"] = vehicle.stock_location_id.id

        result = super().write(vals)
        self._sync_plan_line_state()
        return result

    def action_recompute_visit_health(self):
        self.ensure_one()
        self._compute_sale_order_count()
        self._compute_payment_totals()
        self._compute_refill_picking_count()
        self._compute_return_picking_count()
        self._compute_near_expiry_status()
        if hasattr(self, "_compute_visit_document_links"):
            self._compute_visit_document_links()
        if hasattr(self, "_compute_ux_workflow"):
            self._compute_ux_workflow()
        self._sync_plan_line_state()
        return self._phase0_notification(
            _("Visit Health Refreshed"),
            _("Visit workflow and financial indicators were refreshed successfully."),
        )

    def action_visit_diagnostics(self):
        self.ensure_one()
        checks = []
        if not self.company_id:
            checks.append(_("Missing company"))
        if not self.outlet_id:
            checks.append(_("Missing outlet"))
        if not self.vehicle_id:
            checks.append(_("Missing vehicle"))
        if not self.source_location_id:
            checks.append(_("Missing source location"))
        if not self.destination_location_id:
            checks.append(_("Missing destination location"))
        if self.has_pending_near_expiry:
            checks.append(_("Pending near expiry decisions: %s") % self.pending_near_expiry_line_count)
        draft_payments = self.payment_ids.filtered(lambda p: p.state == "draft")
        if draft_payments:
            checks.append(_("Draft payments: %s") % len(draft_payments))
        if self.refill_backorder_id:
            checks.append(_("Pending refill backorder exists"))
        if not checks:
            checks.append(_("No immediate diagnostics issues detected."))

        return self._phase0_notification(
            _("Visit Diagnostics"),
            " | ".join(checks),
            notif_type="warning" if len(checks) > 1 or checks[0] != _("No immediate diagnostics issues detected.") else "success",
            sticky=True,
        )

    @api.depends("company_id.route_operation_mode", "company_id.route_enable_direct_sale", "company_id.route_enable_direct_return", "outlet_id.outlet_operation_mode")
    def _compute_visit_execution_mode(self):
        labels = {
            "consignment": _("Consignment Visit"),
            "direct_sales": _("Direct Sales Stop"),
        }
        for rec in self:
            company_mode = rec.company_id.route_operation_mode or "hybrid"
            outlet_mode = rec.outlet_id.outlet_operation_mode or "consignment"
            if company_mode == "consignment":
                execution_mode = "consignment"
            elif company_mode == "direct_sales":
                execution_mode = "direct_sales"
            else:
                execution_mode = "direct_sales" if outlet_mode == "direct_sale" else "consignment"
            rec.visit_execution_mode = execution_mode
            rec.visit_execution_mode_label = labels.get(execution_mode, labels["consignment"])
            rec.route_show_consignment_workflow = execution_mode == "consignment"
            rec.route_show_direct_sales_workflow = execution_mode == "direct_sales"

    def _is_direct_sales_stop(self):
        self.ensure_one()
        return self.visit_execution_mode == "direct_sales"

    def _is_consignment_visit(self):
        self.ensure_one()
        return not self._is_direct_sales_stop()

    def _ensure_direct_sales_stop_allowed(self):
        self.ensure_one()
        if not self.company_id.route_operation_allows_direct_sale():
            raise UserError(_("Direct Sales workflow is disabled because Route Operation Mode is Consignment Route."))
        if not self.company_id.route_enable_direct_sale:
            raise UserError(_("Direct Sale is disabled in Route Settings."))
        if not self._is_direct_sales_stop():
            raise UserError(_("This stop is running under the consignment workflow, not the Direct Sales workflow."))
        if self.outlet_id and self.outlet_id.outlet_operation_mode != "direct_sale":
            raise UserError(_("This outlet is not configured for Direct Sale."))

    def _ensure_direct_return_stop_allowed(self):
        self.ensure_one()
        if not self.company_id.route_enable_direct_return:
            raise UserError(_("Direct Return is disabled in Route Settings."))
        if not self._is_direct_sales_stop():
            raise UserError(_("Direct Return from stop is only available on Direct Sales stops."))

    def _open_direct_sale_order_action(self, outlet=None, create=False):
        self.ensure_one()
        outlet = outlet or self.outlet_id
        vehicle = self.vehicle_id
        source_location = vehicle.stock_location_id if vehicle and getattr(vehicle, "stock_location_id", False) else False
        if create:
            action = {
                "type": "ir.actions.act_window",
                "name": _("Create Direct Sale"),
                "res_model": "sale.order",
                "view_mode": "form",
                "target": "current",
                "context": {
                    "default_route_order_mode": "direct_sale",
                    "default_user_id": self.env.user.id,
                    "default_route_source_location_id": source_location.id if source_location else False,
                    "default_route_payment_mode": "cash",
                    "default_route_outlet_id": outlet.id if outlet else False,
                    "default_partner_id": outlet.partner_id.id if outlet and outlet.partner_id else False,
                },
            }
            view = self.env.ref("route_core.view_sale_order_form_route_direct_sale", raise_if_not_found=False)
            if view:
                action["views"] = [(view.id, "form")]
            return action

        action = {
            "type": "ir.actions.act_window",
            "name": _("Direct Sale Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "domain": [("route_order_mode", "=", "direct_sale"), ("user_id", "=", self.env.user.id), ("route_outlet_id", "=", outlet.id if outlet else False)],
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

    def action_ux_create_direct_sale(self):
        self.ensure_one()
        self._ensure_direct_sales_stop_allowed()
        return self._open_direct_sale_order_action(create=True)

    def action_ux_open_direct_sale_orders(self):
        self.ensure_one()
        self._ensure_direct_sales_stop_allowed()
        return self._open_direct_sale_order_action(create=False)

    def action_ux_open_direct_sale_payments(self):
        self.ensure_one()
        self._ensure_direct_sales_stop_allowed()
        action = self.env.ref("route_core.action_route_direct_sale_payment").read()[0]
        action["name"] = _("Direct Sale Payments")
        action["domain"] = [("salesperson_id", "=", self.env.user.id), ("source_type", "=", "direct_sale"), ("outlet_id", "=", self.outlet_id.id)]
        action["context"] = {"create": 0, "delete": 0, "search_default_filter_my_payments": 1, "search_default_filter_confirmed": 1}
        return action

    def action_ux_create_direct_return(self):
        self.ensure_one()
        self._ensure_direct_return_stop_allowed()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Create Direct Return"),
            "res_model": "route.direct.return",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_user_id": self.env.user.id,
                "default_vehicle_id": self.vehicle_id.id if self.vehicle_id else False,
                "default_outlet_id": self.outlet_id.id if self.outlet_id else False,
            },
        }
        view = self.env.ref("route_core.view_route_direct_return_form", raise_if_not_found=False)
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_start_visit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft visits can be started."))
            if not rec.outlet_id:
                raise UserError(_("Please select an outlet before starting the visit."))
            if not rec.vehicle_id:
                raise UserError(_("Please select a vehicle before starting the visit."))

            rec._ensure_single_active_plan_visit()

            rec.write({
                "state": "in_progress",
                "visit_process_state": "checked_in",
                "start_datetime": fields.Datetime.now(),
                "end_datetime": False,
                "no_sale_reason": False,
                "collection_skip_reason": False,
                "has_returns": False,
                "returns_step_done": False,
                "has_refill": False,
                "has_pending_refill": False,
                "no_refill": False,
                "direct_stop_skip_sale": False,
                "direct_stop_skip_return": False,
                "direct_stop_credit_policy": False,
                "direct_stop_credit_note": False,
                "source_location_id": rec.vehicle_id.stock_location_id.id if rec.vehicle_id and getattr(rec.vehicle_id, "stock_location_id", False) else False,
                "destination_location_id": False if rec._is_direct_sales_stop() else (rec.outlet_id.stock_location_id.id if rec.outlet_id and getattr(rec.outlet_id, "stock_location_id", False) else False),
            })

    def _prepare_sale_order_line_vals(self):
        self.ensure_one()
        line_vals = []

        sale_lines = self.line_ids.filtered(
            lambda l: l.product_id and (l.sold_qty or 0.0) > 0
        )

        for line in sale_lines:
            line_vals.append((0, 0, {
                "product_id": line.product_id.id,
                "name": line.product_id.display_name,
                "product_uom_qty": line.sold_qty,
                "price_unit": line.unit_price or line.product_id.lst_price or 0.0,
            }))

        return line_vals

    def _sync_sale_order_lines(self, sale_order):
        self.ensure_one()

        if sale_order.state not in ("draft", "sent"):
            raise UserError(
                _(
                    "The linked Sale Order is already confirmed. "
                    "Reset or cancel it first if you need to rebuild its lines from the visit."
                )
            )

        line_vals = self._prepare_sale_order_line_vals()
        if not line_vals:
            raise UserError(_("No sold quantities were found to create sale order lines."))

        sale_order.order_line.unlink()
        sale_order.write({"order_line": line_vals})

    def _prepare_sale_order_vals(self):
        self.ensure_one()

        vals = {
            "partner_id": self.partner_id.id,
            "user_id": self.user_id.id,
            "origin": self.name,
            "order_line": self._prepare_sale_order_line_vals(),
        }

        if "company_id" in self.env["sale.order"]._fields:
            vals["company_id"] = self.env.company.id

        return vals

    def _get_sale_order_form_action(self, sale_order):
        action = self.env.ref("sale.action_orders").read()[0]
        action["res_id"] = sale_order.id
        action["views"] = [(self.env.ref("sale.view_order_form").id, "form")]
        action["context"] = dict(self.env.context, default_origin=self.name, route_visit_name=self.name)
        return action

    def _get_linked_route_sale_delivery(self):
        self.ensure_one()
        if not self.sale_order_id:
            return self.env["stock.picking"]

        domain = [
            ("origin", "=", self.sale_order_id.name),
            ("state", "!=", "cancel"),
        ]

        if self.outlet_id and getattr(self.outlet_id, "stock_location_id", False):
            domain.append(("location_id", "=", self.outlet_id.stock_location_id.id))

        return self.env["stock.picking"].search(domain, order="id desc", limit=1)

    def _get_route_sale_delivery_form_action(self, picking):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["res_id"] = picking.id
        action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
        action["context"] = dict(self.env.context, default_origin=self.name, route_visit_name=self.name)
        return action

    def action_create_sale_order(self):
        self.ensure_one()

        if self._is_direct_sales_stop():
            raise UserError(_("Visit-based sale order creation is not available for Direct Sales stops. Use the Direct Sale workflow instead."))

        if self.state != "in_progress":
            raise UserError(_("You can only create a sale order when the visit is in progress."))

        if not self.partner_id:
            raise UserError(_("Please set a customer on the visit before creating a sale order."))

        if not self.line_ids.filtered(lambda l: (l.sold_qty or 0.0) > 0):
            raise UserError(_("There are no sold quantities on this visit to create a sale order."))

        if self.sale_order_id:
            self._sync_sale_order_lines(self.sale_order_id)
            confirm_result = self.sale_order_id.action_confirm()
            if isinstance(confirm_result, dict):
                return confirm_result
            return self._get_sale_order_form_action(self.sale_order_id)

        sale_order = self.env["sale.order"].create(self._prepare_sale_order_vals())
        self.sale_order_id = sale_order.id
        confirm_result = sale_order.action_confirm()
        if isinstance(confirm_result, dict):
            return confirm_result

        return self._get_sale_order_form_action(sale_order)

    def action_view_sale_order(self):
        self.ensure_one()

        if not self.sale_order_id:
            raise UserError(_("There is no sale order linked to this visit."))

        return self._get_sale_order_form_action(self.sale_order_id)

    def action_view_pending_refill(self):
        self.ensure_one()

        if not self.refill_backorder_id:
            raise UserError(_("There is no pending refill for this visit."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Pending Refill"),
            "res_model": "route.refill.backorder",
            "view_mode": "form",
            "res_id": self.refill_backorder_id.id,
            "target": "current",
        }

    def action_ux_view_refill_transfer(self):
        self.ensure_one()

        if not self.refill_picking_id:
            raise UserError(_("There is no refill transfer for this visit."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Refill Transfer"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": self.refill_picking_id.id,
            "target": "current",
        }

    def action_end_visit(self):
        self.ensure_one()

        if self.state != "in_progress":
            raise UserError(_("Only visits in progress can be ended."))

        if self._is_direct_sales_stop():
            self.with_context(route_visit_force_write=True).write({
                "state": "done",
                "visit_process_state": "done",
                "end_datetime": fields.Datetime.now(),
            })
            return True

        self._raise_pending_near_expiry_error()

        if self.sale_order_id and self.sale_order_id.state in ("draft", "sent"):
            raise UserError(
                _(
                    "The linked Sale Order is still not confirmed. "
                    "Please confirm it first or end the visit without sale using the wizard."
                )
            )

        if self.sale_order_id:
            delivery = self._get_linked_route_sale_delivery()
            if delivery and delivery.state != "done":
                return self._get_route_sale_delivery_form_action(delivery)

            if not delivery:
                return self._get_sale_order_form_action(self.sale_order_id)

            self.with_context(route_visit_force_write=True).write({
                "state": "done",
                "visit_process_state": "done",
                "end_datetime": fields.Datetime.now(),
            })
            return True

        return {
            "type": "ir.actions.act_window",
            "name": _("End Visit"),
            "res_model": "route.visit.end.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
            },
        }

    def action_cancel(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(_("You cannot cancel a completed visit."))
            rec.with_context(route_visit_force_write=True).write({
                "state": "cancel",
                "visit_process_state": "cancel",
            })

    def action_reset_to_draft(self):
        for rec in self:
            rec.with_context(route_visit_force_write=True, route_visit_force_pending_line=True).write({
                "state": "draft",
                "visit_process_state": "draft",
                "start_datetime": False,
                "end_datetime": False,
                "sale_order_id": False,
                "no_sale_reason": False,
                "collection_skip_reason": False,
                "has_returns": False,
                "returns_step_done": False,
                "has_refill": False,
                "has_pending_refill": False,
                "no_refill": False,
                "refill_datetime": False,
                "refill_backorder_id": False,
                "refill_picking_id": False,
                "source_location_id": False,
                "destination_location_id": False,
            })

