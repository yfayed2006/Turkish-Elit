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

    return_picking_ids = fields.Many2many(
        "stock.picking",
        "route_visit_return_picking_rel",
        "visit_id",
        "picking_id",
        string="Return Transfers",
        copy=False,
        readonly=True,
    )

    return_picking_count = fields.Integer(
        string="Return Transfer Count",
        compute="_compute_return_picking_count",
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
    near_expiry_threshold_days = fields.Integer(
        string="Near Expiry Threshold (Days)",
        default=60,
        help="Products with expiry dates within this number of days will be flagged as near expiry during the visit.",
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

    @api.depends("return_picking_ids")
    def _compute_return_picking_count(self):
        for rec in self:
            rec.return_picking_count = len(rec.return_picking_ids)

    def _get_outlet_default_commission_rate(self):
        self.ensure_one()
        if not self.outlet_id:
            return 0.0
        if hasattr(self.outlet_id, "default_commission_rate"):
            return self.outlet_id.default_commission_rate or 0.0
        if hasattr(self.outlet_id, "commission_rate"):
            return self.outlet_id.commission_rate or 0.0
        return 0.0

    @api.onchange("outlet_id")
    def _onchange_outlet_id_set_defaults(self):
        for rec in self:
            if rec.outlet_id:
                rec.commission_rate = rec._get_outlet_default_commission_rate()
                if hasattr(rec.outlet_id, "partner_id") and rec.outlet_id.partner_id:
                    rec.partner_id = rec.outlet_id.partner_id.commercial_partner_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("outlet_id"):
                outlet = self.env["route.outlet"].browse(vals["outlet_id"])
                if outlet.exists():
                    if not vals.get("partner_id") and hasattr(outlet, "partner_id") and outlet.partner_id:
                        vals["partner_id"] = outlet.partner_id.commercial_partner_id.id

                    if not vals.get("commission_rate"):
                        if hasattr(outlet, "default_commission_rate"):
                            vals["commission_rate"] = outlet.default_commission_rate or 0.0
                        elif hasattr(outlet, "commission_rate"):
                            vals["commission_rate"] = outlet.commission_rate or 0.0

        return super().create(vals_list)

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
            rec.net_due_amount = rec.gross_sales_amount - rec.commission_amount

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
        "return_picking_ids",
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

        if not self.refill_backorder_id and self.has_pending_refill:
            self._create_pending_refill_backorder()

        if not self.refill_backorder_id:
            raise UserError("There is no pending refill linked to this visit.")

        action = self.env.ref("route_core.action_route_refill_backorder").read()[0]
        action["res_id"] = self.refill_backorder_id.id
        action["views"] = [(False, "form")]
        return action

    def action_view_return_transfers(self):
        self.ensure_one()

        if not self.return_picking_ids:
            raise UserError("There are no return transfers linked to this visit.")

        action = self.env.ref("stock.action_picking_tree_all").read()[0]

        if len(self.return_picking_ids) == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = self.return_picking_ids.id
        else:
            action["domain"] = [("id", "in", self.return_picking_ids.ids)]

        return action

    def _set_main_visit_state_in_progress(self):
        for rec in self:
            vals = {}
            if rec.state != "in_progress":
                vals["state"] = "in_progress"
            if not rec.start_datetime:
                vals["start_datetime"] = fields.Datetime.now()
            if vals:
                rec.with_context(route_visit_force_write=True).write(vals)

    def _set_main_visit_state_done(self):
        for rec in self:
            vals = {
                "state": "done",
                "end_datetime": fields.Datetime.now(),
            }
            rec.with_context(route_visit_force_write=True).write(vals)

    def _set_main_visit_state_cancel(self):
        for rec in self:
            vals = {
                "state": "cancel",
                "end_datetime": fields.Datetime.now(),
            }
            rec.with_context(route_visit_force_write=True).write(vals)

    def _get_available_qty_in_source_location(self, product):
        self.ensure_one()
        if not self.source_location_id:
            return 0.0

        quants = self.env["stock.quant"].search([
            ("location_id", "child_of", self.source_location_id.id),
            ("product_id", "=", product.id),
        ])
        return sum(quants.mapped("quantity"))

    def _get_return_source_location(self):
        self.ensure_one()

        if not self.outlet_id or not getattr(self.outlet_id, "stock_location_id", False):
            raise UserError("The selected outlet does not have a stock location for return transfer source.")

        return self.outlet_id.stock_location_id

    def _get_return_destination_location(self, return_route):
        self.ensure_one()

        if return_route == "vehicle":
            if not self.vehicle_id or not self.vehicle_id.stock_location_id:
                raise UserError(
                    "The selected vehicle does not have a stock location for return transfer destination."
                )
            return self.vehicle_id.stock_location_id

        if return_route == "damaged":
            if not self.company_id.return_damaged_location_id:
                raise UserError("Return Damaged Location is not configured on the company.")
            return self.company_id.return_damaged_location_id

        if return_route == "near_expiry":
            if not self.company_id.return_near_expiry_location_id:
                raise UserError("Return Near Expiry Location is not configured on the company.")
            return self.company_id.return_near_expiry_location_id

        raise UserError("Invalid return route.")

    def _get_internal_picking_type(self):
        self.ensure_one()

        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_id.id)],
            limit=1,
        )
        if warehouse and warehouse.int_type_id:
            return warehouse.int_type_id

        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                ("warehouse_id.company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if picking_type:
            return picking_type

        raise UserError("No Internal Transfer operation type was found for this company.")

    def _get_return_lines_grouped_by_route(self):
        self.ensure_one()

        grouped = {}
        return_lines = self.line_ids.filtered(lambda l: (l.return_qty or 0.0) > 0)

        for line in return_lines:
            route = line.return_route or "vehicle"
            grouped.setdefault(route, self.env["route.visit.line"])
            grouped[route] |= line

        return grouped

    def _create_return_transfer_for_route(self, return_route, lines):
        self.ensure_one()

        if not lines:
            return False

        source_location = self._get_return_source_location()
        dest_location = self._get_return_destination_location(return_route)
        picking_type = self._get_internal_picking_type()

        route_label_map = {
            "vehicle": "Vehicle Return",
            "damaged": "Damaged Return",
            "near_expiry": "Near Expiry Return",
        }
        route_label = route_label_map.get(return_route, "Return")

        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": f"{self.name} - {route_label}",
            "move_type": "direct",
            "route_visit_id": self.id,
        })

        created_moves = self.env["stock.move"]

        for line in lines:
            if not line.product_id or (line.return_qty or 0.0) <= 0:
                continue

            move = self.env["stock.move"].create({
                "product_id": line.product_id.id,
                "product_uom_qty": line.return_qty,
                "product_uom": line.uom_id.id,
                "picking_id": picking.id,
                "location_id": source_location.id,
                "location_dest_id": dest_location.id,
                "company_id": self.company_id.id,
                "origin": f"{self.name} - {route_label}",
            })
            created_moves |= move

        if not created_moves:
            picking.unlink()
            return False

        picking.action_confirm()
        picking.action_assign()
        return picking

    def action_confirm_return_transfers(self):
        for rec in self:
            if rec.visit_process_state != "reconciled":
                raise UserError("Return transfers can only be confirmed when the visit is in Reconciled state.")

            if rec.return_picking_ids:
                raise UserError("Return transfers have already been created for this visit.")

            return_lines = rec.line_ids.filtered(lambda l: (l.return_qty or 0.0) > 0)
            if not return_lines:
                raise UserError("There are no returned quantities on this visit.")

            grouped_lines = rec._get_return_lines_grouped_by_route()
            created_pickings = self.env["stock.picking"]

            for return_route, lines in grouped_lines.items():
                picking = rec._create_return_transfer_for_route(return_route, lines)
                if picking:
                    created_pickings |= picking

            if not created_pickings:
                raise UserError("No return transfers were created from the current visit lines.")

            rec.return_picking_ids = [(6, 0, created_pickings.ids)]
            rec._set_main_visit_state_in_progress()

        return True

    def _create_pending_refill_backorder(self):
        self.ensure_one()

        pending_lines = self.line_ids.filtered(lambda l: l.pending_refill_qty > 0)
        if not pending_lines:
            return False

        if self.refill_backorder_id:
            return self.refill_backorder_id

        partner = self.partner_id
        if not partner and self.outlet_id and hasattr(self.outlet_id, "partner_id"):
            partner = self.outlet_id.partner_id
        if partner and hasattr(partner, "commercial_partner_id"):
            partner = partner.commercial_partner_id

        if not partner:
            raise UserError(
                "Cannot create Pending Refill because Customer is empty on this visit.\n"
                "Please set a customer on the visit or ensure the outlet is linked to a customer."
            )

        backorder = self.env["route.refill.backorder"].create({
            "visit_id": self.id,
            "outlet_id": self.outlet_id.id,
            "partner_id": partner.id,
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

            rec.commission_rate = rec._get_outlet_default_commission_rate()

            if not rec.partner_id and hasattr(rec.outlet_id, "partner_id") and rec.outlet_id.partner_id:
                rec.partner_id = rec.outlet_id.partner_id.commercial_partner_id

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
            rec._set_main_visit_state_in_progress()

    def action_generate_refill_proposal(self):
        for rec in self:
            if rec.visit_process_state != "reconciled":
                raise UserError("Refill proposal can only be generated when the visit is in Reconciled state.")

            if not rec.line_ids:
                raise UserError("There are no visit lines to generate a refill proposal.")

            if not rec.source_location_id:
                raise UserError("Please select Source Location before generating refill proposal.")

            rec._set_main_visit_state_in_progress()

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

            confirmed_payments = rec.payment_ids.filtered(lambda p: p.state == "confirmed")
            has_deferred_record = bool(
                confirmed_payments.filtered(
                    lambda p: p.collection_type in ("partial", "defer_date", "next_visit")
                )
            )

            if rec.remaining_due_amount > 0 and not has_deferred_record and not rec.collection_skip_reason:
                raise UserError(
                    "There is still a remaining due amount. Please either collect it fully, "
                    "add a partial payment with carry forward, defer it to a specific date, "
                    "or carry it to the next visit."
                )

            rec.write({
                "visit_process_state": "collection_done",
                "collection_datetime": fields.Datetime.now(),
            })
            rec._set_main_visit_state_in_progress()

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
            rec._set_main_visit_state_in_progress()

    def action_update_outlet_balance(self):
        OutletStockBalance = self.env["outlet.stock.balance"]

        for rec in self:
            if rec.visit_process_state != "collection_done":
                raise UserError("Outlet balance can only be updated after collection is completed.")

            if rec.has_returns and not rec.return_picking_ids:
                raise UserError("Please confirm return transfers before updating outlet balance.")

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
            rec._set_main_visit_state_in_progress()

    def action_set_checked_in(self):
        for rec in self:
            if rec.visit_process_state != "pending":
                raise UserError("Check In is only allowed while the visit is Pending.")

            rec.write({
                "visit_process_state": "checked_in",
                "check_in_datetime": fields.Datetime.now(),
            })
            rec._set_main_visit_state_in_progress()

    def action_set_counting(self):
        for rec in self:
            if rec.visit_process_state != "checked_in":
                raise UserError("Start Count is only allowed after Check In.")

            rec.write({
                "visit_process_state": "counting",
                "count_start_datetime": fields.Datetime.now(),
            })
            rec._set_main_visit_state_in_progress()

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
            rec._set_main_visit_state_in_progress()

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
            rec._set_main_visit_state_done()

    def action_set_cancelled_process(self):
        for rec in self:
            if rec.visit_process_state == "done":
                raise UserError("You cannot cancel a visit that is already Done.")

            rec.write({
                "visit_process_state": "cancelled",
                "cancel_reason": rec.cancel_reason or "Cancelled by user",
                "check_out_datetime": fields.Datetime.now(),
            })
            rec._set_main_visit_state_cancel()
