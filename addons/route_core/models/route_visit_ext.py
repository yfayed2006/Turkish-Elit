from odoo import api, fields, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

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

    check_in_datetime = fields.Datetime(string="Check In")
    count_start_datetime = fields.Datetime(string="Count Start")
    count_end_datetime = fields.Datetime(string="Count End")
    reconciliation_datetime = fields.Datetime(string="Reconciliation Time")
    collection_datetime = fields.Datetime(string="Collection Time")
    refill_datetime = fields.Datetime(string="Refill Time")
    check_out_datetime = fields.Datetime(string="Check Out")

    commission_rate = fields.Float(string="Commission %", default=20.0)
    notes = fields.Text(string="Notes")
    collection_skip_reason = fields.Text(string="Collection Skip Reason")
    no_refill = fields.Boolean(string="No Refill")
    no_refill_reason = fields.Text(string="No Refill Reason")
    cancel_reason = fields.Text(string="Cancel Reason")

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

    previous_total_qty = fields.Float(
        string="Previous Total Qty",
        compute="_compute_visit_totals",
        store=True,
    )
    counted_total_qty = fields.Float(
        string="Counted Total Qty",
        compute="_compute_visit_totals",
        store=True,
    )
    returned_total_qty = fields.Float(
        string="Returned Total Qty",
        compute="_compute_visit_totals",
        store=True,
    )
    sold_total_qty = fields.Float(
        string="Sold Total Qty",
        compute="_compute_visit_totals",
        store=True,
    )
    supplied_total_qty = fields.Float(
        string="Supplied Total Qty",
        compute="_compute_visit_totals",
        store=True,
    )
    new_balance_total_qty = fields.Float(
        string="New Balance Total Qty",
        compute="_compute_visit_totals",
        store=True,
    )

    previous_stock_value = fields.Monetary(
        string="Previous Stock Value",
        currency_field="currency_id",
        compute="_compute_visit_totals",
        store=True,
    )
    counted_stock_value = fields.Monetary(
        string="Counted Stock Value",
        currency_field="currency_id",
        compute="_compute_visit_totals",
        store=True,
    )
    gross_sales_amount = fields.Monetary(
        string="Gross Sales Amount",
        currency_field="currency_id",
        compute="_compute_visit_totals",
        store=True,
    )
    return_amount = fields.Monetary(
        string="Return Amount",
        currency_field="currency_id",
        compute="_compute_visit_totals",
        store=True,
    )
    commission_amount = fields.Monetary(
        string="Commission Amount",
        currency_field="currency_id",
        compute="_compute_visit_totals",
        store=True,
    )
    net_due_amount = fields.Monetary(
        string="Net Due Amount",
        currency_field="currency_id",
        compute="_compute_visit_totals",
        store=True,
    )
    collected_amount = fields.Monetary(
        string="Collected Amount",
        currency_field="currency_id",
        compute="_compute_payment_totals",
        store=True,
    )
    remaining_due_amount = fields.Monetary(
        string="Remaining Due Amount",
        currency_field="currency_id",
        compute="_compute_payment_totals",
        store=True,
    )
    supplied_value = fields.Monetary(
        string="Supplied Value",
        currency_field="currency_id",
        compute="_compute_visit_totals",
        store=True,
    )
    new_balance_value = fields.Monetary(
        string="New Balance Value",
        currency_field="currency_id",
        compute="_compute_visit_totals",
        store=True,
    )

    has_collection = fields.Boolean(
        string="Has Collection",
        compute="_compute_flags",
        store=True,
    )
    has_returns = fields.Boolean(
        string="Has Returns",
        compute="_compute_flags",
        store=True,
    )
    has_refill = fields.Boolean(
        string="Has Refill",
        compute="_compute_flags",
        store=True,
    )
    is_ready_to_close = fields.Boolean(
        string="Ready To Close",
        compute="_compute_flags",
        store=True,
    )

    visit_process_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("checked_in", "Checked In"),
            ("counting", "Counting"),
            ("reconciled", "Reconciled"),
            ("collection_done", "Collection Done"),
            ("refill_done", "Refill Done"),
            ("ready_to_close", "Ready To Close"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Visit Process State",
        default="pending",
        tracking=True,
    )

    @api.depends(
        "line_ids.previous_qty",
        "line_ids.counted_qty",
        "line_ids.return_qty",
        "line_ids.sold_qty",
        "line_ids.supplied_qty",
        "line_ids.new_balance_qty",
        "line_ids.previous_value",
        "line_ids.counted_value",
        "line_ids.sold_amount",
        "line_ids.return_amount",
        "line_ids.supply_value",
        "line_ids.new_balance_value",
        "commission_rate",
    )
    def _compute_visit_totals(self):
        for rec in self:
            rec.previous_total_qty = sum(rec.line_ids.mapped("previous_qty"))
            rec.counted_total_qty = sum(rec.line_ids.mapped("counted_qty"))
            rec.returned_total_qty = sum(rec.line_ids.mapped("return_qty"))
            rec.sold_total_qty = sum(rec.line_ids.mapped("sold_qty"))
            rec.supplied_total_qty = sum(rec.line_ids.mapped("supplied_qty"))
            rec.new_balance_total_qty = sum(rec.line_ids.mapped("new_balance_qty"))

            rec.previous_stock_value = sum(rec.line_ids.mapped("previous_value"))
            rec.counted_stock_value = sum(rec.line_ids.mapped("counted_value"))
            rec.gross_sales_amount = sum(rec.line_ids.mapped("sold_amount"))
            rec.return_amount = sum(rec.line_ids.mapped("return_amount"))
            rec.supplied_value = sum(rec.line_ids.mapped("supply_value"))
            rec.new_balance_value = sum(rec.line_ids.mapped("new_balance_value"))

            rec.commission_amount = rec.gross_sales_amount * (rec.commission_rate / 100.0)
            rec.net_due_amount = rec.gross_sales_amount - rec.commission_amount - rec.return_amount

    @api.depends("payment_ids.amount", "payment_ids.state", "net_due_amount")
    def _compute_payment_totals(self):
        for rec in self:
            confirmed = rec.payment_ids.filtered(lambda p: p.state == "confirmed")
            rec.collected_amount = sum(confirmed.mapped("amount"))
            rec.remaining_due_amount = rec.net_due_amount - rec.collected_amount

    @api.depends(
        "payment_ids",
        "payment_ids.state",
        "line_ids.return_qty",
        "line_ids.supplied_qty",
        "line_ids.counted_qty",
        "visit_process_state",
    )
    def _compute_flags(self):
        for rec in self:
            rec.has_collection = any(p.state == "confirmed" for p in rec.payment_ids)
            rec.has_returns = any(qty > 0 for qty in rec.line_ids.mapped("return_qty"))
            rec.has_refill = any(qty > 0 for qty in rec.line_ids.mapped("supplied_qty"))
            rec.is_ready_to_close = bool(rec.line_ids) and (
                rec.visit_process_state in ("refill_done", "ready_to_close", "done")
            )

    def action_load_previous_balance(self):
        OutletStockBalance = self.env["outlet.stock.balance"]
        RouteVisitLine = self.env["route.visit.line"]

        for rec in self:
            if not rec.outlet_id:
                raise UserError("Please set an outlet before loading previous balance.")

            if rec.line_ids:
                raise UserError(
                    "This visit already has lines. Remove existing lines first if you want to reload previous balance."
                )

            balances = OutletStockBalance.search([
                ("outlet_id", "=", rec.outlet_id.id),
                ("qty", ">", 0),
            ])

            if not balances:
                raise UserError("No previous stock balance was found for this outlet.")

            if hasattr(rec.outlet_id, "default_commission_rate") and rec.outlet_id.default_commission_rate:
                rec.commission_rate = rec.outlet_id.default_commission_rate

            line_vals_list = []
            for balance in balances:
                line_vals_list.append({
                    "visit_id": rec.id,
                    "company_id": rec.company_id.id,
                    "product_id": balance.product_id.id,
                    "previous_qty": balance.qty,
                    "unit_price": balance.unit_price,
                })

            RouteVisitLine.create(line_vals_list)

            vals = {}
            if rec.visit_process_state == "pending":
                vals["visit_process_state"] = "checked_in"
            if not rec.check_in_datetime:
                vals["check_in_datetime"] = fields.Datetime.now()

            if vals:
                rec.write(vals)

    def action_set_checked_in(self):
        for rec in self:
            rec.write({
                "visit_process_state": "checked_in",
                "check_in_datetime": fields.Datetime.now(),
            })

    def action_set_counting(self):
        for rec in self:
            rec.write({
                "visit_process_state": "counting",
                "count_start_datetime": fields.Datetime.now(),
            })

    def action_set_reconciled(self):
        for rec in self:
            rec.write({
                "visit_process_state": "reconciled",
                "count_end_datetime": rec.count_end_datetime or fields.Datetime.now(),
                "reconciliation_datetime": fields.Datetime.now(),
            })

    def action_set_collection_done(self):
        for rec in self:
            rec.write({
                "visit_process_state": "collection_done",
                "collection_datetime": fields.Datetime.now(),
            })

    def action_set_refill_done(self):
        for rec in self:
            rec.write({
                "visit_process_state": "refill_done",
                "refill_datetime": fields.Datetime.now(),
            })

    def action_set_ready_to_close(self):
        for rec in self:
            rec.write({
                "visit_process_state": "ready_to_close",
            })

    def action_set_done_process(self):
        for rec in self:
            rec.write({
                "visit_process_state": "done",
                "check_out_datetime": fields.Datetime.now(),
            })

    def action_set_cancelled_process(self):
        for rec in self:
            rec.write({
                "visit_process_state": "cancelled",
            })
