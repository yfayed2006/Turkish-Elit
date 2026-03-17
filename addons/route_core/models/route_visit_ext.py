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
    source_location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        domain="[('usage', '=', 'internal')]",
    )
    refill_backorder_id = fields.Many2one(
        "route.refill.backorder",
        string="Pending Refill",
        readonly=True,
        copy=False,
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
    pending_refill_total_qty = fields.Float(
        string="Pending Refill Total Qty",
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
    has_pending_refill = fields.Boolean(
        string="Has Pending Refill",
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
        "line_ids.pending_refill_qty",
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
            rec.pending_refill_total_qty = sum(rec.line_ids.mapped("pending_refill_qty"))
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
        "line_ids.pending_refill_qty",
        "visit_process_state",
        "collection_skip_reason",
        "refill_datetime",
    )
    def _compute_flags(self):
        for rec in self:
            rec.has_collection = any(p.state == "confirmed" for p in rec.payment_ids)
            rec.has_returns = any(qty > 0 for qty in rec.line_ids.mapped("return_qty"))
            rec.has_refill = any(qty > 0 for qty in rec.line_ids.mapped("supplied_qty"))
            rec.has_pending_refill = any(qty > 0 for qty in rec.line_ids.mapped("pending_refill_qty"))
            rec.is_ready_to_close = bool(rec.line_ids) and bool(rec.refill_datetime) and (
                rec.has_collection or bool(rec.collection_skip_reason)
            )

    def action_view_pending_refill(self):
        self.ensure_one()
        if not self.refill_backorder_id:
            raise UserError("There is no pending refill document linked to this visit.")

        action = self.env.ref("route_core.action_route_refill_backorder").read()[0]
        action["res_id"] = self.refill_backorder_id.id
        action["views"] = [(False, "form")]
        return action

    def _get_available_qty_in_source_location(self, product):
        self.ensure_one()
        if not self.source_location_id:
            return 0.0
        quants = self.env["stock.quant"].search([
            ("location_id", "child_of", self.source_location_id.id),
            ("product_id", "=", product.id),
        ])
        return sum(quants.mapped("quantity"))

    def _create_pending_refill_backorder(self):
        self.ensure_one()
        pending_lines = self.line_ids.filtered(lambda l: l.pending_refill_qty > 0)
        if not pending_lines:
            return False
        if self.refill_backorder_id:
            return self.refill_backorder_id

        backorder = self.env["route.refill.backorder"].create({
            "visit_id": self.id,
            "outlet_id": self.outlet_id.id,
            "partner_id": self.partner_id.id,
            "vehicle_id": self.vehicle_id.id if self.vehicle_id else False,
            "source_location_id": self.source_location_id.id if self.source_location_id else False,
            "company_id": self.company_id.id,
            "note": "Created automatically from route visit pending refill.",
        })

        line_vals = []
        for line in pending_lines:
            line_vals.append({
                "backorder_id": backorder.id,
                "product_id": line.product_id.id,
                "needed_qty": line.sold_qty,
                "available_qty_at_visit": line.vehicle_available_qty,
                "delivered_qty": line.supplied_qty,
                "pending_qty": line.pending_refill_qty,
                "unit_price": line.unit_price,
                "note": line.note,
            })
        self.env["route.refill.backorder.line"].create(line_vals)
        self.refill_backorder_id = backorder.id
        return backorder

    def action_load_previous_balance(self):
        OutletStockBalance = self.env["outlet.stock.balance"]
        RouteVisitLine = self.env["route.visit.line"]

        for rec in self:
            if rec.visit_process_state not in ("pending",):
                raise UserError("Previous balance can only be loaded while the visit is Pending.")
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

            rec.write({
                "visit_process_state": "checked_in",
                "check_in_datetime": rec.check_in_datetime or fields.Datetime.now(),
            })

    def action_generate_refill_proposal(self):
        for rec in self:
            if rec.visit_process_state != "reconciled":
                raise UserError("Refill proposal can only be generated when the visit is in Reconciled state.")
            if not rec.line_ids:
                raise UserError("There are no visit lines to generate a refill proposal.")
            if not rec.source_location_id:
                raise UserError("Please select Source Location before generating refill proposal.")

            for line in rec.line_ids:
                available_qty = rec._get_available_qty_in_source_location(line.product_id)
                proposed_qty = min(line.sold_qty, available_qty) if line.sold_qty > 0 else 0.0
                line.write({
                    "vehicle_available_qty": available_qty,
                    "supplied_qty": proposed_qty,
                })

    def action_confirm_all_payments(self):
        for rec in self:
            if rec.visit_process_state != "reconciled":
                raise UserError("Payments can only be confirmed when the visit is in Reconciled state.")
            if not rec.payment_ids:
                raise UserError("There are no payments on this visit.")

            draft_payments = rec.payment_ids.filtered(lambda p: p.state == "draft")
            if not draft_payments:
                raise UserError("There are no draft payments to confirm on this visit.")

            for payment in draft_payments:
                payment.action_confirm()

            rec.write({
                "visit_process_state": "collection_done",
                "collection_datetime": fields.Datetime.now(),
            })

    def action_skip_collection(self):
        for rec in self:
            if rec.visit_process_state != "reconciled":
                raise UserError("Collection can only be skipped when the visit is in Reconciled state.")
            if not rec.collection_skip_reason:
                raise UserError("Please enter Collection Skip Reason before skipping collection.")

            rec.write({
                "visit_process_state": "collection_done",
                "collection_datetime": fields.Datetime.now(),
            })

    def action_update_outlet_balance(self):
        OutletStockBalance = self.env["outlet.stock.balance"]

        for rec in self:
            if rec.visit_process_state != "collection_done":
                raise UserError("Outlet balance can only be updated after collection is completed.")
            if not rec.outlet_id:
                raise UserError("Please set an outlet before updating outlet balance.")
            if not rec.line_ids:
                raise UserError("There are no visit lines to update.")

            for line in rec.line_ids:
                balance = OutletStockBalance.search(
                    [
                        ("outlet_id", "=", rec.outlet_id.id),
                        ("product_id", "=", line.product_id.id),
                    ],
                    limit=1,
                )
                vals = {
                    "qty": line.new_balance_qty,
                    "unit_price": line.unit_price,
                    "last_visit_id": rec.id,
                }
                if balance:
                    balance.write(vals)
                else:
                    OutletStockBalance.create({
                        "outlet_id": rec.outlet_id.id,
                        "product_id": line.product_id.id,
                        "qty": line.new_balance_qty,
                        "unit_price": line.unit_price,
                        "last_visit_id": rec.id,
                        "company_id": rec.company_id.id,
                    })

            rec.write({
                "visit_process_state": "ready_to_close",
                "refill_datetime": fields.Datetime.now(),
            })

    def action_set_checked_in(self):
        for rec in self:
            if rec.visit_process_state != "pending":
                raise UserError("Check In is only allowed while the visit is Pending.")
            rec.write({
                "visit_process_state": "checked_in",
                "check_in_datetime": fields.Datetime.now(),
            })

    def action_set_counting(self):
        for rec in self:
            if rec.visit_process_state != "checked_in":
                raise UserError("Start Count is only allowed after Check In.")
            rec.write({
                "visit_process_state": "counting",
                "count_start_datetime": fields.Datetime.now(),
            })

    def action_set_reconciled(self):
        for rec in self:
            if rec.visit_process_state != "counting":
                raise UserError("Reconcile is only allowed while the visit is in Counting state.")
            if not rec.line_ids:
                raise UserError("You cannot reconcile a visit without visit lines.")

            rec.write({
                "visit_process_state": "reconciled",
                "count_end_datetime": rec.count_end_datetime or fields.Datetime.now(),
                "reconciliation_datetime": fields.Datetime.now(),
            })

    def action_set_done_process(self):
        for rec in self:
            if rec.visit_process_state != "ready_to_close":
                raise UserError("Finish Process is only allowed when the visit is Ready To Close.")

            if rec.has_pending_refill and not rec.refill_backorder_id:
                rec._create_pending_refill_backorder()

            rec.write({
                "visit_process_state": "done",
                "check_out_datetime": fields.Datetime.now(),
            })

    def action_set_cancelled_process(self):
        for rec in self:
            if rec.visit_process_state == "done":
                raise UserError("You cannot cancel a visit that is already Done.")
            rec.write({"visit_process_state": "cancelled"})
