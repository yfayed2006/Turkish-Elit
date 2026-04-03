from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteVisitPayment(models.Model):
    _name = "route.visit.payment"
    _description = "Route Visit Payment"
    _order = "payment_date desc, id desc"

    source_type = fields.Selection(
        [
            ("visit", "Visit"),
            ("direct_sale", "Direct Sale"),
        ],
        string="Source Type",
        required=True,
        default="visit",
    )

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        ondelete="cascade",
        index=True,
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Direct Sale Order",
        domain=[("route_order_mode", "=", "direct_sale")],
        ondelete="cascade",
        index=True,
    )

    settlement_visit_id = fields.Many2one(
        "route.visit",
        string="Settlement Visit",
        ondelete="set null",
        index=True,
        help="Direct-sales stop that grouped this payment allocation.",
    )

    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    area_id = fields.Many2one(
        "route.area",
        string="Area",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    salesperson_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

    source_document_ref = fields.Char(
        string="Source Document",
        compute="_compute_source_context",
        store=True,
        readonly=True,
    )

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

    payment_date = fields.Datetime(
        string="Payment Date",
        default=fields.Datetime.now,
        required=True,
    )

    payment_mode = fields.Selection(
        [
            ("cash", "Cash"),
            ("bank", "Bank Transfer"),
            ("pos", "POS"),
            ("deferred", "Deferred"),
        ],
        string="Payment Mode",
        required=True,
        default="cash",
    )

    collection_type = fields.Selection(
        [
            ("full", "Full Payment"),
            ("partial", "Partial Payment + Carry Forward"),
            ("defer_date", "Defer To Specific Date"),
            ("next_visit", "Carry To Next Visit"),
        ],
        string="Collection Scenario",
        required=True,
        default="full",
    )

    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )

    promise_date = fields.Date(string="Promise To Pay Date")
    promise_amount = fields.Monetary(
        string="Promise To Pay Amount",
        currency_field="currency_id",
        default=0.0,
    )
    promise_status = fields.Selection(
        [
            ("open", "Open"),
            ("due_today", "Due Today"),
            ("overdue", "Overdue"),
            ("closed", "Closed"),
        ],
        string="Promise Status",
        compute="_compute_promise_status",
        store=False,
    )

    remaining_due_amount = fields.Monetary(
        string="Unpaid Amount",
        currency_field="currency_id",
        compute="_compute_remaining_due_amount",
        store=False,
    )

    due_date = fields.Date(string="Deferred Due Date")

    reference = fields.Char(string="Reference")
    bank_name = fields.Char(string="Bank Name")
    pos_terminal = fields.Char(string="POS Terminal")
    note = fields.Text(string="Note")

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    visit_remaining_due = fields.Monetary(
        string="Current Remaining Due",
        currency_field="currency_id",
        compute="_compute_visit_remaining_due",
        store=False,
    )

    @api.depends(
        "source_type",
        "visit_id",
        "visit_id.outlet_id",
        "visit_id.area_id",
        "visit_id.user_id",
        "sale_order_id",
        "sale_order_id.name",
        "sale_order_id.route_outlet_id",
        "sale_order_id.route_outlet_id.area_id",
        "sale_order_id.user_id",
    )
    def _compute_source_context(self):
        for rec in self:
            outlet = False
            area = False
            salesperson = False
            source_ref = False

            if rec.source_type == "direct_sale" and rec.sale_order_id:
                outlet = rec.sale_order_id.route_outlet_id
                area = outlet.area_id if outlet else False
                salesperson = rec.sale_order_id.user_id
                source_ref = rec.sale_order_id.name
            elif rec.visit_id:
                outlet = rec.visit_id.outlet_id
                area = rec.visit_id.area_id
                salesperson = rec.visit_id.user_id
                source_ref = rec.visit_id.display_name or rec.visit_id.name

            rec.outlet_id = outlet
            rec.area_id = area
            rec.salesperson_id = salesperson
            rec.source_document_ref = source_ref

    def _get_target_model(self):
        self.ensure_one()
        if self.source_type == "direct_sale":
            return self.sale_order_id
        return self.visit_id

    def _is_target_direct_sales_visit(self):
        self.ensure_one()
        visit = self.visit_id
        if not visit:
            return False
        if hasattr(visit, "_is_direct_sales_stop"):
            try:
                return bool(visit._is_direct_sales_stop())
            except Exception:
                pass
        if getattr(visit, "visit_execution_mode", False) == "direct_sales":
            return True
        if getattr(visit, "outlet_id", False) and getattr(visit.outlet_id, "outlet_operation_mode", False) == "direct_sale":
            return True
        return bool(
            getattr(visit, "direct_stop_order_ids", False)
            or getattr(visit, "direct_stop_return_ids", False)
            or getattr(visit, "direct_stop_skip_sale", False)
            or getattr(visit, "direct_stop_skip_return", False)
        )

    def _get_target_total_amount(self):
        self.ensure_one()
        if self.source_type == "direct_sale":
            return self.sale_order_id.amount_total or 0.0

        if self._is_target_direct_sales_visit():
            direct_total = 0.0
            if hasattr(self.visit_id, "direct_stop_current_net_amount"):
                direct_total = self.visit_id.direct_stop_current_net_amount or 0.0
            if not direct_total and hasattr(self.visit_id, "net_due_amount"):
                direct_total = self.visit_id.net_due_amount or 0.0
            return max(direct_total, 0.0)

        total_sales = 0.0
        for line in self.visit_id.line_ids:
            sold_qty = getattr(line, "sold_qty", 0.0) or 0.0
            unit_price = getattr(line, "unit_price", 0.0) or 0.0
            total_sales += sold_qty * unit_price
        return total_sales

    def _get_confirmed_target_payments(self, exclude_self=False):
        self.ensure_one()
        domain = [("state", "=", "confirmed")]
        if self.source_type == "direct_sale":
            domain.append(("sale_order_id", "=", self.sale_order_id.id or 0))
        else:
            domain.append(("visit_id", "=", self.visit_id.id or 0))

        payments = self.search(domain)
        if exclude_self and self.id:
            payments = payments.filtered(lambda p: p.id != self.id)
        return payments

    def _get_target_remaining_due(self, exclude_self=False):
        self.ensure_one()
        total_amount = self._get_target_total_amount()
        confirmed_amount = sum(self._get_confirmed_target_payments(exclude_self=exclude_self).mapped("amount"))
        return max((total_amount or 0.0) - (confirmed_amount or 0.0), 0.0)

    def _get_target_label(self):
        self.ensure_one()
        if self.source_type == "direct_sale":
            return _("direct sale order")
        return _("visit")

    @api.depends(
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.state",
    )
    def _compute_visit_remaining_due(self):
        for rec in self:
            rec.visit_remaining_due = rec._get_target_remaining_due() if rec._get_target_model() else 0.0

    @api.depends(
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.state",
    )
    def _compute_remaining_due_amount(self):
        for rec in self:
            rec.remaining_due_amount = rec._get_target_remaining_due() if rec._get_target_model() else 0.0

    @api.depends(
        "promise_amount",
        "promise_date",
        "state",
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.state",
    )
    def _compute_promise_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == "cancelled" or (rec.promise_amount or 0.0) <= 0:
                rec.promise_status = False
                continue

            remaining_due = rec._get_target_remaining_due()
            if remaining_due <= 0:
                rec.promise_status = "closed"
            elif rec.promise_date and rec.promise_date < today:
                rec.promise_status = "overdue"
            elif rec.promise_date and rec.promise_date == today:
                rec.promise_status = "due_today"
            else:
                rec.promise_status = "open"

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        visit_id = self.env.context.get("default_visit_id")
        sale_order_id = self.env.context.get("default_sale_order_id")

        if sale_order_id:
            order = self.env["sale.order"].browse(sale_order_id)
            vals.setdefault("source_type", "direct_sale")
            vals.setdefault("sale_order_id", sale_order_id)
            vals.setdefault("payment_mode", order.route_payment_mode or "cash")
            if "amount" in fields_list:
                vals["amount"] = max(order._get_route_payment_remaining_due() if hasattr(order, "_get_route_payment_remaining_due") else (order.amount_total or 0.0), 0.0)
            if "collection_type" in fields_list:
                vals.setdefault("collection_type", "defer_date" if order.route_payment_mode == "deferred" else "full")
            if order.route_payment_mode == "deferred":
                vals.setdefault("due_date", order.route_payment_due_date)
                vals.setdefault("promise_date", order.route_payment_due_date)
                vals.setdefault("promise_amount", max(order._get_route_payment_remaining_due() if hasattr(order, "_get_route_payment_remaining_due") else (order.amount_total or 0.0), 0.0))
                vals.setdefault("amount", 0.0)
        elif visit_id:
            visit = self.env["route.visit"].browse(visit_id)
            vals.setdefault("source_type", "visit")
            vals.setdefault("visit_id", visit_id)
            if "amount" in fields_list:
                vals["amount"] = max(visit.remaining_due_amount or 0.0, 0.0)
            if "collection_type" in fields_list:
                vals.setdefault("collection_type", "full")
        return vals

    @api.onchange("source_type")
    def _onchange_source_type(self):
        for rec in self:
            if rec.source_type == "direct_sale":
                rec.visit_id = False
            else:
                rec.sale_order_id = False

    def _sync_promise_fields(self):
        for rec in self:
            due = rec._get_target_remaining_due(exclude_self=(rec.state == "confirmed")) if rec._get_target_model() else 0.0
            if rec.collection_type == "full":
                rec.promise_date = False
                rec.promise_amount = 0.0
            elif rec.collection_type == "partial":
                rec.promise_amount = max(due - (rec.amount or 0.0), 0.0)
            elif rec.collection_type == "defer_date":
                rec.promise_date = rec.due_date or rec.promise_date
                rec.promise_amount = due
            elif rec.collection_type == "next_visit":
                rec.promise_amount = due

    @api.onchange("visit_id", "sale_order_id", "source_type")
    def _onchange_payment_target_set_amount(self):
        for rec in self:
            due = rec._get_target_remaining_due(exclude_self=(rec.state == "confirmed")) if rec._get_target_model() else 0.0
            if rec.source_type == "direct_sale" and rec.sale_order_id and rec.sale_order_id.route_payment_mode == "deferred" and rec.collection_type == "full":
                rec.collection_type = "defer_date"
                rec.payment_mode = "deferred"
            if rec.collection_type == "full":
                rec.amount = due
            elif rec.collection_type == "partial":
                if due > 0 and (rec.amount <= 0 or rec.amount >= due):
                    rec.amount = due / 2.0
            rec._sync_promise_fields()

    @api.onchange("collection_type", "amount", "due_date", "promise_date")
    def _onchange_collection_type(self):
        for rec in self:
            due = rec._get_target_remaining_due(exclude_self=(rec.state == "confirmed")) if rec._get_target_model() else 0.0

            if rec.collection_type == "full":
                rec.amount = due
                rec.due_date = False

            elif rec.collection_type == "partial":
                rec.due_date = False
                if due <= 0:
                    rec.amount = 0.0
                elif rec.amount <= 0 or rec.amount >= due:
                    rec.amount = due / 2.0

            elif rec.collection_type == "defer_date":
                rec.amount = 0.0

            elif rec.collection_type == "next_visit":
                rec.amount = 0.0
                rec.due_date = False

            rec._sync_promise_fields()

    @api.constrains("source_type", "visit_id", "sale_order_id")
    def _check_source_target(self):
        for rec in self:
            if rec.source_type == "visit":
                if not rec.visit_id:
                    raise ValidationError(_("A Visit is required for payments with source type Visit."))
                if rec.sale_order_id:
                    raise ValidationError(_("Do not set a Direct Sale Order when the payment source type is Visit."))
            elif rec.source_type == "direct_sale":
                if not rec.sale_order_id:
                    raise ValidationError(_("A Direct Sale Order is required for payments with source type Direct Sale."))
                if rec.visit_id:
                    raise ValidationError(_("Do not set a Visit when the payment source type is Direct Sale."))
                if rec.sale_order_id.route_order_mode != "direct_sale":
                    raise ValidationError(_("Only Direct Sale orders can be used here."))

    @api.constrains("amount", "collection_type", "due_date", "promise_date", "promise_amount", "visit_id", "sale_order_id")
    def _check_payment_rules(self):
        for rec in self:
            if not rec._get_target_model():
                continue

            due = rec._get_target_remaining_due(exclude_self=(rec.state == "confirmed"))
            target_label = rec._get_target_label()

            if rec.amount < 0:
                raise ValidationError(_("Payment amount cannot be negative."))

            if rec.collection_type == "full":
                if due <= 0:
                    raise ValidationError(_("There is no remaining due amount on this %s.") % target_label)
                if rec.amount <= 0:
                    raise ValidationError(_("Full payment amount must be greater than zero."))
                if rec.amount > due:
                    raise ValidationError(_("Full payment cannot be more than the remaining due amount."))

            elif rec.collection_type == "partial":
                if due <= 0:
                    raise ValidationError(_("There is no remaining due amount on this %s.") % target_label)
                if rec.amount <= 0:
                    raise ValidationError(_("Partial payment amount must be greater than zero."))
                if rec.amount >= due:
                    raise ValidationError(
                        _("Partial payment must be less than the remaining due amount. Use Full Payment instead.")
                    )
                if (rec.promise_amount or 0.0) <= 0:
                    raise ValidationError(_("Please set the promised unpaid amount."))
                if not rec.promise_date:
                    raise ValidationError(_("Please set the promise to pay date for the carried-forward balance."))
                if not rec.note:
                    raise ValidationError(_("Please add a note for the carried-forward balance."))

            elif rec.collection_type == "defer_date":
                if rec.amount != 0:
                    raise ValidationError(_("Deferred payment to a specific date must have amount = 0."))
                if not rec.due_date:
                    raise ValidationError(_("Please set the deferred due date."))
                if (rec.promise_amount or 0.0) <= 0:
                    raise ValidationError(_("Please set the promise to pay amount."))
                if not (rec.promise_date or rec.due_date):
                    raise ValidationError(_("Please set the promise to pay date."))
                if not rec.note:
                    raise ValidationError(_("Please add a note explaining the deferment."))

            elif rec.collection_type == "next_visit":
                if rec.amount != 0:
                    raise ValidationError(_("Carry to next visit must have amount = 0."))
                if rec.due_date:
                    raise ValidationError(_("Do not set a due date when carrying payment to the next visit."))
                if (rec.promise_amount or 0.0) <= 0:
                    raise ValidationError(_("Please set the promise to pay amount."))
                if not rec.promise_date:
                    raise ValidationError(_("Please set the promise to pay date for the next visit."))
                if not rec.note:
                    raise ValidationError(_("Please add a note explaining why payment is carried to next visit."))

    def action_confirm(self):
        for rec in self:
            rec._check_payment_rules()
            rec.state = "confirmed"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"

    def unlink(self):
        for rec in self:
            if rec.state == "confirmed":
                raise ValidationError(_("You cannot delete a confirmed payment."))
        return super().unlink()
