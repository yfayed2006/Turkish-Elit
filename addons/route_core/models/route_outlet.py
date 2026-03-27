from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteOutlet(models.Model):
    _name = "route.outlet"
    _description = "Route Outlet"
    _order = "name"

    name = fields.Char(string="Outlet Name", required=True)
    code = fields.Char(string="Code", copy=False)
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    area_id = fields.Many2one(
        "route.area",
        string="Area",
        required=True,
        ondelete="restrict",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Related Contact",
        required=False,
        ondelete="restrict",
        help="Main related contact/customer for this outlet.",
    )

    commission_rate = fields.Float(
        string="Commission %",
        required=True,
        default=20.0,
        digits=(16, 2),
        help="Outlet commission percentage used to calculate net due collection.",
    )

    phone = fields.Char(string="Phone")
    mobile = fields.Char(string="Mobile")
    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street 2")
    city = fields.Char(string="City")
    state_id = fields.Many2one("res.country.state", string="State")
    country_id = fields.Many2one("res.country", string="Country")
    zip = fields.Char(string="ZIP")
    note = fields.Text(string="Notes")

    visit_ids = fields.One2many(
        "route.visit",
        "outlet_id",
        string="Visits",
    )
    payment_ids = fields.One2many(
        "route.visit.payment",
        "outlet_id",
        string="Payments",
    )
    shortage_ids = fields.One2many(
        "route.shortage",
        "outlet_id",
        string="Shortages",
    )
    stock_balance_ids = fields.One2many(
        "outlet.stock.balance",
        "outlet_id",
        string="Stock Balances",
    )

    plan_line_ids = fields.One2many(
        "route.plan.line",
        "outlet_id",
        string="Route Plan Lines",
    )

    visit_count = fields.Integer(
        string="Visits Count",
        compute="_compute_visit_stats",
    )
    payment_count = fields.Integer(
        string="Payments Count",
        compute="_compute_payment_stats",
    )
    sale_order_count = fields.Integer(
        string="Sale Orders Count",
        compute="_compute_visit_stats",
    )
    stock_balance_count = fields.Integer(
        string="Stock Items",
        compute="_compute_stock_stats",
    )

    last_visit_id = fields.Many2one(
        "route.visit",
        string="Last Visit",
        compute="_compute_visit_stats",
    )
    last_visit_date = fields.Date(
        string="Last Visit Date",
        compute="_compute_visit_stats",
    )
    in_progress_visit_id = fields.Many2one(
        "route.visit",
        string="Visit In Progress",
        compute="_compute_visit_stats",
    )
    last_sale_order_id = fields.Many2one(
        "sale.order",
        string="Last Sale Order",
        compute="_compute_visit_stats",
    )
    last_no_sale_reason = fields.Text(
        string="Last No Sale Reason",
        compute="_compute_visit_stats",
    )

    current_due_amount = fields.Monetary(
        string="Current Due",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    unpaid_visit_count = fields.Integer(
        string="Unpaid Visits",
        compute="_compute_visit_stats",
    )
    sales_current_month = fields.Monetary(
        string="Current Month Sales",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    sales_previous_month = fields.Monetary(
        string="Previous Month Sales",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    sales_two_months_ago = fields.Monetary(
        string="2 Months Ago Sales",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    sales_last_3_months_total = fields.Monetary(
        string="Last 3 Months Sales",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    deferred_payment_count = fields.Integer(
        string="Deferred Payments",
        compute="_compute_payment_stats",
    )

    last_payment_id = fields.Many2one(
        "route.visit.payment",
        string="Last Payment",
        compute="_compute_payment_stats",
    )
    last_payment_date = fields.Datetime(
        string="Last Payment Date",
        compute="_compute_payment_stats",
    )
    last_payment_amount = fields.Monetary(
        string="Last Payment Amount",
        currency_field="currency_id",
        compute="_compute_payment_stats",
    )

    next_route_plan_id = fields.Many2one(
        "route.plan",
        string="Next Route Plan",
        compute="_compute_plan_stats",
    )
    next_planned_visit_date = fields.Date(
        string="Next Planned Visit",
        compute="_compute_plan_stats",
    )
    open_plan_count = fields.Integer(
        string="Open Route Plans",
        compute="_compute_plan_stats",
    )

    open_shortage_count = fields.Integer(
        string="Open Shortages",
        compute="_compute_shortage_stats",
    )
    planned_shortage_count = fields.Integer(
        string="Planned Shortages",
        compute="_compute_shortage_stats",
    )
    total_shortage_count = fields.Integer(
        string="Total Active Shortages",
        compute="_compute_shortage_stats",
    )
    last_shortage_id = fields.Many2one(
        "route.shortage",
        string="Last Shortage",
        compute="_compute_shortage_stats",
    )

    stock_total_qty = fields.Float(
        string="Total Shelf Qty",
        compute="_compute_stock_stats",
    )
    stock_total_value = fields.Monetary(
        string="Stock Value",
        currency_field="currency_id",
        compute="_compute_stock_stats",
    )
    zero_stock_product_count = fields.Integer(
        string="Zero Stock Items",
        compute="_compute_stock_stats",
    )
    near_expiry_product_count = fields.Integer(
        string="Near Expiry Items",
        compute="_compute_stock_stats",
    )
    expired_product_count = fields.Integer(
        string="Expired Items",
        compute="_compute_stock_stats",
    )
    last_stock_update_at = fields.Datetime(
        string="Last Stock Update",
        compute="_compute_stock_stats",
    )

    summary_alert_level = fields.Selection(
        [
            ("normal", "Normal"),
            ("warning", "Needs Follow-up"),
            ("critical", "Critical"),
        ],
        string="Status",
        compute="_compute_summary_alert_level",
    )

    display_address = fields.Text(
        string="Address",
        compute="_compute_display_address",
    )

    _sql_constraints = [
        ("route_outlet_name_unique", "unique(name)", "Outlet name must be unique."),
        ("route_outlet_code_unique", "unique(code)", "Outlet code must be unique."),
    ]

    @api.depends(
        "visit_ids",
        "visit_ids.date",
        "visit_ids.state",
        "visit_ids.sale_order_id",
        "visit_ids.sale_order_id.amount_total",
        "visit_ids.sale_order_id.amount_untaxed",
        "visit_ids.sale_order_id.date_order",
        "visit_ids.sale_order_id.state",
        "visit_ids.no_sale_reason",
        "visit_ids.payment_ids.amount",
        "visit_ids.payment_ids.state",
        "visit_ids.line_ids.sold_qty",
        "visit_ids.line_ids.unit_price",
        "visit_ids.write_date",
    )
    def _compute_visit_stats(self):
        today = fields.Date.context_today(self)
        for record in self:
            visits = record.visit_ids.sorted(
                key=lambda v: ((v.date or today), v.id),
                reverse=True,
            )
            active_visits = visits.filtered(lambda v: v.state != "cancel")

            record.visit_count = len(visits)
            record.last_visit_id = visits[0] if visits else False
            record.last_visit_date = visits[0].date if visits else False
            record.in_progress_visit_id = next(
                (visit for visit in visits if visit.state == "in_progress"),
                False,
            )

            sale_orders = visits.mapped("sale_order_id").filtered(lambda so: so and so.state != "cancel")
            sale_orders = sale_orders.sorted(
                key=lambda so: ((fields.Datetime.to_datetime(so.date_order) if so.date_order else fields.Datetime.now()), so.id),
                reverse=True,
            )
            record.sale_order_count = len(sale_orders)
            record.last_sale_order_id = sale_orders[:1] if sale_orders else False

            today_date = fields.Date.to_date(today)
            current_month_start = today_date.replace(day=1)
            previous_month_start = current_month_start - relativedelta(months=1)
            two_months_ago_start = current_month_start - relativedelta(months=2)
            next_month_start = current_month_start + relativedelta(months=1)

            monthly_sales = {
                "current": 0.0,
                "previous": 0.0,
                "two_months_ago": 0.0,
            }
            for order in sale_orders:
                order_date = fields.Datetime.to_datetime(order.date_order).date() if order.date_order else False
                if not order_date:
                    order_date = fields.Date.to_date(order.create_date) if order.create_date else False
                amount = order.amount_total or order.amount_untaxed or 0.0
                if not order_date:
                    continue
                if current_month_start <= order_date < next_month_start:
                    monthly_sales["current"] += amount
                elif previous_month_start <= order_date < current_month_start:
                    monthly_sales["previous"] += amount
                elif two_months_ago_start <= order_date < previous_month_start:
                    monthly_sales["two_months_ago"] += amount

            record.sales_current_month = monthly_sales["current"]
            record.sales_previous_month = monthly_sales["previous"]
            record.sales_two_months_ago = monthly_sales["two_months_ago"]
            record.sales_last_3_months_total = sum(monthly_sales.values())

            record.current_due_amount = sum(
                active_visits.filtered(lambda v: (v.remaining_due_amount or 0.0) > 0).mapped("remaining_due_amount")
            )
            record.unpaid_visit_count = len(
                active_visits.filtered(lambda v: (v.remaining_due_amount or 0.0) > 0)
            )

            last_no_sale_visit = next((visit for visit in visits if visit.no_sale_reason), False)
            record.last_no_sale_reason = last_no_sale_visit.no_sale_reason if last_no_sale_visit else False

    @api.depends(
        "payment_ids",
        "payment_ids.payment_date",
        "payment_ids.amount",
        "payment_ids.state",
        "payment_ids.collection_type",
        "payment_ids.visit_id",
        "payment_ids.visit_id.payment_ids.amount",
        "payment_ids.visit_id.payment_ids.state",
        "payment_ids.visit_id.line_ids.sold_qty",
        "payment_ids.visit_id.line_ids.unit_price",
    )
    def _compute_payment_stats(self):
        now = fields.Datetime.now()
        for record in self:
            payments = record.payment_ids.sorted(
                key=lambda p: ((p.payment_date or now), p.id),
                reverse=True,
            )
            confirmed_payments = payments.filtered(lambda p: p.state == "confirmed")
            last_payment = confirmed_payments[:1] if confirmed_payments else False

            record.payment_count = len(payments)
            record.last_payment_id = last_payment
            record.last_payment_date = last_payment.payment_date if last_payment else False
            record.last_payment_amount = last_payment.amount if last_payment else 0.0
            record.deferred_payment_count = len(
                confirmed_payments.filtered(
                    lambda p: p.collection_type in ("defer_date", "next_visit")
                    and p.visit_id
                    and (p.visit_id.remaining_due_amount or 0.0) > 0
                )
            )

    @api.depends("stock_balance_ids", "stock_balance_ids.qty", "stock_balance_ids.unit_price", "stock_balance_ids.last_updated_at", "stock_balance_ids.nearest_expiry_date", "stock_balance_ids.nearest_alert_date")
    def _compute_stock_stats(self):
        today = fields.Date.context_today(self)
        for record in self:
            balances = record.stock_balance_ids
            last_update = balances.sorted(
                key=lambda b: ((b.last_updated_at or fields.Datetime.from_string("1970-01-01 00:00:00")), b.id),
                reverse=True,
            )[:1]

            near_expiry_count = 0
            expired_count = 0
            for balance in balances:
                expiry_date = balance.nearest_expiry_date
                alert_date = balance.nearest_alert_date
                if not expiry_date:
                    continue
                if expiry_date < today:
                    expired_count += 1
                elif alert_date and alert_date <= today:
                    near_expiry_count += 1

            record.stock_balance_count = len(balances)
            record.stock_total_qty = sum(balances.mapped("qty")) if balances else 0.0
            record.stock_total_value = sum((bal.qty or 0.0) * (bal.unit_price or 0.0) for bal in balances)
            record.zero_stock_product_count = len(balances.filtered(lambda b: (b.qty or 0.0) <= 0))
            record.near_expiry_product_count = near_expiry_count
            record.expired_product_count = expired_count
            record.last_stock_update_at = last_update.last_updated_at if last_update else False

    @api.depends("shortage_ids", "shortage_ids.state", "shortage_ids.date")
    def _compute_shortage_stats(self):
        today = fields.Date.context_today(self)
        for record in self:
            shortages = record.shortage_ids.sorted(
                key=lambda s: ((s.date or today), s.id),
                reverse=True,
            )
            record.open_shortage_count = len(shortages.filtered(lambda s: s.state == "open"))
            record.planned_shortage_count = len(shortages.filtered(lambda s: s.state == "planned"))
            record.total_shortage_count = len(shortages.filtered(lambda s: s.state in ["open", "planned"]))
            record.last_shortage_id = shortages[:1] if shortages else False

    @api.depends(
        "plan_line_ids",
        "plan_line_ids.state",
        "plan_line_ids.sequence",
        "plan_line_ids.plan_id",
        "plan_line_ids.plan_id.date",
        "plan_line_ids.plan_id.state",
    )
    def _compute_plan_stats(self):
        PlanLine = self.env["route.plan.line"]
        today = fields.Date.context_today(self)
        for record in self:
            pending_lines = PlanLine.search(
                [
                    ("outlet_id", "=", record.id),
                    ("state", "=", "pending"),
                    ("plan_id.state", "in", ["draft", "in_progress"]),
                ]
            )
            pending_lines = pending_lines.sorted(
                key=lambda line: (
                    line.plan_id.date or fields.Date.to_date("9999-12-31"),
                    line.sequence or 0,
                    line.id,
                )
            )
            future_lines = pending_lines.filtered(
                lambda line: line.plan_id.date and line.plan_id.date >= today
            )
            next_line = (future_lines[:1] or pending_lines[:1]) if pending_lines else False

            record.next_route_plan_id = next_line.plan_id if next_line else False
            record.next_planned_visit_date = next_line.plan_id.date if next_line else False
            record.open_plan_count = len(pending_lines.mapped("plan_id"))

    @api.depends(
        "open_shortage_count",
        "planned_shortage_count",
        "deferred_payment_count",
        "near_expiry_product_count",
        "expired_product_count",
    )
    def _compute_summary_alert_level(self):
        for record in self:
            if record.expired_product_count > 0 or record.open_shortage_count > 0:
                record.summary_alert_level = "critical"
            elif (
                record.near_expiry_product_count > 0
                or record.planned_shortage_count > 0
                or record.deferred_payment_count > 0
            ):
                record.summary_alert_level = "warning"
            else:
                record.summary_alert_level = "normal"

    @api.depends("street", "street2", "city", "state_id", "country_id", "zip")
    def _compute_display_address(self):
        for record in self:
            parts = [
                record.street or "",
                record.street2 or "",
                record.city or "",
                record.state_id.name or "",
                record.zip or "",
                record.country_id.name or "",
            ]
            record.display_address = ", ".join([part for part in parts if part])

    @api.constrains("partner_id")
    def _check_partner_company_type(self):
        for record in self:
            if record.partner_id and record.partner_id.company_type == "person":
                raise ValidationError("Related Contact should preferably be a company/customer record.")

    @api.constrains("commission_rate")
    def _check_commission_rate(self):
        for record in self:
            if record.commission_rate < 0 or record.commission_rate > 100:
                raise ValidationError("Commission % must be between 0 and 100.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code("route.outlet") or "/"
            if "commission_rate" not in vals:
                vals["commission_rate"] = 20.0
        return super().create(vals_list)

    def action_view_visits(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["domain"] = [("outlet_id", "=", self.id)]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
            default_area_id=self.area_id.id,
            default_partner_id=self.partner_id.id if self.partner_id else False,
        )
        return action

    def action_view_payments(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_visit_payment").read()[0]
        action["domain"] = [("outlet_id", "=", self.id)]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
            create=0,
        )
        return action

    def action_view_stock_balances(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_outlet_stock_balance").read()[0]
        action["domain"] = [("outlet_id", "=", self.id)]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
        )
        return action

    def action_view_sale_orders(self):
        self.ensure_one()
        sale_orders = self.visit_ids.mapped("sale_order_id").filtered(lambda so: so)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Sale Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
        }
        try:
            action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        except Exception:
            pass

        action["domain"] = [("id", "in", sale_orders.ids)]
        action["context"] = dict(
            self.env.context,
            default_partner_id=self.partner_id.id if self.partner_id else False,
        )
        return action

    def action_view_open_shortages(self):
        self.ensure_one()
        action = self.env.ref("route_core.action_route_shortage").read()[0]
        action["domain"] = [
            ("outlet_id", "=", self.id),
            ("state", "in", ["open", "planned"]),
        ]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
        )
        return action
