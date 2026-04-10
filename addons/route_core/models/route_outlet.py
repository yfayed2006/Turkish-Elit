import calendar
import html
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

    area_id = fields.Many2one(
        "route.area",
        string="Area",
        required=True,
        ondelete="restrict",
    )
    route_country_id = fields.Many2one(
        "res.country",
        string="Route Country",
        index=True,
    )
    route_city_id = fields.Many2one(
        "route.city",
        string="Route City",
        ondelete="restrict",
        index=True,
    )
    route_area_name = fields.Char(
        string="Route Area",
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Related Contact",
        required=False,
        ondelete="restrict",
        help="Main related contact/customer for this outlet.",
    )

    outlet_operation_mode = fields.Selection(
        [
            ("consignment", "Consignment"),
            ("direct_sale", "Direct Sale"),
        ],
        string="Outlet Operation Mode",
        required=True,
        default="consignment",
        help="Consignment = our stock remains under route counting and refill workflow. Direct Sale = outlet buys products directly from us.",
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
    shelf_credit_limit_amount = fields.Monetary(
        string="Shelf Credit Limit",
        currency_field="currency_id",
        default=0.0,
        help="Maximum allowed shelf stock value for this outlet. Refill transfer is blocked if projected shelf value exceeds this amount.",
    )
    remaining_shelf_credit_amount = fields.Monetary(
        string="Remaining Shelf Capacity",
        currency_field="currency_id",
        compute="_compute_remaining_shelf_credit_amount",
    )


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
    return_order_count = fields.Integer(
        string="Return Orders Count",
        compute="_compute_reference_stats",
    )
    transfer_count = fields.Integer(
        string="Transfers Count",
        compute="_compute_reference_stats",
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
    last_return_ref = fields.Char(
        string="Last Return Order",
        compute="_compute_reference_stats",
    )
    last_transfer_ref = fields.Char(
        string="Last Transfer",
        compute="_compute_reference_stats",
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
    sales_last_3_months_average = fields.Monetary(
        string="3 Month Average",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    sales_lifetime_total = fields.Monetary(
        string="Lifetime Sales",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    sales_current_month_label = fields.Char(
        string="Current Month Label",
        compute="_compute_visit_stats",
    )
    sales_previous_month_label = fields.Char(
        string="Previous Month Label",
        compute="_compute_visit_stats",
    )
    sales_two_months_ago_label = fields.Char(
        string="2 Months Ago Label",
        compute="_compute_visit_stats",
    )
    sales_growth_vs_previous_pct = fields.Float(
        string="Growth vs Previous Month %",
        digits=(16, 2),
        compute="_compute_visit_stats",
    )
    sales_previous_growth_pct = fields.Float(
        string="Previous Month Growth %",
        digits=(16, 2),
        compute="_compute_visit_stats",
    )
    sales_trend_status = fields.Selection(
        [
            ("up", "Up"),
            ("flat", "Flat"),
            ("down", "Down"),
        ],
        string="Trend Status",
        compute="_compute_visit_stats",
    )
    sales_growth_vs_previous_display = fields.Char(
        string="Growth vs Previous Month",
        compute="_compute_visit_stats",
    )
    sales_previous_growth_display = fields.Char(
        string="Previous Month Growth",
        compute="_compute_visit_stats",
    )
    collections_current_month = fields.Monetary(
        string="Current Month Collections",
        currency_field="currency_id",
        compute="_compute_payment_stats",
    )
    collections_previous_month = fields.Monetary(
        string="Previous Month Collections",
        currency_field="currency_id",
        compute="_compute_payment_stats",
    )
    collections_two_months_ago = fields.Monetary(
        string="2 Months Ago Collections",
        currency_field="currency_id",
        compute="_compute_payment_stats",
    )
    collections_last_3_months_total = fields.Monetary(
        string="Last 3 Months Collections",
        currency_field="currency_id",
        compute="_compute_payment_stats",
    )
    collections_last_3_months_average = fields.Monetary(
        string="3 Month Collection Average",
        currency_field="currency_id",
        compute="_compute_payment_stats",
    )
    collection_current_rate_display = fields.Char(
        string="Current Month Collection Rate",
        compute="_compute_payment_stats",
    )
    collection_previous_rate_display = fields.Char(
        string="Previous Month Collection Rate",
        compute="_compute_payment_stats",
    )
    collection_two_months_ago_rate_display = fields.Char(
        string="2 Months Ago Collection Rate",
        compute="_compute_payment_stats",
    )
    collection_status = fields.Selection(
        [
            ("good", "Good"),
            ("warning", "Warning"),
            ("weak", "Weak"),
            ("no_basis", "No Basis"),
        ],
        string="Collection Status",
        compute="_compute_payment_stats",
    )
    commission_current_month_amount = fields.Monetary(
        string="Current Month Commission",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    commission_previous_month_amount = fields.Monetary(
        string="Previous Month Commission",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    commission_two_months_ago_amount = fields.Monetary(
        string="2 Months Ago Commission",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    commission_last_3_months_total = fields.Monetary(
        string="Last 3 Months Commission",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    commission_last_3_months_average = fields.Monetary(
        string="3 Month Commission Average",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    commission_lifetime_total = fields.Monetary(
        string="Lifetime Commission",
        currency_field="currency_id",
        compute="_compute_visit_stats",
    )
    commission_current_month_rate_display = fields.Char(
        string="Current Month Commission %",
        compute="_compute_visit_stats",
    )
    commission_previous_month_rate_display = fields.Char(
        string="Previous Month Commission %",
        compute="_compute_visit_stats",
    )
    commission_two_months_ago_rate_display = fields.Char(
        string="2 Months Ago Commission %",
        compute="_compute_visit_stats",
    )
    commission_trend_status = fields.Selection(
        [
            ("up", "Up"),
            ("flat", "Flat"),
            ("down", "Down"),
        ],
        string="Commission Trend Status",
        compute="_compute_visit_stats",
    )
    commission_growth_vs_previous_display = fields.Char(
        string="Commission Growth vs Previous Month",
        compute="_compute_visit_stats",
    )
    commission_previous_growth_display = fields.Char(
        string="Previous Month Commission Growth",
        compute="_compute_visit_stats",
    )
    returns_current_month = fields.Monetary(
        string="Current Month Returns",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    returns_previous_month = fields.Monetary(
        string="Previous Month Returns",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    returns_two_months_ago = fields.Monetary(
        string="2 Months Ago Returns",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    returns_last_3_months_total = fields.Monetary(
        string="Last 3 Months Returns",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    returns_lifetime_total = fields.Monetary(
        string="Lifetime Returns",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    net_current_month = fields.Monetary(
        string="Current Month Net Sales",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    net_previous_month = fields.Monetary(
        string="Previous Month Net Sales",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    net_two_months_ago = fields.Monetary(
        string="2 Months Ago Net Sales",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    net_last_3_months_total = fields.Monetary(
        string="Last 3 Months Net Sales",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    net_lifetime_total = fields.Monetary(
        string="Lifetime Net Sales",
        currency_field="currency_id",
        compute="_compute_profitability_stats",
    )
    aging_0_30_amount = fields.Monetary(
        string="0-30 Days",
        currency_field="currency_id",
        compute="_compute_receivables_stats",
    )
    aging_31_60_amount = fields.Monetary(
        string="31-60 Days",
        currency_field="currency_id",
        compute="_compute_receivables_stats",
    )
    aging_61_90_amount = fields.Monetary(
        string="61-90 Days",
        currency_field="currency_id",
        compute="_compute_receivables_stats",
    )
    aging_90_plus_amount = fields.Monetary(
        string="90+ Days",
        currency_field="currency_id",
        compute="_compute_receivables_stats",
    )
    decision_flags_html = fields.Html(
        string="Decision Flags",
        compute="_compute_decision_flags",
        sanitize=False,
    )
    deferred_payment_count = fields.Integer(
        string="Deferred Payments",
        compute="_compute_payment_stats",
    )
    open_promise_count = fields.Integer(
        string="Open Promises",
        compute="_compute_payment_stats",
    )
    total_collected_amount = fields.Monetary(
        string="Total Collected",
        currency_field="currency_id",
        compute="_compute_payment_stats",
    )
    last_collected_amount = fields.Monetary(
        string="Last Collected Amount",
        currency_field="currency_id",
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

    refill_needed_count = fields.Integer(
        string="Refill Needed Items",
        compute="_compute_top_risk_products",
    )
    top_risk_products_html = fields.Html(
        string="Top Risk Products",
        compute="_compute_top_risk_products",
        sanitize=False,
    )
    top_selling_products_html = fields.Html(
        string="Top 3 Selling Products",
        compute="_compute_top_selling_products",
        sanitize=False,
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

    @staticmethod
    def _month_label(date_value):
        if not date_value:
            return False
        return f"{calendar.month_name[date_value.month]} {date_value.year}"

    @staticmethod
    def _compute_growth_percentage(current_amount, previous_amount):
        current_amount = current_amount or 0.0
        previous_amount = previous_amount or 0.0
        if previous_amount:
            return ((current_amount - previous_amount) / previous_amount) * 100.0
        if current_amount:
            return 100.0
        return 0.0

    @staticmethod
    def _format_growth_display(current_amount, previous_amount):
        current_amount = current_amount or 0.0
        previous_amount = previous_amount or 0.0
        if previous_amount:
            growth = ((current_amount - previous_amount) / previous_amount) * 100.0
            return f"{growth:+.2f}%"
        if current_amount:
            return "New"
        return "Flat"

    @staticmethod
    def _format_collection_rate_display(collections_amount, sales_amount):
        collections_amount = collections_amount or 0.0
        sales_amount = sales_amount or 0.0
        if sales_amount > 0:
            return f"{(collections_amount / sales_amount) * 100.0:.2f}%"
        if collections_amount > 0:
            return "No Sales Basis"
        return "N/A"

    @staticmethod
    def _format_percentage_display(numerator, denominator):
        numerator = numerator or 0.0
        denominator = denominator or 0.0
        if denominator > 0:
            return f"{(numerator / denominator) * 100.0:.2f}%"
        return "N/A"

    @staticmethod
    def _get_collection_status(collections_amount, sales_amount):
        collections_amount = collections_amount or 0.0
        sales_amount = sales_amount or 0.0
        if sales_amount <= 0:
            return "no_basis"
        rate = (collections_amount / sales_amount) * 100.0
        if rate >= 90.0:
            return "good"
        if rate >= 60.0:
            return "warning"
        return "weak"

    @api.depends("shelf_credit_limit_amount", "stock_total_value")
    def _compute_remaining_shelf_credit_amount(self):
        for record in self:
            limit_amount = record.shelf_credit_limit_amount or 0.0
            current_value = record.stock_total_value or 0.0
            remaining_amount = limit_amount - current_value
            record.remaining_shelf_credit_amount = remaining_amount if remaining_amount > 0 else 0.0

    @api.onchange("route_country_id")
    def _onchange_route_country_id(self):
        for rec in self:
            if rec.route_city_id and rec.route_city_id.country_id != rec.route_country_id:
                rec.route_city_id = False
            rec.area_id = False

    @api.onchange("route_city_id")
    def _onchange_route_city_id(self):
        for rec in self:
            if rec.route_city_id:
                rec.route_country_id = rec.route_city_id.country_id
            rec.area_id = False

    @api.onchange("area_id")
    def _onchange_area_id(self):
        for rec in self:
            if rec.area_id:
                rec.route_city_id = rec.area_id.city_id
                rec.route_country_id = rec.area_id.country_id
                rec.route_area_name = rec.area_id.name

    def _prepare_route_area_vals(self, vals):
        country_id = vals.get("route_country_id")
        city_id = vals.get("route_city_id")
        area_name = vals.get("route_area_name")

        if country_id is None:
            country_id = self.route_country_id.id if self else False
        if city_id is None:
            city_id = self.route_city_id.id if self else False
        if area_name is None:
            area_name = self.route_area_name if self else False

        area_name = (area_name or "").strip()

        if not country_id:
            raise ValidationError(_("Please select Route Country first."))
        if not city_id:
            raise ValidationError(_("Please select Route City first."))
        if not area_name:
            raise ValidationError(_("Please enter Route Area name."))

        city = self.env["route.city"].browse(city_id)
        if not city.exists():
            raise ValidationError(_("Selected Route City does not exist."))
        if city.country_id.id != country_id:
            raise ValidationError(_("Selected Route City must belong to the selected Route Country."))

        area = self.env["route.area"].search(
            [
                ("name", "=", area_name),
                ("city_id", "=", city_id),
            ],
            limit=1,
        )
        if not area:
            area = self.env["route.area"].create(
                {
                    "name": area_name,
                    "city_id": city_id,
                    "active": True,
                }
            )
        return area

    def _get_direct_sale_orders(self):
        self.ensure_one()
        return self.env["sale.order"].search([
            ("route_outlet_id", "=", self.id),
            ("route_order_mode", "=", "direct_sale"),
            ("state", "!=", "cancel"),
        ], order="date_order desc, id desc")

    def _get_consignment_transfer_pickings(self):
        self.ensure_one()
        visits = self.visit_ids.filtered(lambda v: v.state != "cancel")
        pickings = (visits.mapped("return_picking_ids") | visits.mapped("refill_picking_id")).filtered(
            lambda p: p and p.state != "cancel" and getattr(p.picking_type_id, "code", False) == "internal"
        )
        return pickings.sorted(key=lambda p: ((p.scheduled_date or p.date_done or p.create_date or fields.Datetime.now()), p.id), reverse=True)

    @api.depends(
        "visit_ids.return_picking_ids",
        "visit_ids.return_picking_ids.name",
        "visit_ids.return_picking_ids.state",
        "visit_ids.refill_picking_id",
        "visit_ids.refill_picking_id.name",
        "visit_ids.refill_picking_id.state",
        "visit_ids.refill_picking_id.scheduled_date",
        "visit_ids.return_picking_ids.scheduled_date",
    )
    def _compute_reference_stats(self):
        direct_return_model = self.env["route.direct.return"]
        for record in self:
            record.return_order_count = 0
            record.transfer_count = 0
            record.last_return_ref = False
            record.last_transfer_ref = False

            if record.outlet_operation_mode == "direct_sale":
                direct_returns = direct_return_model.search([
                    ("outlet_id", "=", record.id),
                    ("state", "!=", "cancel"),
                ], order="return_date desc, id desc")
                record.return_order_count = len(direct_returns)
                record.last_return_ref = direct_returns[:1].name if direct_returns else False
            else:
                pickings = record._get_consignment_transfer_pickings()
                refill_ids = set(record.visit_ids.mapped("refill_picking_id").ids)
                return_pickings = pickings.filtered(lambda p: p.id not in refill_ids)
                record.return_order_count = len(return_pickings)
                record.transfer_count = len(pickings)
                record.last_return_ref = return_pickings[:1].name if return_pickings else False
                record.last_transfer_ref = pickings[:1].name if pickings else False

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
            if record.outlet_operation_mode == "direct_sale":
                sale_orders |= record._get_direct_sale_orders()
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

            current_sales = monthly_sales["current"]
            previous_sales = monthly_sales["previous"]
            two_months_ago_sales = monthly_sales["two_months_ago"]
            total_last_3_months = current_sales + previous_sales + two_months_ago_sales
            sales_lifetime_total = sum((order.amount_total or order.amount_untaxed or 0.0) for order in sale_orders)

            record.sales_current_month = current_sales
            record.sales_previous_month = previous_sales
            record.sales_two_months_ago = two_months_ago_sales
            record.sales_last_3_months_total = total_last_3_months
            record.sales_last_3_months_average = total_last_3_months / 3.0
            record.sales_lifetime_total = sales_lifetime_total
            record.sales_current_month_label = self._month_label(current_month_start)
            record.sales_previous_month_label = self._month_label(previous_month_start)
            record.sales_two_months_ago_label = self._month_label(two_months_ago_start)
            record.sales_growth_vs_previous_pct = self._compute_growth_percentage(current_sales, previous_sales)
            record.sales_previous_growth_pct = self._compute_growth_percentage(previous_sales, two_months_ago_sales)
            record.sales_growth_vs_previous_display = self._format_growth_display(current_sales, previous_sales)
            record.sales_previous_growth_display = self._format_growth_display(previous_sales, two_months_ago_sales)
            if current_sales > previous_sales:
                record.sales_trend_status = "up"
            elif current_sales < previous_sales:
                record.sales_trend_status = "down"
            else:
                record.sales_trend_status = "flat"

            commission_monthly = {
                "current": 0.0,
                "previous": 0.0,
                "two_months_ago": 0.0,
            }
            commission_lifetime_total = 0.0
            outlet_default_rate = (
                record.default_commission_rate
                if "default_commission_rate" in record._fields and record.default_commission_rate
                else record.commission_rate
            ) or 0.0
            for visit in active_visits.filtered(lambda v: v.sale_order_id):
                order = visit.sale_order_id
                visit_date = fields.Datetime.to_datetime(order.date_order).date() if order and order.date_order else False
                if not visit_date:
                    visit_date = visit.date or False
                if not visit_date:
                    visit_date = fields.Date.to_date(order.create_date) if order and order.create_date else False
                if not visit_date:
                    continue
                sale_amount = (order.amount_total or order.amount_untaxed or 0.0) if order else 0.0
                effective_rate = getattr(visit, "commission_rate", 0.0) or outlet_default_rate
                commission_amount = sale_amount * (effective_rate / 100.0)
                commission_lifetime_total += commission_amount
                if current_month_start <= visit_date < next_month_start:
                    commission_monthly["current"] += commission_amount
                elif previous_month_start <= visit_date < current_month_start:
                    commission_monthly["previous"] += commission_amount
                elif two_months_ago_start <= visit_date < previous_month_start:
                    commission_monthly["two_months_ago"] += commission_amount

            current_commission = commission_monthly["current"]
            previous_commission = commission_monthly["previous"]
            two_months_ago_commission = commission_monthly["two_months_ago"]
            total_last_3_months_commission = (
                current_commission + previous_commission + two_months_ago_commission
            )
            record.commission_current_month_amount = current_commission
            record.commission_previous_month_amount = previous_commission
            record.commission_two_months_ago_amount = two_months_ago_commission
            record.commission_last_3_months_total = total_last_3_months_commission
            record.commission_last_3_months_average = total_last_3_months_commission / 3.0
            record.commission_lifetime_total = commission_lifetime_total
            record.commission_current_month_rate_display = self._format_percentage_display(
                current_commission, current_sales
            )
            record.commission_previous_month_rate_display = self._format_percentage_display(
                previous_commission, previous_sales
            )
            record.commission_two_months_ago_rate_display = self._format_percentage_display(
                two_months_ago_commission, two_months_ago_sales
            )
            record.commission_growth_vs_previous_display = self._format_growth_display(
                current_commission, previous_commission
            )
            record.commission_previous_growth_display = self._format_growth_display(
                previous_commission, two_months_ago_commission
            )
            if current_commission > previous_commission:
                record.commission_trend_status = "up"
            elif current_commission < previous_commission:
                record.commission_trend_status = "down"
            else:
                record.commission_trend_status = "flat"

            if record.outlet_operation_mode == "direct_sale":
                direct_sale_orders = record._get_direct_sale_orders()
                record.current_due_amount = sum(direct_sale_orders.mapped("direct_sale_remaining_due"))
                record.unpaid_visit_count = len(direct_sale_orders.filtered(lambda so: (so.direct_sale_remaining_due or 0.0) > 0.0))
            else:
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
        "visit_ids.sale_order_id",
        "visit_ids.sale_order_id.amount_total",
        "visit_ids.sale_order_id.amount_untaxed",
        "visit_ids.sale_order_id.date_order",
        "visit_ids.sale_order_id.state",
    )
    def _compute_payment_stats(self):
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        today_date = fields.Date.to_date(today)
        current_month_start = today_date.replace(day=1)
        previous_month_start = current_month_start - relativedelta(months=1)
        two_months_ago_start = current_month_start - relativedelta(months=2)
        next_month_start = current_month_start + relativedelta(months=1)
        for record in self:
            payments = record.payment_ids.sorted(
                key=lambda p: ((p.payment_date or now), p.id),
                reverse=True,
            )
            confirmed_payments = payments.filtered(lambda p: p.state == "confirmed")
            last_payment = confirmed_payments[:1] if confirmed_payments else False

            last_collected = confirmed_payments.filtered(lambda p: (p.amount or 0.0) > 0.0)[:1]
            open_promises = confirmed_payments.filtered(
                lambda p: (p.collection_type in ("defer_date", "next_visit") or (p.promise_amount or 0.0) > 0.0)
                and (p._get_target_remaining_due(exclude_self=(p.state == "confirmed")) or 0.0) > 0.0
            )

            record.payment_count = len(payments)
            record.last_payment_id = last_payment
            record.last_payment_date = last_payment.payment_date if last_payment else False
            record.last_payment_amount = last_payment.amount if last_payment else 0.0
            record.last_collected_amount = last_collected.amount if last_collected else 0.0
            record.total_collected_amount = sum(confirmed_payments.mapped("amount"))
            record.open_promise_count = len(open_promises)
            record.deferred_payment_count = len(open_promises)

            monthly_collections = {
                "current": 0.0,
                "previous": 0.0,
                "two_months_ago": 0.0,
            }
            for payment in confirmed_payments:
                payment_date = fields.Datetime.to_datetime(payment.payment_date).date() if payment.payment_date else False
                if not payment_date:
                    continue
                amount = payment.amount or 0.0
                if current_month_start <= payment_date < next_month_start:
                    monthly_collections["current"] += amount
                elif previous_month_start <= payment_date < current_month_start:
                    monthly_collections["previous"] += amount
                elif two_months_ago_start <= payment_date < previous_month_start:
                    monthly_collections["two_months_ago"] += amount

            sale_orders = record.visit_ids.mapped("sale_order_id").filtered(lambda so: so and so.state != "cancel")
            monthly_sales = {
                "current": 0.0,
                "previous": 0.0,
                "two_months_ago": 0.0,
            }
            for order in sale_orders:
                order_date = fields.Datetime.to_datetime(order.date_order).date() if order.date_order else False
                if not order_date:
                    order_date = fields.Date.to_date(order.create_date) if order.create_date else False
                if not order_date:
                    continue
                amount = order.amount_total or order.amount_untaxed or 0.0
                if current_month_start <= order_date < next_month_start:
                    monthly_sales["current"] += amount
                elif previous_month_start <= order_date < current_month_start:
                    monthly_sales["previous"] += amount
                elif two_months_ago_start <= order_date < previous_month_start:
                    monthly_sales["two_months_ago"] += amount

            current_collections = monthly_collections["current"]
            previous_collections = monthly_collections["previous"]
            two_months_ago_collections = monthly_collections["two_months_ago"]
            total_last_3_months_collections = (
                current_collections + previous_collections + two_months_ago_collections
            )

            record.collections_current_month = current_collections
            record.collections_previous_month = previous_collections
            record.collections_two_months_ago = two_months_ago_collections
            record.collections_last_3_months_total = total_last_3_months_collections
            record.collections_last_3_months_average = total_last_3_months_collections / 3.0
            record.collection_current_rate_display = self._format_collection_rate_display(
                current_collections, monthly_sales["current"]
            )
            record.collection_previous_rate_display = self._format_collection_rate_display(
                previous_collections, monthly_sales["previous"]
            )
            record.collection_two_months_ago_rate_display = self._format_collection_rate_display(
                two_months_ago_collections, monthly_sales["two_months_ago"]
            )
            record.collection_status = self._get_collection_status(
                current_collections, monthly_sales["current"]
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
        "stock_balance_ids",
        "stock_balance_ids.product_id",
        "stock_balance_ids.qty",
        "stock_balance_ids.lot_names",
        "stock_balance_ids.nearest_expiry_date",
        "stock_balance_ids.nearest_alert_date",
    )
    def _compute_top_risk_products(self):
        today = fields.Date.context_today(self)
        for record in self:
            risky_rows = []
            refill_needed_count = 0
            for balance in record.stock_balance_ids:
                qty = balance.qty or 0.0
                expiry_date = balance.nearest_expiry_date
                alert_date = balance.nearest_alert_date
                status = False
                priority = 0

                if expiry_date and expiry_date < today:
                    status = "Expired"
                    priority = 400
                elif alert_date and alert_date <= today:
                    status = "Near Expiry"
                    priority = 300
                elif qty <= 0:
                    status = "Zero Stock"
                    priority = 250
                elif qty <= 5:
                    status = "Refill Needed"
                    priority = 150

                if qty <= 5:
                    refill_needed_count += 1

                if not status:
                    continue

                risky_rows.append({
                    "product": balance.product_id.display_name or "-",
                    "qty": qty,
                    "lot": balance.lot_names or "-",
                    "expiry": fields.Date.to_string(expiry_date) if expiry_date else "-",
                    "status": status,
                    "priority": priority,
                })

            risky_rows.sort(
                key=lambda row: (
                    -row["priority"],
                    row["expiry"] if row["expiry"] != "-" else "9999-12-31",
                    row["product"],
                )
            )

            record.refill_needed_count = refill_needed_count

            if not risky_rows:
                record.top_risk_products_html = (
                    '<div class="text-muted">No risk products detected for this outlet.</div>'
                )
                continue

            rows_html = []
            for row in risky_rows[:5]:
                status_class = {
                    "Expired": "background:#f8d7da;color:#842029;",
                    "Near Expiry": "background:#fff3cd;color:#664d03;",
                    "Zero Stock": "background:#fde2e4;color:#9b1c31;",
                    "Refill Needed": "background:#e7f1ff;color:#0a58ca;",
                }.get(row["status"], "background:#f8f9fa;color:#495057;")
                rows_html.append(
                    "<tr>"
                    f"<td style='padding:8px 10px; min-width:220px; word-break:break-word;'>{html.escape(row['product'])}</td>"
                    f"<td style='padding:8px 10px; min-width:90px; text-align:right;'>{row['qty']:.2f}</td>"
                    f"<td style='padding:8px 10px; min-width:180px; word-break:break-word;'>{html.escape(row['lot'])}</td>"
                    f"<td style='padding:8px 10px; min-width:120px;'>{html.escape(row['expiry'])}</td>"
                    f"<td style='padding:8px 10px; min-width:130px;'><span style='display:inline-block; padding:2px 8px; border-radius:999px; font-weight:600; {status_class}'>{html.escape(row['status'])}</span></td>"
                    "</tr>"
                )

            record.top_risk_products_html = (
                "<div style='width:100%; overflow-x:auto;'>"
                "<table style='width:100%; border-collapse:collapse; table-layout:auto;'>"
                "<thead><tr>"
                "<th style='text-align:left; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Product</th>"
                "<th style='text-align:right; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Shelf Qty</th>"
                "<th style='text-align:left; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Lot</th>"
                "<th style='text-align:left; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Expiry Date</th>"
                "<th style='text-align:left; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Risk Status</th>"
                "</tr></thead>"
                f"<tbody>{''.join(rows_html)}</tbody>"
                "</table>"
                "</div>"
            )

    def _get_direct_sale_orders(self):
        self.ensure_one()
        return self.env["sale.order"].search([
            ("route_outlet_id", "=", self.id),
            ("route_order_mode", "=", "direct_sale"),
            ("state", "!=", "cancel"),
        ], order="date_order desc, id desc")

    def _get_consignment_transfer_pickings(self):
        self.ensure_one()
        visits = self.visit_ids.filtered(lambda v: v.state != "cancel")
        pickings = (visits.mapped("return_picking_ids") | visits.mapped("refill_picking_id")).filtered(
            lambda p: p and p.state != "cancel" and getattr(p.picking_type_id, "code", False) == "internal"
        )
        return pickings.sorted(key=lambda p: ((p.scheduled_date or p.date_done or p.create_date or fields.Datetime.now()), p.id), reverse=True)

    @api.depends(
        "visit_ids.return_picking_ids",
        "visit_ids.return_picking_ids.name",
        "visit_ids.return_picking_ids.state",
        "visit_ids.refill_picking_id",
        "visit_ids.refill_picking_id.name",
        "visit_ids.refill_picking_id.state",
        "visit_ids.refill_picking_id.scheduled_date",
        "visit_ids.return_picking_ids.scheduled_date",
    )
    def _compute_reference_stats(self):
        direct_return_model = self.env["route.direct.return"]
        for record in self:
            record.return_order_count = 0
            record.transfer_count = 0
            record.last_return_ref = False
            record.last_transfer_ref = False

            if record.outlet_operation_mode == "direct_sale":
                direct_returns = direct_return_model.search([
                    ("outlet_id", "=", record.id),
                    ("state", "!=", "cancel"),
                ], order="return_date desc, id desc")
                record.return_order_count = len(direct_returns)
                record.last_return_ref = direct_returns[:1].name if direct_returns else False
            else:
                pickings = record._get_consignment_transfer_pickings()
                refill_ids = set(record.visit_ids.mapped("refill_picking_id").ids)
                return_pickings = pickings.filtered(lambda p: p.id not in refill_ids)
                record.return_order_count = len(return_pickings)
                record.transfer_count = len(pickings)
                record.last_return_ref = return_pickings[:1].name if return_pickings else False
                record.last_transfer_ref = pickings[:1].name if pickings else False

    @api.depends(
        "visit_ids",
        "visit_ids.date",
        "visit_ids.state",
        "visit_ids.sale_order_id",
        "visit_ids.sale_order_id.state",
        "visit_ids.line_ids",
        "visit_ids.line_ids.product_id",
        "visit_ids.line_ids.sold_qty",
    )
    def _compute_top_selling_products(self):
        today = fields.Date.to_date(fields.Date.context_today(self))
        current_month_start = today.replace(day=1)
        two_months_ago_start = current_month_start - relativedelta(months=2)
        next_month_start = current_month_start + relativedelta(months=1)
        VisitLine = self.env["route.visit.line"]

        for record in self:
            product_totals = {}
            lines = VisitLine.search([
                ("visit_id.outlet_id", "=", record.id),
                ("visit_id.state", "!=", "cancel"),
                ("visit_id.sale_order_id", "!=", False),
                ("visit_id.date", ">=", two_months_ago_start),
                ("visit_id.date", "<", next_month_start),
                ("sold_qty", ">", 0),
            ])

            for line in lines:
                product = line.product_id
                if not product:
                    continue
                bucket = product_totals.setdefault(product.id, {
                    "name": product.display_name or "-",
                    "qty": 0.0,
                    "last_date": False,
                })
                bucket["qty"] += line.sold_qty or 0.0
                visit_date = line.visit_id.date
                if visit_date and (not bucket["last_date"] or visit_date > bucket["last_date"]):
                    bucket["last_date"] = visit_date

            top_rows = sorted(
                product_totals.values(),
                key=lambda row: (-(row["qty"] or 0.0), row["name"]),
            )[:3]

            if not top_rows:
                record.top_selling_products_html = (
                    '<div class="text-muted">No sold products found for the last 3 months.</div>'
                )
                continue

            rows_html = []
            for idx, row in enumerate(top_rows, start=1):
                last_date = fields.Date.to_string(row["last_date"]) if row["last_date"] else "-"
                rows_html.append(
                    "<tr>"
                    f"<td style='padding:8px 10px; width:60px; text-align:center;'>{idx}</td>"
                    f"<td style='padding:8px 10px; min-width:240px; word-break:break-word;'>{html.escape(row['name'])}</td>"
                    f"<td style='padding:8px 10px; width:140px; text-align:right; font-weight:600;'>{row['qty']:.2f}</td>"
                    f"<td style='padding:8px 10px; width:140px;'>{html.escape(last_date)}</td>"
                    "</tr>"
                )

            record.top_selling_products_html = (
                "<div style='width:100%; overflow-x:auto;'>"
                "<table style='width:100%; border-collapse:collapse; table-layout:auto;'>"
                "<thead><tr>"
                "<th style='text-align:center; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Rank</th>"
                "<th style='text-align:left; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Product</th>"
                "<th style='text-align:right; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Sold Qty</th>"
                "<th style='text-align:left; padding:8px 10px; border-bottom:1px solid #dee2e6;'>Last Sold Date</th>"
                "</tr></thead>"
                f"<tbody>{''.join(rows_html)}</tbody>"
                "</table>"
                "</div>"
            )

    def _get_direct_sale_orders(self):
        self.ensure_one()
        return self.env["sale.order"].search([
            ("route_outlet_id", "=", self.id),
            ("route_order_mode", "=", "direct_sale"),
            ("state", "!=", "cancel"),
        ], order="date_order desc, id desc")

    def _get_consignment_transfer_pickings(self):
        self.ensure_one()
        visits = self.visit_ids.filtered(lambda v: v.state != "cancel")
        pickings = (visits.mapped("return_picking_ids") | visits.mapped("refill_picking_id")).filtered(
            lambda p: p and p.state != "cancel" and getattr(p.picking_type_id, "code", False) == "internal"
        )
        return pickings.sorted(key=lambda p: ((p.scheduled_date or p.date_done or p.create_date or fields.Datetime.now()), p.id), reverse=True)

    @api.depends(
        "visit_ids.return_picking_ids",
        "visit_ids.return_picking_ids.name",
        "visit_ids.return_picking_ids.state",
        "visit_ids.refill_picking_id",
        "visit_ids.refill_picking_id.name",
        "visit_ids.refill_picking_id.state",
        "visit_ids.refill_picking_id.scheduled_date",
        "visit_ids.return_picking_ids.scheduled_date",
    )
    def _compute_reference_stats(self):
        direct_return_model = self.env["route.direct.return"]
        for record in self:
            record.return_order_count = 0
            record.transfer_count = 0
            record.last_return_ref = False
            record.last_transfer_ref = False

            if record.outlet_operation_mode == "direct_sale":
                direct_returns = direct_return_model.search([
                    ("outlet_id", "=", record.id),
                    ("state", "!=", "cancel"),
                ], order="return_date desc, id desc")
                record.return_order_count = len(direct_returns)
                record.last_return_ref = direct_returns[:1].name if direct_returns else False
            else:
                pickings = record._get_consignment_transfer_pickings()
                refill_ids = set(record.visit_ids.mapped("refill_picking_id").ids)
                return_pickings = pickings.filtered(lambda p: p.id not in refill_ids)
                record.return_order_count = len(return_pickings)
                record.transfer_count = len(pickings)
                record.last_return_ref = return_pickings[:1].name if return_pickings else False
                record.last_transfer_ref = pickings[:1].name if pickings else False

    @api.depends(
        "visit_ids",
        "visit_ids.date",
        "visit_ids.state",
        "visit_ids.sale_order_id",
        "visit_ids.sale_order_id.amount_total",
        "visit_ids.sale_order_id.amount_untaxed",
        "visit_ids.sale_order_id.date_order",
        "visit_ids.line_ids.return_amount",
        "visit_ids.line_ids.write_date",
        "visit_ids.write_date",
    )
    def _compute_profitability_stats(self):
        today = fields.Date.to_date(fields.Date.context_today(self))
        current_month_start = today.replace(day=1)
        previous_month_start = current_month_start - relativedelta(months=1)
        two_months_ago_start = current_month_start - relativedelta(months=2)
        next_month_start = current_month_start + relativedelta(months=1)

        for record in self:
            monthly_returns = {
                "current": 0.0,
                "previous": 0.0,
                "two_months_ago": 0.0,
            }
            monthly_net = {
                "current": 0.0,
                "previous": 0.0,
                "two_months_ago": 0.0,
            }
            returns_lifetime_total = 0.0
            net_lifetime_total = 0.0
            outlet_default_rate = (
                record.default_commission_rate
                if "default_commission_rate" in record._fields and record.default_commission_rate
                else record.commission_rate
            ) or 0.0

            visits = record.visit_ids.filtered(lambda v: v.state != "cancel" and v.sale_order_id)
            for visit in visits:
                order = visit.sale_order_id
                visit_date = fields.Datetime.to_datetime(order.date_order).date() if order and order.date_order else False
                if not visit_date:
                    visit_date = visit.date or False
                if not visit_date and order and order.create_date:
                    visit_date = fields.Date.to_date(order.create_date)
                if not visit_date:
                    continue

                gross_amount = order.amount_total or order.amount_untaxed or 0.0
                returns_amount = sum((line.return_amount or 0.0) for line in visit.line_ids)
                effective_rate = getattr(visit, "commission_rate", 0.0) or outlet_default_rate
                commission_amount = gross_amount * (effective_rate / 100.0)
                net_amount = gross_amount - returns_amount - commission_amount

                returns_lifetime_total += returns_amount
                net_lifetime_total += net_amount

                if current_month_start <= visit_date < next_month_start:
                    monthly_returns["current"] += returns_amount
                    monthly_net["current"] += net_amount
                elif previous_month_start <= visit_date < current_month_start:
                    monthly_returns["previous"] += returns_amount
                    monthly_net["previous"] += net_amount
                elif two_months_ago_start <= visit_date < previous_month_start:
                    monthly_returns["two_months_ago"] += returns_amount
                    monthly_net["two_months_ago"] += net_amount

            record.returns_current_month = monthly_returns["current"]
            record.returns_previous_month = monthly_returns["previous"]
            record.returns_two_months_ago = monthly_returns["two_months_ago"]
            record.returns_last_3_months_total = sum(monthly_returns.values())
            record.returns_lifetime_total = returns_lifetime_total

            record.net_current_month = monthly_net["current"]
            record.net_previous_month = monthly_net["previous"]
            record.net_two_months_ago = monthly_net["two_months_ago"]
            record.net_last_3_months_total = sum(monthly_net.values())
            record.net_lifetime_total = net_lifetime_total

    def _get_direct_sale_orders(self):
        self.ensure_one()
        return self.env["sale.order"].search([
            ("route_outlet_id", "=", self.id),
            ("route_order_mode", "=", "direct_sale"),
            ("state", "!=", "cancel"),
        ], order="date_order desc, id desc")

    def _get_consignment_transfer_pickings(self):
        self.ensure_one()
        visits = self.visit_ids.filtered(lambda v: v.state != "cancel")
        pickings = (visits.mapped("return_picking_ids") | visits.mapped("refill_picking_id")).filtered(
            lambda p: p and p.state != "cancel" and getattr(p.picking_type_id, "code", False) == "internal"
        )
        return pickings.sorted(key=lambda p: ((p.scheduled_date or p.date_done or p.create_date or fields.Datetime.now()), p.id), reverse=True)

    @api.depends(
        "visit_ids.return_picking_ids",
        "visit_ids.return_picking_ids.name",
        "visit_ids.return_picking_ids.state",
        "visit_ids.refill_picking_id",
        "visit_ids.refill_picking_id.name",
        "visit_ids.refill_picking_id.state",
        "visit_ids.refill_picking_id.scheduled_date",
        "visit_ids.return_picking_ids.scheduled_date",
    )
    def _compute_reference_stats(self):
        direct_return_model = self.env["route.direct.return"]
        for record in self:
            record.return_order_count = 0
            record.transfer_count = 0
            record.last_return_ref = False
            record.last_transfer_ref = False

            if record.outlet_operation_mode == "direct_sale":
                direct_returns = direct_return_model.search([
                    ("outlet_id", "=", record.id),
                    ("state", "!=", "cancel"),
                ], order="return_date desc, id desc")
                record.return_order_count = len(direct_returns)
                record.last_return_ref = direct_returns[:1].name if direct_returns else False
            else:
                pickings = record._get_consignment_transfer_pickings()
                refill_ids = set(record.visit_ids.mapped("refill_picking_id").ids)
                return_pickings = pickings.filtered(lambda p: p.id not in refill_ids)
                record.return_order_count = len(return_pickings)
                record.transfer_count = len(pickings)
                record.last_return_ref = return_pickings[:1].name if return_pickings else False
                record.last_transfer_ref = pickings[:1].name if pickings else False

    @api.depends(
        "visit_ids",
        "visit_ids.date",
        "visit_ids.state",
        "visit_ids.remaining_due_amount",
        "visit_ids.write_date",
    )
    def _compute_receivables_stats(self):
        today = fields.Date.to_date(fields.Date.context_today(self))
        for record in self:
            bucket_0_30 = 0.0
            bucket_31_60 = 0.0
            bucket_61_90 = 0.0
            bucket_90_plus = 0.0

            unpaid_visits = record.visit_ids.filtered(
                lambda v: v.state != "cancel" and (v.remaining_due_amount or 0.0) > 0
            )
            for visit in unpaid_visits:
                base_date = visit.date or False
                if not base_date and visit.sale_order_id and visit.sale_order_id.date_order:
                    base_date = fields.Datetime.to_datetime(visit.sale_order_id.date_order).date()
                if not base_date:
                    base_date = today
                age_days = max((today - base_date).days, 0)
                amount = visit.remaining_due_amount or 0.0
                if age_days <= 30:
                    bucket_0_30 += amount
                elif age_days <= 60:
                    bucket_31_60 += amount
                elif age_days <= 90:
                    bucket_61_90 += amount
                else:
                    bucket_90_plus += amount

            record.aging_0_30_amount = bucket_0_30
            record.aging_31_60_amount = bucket_31_60
            record.aging_61_90_amount = bucket_61_90
            record.aging_90_plus_amount = bucket_90_plus

    @api.depends(
        "summary_alert_level",
        "collection_status",
        "current_due_amount",
        "sales_last_3_months_average",
        "refill_needed_count",
        "near_expiry_product_count",
        "expired_product_count",
        "open_shortage_count",
        "aging_61_90_amount",
        "aging_90_plus_amount",
    )
    def _compute_decision_flags(self):
        for record in self:
            badges = []

            def add_badge(label, style):
                badges.append(
                    f"<span style='display:inline-block; padding:4px 10px; border-radius:999px; font-weight:600; margin:0 8px 8px 0; {style}'>{html.escape(label)}</span>"
                )

            visit_now = (
                record.open_shortage_count > 0
                or record.refill_needed_count > 0
                or record.near_expiry_product_count > 0
                or record.expired_product_count > 0
            )
            collect_first = (
                (record.aging_61_90_amount or 0.0) > 0
                or (record.aging_90_plus_amount or 0.0) > 0
                or record.collection_status == "weak"
            )
            refill_needed = record.refill_needed_count > 0 or record.open_shortage_count > 0
            near_expiry_risk = record.near_expiry_product_count > 0 or record.expired_product_count > 0
            high_debt = (
                (record.current_due_amount or 0.0) > max((record.sales_last_3_months_average or 0.0) * 1.5, 500.0)
            )
            healthy = not any([visit_now, collect_first, refill_needed, near_expiry_risk, high_debt])

            if visit_now:
                add_badge("Visit Now", "background:#fde2e4;color:#9b1c31;")
            if collect_first:
                add_badge("Collect First", "background:#fff3cd;color:#7a5d00;")
            if refill_needed:
                add_badge("Refill Needed", "background:#e7f1ff;color:#0a58ca;")
            if near_expiry_risk:
                add_badge("Near Expiry Risk", "background:#fff3cd;color:#7a5d00;")
            if high_debt:
                add_badge("High Debt", "background:#fde2e4;color:#9b1c31;")
            if healthy:
                add_badge("Healthy Outlet", "background:#d1e7dd;color:#0f5132;")

            aging_summary = (
                f"<div style='margin-top:6px; color:#6c757d;'>Aging: 0-30 = {record.aging_0_30_amount:.2f}, "
                f"31-60 = {record.aging_31_60_amount:.2f}, 61-90 = {record.aging_61_90_amount:.2f}, "
                f"90+ = {record.aging_90_plus_amount:.2f}</div>"
            )
            record.decision_flags_html = (
                "<div style='width:100%;'>" + "".join(badges) + aging_summary + "</div>"
            )

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


    @api.constrains("outlet_operation_mode", "partner_id")
    def _check_direct_sale_partner_required(self):
        for record in self:
            if record.outlet_operation_mode == "direct_sale" and not record.partner_id:
                raise ValidationError(_("Related Contact is required when Outlet Operation Mode is Direct Sale."))

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

    @api.constrains("shelf_credit_limit_amount")
    def _check_shelf_credit_limit_amount(self):
        for record in self:
            if (record.shelf_credit_limit_amount or 0.0) < 0:
                raise ValidationError("Shelf Credit Limit must be zero or greater.")

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
        for vals in vals_list:
            if not vals.get("code"):
                vals["code"] = self.env["ir.sequence"].next_by_code("route.outlet") or "/"
            if "commission_rate" not in vals:
                vals["commission_rate"] = 20.0
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id

            if not vals.get("area_id"):
                outlet = self.env["route.outlet"]
                area = outlet._prepare_route_area_vals(vals)
                vals["area_id"] = area.id
                vals["route_country_id"] = area.country_id.id
                vals["route_city_id"] = area.city_id.id
                vals["route_area_name"] = area.name
            elif vals.get("area_id") and not vals.get("route_area_name"):
                area = self.env["route.area"].browse(vals["area_id"])
                if area.exists():
                    vals.setdefault("route_country_id", area.country_id.id)
                    vals.setdefault("route_city_id", area.city_id.id)
                    vals["route_area_name"] = area.name

        return super().create(vals_list)

    def write(self, vals):
        if "company_id" in self._fields and not vals.get("company_id"):
            missing_company = any(not record.company_id for record in self)
            if missing_company:
                vals = dict(vals, company_id=self.env.company.id)

        geo_keys = {"route_country_id", "route_city_id", "route_area_name"}
        if geo_keys.intersection(vals.keys()) and not vals.get("area_id"):
            for record in self:
                area = record._prepare_route_area_vals(vals)
                item_vals = dict(vals)
                item_vals["area_id"] = area.id
                item_vals["route_country_id"] = area.country_id.id
                item_vals["route_city_id"] = area.city_id.id
                item_vals["route_area_name"] = area.name
                super(RouteOutlet, record).write(item_vals)
            return True

        if vals.get("area_id") and "route_area_name" not in vals:
            area = self.env["route.area"].browse(vals["area_id"])
            if area.exists():
                vals = dict(
                    vals,
                    route_country_id=area.country_id.id,
                    route_city_id=area.city_id.id,
                    route_area_name=area.name,
                )

        return super().write(vals)

    def action_recompute_summary(self):
        self.ensure_one()
        self._compute_visit_stats()
        self._compute_payment_stats()
        self._compute_stock_stats()
        self._compute_shortage_stats()
        self._compute_top_risk_products()
        self._compute_top_selling_products()
        self._compute_summary_alert_level()
        self._compute_display_address()
        return self._phase0_notification(
            _("Outlet Summary Refreshed"),
            _("Outlet summary metrics were refreshed successfully."),
        )

    def action_outlet_diagnostics(self):
        self.ensure_one()
        checks = []
        if not self.company_id:
            checks.append(_("Missing company"))
        if not self.area_id:
            checks.append(_("Missing area"))
        if not self.partner_id:
            checks.append(_("Missing related contact"))
        if hasattr(self, "stock_location_id") and not self.stock_location_id:
            checks.append(_("Missing stock location"))
        if self.in_progress_visit_id:
            checks.append(_("Visit in progress: %s") % self.in_progress_visit_id.display_name)
        if self.open_shortage_count:
            checks.append(_("Open shortages: %s") % self.open_shortage_count)
        if self.near_expiry_product_count:
            checks.append(_("Near expiry products: %s") % self.near_expiry_product_count)
        if self.current_due_amount:
            checks.append(_("Current due: %s") % self.current_due_amount)
        if not checks:
            checks.append(_("No immediate diagnostics issues detected."))

        return self._phase0_notification(
            _("Outlet Diagnostics"),
            " | ".join(checks),
            notif_type="warning" if len(checks) > 1 or checks[0] != _("No immediate diagnostics issues detected.") else "success",
            sticky=True,
        )

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
        sale_orders = self.visit_ids.mapped("sale_order_id").filtered(lambda so: so and so.state != "cancel")
        if self.outlet_operation_mode == "direct_sale":
            sale_orders |= self._get_direct_sale_orders()
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
            create=0,
        )
        return action


    def action_view_return_orders(self):
        self.ensure_one()
        if self.outlet_operation_mode == "direct_sale":
            action = self.env.ref("route_core.action_route_direct_return").read()[0]
            action["name"] = _("Return Orders")
            action["domain"] = [("outlet_id", "=", self.id), ("state", "!=", "cancel")]
            action["context"] = dict(self.env.context, default_outlet_id=self.id, create=0)
            return action

        pickings = self._get_consignment_transfer_pickings()
        refill_ids = set(self.visit_ids.mapped("refill_picking_id").ids)
        pickings = pickings.filtered(lambda p: p.id not in refill_ids)
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["name"] = _("Return Orders")
        action["domain"] = [("id", "in", pickings.ids)]
        action["context"] = dict(self.env.context, create=0)
        return action

    def action_view_transfers(self):
        self.ensure_one()
        action = self.env.ref("stock.action_picking_tree_all").read()[0]
        action["name"] = _("Transfers")
        if self.outlet_operation_mode == "consignment":
            pickings = self._get_consignment_transfer_pickings()
            action["domain"] = [("id", "in", pickings.ids)]
        else:
            action["domain"] = [("id", "=", 0)]
        action["context"] = dict(self.env.context, create=0)
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

    def _get_last_3_months_window(self):
        self.ensure_one()
        today = fields.Date.to_date(fields.Date.context_today(self))
        current_month_start = today.replace(day=1)
        window_start = current_month_start - relativedelta(months=2)
        window_end = current_month_start + relativedelta(months=1)
        return window_start, window_end

    def action_open_unpaid_visits(self):
        self.ensure_one()
        visits = self.visit_ids.filtered(
            lambda v: v.state != "cancel" and (v.remaining_due_amount or 0.0) > 0.0
        ).sorted(key=lambda v: (v.date or fields.Date.today(), v.id), reverse=True)

        action = self.env.ref("route_core.action_route_visit").read()[0]
        action["name"] = _("Unpaid Visits")
        action["domain"] = [("id", "in", visits.ids)]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
            default_area_id=self.area_id.id,
            default_partner_id=self.partner_id.id if self.partner_id else False,
            create=0,
        )
        return action

    def action_open_near_expiry_stock(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        balances = self.stock_balance_ids.filtered(
            lambda b: bool(b.nearest_expiry_date) and (
                b.nearest_expiry_date < today
                or (b.nearest_alert_date and b.nearest_alert_date <= today)
            )
        ).sorted(
            key=lambda b: (
                b.nearest_expiry_date or fields.Date.to_date("9999-12-31"),
                b.product_id.display_name or "",
                b.id,
            )
        )

        action = self.env.ref("route_core.action_outlet_stock_balance").read()[0]
        action["name"] = _("Near Expiry Stock")
        action["domain"] = [("id", "in", balances.ids)]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
            create=0,
        )
        return action

    def action_open_risk_products(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        balances = self.stock_balance_ids.filtered(
            lambda b: (b.qty or 0.0) <= 5.0
            or (b.nearest_expiry_date and b.nearest_expiry_date < today)
            or (b.nearest_alert_date and b.nearest_alert_date <= today)
        ).sorted(
            key=lambda b: (
                b.nearest_expiry_date or fields.Date.to_date("9999-12-31"),
                b.product_id.display_name or "",
                b.id,
            )
        )

        action = self.env.ref("route_core.action_outlet_stock_balance").read()[0]
        action["name"] = _("Risk Products")
        action["domain"] = [("id", "in", balances.ids)]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
            create=0,
        )
        return action

    def action_open_last_3_months_sale_orders(self):
        self.ensure_one()
        window_start, window_end = self._get_last_3_months_window()
        sale_orders = self.visit_ids.filtered(
            lambda v: v.state != "cancel"
            and v.sale_order_id
            and v.date
            and window_start <= v.date < window_end
        ).mapped("sale_order_id")

        action = {
            "type": "ir.actions.act_window",
            "name": _("Last 3 Months Sale Orders"),
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
            create=0,
        )
        return action

    def action_open_last_3_months_payments(self):
        self.ensure_one()
        window_start, window_end = self._get_last_3_months_window()
        start_dt = fields.Datetime.to_string(fields.Datetime.from_string(f"{window_start} 00:00:00"))
        end_dt = fields.Datetime.to_string(fields.Datetime.from_string(f"{window_end} 00:00:00"))
        payments = self.env["route.visit.payment"].search([
            ("outlet_id", "=", self.id),
            ("state", "=", "confirmed"),
            ("payment_date", ">=", start_dt),
            ("payment_date", "<", end_dt),
        ], order="payment_date desc, id desc")

        action = self.env.ref("route_core.action_route_visit_payment").read()[0]
        action["name"] = _("Last 3 Months Payments")
        action["domain"] = [("id", "in", payments.ids)]
        action["context"] = dict(
            self.env.context,
            default_outlet_id=self.id,
            create=0,
        )
        return action

