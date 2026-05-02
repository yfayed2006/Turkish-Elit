from html import escape as html_escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteOutletCategoryCommission(models.Model):
    _name = "route.outlet.category.commission"
    _description = "Route Outlet Category Commission"
    _order = "outlet_id, category_id"

    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="outlet_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="outlet_id.currency_id",
        store=True,
        readonly=True,
    )
    category_id = fields.Many2one(
        "product.category",
        string="Product Category",
        required=True,
        ondelete="cascade",
        index=True,
    )
    commission_rate = fields.Float(
        string="Commission %",
        digits=(16, 2),
        default=0.0,
        required=True,
        help="Commission percentage deducted from consignment sold value for this category.",
    )
    active = fields.Boolean(default=True)
    note = fields.Char(string="Note")

    _sql_constraints = [
        (
            "route_outlet_category_commission_unique",
            "unique(outlet_id, category_id)",
            "Each product category can only have one commission rule per outlet.",
        )
    ]


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    financial_policy = fields.Selection(
        [
            ("auto", "Automatic by Operation Mode"),
            ("direct_sale_pricelist", "Direct Sale Pricelist"),
            ("consignment_commission", "Consignment Commission"),
        ],
        string="Financial Policy",
        default="auto",
        required=True,
        help="Controls how this outlet is priced and settled in route visits.",
    )
    consignment_settlement_policy = fields.Selection(
        [
            ("gross_sale", "Collect Gross Sold Value"),
            ("net_after_commission", "Collect Net After Commission"),
        ],
        string="Consignment Settlement",
        default="net_after_commission",
        required=True,
        help=(
            "Technical settlement switch kept for compatibility. "
            "The user-facing setup is controlled by Consignment Commission Type."
        ),
    )
    consignment_commission_mode = fields.Selection(
        [
            ("fixed_rate", "Fixed Commission %"),
            ("category_rate", "Category Commission by Product Category"),
        ],
        string="Consignment Commission Type",
        default="fixed_rate",
        required=True,
        help=(
            "Fixed Commission uses the same percentage for all products. "
            "Category Commission uses one percentage per product category."
        ),
    )
    commission_line_ids = fields.One2many(
        "route.outlet.category.commission",
        "outlet_id",
        string="Category Commission Rules",
    )
    commission_line_count = fields.Integer(
        string="Commission Rules",
        compute="_compute_route_commission_line_count",
    )
    effective_financial_policy_label = fields.Char(
        string="Effective Financial Policy",
        compute="_compute_effective_financial_policy_label",
        store=False,
    )

    @api.depends("commission_line_ids")
    def _compute_route_commission_line_count(self):
        for outlet in self:
            outlet.commission_line_count = len(outlet.commission_line_ids)

    @api.depends(
        "financial_policy",
        "outlet_operation_mode",
        "consignment_settlement_policy",
        "consignment_commission_mode",
    )
    def _compute_effective_financial_policy_label(self):
        for outlet in self:
            policy = outlet._get_effective_financial_policy()
            if policy == "direct_sale_pricelist":
                label = _("Direct Sale Pricelist")
            elif outlet._get_consignment_commission_mode() == "category_rate":
                label = _("Consignment Net After Category Commission")
            else:
                label = _("Consignment Net After Fixed Commission")
            outlet.effective_financial_policy_label = label

    @api.onchange("outlet_operation_mode", "consignment_commission_mode")
    def _onchange_route_financial_policy_setup(self):
        for outlet in self:
            if outlet.outlet_operation_mode == "direct_sale":
                outlet.financial_policy = "auto"
                continue
            outlet.financial_policy = "auto"
            outlet.consignment_settlement_policy = "net_after_commission"
            if not outlet.consignment_commission_mode:
                outlet.consignment_commission_mode = "fixed_rate"

    def _get_effective_financial_policy(self):
        self.ensure_one()
        if self.financial_policy and self.financial_policy != "auto":
            return self.financial_policy
        if self.outlet_operation_mode == "direct_sale":
            return "direct_sale_pricelist"
        return "consignment_commission"

    def _get_consignment_commission_mode(self):
        self.ensure_one()
        return self.consignment_commission_mode or "fixed_rate"

    def _use_consignment_commission_deduction(self):
        self.ensure_one()
        return bool(
            self.outlet_operation_mode == "consignment"
            and self._get_effective_financial_policy() == "consignment_commission"
            and self._get_consignment_commission_mode() in ("fixed_rate", "category_rate")
        )

    def _get_default_commission_rate(self):
        self.ensure_one()
        if "default_commission_rate" in self._fields and self.default_commission_rate:
            return self.default_commission_rate or 0.0
        return self.commission_rate or 0.0

    def _get_category_ancestor_ids(self, category):
        ids = []
        current = category
        while current:
            ids.append(current.id)
            current = current.parent_id
        return ids

    def _get_consignment_category_commission_rate(self, category):
        self.ensure_one()
        default_rate = self._get_default_commission_rate()
        if self._get_consignment_commission_mode() != "category_rate" or not category:
            return default_rate

        ancestor_ids = self._get_category_ancestor_ids(category)
        active_lines = self.commission_line_ids.filtered(lambda line: line.active and line.category_id)
        if not active_lines:
            return default_rate

        best_line = False
        best_distance = 999999
        for line in active_lines:
            if line.category_id.id not in ancestor_ids:
                continue
            distance = ancestor_ids.index(line.category_id.id)
            if distance < best_distance:
                best_line = line
                best_distance = distance
        return best_line.commission_rate if best_line else default_rate

    def action_generate_consignment_category_commissions(self):
        self.ensure_one()
        if not self.id:
            raise UserError(_("Please save the outlet before loading product categories."))
        if self.outlet_operation_mode != "consignment":
            raise UserError(_("Category commission rules are only available for consignment outlets."))

        self.write({
            "consignment_commission_mode": "category_rate",
            "consignment_settlement_policy": "net_after_commission",
            "financial_policy": "auto",
        })

        existing_category_ids = set(self.commission_line_ids.mapped("category_id").ids)
        categories = self.env["product.category"].search([], order="complete_name, id")
        default_rate = self._get_default_commission_rate()
        vals_list = []
        for category in categories:
            if category.id in existing_category_ids:
                continue
            vals_list.append(
                {
                    "outlet_id": self.id,
                    "category_id": category.id,
                    "commission_rate": default_rate,
                    "active": True,
                }
            )
        if vals_list:
            self.env["route.outlet.category.commission"].create(vals_list)

        form_view = self.env.ref(
            "route_core.view_route_outlet_management_config_form",
            raise_if_not_found=False,
        ) or self.env.ref("route_core.view_route_outlet_form", raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window",
            "name": _("Outlets"),
            "res_model": "route.outlet",
            "res_id": self.id,
            "view_mode": "form",
            "views": [(form_view.id, "form")] if form_view else [(False, "form")],
            "target": "current",
            "context": dict(self.env.context, route_open_financial_policy=True),
        }


class RouteVisitLine(models.Model):
    _inherit = "route.visit.line"

    route_product_category_id = fields.Many2one(
        "product.category",
        string="Product Category",
        related="product_id.categ_id",
        readonly=True,
        store=False,
    )
    route_commission_rate = fields.Float(
        string="Commission %",
        digits=(16, 2),
        compute="_compute_route_financial_amounts",
        store=False,
    )
    route_commission_base_amount = fields.Monetary(
        string="Commission Base",
        currency_field="currency_id",
        compute="_compute_route_financial_amounts",
        store=False,
    )
    route_commission_amount = fields.Monetary(
        string="Commission Amount",
        currency_field="currency_id",
        compute="_compute_route_financial_amounts",
        store=False,
    )
    route_net_payable_amount = fields.Monetary(
        string="Net Payable",
        currency_field="currency_id",
        compute="_compute_route_financial_amounts",
        store=False,
    )

    @api.depends(
        "sold_amount",
        "return_amount",
        "product_id.categ_id",
        "visit_id.visit_execution_mode",
        "visit_id.outlet_id",
        "visit_id.outlet_id.financial_policy",
        "visit_id.outlet_id.consignment_settlement_policy",
        "visit_id.outlet_id.consignment_commission_mode",
        "visit_id.outlet_id.default_commission_rate",
        "visit_id.outlet_id.commission_rate",
        "visit_id.outlet_id.commission_line_ids.active",
        "visit_id.outlet_id.commission_line_ids.category_id",
        "visit_id.outlet_id.commission_line_ids.commission_rate",
    )
    def _compute_route_financial_amounts(self):
        for line in self:
            gross_sold = line.sold_amount or 0.0
            returns = line.return_amount or 0.0
            base_net = max(gross_sold - returns, 0.0)
            rate = 0.0
            commission_base = 0.0
            commission_amount = 0.0
            net_payable = base_net

            visit = line.visit_id
            outlet = visit.outlet_id if visit else False
            is_direct = bool(visit and hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop())
            if outlet and not is_direct:
                rate = outlet._get_consignment_category_commission_rate(line.product_id.categ_id)
                if outlet._use_consignment_commission_deduction():
                    commission_base = gross_sold
                    commission_amount = min(commission_base * (rate / 100.0), max(gross_sold, 0.0))
                    net_payable = max(gross_sold - returns - commission_amount, 0.0)

            line.route_commission_rate = rate
            line.route_commission_base_amount = commission_base
            line.route_commission_amount = commission_amount
            line.route_net_payable_amount = net_payable


class RouteVisit(models.Model):
    _inherit = "route.visit"

    consignment_commission_amount = fields.Monetary(
        string="Commission Amount",
        currency_field="currency_id",
        compute="_compute_route_consignment_policy_totals",
        store=False,
    )
    consignment_gross_after_returns_amount = fields.Monetary(
        string="Gross After Returns",
        currency_field="currency_id",
        compute="_compute_route_consignment_policy_totals",
        store=False,
    )
    consignment_net_payable_amount = fields.Monetary(
        string="Net Payable After Commission",
        currency_field="currency_id",
        compute="_compute_route_consignment_policy_totals",
        store=False,
    )
    consignment_settlement_policy = fields.Selection(
        related="outlet_id.consignment_settlement_policy",
        readonly=True,
        store=False,
    )

    show_consignment_category_commission_breakdown = fields.Boolean(
        string="Show Category Commission Breakdown",
        compute="_compute_consignment_category_commission_html",
        store=False,
    )
    consignment_category_commission_html = fields.Html(
        string="Category Commission Breakdown",
        compute="_compute_consignment_category_commission_html",
        sanitize=False,
        store=False,
    )

    def _get_route_consignment_financial_amounts(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda line: line.product_id)
        gross_sale = sum((line.sold_amount or 0.0) for line in lines)
        returns = sum((line.return_amount or 0.0) for line in lines)
        commission = sum((line.route_commission_amount or 0.0) for line in lines)
        gross_after_returns = max(gross_sale - returns, 0.0)
        net_payable = sum((line.route_net_payable_amount or 0.0) for line in lines)
        if not lines:
            net_payable = 0.0
        return {
            "gross_sale_amount": gross_sale,
            "return_amount": returns,
            "gross_after_returns_amount": gross_after_returns,
            "commission_amount": commission,
            "net_payable_amount": net_payable,
        }


    def _format_route_policy_currency(self, amount):
        self.ensure_one()
        amount = amount or 0.0
        currency = self.currency_id or self.env.company.currency_id
        precision = currency.decimal_places or 2 if currency else 2
        formatted = f"{amount:,.{precision}f}"
        symbol = (currency.symbol or currency.name or "") if currency else ""
        if not symbol:
            return formatted
        if currency.position == "before":
            return f"{symbol} {formatted}"
        return f"{formatted} {symbol}"

    def _get_consignment_category_commission_breakdown(self):
        self.ensure_one()
        empty = {
            "lines": [],
            "total_sold_qty": 0.0,
            "total_return_qty": 0.0,
            "total_sold_value": 0.0,
            "total_return_value": 0.0,
            "total_gross_after_returns": 0.0,
            "total_commission_amount": 0.0,
            "total_net_payable_amount": 0.0,
        }
        if hasattr(self, "_is_direct_sales_stop") and self._is_direct_sales_stop():
            return empty

        buckets = {}
        lines = self.line_ids.filtered(lambda line: line.product_id)
        for line in lines:
            sold_value = line.sold_amount or 0.0
            return_value = line.return_amount or 0.0
            commission_amount = line.route_commission_amount or 0.0
            net_payable = line.route_net_payable_amount or max(sold_value - return_value - commission_amount, 0.0)
            if not any((sold_value, return_value, commission_amount, net_payable, line.sold_qty or 0.0, line.return_qty or 0.0)):
                continue

            category = line.product_id.categ_id
            key = category.id if category else 0
            if key not in buckets:
                rate = line.route_commission_rate or 0.0
                buckets[key] = {
                    "category_id": category.id if category else False,
                    "category_name": category.complete_name if category else _("Uncategorized"),
                    "sold_qty": 0.0,
                    "return_qty": 0.0,
                    "sold_value": 0.0,
                    "return_value": 0.0,
                    "gross_after_returns": 0.0,
                    "commission_rate": rate,
                    "commission_amount": 0.0,
                    "net_payable_amount": 0.0,
                    "product_ids": set(),
                }
            bucket = buckets[key]
            bucket["sold_qty"] += line.sold_qty or 0.0
            bucket["return_qty"] += line.return_qty or 0.0
            bucket["sold_value"] += sold_value
            bucket["return_value"] += return_value
            bucket["commission_amount"] += commission_amount
            bucket["net_payable_amount"] += net_payable
            if line.product_id:
                bucket["product_ids"].add(line.product_id.id)
            # Keep the displayed rate meaningful if products in the same category are using the same rule.
            # If data was edited manually and rates differ, the weighted result is still clear through amounts.
            if not bucket["commission_rate"] and line.route_commission_rate:
                bucket["commission_rate"] = line.route_commission_rate

        result_lines = []
        totals = empty.copy()
        totals["lines"] = result_lines
        for bucket in sorted(buckets.values(), key=lambda val: val["category_name"] or ""):
            bucket["gross_after_returns"] = max((bucket["sold_value"] or 0.0) - (bucket["return_value"] or 0.0), 0.0)
            bucket["product_count"] = len(bucket.pop("product_ids", set()))
            result_lines.append(bucket)
            totals["total_sold_qty"] += bucket["sold_qty"]
            totals["total_return_qty"] += bucket["return_qty"]
            totals["total_sold_value"] += bucket["sold_value"]
            totals["total_return_value"] += bucket["return_value"]
            totals["total_gross_after_returns"] += bucket["gross_after_returns"]
            totals["total_commission_amount"] += bucket["commission_amount"]
            totals["total_net_payable_amount"] += bucket["net_payable_amount"]
        return totals

    def _build_consignment_category_commission_html(self):
        self.ensure_one()
        breakdown = self._get_consignment_category_commission_breakdown()
        lines = breakdown.get("lines") or []
        if not lines:
            return ""

        def money(amount):
            return html_escape(self._format_route_policy_currency(amount))

        rows = []
        for line in lines:
            rows.append(
                "".join([
                    "<tr>",
                    "<td>", html_escape(line.get("category_name") or "-"), "</td>",
                    "<td class='route_commission_num'>", f"{line.get('sold_qty', 0.0):,.2f}", "</td>",
                    "<td class='route_commission_num'>", money(line.get("sold_value", 0.0)), "</td>",
                    "<td class='route_commission_num'>", money(line.get("return_value", 0.0)), "</td>",
                    "<td class='route_commission_num'>", money(line.get("gross_after_returns", 0.0)), "</td>",
                    "<td class='route_commission_num'>", f"{line.get('commission_rate', 0.0):,.2f}%", "</td>",
                    "<td class='route_commission_num'>", money(line.get("commission_amount", 0.0)), "</td>",
                    "<td class='route_commission_num route_commission_net'>", money(line.get("net_payable_amount", 0.0)), "</td>",
                    "</tr>",
                ])
            )
        rows.append(
            "".join([
                "<tr class='route_commission_total'>",
                "<td>Total</td>",
                "<td class='route_commission_num'>", f"{breakdown.get('total_sold_qty', 0.0):,.2f}", "</td>",
                "<td class='route_commission_num'>", money(breakdown.get("total_sold_value", 0.0)), "</td>",
                "<td class='route_commission_num'>", money(breakdown.get("total_return_value", 0.0)), "</td>",
                "<td class='route_commission_num'>", money(breakdown.get("total_gross_after_returns", 0.0)), "</td>",
                "<td class='route_commission_num'>-</td>",
                "<td class='route_commission_num'>", money(breakdown.get("total_commission_amount", 0.0)), "</td>",
                "<td class='route_commission_num route_commission_net'>", money(breakdown.get("total_net_payable_amount", 0.0)), "</td>",
                "</tr>",
            ])
        )
        return "".join([
            "<div class='route_commission_breakdown'>",
            "<div class='route_commission_title'>Category Commission Breakdown</div>",
            "<div class='route_commission_hint'>Sold value, returns, commission percentage, outlet commission, and net payable are shown by product category.</div>",
            "<div class='route_commission_table_wrap'>",
            "<table class='route_commission_table'>",
            "<thead><tr>",
            "<th>Category</th>",
            "<th>Sold Qty</th>",
            "<th>Sold Value</th>",
            "<th>Returns</th>",
            "<th>After Returns</th>",
            "<th>Commission %</th>",
            "<th>Outlet Commission</th>",
            "<th>Net Payable</th>",
            "</tr></thead>",
            "<tbody>",
            "".join(rows),
            "</tbody></table></div></div>",
            "<style>",
            ".route_commission_breakdown{border:1px solid #dbe3ec;border-radius:14px;background:#fff;padding:12px;margin:10px 0 14px 0;}",
            ".route_commission_title{font-size:17px;font-weight:800;color:#0f172a;margin-bottom:4px;}",
            ".route_commission_hint{font-size:13px;color:#475569;background:#ecfeff;border:1px solid #bae6fd;border-radius:10px;padding:8px 10px;margin-bottom:10px;}",
            ".route_commission_table_wrap{overflow-x:auto;}",
            ".route_commission_table{width:100%;border-collapse:collapse;min-width:760px;}",
            ".route_commission_table th{background:#f8fafc;color:#64748b;text-transform:uppercase;font-size:11px;letter-spacing:.35px;text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;}",
            ".route_commission_table td{padding:8px;border-bottom:1px solid #f1f5f9;color:#0f172a;vertical-align:top;}",
            ".route_commission_num{text-align:right;white-space:nowrap;}",
            ".route_commission_net{font-weight:800;color:#0f766e;}",
            ".route_commission_total td{font-weight:800;background:#f8fafc;border-top:1px solid #cbd5e1;}",
            "@media(max-width:768px){.route_commission_breakdown{padding:10px;}.route_commission_table{min-width:720px;}.route_commission_title{font-size:15px;}}",
            "</style>",
        ])

    @api.depends(
        "visit_execution_mode",
        "line_ids.product_id",
        "line_ids.product_id.categ_id",
        "line_ids.sold_qty",
        "line_ids.return_qty",
        "line_ids.sold_amount",
        "line_ids.return_amount",
        "line_ids.route_commission_rate",
        "line_ids.route_commission_amount",
        "line_ids.route_net_payable_amount",
    )
    def _compute_consignment_category_commission_html(self):
        for visit in self:
            visit.show_consignment_category_commission_breakdown = False
            visit.consignment_category_commission_html = False
            if hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop():
                continue
            breakdown = visit._get_consignment_category_commission_breakdown()
            has_breakdown = bool(breakdown.get("lines"))
            visit.show_consignment_category_commission_breakdown = has_breakdown
            visit.consignment_category_commission_html = visit._build_consignment_category_commission_html() if has_breakdown else False

    @api.depends(
        "line_ids.sold_amount",
        "line_ids.return_amount",
        "line_ids.route_commission_amount",
        "line_ids.route_net_payable_amount",
        "visit_execution_mode",
        "outlet_id.consignment_settlement_policy",
        "outlet_id.consignment_commission_mode",
    )
    def _compute_route_consignment_policy_totals(self):
        for visit in self:
            visit.consignment_commission_amount = 0.0
            visit.consignment_gross_after_returns_amount = 0.0
            visit.consignment_net_payable_amount = 0.0
            if hasattr(visit, "_is_direct_sales_stop") and visit._is_direct_sales_stop():
                continue
            amounts = visit._get_route_consignment_financial_amounts()
            visit.consignment_commission_amount = amounts["commission_amount"]
            visit.consignment_gross_after_returns_amount = amounts["gross_after_returns_amount"]
            visit.consignment_net_payable_amount = amounts["net_payable_amount"]

    @api.depends(
        "visit_execution_mode",
        "payment_ids.state",
        "payment_ids.amount",
        "settlement_payment_ids.state",
        "settlement_payment_ids.amount",
        "line_ids.sold_amount",
        "line_ids.return_amount",
        "line_ids.route_net_payable_amount",
        "direct_stop_grand_due_amount",
    )
    def _compute_payment_totals(self):
        Payment = self.env["route.visit.payment"]
        for rec in self:
            if hasattr(rec, "_is_direct_sales_stop") and rec._is_direct_sales_stop():
                net_due = getattr(rec, "direct_stop_grand_due_amount", 0.0) or 0.0
                confirmed_payments = rec._get_direct_stop_settlement_payments(states=["confirmed"]) if rec.id and hasattr(rec, "_get_direct_stop_settlement_payments") else Payment
                total_collected = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0
                resolved_amount = rec._get_direct_stop_settlement_resolved_amount(states=["confirmed"]) if rec.id and hasattr(rec, "_get_direct_stop_settlement_resolved_amount") else total_collected
                remaining_amount = max((net_due or 0.0) - (resolved_amount or 0.0), 0.0)
            else:
                amounts = rec._get_route_consignment_financial_amounts()
                net_due = amounts["net_payable_amount"]
                confirmed_payments = rec.payment_ids.filtered(lambda p: p.state == "confirmed") if rec.payment_ids else rec.payment_ids
                total_collected = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0
                remaining_amount = max((net_due or 0.0) - (total_collected or 0.0), 0.0)

            rec.net_due_amount = net_due
            rec.collected_amount = total_collected
            rec.remaining_due_amount = remaining_amount

    @api.depends(
        "visit_execution_mode",
        "outlet_current_due_amount",
        "net_due_amount",
        "remaining_due_amount",
        "collected_amount",
        "payment_ids.state",
        "payment_ids.amount",
        "payment_ids.promise_amount",
        "line_ids.sold_amount",
        "line_ids.return_amount",
        "line_ids.route_commission_amount",
        "line_ids.route_net_payable_amount",
    )
    def _compute_consignment_financial_snapshot(self):
        for rec in self:
            rec.consignment_previous_due_amount = 0.0
            rec.consignment_current_visit_sale_amount = 0.0
            rec.consignment_current_visit_return_amount = 0.0
            rec.consignment_net_amount_for_visit = 0.0
            rec.consignment_amount_due_now = 0.0
            rec.consignment_immediate_remaining_amount = 0.0
            rec.consignment_promise_amount = 0.0

            if hasattr(rec, "_is_direct_sales_stop") and rec._is_direct_sales_stop():
                continue

            amounts = rec._get_route_consignment_financial_amounts()
            sale_amount = amounts["gross_sale_amount"]
            return_amount = amounts["return_amount"]
            net_amount_for_visit = amounts["net_payable_amount"]
            confirmed_payments = rec.payment_ids.filtered(lambda p: p.state == "confirmed") if rec.payment_ids else rec.payment_ids
            confirmed_amount = sum(confirmed_payments.mapped("amount")) if confirmed_payments else 0.0
            promise_amount = sum((getattr(payment, "effective_promise_amount", False) or payment.promise_amount or 0.0) for payment in confirmed_payments) if confirmed_payments else 0.0

            effective_remaining = rec.remaining_due_amount or 0.0
            outlet_balance_after_collection = max(rec.outlet_current_due_amount or 0.0, effective_remaining)
            amount_due_before_collection = max(outlet_balance_after_collection + confirmed_amount, net_amount_for_visit)

            rec.consignment_current_visit_sale_amount = sale_amount
            rec.consignment_current_visit_return_amount = return_amount
            rec.consignment_net_amount_for_visit = net_amount_for_visit
            rec.consignment_amount_due_now = amount_due_before_collection
            rec.consignment_previous_due_amount = max(amount_due_before_collection - max(net_amount_for_visit, 0.0), 0.0)
            rec.consignment_immediate_remaining_amount = effective_remaining
            rec.consignment_promise_amount = min(promise_amount, outlet_balance_after_collection) if promise_amount else 0.0

    def _get_consignment_receipt_summary(self):
        self.ensure_one()
        summary = super()._get_consignment_receipt_summary()
        if hasattr(self, "_is_direct_sales_stop") and self._is_direct_sales_stop():
            return summary

        amounts = self._get_route_consignment_financial_amounts()
        payments = self._get_consignment_receipt_payments() if hasattr(self, "_get_consignment_receipt_payments") else self.payment_ids.filtered(lambda p: p.state == "confirmed")
        promise_payments = payments.filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
        latest_promise = promise_payments[:1]
        settled_amount = sum(payments.mapped("amount")) if payments else (self.collected_amount or 0.0)
        remaining_amount = self.remaining_due_amount or 0.0
        current_visit_net = amounts["net_payable_amount"]
        total_outstanding_after_collection = max(self.outlet_current_due_amount or 0.0, remaining_amount)
        total_outlet_due = max(total_outstanding_after_collection + settled_amount, current_visit_net)
        previous_due = max(total_outlet_due - max(current_visit_net, 0.0), 0.0)
        raw_promise_amount = sum((getattr(payment, "effective_promise_amount", False) or payment.promise_amount or 0.0) for payment in promise_payments) if promise_payments else 0.0

        summary.update(
            {
                "visit_sale_amount": amounts["gross_sale_amount"],
                "returned_value": amounts["return_amount"],
                "gross_after_returns_amount": amounts["gross_after_returns_amount"],
                "commission_amount": amounts["commission_amount"],
                "current_visit_net": current_visit_net,
                "current_due": total_outlet_due,
                "total_outlet_due": total_outlet_due,
                "previous_due": previous_due,
                "settled_amount": settled_amount,
                "remaining_amount": remaining_amount,
                "current_visit_remaining": remaining_amount,
                "total_outstanding_after_collection": total_outstanding_after_collection,
                "promise_amount": min(raw_promise_amount, remaining_amount) if raw_promise_amount else 0.0,
                "latest_promise_date": latest_promise.promise_date if latest_promise else False,
            }
        )
        return summary

    def _prepare_sale_order_line_vals(self):
        self.ensure_one()
        line_vals = []
        sale_lines = self.line_ids.filtered(lambda line: line.product_id and (line.sold_qty or 0.0) > 0)
        use_commission_discount = bool(
            self.outlet_id
            and self.visit_execution_mode != "direct_sales"
            and self.outlet_id._use_consignment_commission_deduction()
        )

        for line in sale_lines:
            vals = {
                "product_id": line.product_id.id,
                "name": line.product_id.display_name,
                "product_uom_qty": line.sold_qty,
                "price_unit": line.unit_price or line.product_id.lst_price or 0.0,
            }
            if use_commission_discount and "discount" in self.env["sale.order.line"]._fields:
                vals["discount"] = line.route_commission_rate or 0.0
            if "route_product_barcode" in self.env["sale.order.line"]._fields:
                vals["route_product_barcode"] = line.barcode or line.product_id.barcode or False
            if (
                "route_lot_id" in self.env["sale.order.line"]._fields
                and getattr(line.product_id, "tracking", "none") in ("lot", "serial")
                and line.lot_id
            ):
                vals["route_lot_id"] = line.lot_id.id
            line_vals.append((0, 0, vals))
        return line_vals

    def _open_direct_sale_order_action(self, outlet=None, create=False):
        self.ensure_one()
        action = super()._open_direct_sale_order_action(outlet=outlet, create=create)
        outlet = outlet or self.outlet_id
        if create and outlet:
            pricelist = self.env["sale.order"]._route_get_outlet_pricelist(outlet)
            if pricelist:
                context = dict(action.get("context") or {})
                context["default_pricelist_id"] = pricelist.id
                action["context"] = context
        return action


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _route_get_outlet_pricelist(self, outlet):
        if not outlet:
            return self.env["product.pricelist"]
        if getattr(outlet, "direct_sale_pricelist_id", False):
            return outlet.direct_sale_pricelist_id
        partner = outlet.partner_id
        if partner and getattr(partner, "property_product_pricelist", False):
            return partner.property_product_pricelist
        return self.env["product.pricelist"]

    @api.onchange("route_outlet_id")
    def _onchange_route_outlet_id(self):
        result = super()._onchange_route_outlet_id()
        for order in self:
            if order.route_order_mode != "direct_sale" or not order.route_outlet_id:
                continue
            pricelist = order._route_get_outlet_pricelist(order.route_outlet_id)
            if pricelist:
                order.pricelist_id = pricelist
        return result

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if vals.get("route_order_mode") == "direct_sale" and vals.get("route_outlet_id") and not vals.get("pricelist_id"):
            outlet = self.env["route.outlet"].browse(vals["route_outlet_id"]).exists()
            pricelist = self._route_get_outlet_pricelist(outlet)
            if pricelist:
                vals["pricelist_id"] = pricelist.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("route_order_mode") == "direct_sale" and vals.get("route_outlet_id") and not vals.get("pricelist_id"):
                outlet = self.env["route.outlet"].browse(vals["route_outlet_id"]).exists()
                pricelist = self._route_get_outlet_pricelist(outlet)
                if pricelist:
                    vals["pricelist_id"] = pricelist.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("route_outlet_id") and not vals.get("pricelist_id"):
            target_is_direct = vals.get("route_order_mode") == "direct_sale" or any(order.route_order_mode == "direct_sale" for order in self)
            if target_is_direct:
                outlet = self.env["route.outlet"].browse(vals["route_outlet_id"]).exists()
                pricelist = self._route_get_outlet_pricelist(outlet)
                if pricelist:
                    vals = dict(vals)
                    vals["pricelist_id"] = pricelist.id
        return super().write(vals)
