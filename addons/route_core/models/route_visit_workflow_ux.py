import re
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    first_consignment_empty_balance = fields.Boolean(
        string="First Consignment Empty Balance",
        default=False,
        copy=False,
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
    outlet_operation_mode = fields.Selection(
        related="outlet_id.outlet_operation_mode",
        readonly=True,
        store=False,
    )
    visit_execution_mode = fields.Selection(
        [("consignment", "Consignment Visit"), ("direct_sales", "Direct Sales Stop")],
        compute="_compute_visit_execution_mode",
        store=False,
    )
    visit_execution_mode_label = fields.Char(
        compute="_compute_visit_execution_mode",
        store=False,
    )
    ux_stage = fields.Selection(
        [
            ("arrival", "Arrival"),
            ("load_balance", "Load Balance"),
            ("count", "Count Shelf"),
            ("returns", "Returns"),
            ("reconcile", "Reconcile"),
            ("return_transfer", "Return Transfer"),
            ("refill", "Refill"),
            ("collection", "Collection"),
            ("ready_to_close", "Ready to Close"),
            ("done", "Done"),
        ],
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_primary_action = fields.Selection(
        [
            ("start_visit", "Start Visit"),
            ("load_previous_balance", "Load Previous Balance"),
            ("scan_shelf", "Scan Shelf"),
            ("returns_step", "Scan Returns"),
            ("reconcile_count", "Reconcile Count"),
            ("confirm_return_transfers", "Confirm Return Transfers"),
            ("generate_refill", "Generate Refill Proposal"),
            ("confirm_refill", "Confirm Refill"),
            ("open_pending_refill", "Open Pending Refill"),
            ("collect_payment", "Collect Payment"),
            ("confirm_payments", "Confirm Payments"),
            ("direct_sale_decision", "Direct Sale Decision"),
            ("direct_return_decision", "Direct Return Decision"),
            ("finalize_visit", "Finalize Visit"),
            ("finish_visit", "Finish Visit"),
            ("none", "No Action"),
        ],
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_stage_title = fields.Char(compute="_compute_ux_workflow", store=False)
    ux_stage_help = fields.Char(compute="_compute_ux_workflow", store=False)

    ux_can_scan_barcode = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_scan_returns = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_no_returns = fields.Boolean(compute="_compute_ux_workflow", store=False)

    ux_can_create_sale_order = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_view_sale_order = fields.Boolean(compute="_compute_ux_workflow", store=False)

    ux_can_confirm_return_transfers = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_view_return_transfers = fields.Boolean(compute="_compute_ux_workflow", store=False)

    ux_can_generate_refill = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_confirm_refill = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_view_refill_transfer = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_pending_refill = fields.Boolean(compute="_compute_ux_workflow", store=False)

    ux_can_collect_payment = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_confirm_payments = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_skip_collection = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_payments = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_review_settlement = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_receipt_actions = fields.Boolean(compute="_compute_ux_workflow", store=False)

    direct_stop_settlement_reviewed = fields.Boolean(
        string="Direct Stop Settlement Reviewed",
        default=False,
        copy=False,
    )

    ux_can_create_direct_sale = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_direct_sale_orders = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_direct_sale_payments = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_create_direct_return = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_direct_returns = fields.Boolean(compute="_compute_ux_workflow", store=False)

    ux_can_no_sale = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_no_return = fields.Boolean(compute="_compute_ux_workflow", store=False)

    ux_can_finish_visit = fields.Boolean(compute="_compute_ux_workflow", store=False)

    refill_credit_warning_visible = fields.Boolean(
        compute="_compute_refill_credit_warning",
        store=False,
    )
    refill_credit_warning_level = fields.Selection(
        [
            ("warning", "Warning"),
            ("danger", "Danger"),
        ],
        compute="_compute_refill_credit_warning",
        store=False,
    )
    refill_credit_warning_text = fields.Text(
        compute="_compute_refill_credit_warning",
        store=False,
    )

    summary_sale_order_ref = fields.Char(
        string="Sale Order Ref",
        compute="_compute_consignment_document_refs",
        store=False,
    )
    summary_refill_transfer_ref = fields.Char(
        string="Refill Transfer Ref",
        compute="_compute_consignment_document_refs",
        store=False,
    )
    summary_return_transfer_refs = fields.Char(
        string="Return Transfer Refs",
        compute="_compute_consignment_document_refs",
        store=False,
    )
    consignment_previous_due_amount = fields.Monetary(
        string="Previous Due",
        currency_field="currency_id",
        compute="_compute_consignment_financial_snapshot",
        store=False,
    )
    consignment_current_visit_sale_amount = fields.Monetary(
        string="Current Visit Sale",
        currency_field="currency_id",
        compute="_compute_consignment_financial_snapshot",
        store=False,
    )
    consignment_current_visit_return_amount = fields.Monetary(
        string="Current Visit Returns",
        currency_field="currency_id",
        compute="_compute_consignment_financial_snapshot",
        store=False,
    )
    consignment_net_amount_for_visit = fields.Monetary(
        string="Net Amount For This Visit",
        currency_field="currency_id",
        compute="_compute_consignment_financial_snapshot",
        store=False,
    )
    consignment_amount_due_now = fields.Monetary(
        string="Total Outlet Due",
        currency_field="currency_id",
        compute="_compute_consignment_financial_snapshot",
        store=False,
    )
    consignment_immediate_remaining_amount = fields.Monetary(
        string="Current Visit Remaining",
        currency_field="currency_id",
        compute="_compute_consignment_financial_snapshot",
        store=False,
    )
    consignment_promise_amount = fields.Monetary(
        string="Promise Amount",
        currency_field="currency_id",
        compute="_compute_consignment_financial_snapshot",
        store=False,
    )
    direct_stop_immediate_remaining_amount = fields.Monetary(
        string="Remaining After Collection",
        currency_field="currency_id",
        compute="_compute_direct_stop_financial_snapshot",
        store=False,
    )
    direct_stop_open_promise_amount = fields.Monetary(
        string="Promise Amount",
        currency_field="currency_id",
        compute="_compute_direct_stop_financial_snapshot",
        store=False,
    )
    direct_stop_latest_promise_date = fields.Date(
        string="Next Promise Date",
        compute="_compute_direct_stop_financial_snapshot",
        store=False,
    )
    direct_stop_latest_promise_status = fields.Selection(
        [
            ("open", "Open"),
            ("due_today", "Due Today"),
            ("overdue", "Overdue"),
            ("closed", "Closed"),
        ],
        string="Latest Promise Status",
        compute="_compute_direct_stop_financial_snapshot",
        store=False,
    )


    resolved_supervisor_user_id = fields.Many2one(
        "res.users",
        string="Resolved Supervisor User",
        compute="_compute_resolved_supervisor_info",
        store=False,
    )
    resolved_supervisor_partner_id = fields.Many2one(
        "res.partner",
        string="Resolved Supervisor",
        compute="_compute_resolved_supervisor_info",
        store=False,
    )
    resolved_supervisor_phone = fields.Char(
        string="Supervisor WhatsApp",
        compute="_compute_resolved_supervisor_info",
        store=False,
    )
    resolved_supervisor_reason = fields.Text(
        string="Supervisor Match Reason",
        compute="_compute_resolved_supervisor_info",
        store=False,
    )
    resolved_supervisor_status = fields.Char(
        string="Supervisor Resolution Status",
        compute="_compute_resolved_supervisor_info",
        store=False,
    )

    @api.depends(
        "visit_execution_mode",
        "direct_stop_grand_due_amount",
        "direct_stop_settlement_paid_amount",
        "direct_stop_settlement_remaining_amount",
        "settlement_payment_ids.amount",
        "settlement_payment_ids.promise_amount",
        "settlement_payment_ids.promise_date",
        "settlement_payment_ids.state",
        "settlement_payment_ids.collection_type",
    )
    def _compute_direct_stop_financial_snapshot(self):
        for rec in self:
            rec.direct_stop_immediate_remaining_amount = 0.0
            rec.direct_stop_open_promise_amount = 0.0
            rec.direct_stop_latest_promise_date = False
            rec.direct_stop_latest_promise_status = False

            if rec.visit_execution_mode != "direct_sales":
                continue

            summary = rec._get_direct_stop_receipt_summary() if rec.id else {}
            rec.direct_stop_immediate_remaining_amount = summary.get("immediate_remaining_amount", 0.0)
            rec.direct_stop_open_promise_amount = summary.get("promise_amount", 0.0)
            rec.direct_stop_latest_promise_date = summary.get("latest_promise_date", False)
            rec.direct_stop_latest_promise_status = summary.get("latest_promise_status", False)

    @api.depends("company_id", "user_id", "vehicle_id", "outlet_id", "outlet_id.area_id")
    def _compute_resolved_supervisor_info(self):
        for rec in self:
            resolution = rec._get_route_supervisor_resolution()
            rec.resolved_supervisor_user_id = resolution["user"]
            rec.resolved_supervisor_partner_id = resolution["partner"]
            rec.resolved_supervisor_phone = resolution["phone"]
            rec.resolved_supervisor_reason = resolution["reason"]
            rec.resolved_supervisor_status = resolution["status"]

    @api.depends(
        "visit_process_state",
        "outlet_id",
        "outlet_id.shelf_credit_limit_amount",
        "outlet_id.stock_total_value",
        "line_ids.supplied_qty",
        "line_ids.unit_price",
        "refill_datetime",
        "refill_picking_id",
    )
    def _compute_refill_credit_warning(self):
        for rec in self:
            rec.refill_credit_warning_visible = False
            rec.refill_credit_warning_level = False
            rec.refill_credit_warning_text = False

            if rec.visit_process_state != "reconciled":
                continue

            outlet = rec.outlet_id
            if not outlet:
                continue

            limit_amount = outlet.shelf_credit_limit_amount or 0.0
            if limit_amount <= 0:
                continue

            current_shelf_value = outlet.stock_total_value or 0.0

            if hasattr(rec, "_get_refill_total_value"):
                refill_value = rec._get_refill_total_value()
            else:
                refill_value = sum(
                    (line.supplied_qty or 0.0) * (line.unit_price or 0.0)
                    for line in rec.line_ids
                    if (line.supplied_qty or 0.0) > 0
                )

            projected_shelf_value = current_shelf_value + refill_value
            available_capacity = max(limit_amount - current_shelf_value, 0.0)

            if projected_shelf_value > limit_amount and refill_value > 0:
                rec.refill_credit_warning_visible = True
                rec.refill_credit_warning_level = "danger"
                rec.refill_credit_warning_text = _(
                    "Outlet shelf credit limit will be exceeded.\n"
                    "Outlet: %(outlet)s\n"
                    "Current shelf value: %(current).2f\n"
                    "Refill value: %(refill).2f\n"
                    "Projected shelf value: %(projected).2f\n"
                    "Shelf credit limit: %(limit).2f\n"
                    "Available capacity before refill: %(available).2f\n"
                    "Over limit by: %(over).2f"
                ) % {
                    "outlet": outlet.display_name,
                    "current": current_shelf_value,
                    "refill": refill_value,
                    "projected": projected_shelf_value,
                    "limit": limit_amount,
                    "available": available_capacity,
                    "over": max(projected_shelf_value - limit_amount, 0.0),
                }
            elif current_shelf_value > limit_amount:
                rec.refill_credit_warning_visible = True
                rec.refill_credit_warning_level = "warning"
                rec.refill_credit_warning_text = _(
                    "Outlet is already over shelf credit limit.\n"
                    "Outlet: %(outlet)s\n"
                    "Current shelf value: %(current).2f\n"
                    "Shelf credit limit: %(limit).2f\n"
                    "Over limit by: %(over).2f"
                ) % {
                    "outlet": outlet.display_name,
                    "current": current_shelf_value,
                    "limit": limit_amount,
                    "over": max(current_shelf_value - limit_amount, 0.0),
                }

    @api.depends("route_operation_mode", "outlet_operation_mode")
    def _compute_visit_execution_mode(self):
        labels = {
            "consignment": _("Consignment Visit"),
            "direct_sales": _("Direct Sales Stop"),
        }
        for rec in self:
            mode = rec.route_operation_mode or "hybrid"
            execution_mode = "consignment"
            if mode == "direct_sales":
                execution_mode = "direct_sales"
            elif mode == "hybrid" and rec.outlet_operation_mode == "direct_sale":
                execution_mode = "direct_sales"
            rec.visit_execution_mode = execution_mode
            rec.visit_execution_mode_label = labels.get(execution_mode, labels["consignment"])

    def _is_direct_sales_stop(self):
        self.ensure_one()
        return self.visit_execution_mode == "direct_sales"

    @api.depends(
        "state",
        "visit_process_state",
        "first_consignment_empty_balance",
        "route_operation_mode",
        "route_enable_direct_sale",
        "route_enable_direct_return",
        "outlet_operation_mode",
        "sale_order_id",
        "sale_order_count",
        "payment_ids.state",
        "payment_ids.amount",
        "collection_skip_reason",
        "has_pending_refill",
        "has_refill",
        "has_returns",
        "no_refill",
        "refill_backorder_id",
        "refill_datetime",
        "returns_step_done",
        "refill_picking_id",
        "refill_picking_count",
        "return_picking_ids",
        "return_picking_count",
        "remaining_due_amount",
        "line_ids.product_id",
        "line_ids.previous_qty",
        "line_ids.counted_qty",
        "line_ids.supplied_qty",
        "line_ids.return_qty",
    )
    def _compute_ux_workflow(self):
        for rec in self:
            direct_sales_stop = rec.visit_execution_mode == "direct_sales"
            has_lines = bool(rec.line_ids)
            has_supplied_qty = any((line.supplied_qty or 0.0) > 0 for line in rec.line_ids)
            has_return_qty = any((line.return_qty or 0.0) > 0 for line in rec.line_ids)
            has_return_transfers = bool(rec.return_picking_ids or rec.return_picking_count)

            load_balance_required = (
                rec.state == "in_progress"
                and rec.visit_process_state == "checked_in"
                and not has_lines
                and not rec.first_consignment_empty_balance
            )

            can_enter_collection = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and (
                    bool(rec.refill_picking_id)
                    or bool(rec.no_refill)
                    or (bool(rec.refill_datetime) and not has_supplied_qty)
                )
            )

            has_draft_payments = bool(rec.payment_ids.filtered(lambda p: p.state == "draft"))
            has_confirmed_payments = bool(rec.payment_ids.filtered(lambda p: p.state == "confirmed"))
            no_due_to_collect = (rec.remaining_due_amount or 0.0) <= 0.0

            # defaults
            rec.ux_can_scan_barcode = False
            rec.ux_can_scan_returns = False
            rec.ux_can_no_returns = False
            rec.ux_can_create_sale_order = False
            rec.ux_can_view_sale_order = bool(rec.sale_order_id or rec.sale_order_count)
            rec.ux_can_confirm_return_transfers = False
            rec.ux_can_view_return_transfers = has_return_transfers
            rec.ux_can_generate_refill = False
            rec.ux_can_confirm_refill = False
            rec.ux_can_view_refill_transfer = bool(rec.refill_picking_id or rec.refill_picking_count)
            rec.ux_can_open_pending_refill = bool(rec.has_pending_refill or rec.refill_backorder_id)
            rec.ux_can_collect_payment = False
            rec.ux_can_confirm_payments = False
            rec.ux_can_skip_collection = False
            rec.ux_can_open_payments = False
            rec.ux_can_review_settlement = False
            rec.ux_can_receipt_actions = False
            rec.ux_can_create_direct_sale = False
            rec.ux_can_open_direct_sale_orders = False
            rec.ux_can_open_direct_sale_payments = False
            rec.ux_can_create_direct_return = False
            rec.ux_can_open_direct_returns = False
            rec.ux_can_no_sale = False
            rec.ux_can_no_return = False
            rec.ux_can_finish_visit = False

            if direct_sales_stop:
                sale_orders = rec._get_direct_stop_sale_orders() if rec.id else self.env["sale.order"]
                direct_returns = rec._get_direct_stop_returns() if rec.id else self.env["route.direct.return"]
                sales_answered = bool(sale_orders or rec.direct_stop_skip_sale)
                returns_answered = bool((not rec.route_enable_direct_return) or direct_returns or rec.direct_stop_skip_return)
                rec.ux_can_receipt_actions = bool(
                    rec.state != "cancel"
                    and (
                        sales_answered
                        or returns_answered
                        or bool(sale_orders)
                        or bool(direct_returns)
                        or bool(rec.direct_stop_settlement_reviewed)
                        or bool(rec.direct_stop_settlement_paid_amount)
                        or bool(rec.direct_stop_settlement_remaining_amount)
                        or bool(rec.direct_stop_sales_total)
                        or bool(rec.direct_stop_returns_total)
                        or rec.visit_process_state in ("collection_done", "ready_to_close", "done")
                        or rec.state == "done"
                    )
                )

                if rec.state == "draft":
                    rec.ux_stage = "arrival"
                    rec.ux_primary_action = "start_visit"
                    rec.ux_stage_title = _("Start direct sales stop")
                    rec.ux_stage_help = _("Begin the visit.")
                elif rec.state == "in_progress" and not sales_answered:
                    rec.ux_stage = "arrival"
                    rec.ux_primary_action = "direct_sale_decision"
                    rec.ux_stage_title = _("Sales decision")
                    rec.ux_stage_help = _("Decide whether to create a direct sale order for this stop.")
                    rec.ux_can_create_direct_sale = bool(rec.route_enable_direct_sale)
                    rec.ux_can_no_sale = True
                elif rec.state == "in_progress" and not returns_answered:
                    rec.ux_stage = "arrival"
                    rec.ux_primary_action = "direct_return_decision"
                    rec.ux_stage_title = _("Return decision")
                    rec.ux_stage_help = _("Decide whether there is a direct return for this stop.")
                    rec.ux_can_open_direct_sale_orders = bool(sale_orders)
                    rec.ux_can_open_direct_sale_payments = bool(sale_orders)
                    rec.ux_can_create_direct_return = bool(rec.route_enable_direct_return)
                    rec.ux_can_no_return = True
                elif rec.state == "in_progress":
                    settlement_payments = rec._get_direct_stop_settlement_payments() if rec.id else self.env["route.visit.payment"]
                    has_draft_payments = bool(settlement_payments.filtered(lambda p: p.state == "draft"))
                    has_confirmed_payments = bool(settlement_payments.filtered(lambda p: p.state == "confirmed"))
                    remaining_due = rec.direct_stop_settlement_remaining_amount or 0.0
                    credit_pending = bool((rec.direct_stop_credit_amount or 0.0) > 0.0 and not rec.direct_stop_credit_policy)
                    settlement_review_ready = bool(sales_answered and returns_answered)
                    settlement_reviewed = bool(rec.direct_stop_settlement_reviewed)
                    settlement_ready = bool(rec.direct_stop_settlement_ready)

                    rec.ux_can_review_settlement = settlement_review_ready and not has_draft_payments

                    if has_draft_payments:
                        rec.ux_stage = "collection"
                        rec.ux_primary_action = "confirm_payments"
                        rec.ux_stage_title = _("Confirm direct stop settlement")
                        rec.ux_stage_help = _("Confirm the draft settlement entries before finishing the stop.")
                        rec.ux_can_confirm_payments = True
                        rec.ux_can_open_payments = True
                    elif credit_pending or (not settlement_ready and remaining_due > 0.0):
                        rec.ux_stage = "collection"
                        rec.ux_primary_action = "collect_payment"
                        rec.ux_stage_title = _("Direct stop settlement")
                        rec.ux_stage_help = _("Review amount due now, immediate remaining, and promise amount, then settle the stop.")
                        rec.ux_can_collect_payment = True
                        rec.ux_can_open_payments = has_confirmed_payments
                    elif not settlement_reviewed:
                        rec.ux_stage = "collection"
                        rec.ux_primary_action = "collect_payment"
                        rec.ux_stage_title = _("Review settlement")
                        rec.ux_stage_help = _("No payment is due. Open the settlement screen, review the summary, then close it to continue.")
                        rec.ux_can_collect_payment = True
                        rec.ux_can_open_payments = has_confirmed_payments
                    else:
                        rec.ux_stage = "ready_to_close"
                        rec.ux_primary_action = "finish_visit"
                        rec.ux_stage_title = _("Settlement and finish")
                        rec.ux_stage_help = _("Settlement has been reviewed. Finish the visit.")
                        rec.ux_can_finish_visit = True
                        rec.ux_can_open_payments = has_confirmed_payments

                    rec.ux_can_open_direct_sale_orders = bool(sale_orders)
                    rec.ux_can_open_direct_sale_payments = bool(sale_orders or has_confirmed_payments or has_draft_payments or (rec.direct_stop_previous_due_amount or 0.0) > 0.0)
                    rec.ux_can_open_direct_returns = bool(direct_returns)
                else:
                    rec.ux_stage = "done"
                    rec.ux_primary_action = "none"
                    rec.ux_stage_title = _("Stop completed")
                    rec.ux_stage_help = _("No action required. Use Visit Summary for final review, receipt, or sharing actions when needed.")
                continue

            rec.ux_can_scan_barcode = (
                rec.state == "in_progress"
                and rec.visit_process_state in ("checked_in", "counting")
                and (has_lines or rec.first_consignment_empty_balance)
            )

            rec.ux_can_scan_returns = (
                rec.state == "in_progress"
                and rec.visit_process_state == "counting"
                and not rec.returns_step_done
            )
            rec.ux_can_no_returns = rec.ux_can_scan_returns

            rec.ux_can_confirm_return_transfers = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and has_return_qty
                and not has_return_transfers
            )

            rec.ux_can_generate_refill = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and (not has_return_qty or has_return_transfers)
                and not rec.refill_datetime
            )

            rec.ux_can_confirm_refill = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and (not has_return_qty or has_return_transfers)
                and bool(rec.refill_datetime)
                and has_supplied_qty
                and not rec.refill_picking_id
            )

            rec.ux_can_collect_payment = (
                can_enter_collection
                and not rec.ux_can_open_pending_refill
                and not has_draft_payments
                and not rec.collection_skip_reason
                and not no_due_to_collect
            )

            rec.ux_can_confirm_payments = (
                can_enter_collection
                and not rec.ux_can_open_pending_refill
                and has_draft_payments
            )

            rec.ux_can_skip_collection = (
                can_enter_collection
                and not rec.ux_can_open_pending_refill
            )

            rec.ux_can_open_payments = (
                (can_enter_collection and not rec.ux_can_open_pending_refill)
                or has_draft_payments
                or has_confirmed_payments
            )

            rec.ux_can_receipt_actions = bool(
                rec.state != "cancel"
                and (
                    bool(rec.sale_order_id)
                    or has_confirmed_payments
                    or bool(rec.collected_amount)
                    or rec.visit_process_state in ("collection_done", "ready_to_close", "done")
                    or rec.state == "done"
                )
            )

            rec.ux_can_finish_visit = (
                (
                    rec.state == "in_progress"
                    and rec.visit_process_state in ("collection_done", "ready_to_close")
                )
                or (
                    can_enter_collection
                    and not rec.ux_can_open_pending_refill
                    and not has_draft_payments
                    and no_due_to_collect
                )
            )

            if rec.state == "draft":
                rec.ux_stage = "arrival"
                rec.ux_primary_action = "start_visit"
                rec.ux_stage_title = _("Start the visit")
                rec.ux_stage_help = _("Begin the visit.")

            elif rec.state == "in_progress" and rec.visit_process_state == "pending":
                rec.ux_stage = "load_balance"
                rec.ux_primary_action = "load_previous_balance"
                rec.ux_stage_title = _("Load previous balance")
                rec.ux_stage_help = _("Load previous shelf quantities.")

            elif load_balance_required:
                rec.ux_stage = "load_balance"
                rec.ux_primary_action = "load_previous_balance"
                rec.ux_stage_title = _("Load previous balance")
                rec.ux_stage_help = _("Load previous shelf quantities before counting.")

            elif rec.visit_process_state == "checked_in":
                rec.ux_stage = "count"
                rec.ux_primary_action = "scan_shelf"
                rec.ux_stage_title = _("Scan shelf stock")
                rec.ux_stage_help = _("Scan the current shelf quantities.")

            elif rec.visit_process_state == "counting" and not rec.returns_step_done:
                rec.ux_stage = "returns"
                rec.ux_primary_action = "returns_step"
                rec.ux_stage_title = _("Check Return")
                rec.ux_stage_help = _("Use the main button to scan additional returns, or use Skip Additional Returns below if there are no more returns.")

            elif rec.visit_process_state == "counting" and rec.returns_step_done:
                rec.ux_stage = "reconcile"
                rec.ux_primary_action = "reconcile_count"
                rec.ux_stage_title = _("Reconcile counted stock")
                rec.ux_stage_help = _("Confirm reconciliation.")

            elif rec.visit_process_state == "reconciled" and has_return_qty and not has_return_transfers:
                rec.ux_stage = "return_transfer"
                rec.ux_primary_action = "confirm_return_transfers"
                rec.ux_stage_title = _("Confirm return transfers")
                rec.ux_stage_help = _("Create the internal transfers for returned products.")

            elif rec.visit_process_state == "reconciled" and not rec.refill_datetime and (not has_return_qty or has_return_transfers):
                rec.ux_stage = "refill"
                rec.ux_primary_action = "generate_refill"
                rec.ux_stage_title = _("Generate refill proposal")
                rec.ux_stage_help = _("Generate the suggested refill.")

            elif rec.visit_process_state == "reconciled" and (not has_return_qty or has_return_transfers) and bool(rec.refill_datetime) and has_supplied_qty and not rec.refill_picking_id:
                rec.ux_stage = "refill"
                rec.ux_primary_action = "confirm_refill"
                rec.ux_stage_title = _("Confirm refill transfer")
                rec.ux_stage_help = _("Create the internal transfer from van to outlet.")

            elif rec.ux_can_open_pending_refill:
                rec.ux_stage = "refill"
                rec.ux_primary_action = "open_pending_refill"
                rec.ux_stage_title = _("Open pending refill")
                rec.ux_stage_help = _("There is a pending refill/backorder that must be reviewed first.")

            elif can_enter_collection and has_draft_payments:
                rec.ux_stage = "collection"
                rec.ux_primary_action = "confirm_payments"
                rec.ux_stage_title = _("Confirm payments")
                rec.ux_stage_help = _("Review and confirm the drafted payment decisions.")

            elif can_enter_collection and not has_confirmed_payments and not rec.collection_skip_reason and not rec.ux_can_open_pending_refill and no_due_to_collect:
                rec.ux_stage = "ready_to_close"
                rec.ux_primary_action = "finish_visit"
                rec.ux_stage_title = _("Finish visit")
                rec.ux_stage_help = _("No payment is due on this visit. Close the visit.")

            elif can_enter_collection and not has_confirmed_payments and not rec.collection_skip_reason and not rec.ux_can_open_pending_refill:
                rec.ux_stage = "collection"
                rec.ux_primary_action = "collect_payment"
                rec.ux_stage_title = _("Collect payment")
                rec.ux_stage_help = _("Review amount due now, immediate remaining, and promise amount, then save the collection decision. Use Skip Collection only when collection is not possible.")

            elif rec.visit_process_state in ("collection_done", "ready_to_close"):
                rec.ux_stage = "ready_to_close"
                rec.ux_primary_action = "finish_visit"
                rec.ux_stage_title = _("Finish visit")
                rec.ux_stage_help = _("Close the visit.")

            else:
                rec.ux_stage = "done"
                rec.ux_primary_action = "none"
                rec.ux_stage_title = _("Visit completed")
                rec.ux_stage_help = _("No action required. Use Visit Summary for final review, receipt, or sharing actions when needed.")

    @api.depends(
        "sale_order_id",
        "sale_order_id.name",
        "refill_picking_id",
        "refill_picking_id.name",
        "return_picking_ids",
        "return_picking_ids.name",
        "return_picking_ids.state",
        "return_picking_ids.location_id",
        "return_picking_ids.location_dest_id",
        "partner_id",
    )
    def _compute_consignment_document_refs(self):
        for rec in self:
            if rec._is_direct_sales_stop():
                rec.summary_sale_order_ref = False
                rec.summary_refill_transfer_ref = False
                rec.summary_return_transfer_refs = False
                continue

            sale_order = rec._get_route_receipt_sale_order()
            rec.summary_sale_order_ref = sale_order.name if sale_order else "-"
            rec.summary_refill_transfer_ref = rec.refill_picking_id.name or "-"
            rec.summary_return_transfer_refs = rec._get_route_receipt_return_refs()

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

            if rec._is_direct_sales_stop():
                continue

            sale_amount = sum((line.sold_amount or 0.0) for line in rec.line_ids) if rec.line_ids else (rec.net_due_amount or 0.0)
            return_amount = sum((line.return_amount or 0.0) for line in rec.line_ids) if rec.line_ids else 0.0
            net_amount_for_visit = max((sale_amount or 0.0) - (return_amount or 0.0), 0.0)
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

    def _get_route_receipt_sale_order(self):
        self.ensure_one()
        if self.sale_order_id:
            return self.sale_order_id

        domain = [("origin", "=", self.name), ("state", "!=", "cancel")]
        if self.partner_id:
            domain.append(("partner_id", "=", self.partner_id.id))
        return self.env["sale.order"].search(domain, order="id desc", limit=1)

    def _get_route_receipt_return_pickings(self):
        self.ensure_one()
        domain = self._get_return_transfer_domain() if hasattr(self, "_get_return_transfer_domain") else []
        if domain:
            return self.env["stock.picking"].search(domain, order="id asc")

        return self.return_picking_ids.filtered(
            lambda p: p.state != "cancel"
            and p.location_id == self.outlet_stock_location_id
            and (not self.refill_picking_id or p.id != self.refill_picking_id.id)
        ).sorted(key=lambda p: p.id)

    def _get_route_receipt_return_refs(self):
        self.ensure_one()
        refs = self._get_route_receipt_return_pickings().mapped("name")
        return ", ".join(refs) if refs else "-"

    def _ensure_route_sale_order_for_summary(self):
        self.ensure_one()
        if self._is_direct_sales_stop():
            return self.env["sale.order"]
        if self.sale_order_id:
            return self.sale_order_id
        if self.state != "in_progress":
            return self.env["sale.order"]
        if not self.partner_id:
            return self.env["sale.order"]
        if not self.line_ids.filtered(lambda l: (l.sold_qty or 0.0) > 0):
            return self.env["sale.order"]

        visit = self.with_context(skip_missing_lot_check=True)
        visit.action_create_sale_order()
        return visit.sale_order_id

    def _get_pda_form_action(self):
        self.ensure_one()
        form_view = self.env.ref("route_core.view_route_visit_pda_form")
        action_ref = self.env.ref("route_core.action_route_visit_pda_salesperson", raise_if_not_found=False)
        if not action_ref:
            action_ref = self.env.ref("route_core.action_route_visit_pda", raise_if_not_found=False)

        if action_ref:
            action = action_ref.read()[0]
            action.update({
                "name": action.get("name") or _("My Visits"),
                "res_model": "route.visit",
                "res_id": self.id,
                "view_mode": "form",
                "view_id": form_view.id,
                "views": [(form_view.id, "form")],
                "target": "current",
                "context": {
                    "search_default_filter_my_visits": 1,
                    "search_default_filter_today": 1,
                                        "pda_mode": True,
                    "create": 0,
                    "edit": 1,
                    "delete": 0,
                },
            })
            return action

        return {
            "type": "ir.actions.act_window",
            "name": _("My Visits"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": form_view.id,
            "views": [(form_view.id, "form")],
            "target": "current",
            "context": {
                "search_default_filter_my_visits": 1,
                "search_default_filter_today": 1,
                                "pda_mode": True,
                "create": 0,
                "edit": 1,
                "delete": 0,
            },
        }

    def _ensure_direct_sales_stop(self):
        self.ensure_one()
        if not self._is_direct_sales_stop():
            raise UserError(_("This action is only available for Direct Sales stops."))


    def _get_direct_stop_sale_orders(self):
        self.ensure_one()
        if not self.outlet_id:
            return self.env["sale.order"]
        domain = [
            ("route_order_mode", "=", "direct_sale"),
            ("route_outlet_id", "=", self.outlet_id.id),
            ("origin", "=", self.name),
        ]
        if self.user_id:
            domain.append(("user_id", "=", self.user_id.id))
        return self.env["sale.order"].search(domain, order="id desc")

    def _get_direct_stop_returns(self):
        self.ensure_one()
        returns = self.env["route.direct.return"]
        if not self.outlet_id:
            return returns
        returns = self.env["route.direct.return"].search(
            [
                ("outlet_id", "=", self.outlet_id.id),
                ("state", "!=", "cancel"),
            ],
            order="id desc",
        )
        if self.user_id:
            returns = returns.filtered(lambda r: r.user_id == self.user_id)
        sale_orders = self._get_direct_stop_sale_orders()
        return returns.filtered(
            lambda r: (r.visit_id and r.visit_id.id == self.id)
            or (r.sale_order_id and r.sale_order_id in sale_orders)
            or (self.name and self.name in (r.note or ""))
        )

    def action_ux_no_sale(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        self.write({"direct_stop_skip_sale": True})
        return self._get_pda_form_action()

    def action_ux_no_return(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        self.write({"direct_stop_skip_return": True})
        return self._get_pda_form_action()

    def action_ux_create_direct_sale(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        if not self.route_enable_direct_sale:
            raise UserError(_("Direct Sale is disabled in Route Settings."))
        self.write({"direct_stop_skip_sale": False})
        action = {
            "type": "ir.actions.act_window",
            "name": _("Create Direct Sale"),
            "res_model": "sale.order",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_route_order_mode": "direct_sale",
                "default_user_id": self.user_id.id or self.env.user.id,
                "default_route_source_location_id": self.vehicle_id.stock_location_id.id if self.vehicle_id and self.vehicle_id.stock_location_id else False,
                "default_route_payment_mode": "cash",
                "default_route_outlet_id": self.outlet_id.id if self.outlet_id else False,
                "default_partner_id": self.outlet_id.partner_id.id if self.outlet_id and self.outlet_id.partner_id else False,
                "default_origin": self.name,
            },
        }
        view = self.env.ref("route_core.view_sale_order_form_route_direct_sale", raise_if_not_found=False)
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_ux_open_direct_sale_orders(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        if not self.route_enable_direct_sale:
            raise UserError(_("Direct Sale is disabled in Route Settings."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Direct Sale Orders"),
            "res_model": "sale.order",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("id", "in", self._get_direct_stop_sale_orders().ids)],
            "context": {"search_default_route_order_mode": "direct_sale"},
        }

    def action_ux_open_direct_sale_payments(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        if not self.route_enable_direct_sale:
            raise UserError(_("Direct Sale is disabled in Route Settings."))
        sale_orders = self._get_direct_stop_sale_orders()
        return {
            "type": "ir.actions.act_window",
            "name": _("Direct Sale Payments"),
            "res_model": "route.visit.payment",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("source_type", "=", "direct_sale"), ("sale_order_id", "in", sale_orders.ids)],
        }

    def action_ux_create_direct_return(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        if not self.route_enable_direct_return:
            raise UserError(_("Direct Return is disabled in Route Settings."))
        self.write({"direct_stop_skip_return": False})
        sale_orders = self._get_direct_stop_sale_orders()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Create Direct Return"),
            "res_model": "route.direct.return",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_user_id": self.user_id.id or self.env.user.id,
                "default_vehicle_id": self.vehicle_id.id if self.vehicle_id else False,
                "default_outlet_id": self.outlet_id.id if self.outlet_id else False,
                "default_sale_order_id": sale_orders[:1].id if sale_orders else False,
                "default_visit_id": self.id,
                "route_visit_id": self.id,
                "default_note": self.name,
            },
        }
        view = self.env.ref("route_core.view_route_direct_return_form", raise_if_not_found=False)
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_ux_open_direct_returns(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        if not self.route_enable_direct_return:
            raise UserError(_("Direct Return is disabled in Route Settings."))
        returns = self._get_direct_stop_returns()
        return {
            "type": "ir.actions.act_window",
            "name": _("Direct Returns"),
            "res_model": "route.direct.return",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("id", "in", returns.ids)],
        }

    def action_ux_refresh_visit(self):
        self.ensure_one()
        self.action_recompute_visit_health()
        return self._get_pda_form_action()

    def action_ux_start_visit(self):
        self.ensure_one()
        self.action_start_visit()
        return self._get_pda_form_action()

    def action_ux_load_previous_balance(self):
        self.ensure_one()
        if self._is_direct_sales_stop():
            raise UserError(_("Previous balance is not used for Direct Sales stops."))
        result = self.action_load_previous_balance()
        if isinstance(result, dict):
            return result
        return self._get_pda_form_action()

    def action_ux_scan_shelf(self):
        self.ensure_one()
        if self._is_direct_sales_stop():
            raise UserError(_("Shelf counting is not used for Direct Sales stops."))
        return self.action_open_scan_wizard()

    def action_ux_returns_step(self):
        self.ensure_one()
        if self._is_direct_sales_stop():
            raise UserError(_("Return scan is not used for Direct Sales stops. Use Direct Return instead."))
        return self._action_open_returns_scan_wizard()

    def action_ux_no_returns(self):
        self.ensure_one()
        return self._action_mark_no_returns()

    def action_ux_reconcile_count(self):
        self.ensure_one()

        if self._is_direct_sales_stop():
            raise UserError(_("Reconciliation is not used for Direct Sales stops."))

        if self.visit_process_state != "counting":
            return self._get_pda_form_action()

        values = {"visit_process_state": "reconciled"}
        if hasattr(self, "reconciliation_datetime"):
            values["reconciliation_datetime"] = fields.Datetime.now()
        self.write(values)

        if self.line_ids.filtered(lambda l: (l.sold_qty or 0.0) > 0) and not self.sale_order_id:
            self._ensure_route_sale_order_for_summary()

        return self._get_pda_form_action()

    def action_ux_confirm_return_transfers(self):
        self.ensure_one()
        self.action_confirm_return_transfers()
        return self._get_pda_form_action()

    def action_ux_view_return_transfers(self):
        self.ensure_one()
        return self.action_view_return_transfers()

    def action_ux_generate_refill(self):
        self.ensure_one()
        if self._is_direct_sales_stop():
            raise UserError(_("Refill proposal is not used for Direct Sales stops."))
        self.action_generate_refill_proposal()

        if not self.refill_datetime:
            self.write({"refill_datetime": fields.Datetime.now()})

        return self._get_pda_form_action()

    def action_ux_confirm_refill(self):
        self.ensure_one()
        if self._is_direct_sales_stop():
            raise UserError(_("Refill transfer is not used for Direct Sales stops."))
        self.action_confirm_refill_transfer()
        return self._get_pda_form_action()

    def action_ux_view_refill_transfer(self):
        self.ensure_one()
        return self.action_view_refill_transfer()

    def action_ux_open_pending_refill(self):
        self.ensure_one()
        return self.action_view_pending_refill()

    def action_ux_open_payments(self):
        self.ensure_one()
        domain = [("visit_id", "=", self.id)]
        if self._is_direct_sales_stop():
            domain = ["|", ("settlement_visit_id", "=", self.id), ("visit_id", "=", self.id)]
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit Payments"),
            "res_model": "route.visit.payment",
            "view_mode": "list,form",
            "target": "current",
            "domain": domain,
            "context": {
                "default_visit_id": self.id,
                "default_settlement_visit_id": self.id,
                "search_default_visit_id": self.id,
            },
        }

    def action_open_statement_of_account(self):
        self.ensure_one()

        # Once the visit is done, the salesperson should see the final visit
        # summary/receipt dialog, not the pre-collection Statement of Account.
        if self.visit_process_state == "done" or self.state == "done":
            return self._get_route_visit_finish_summary_action()

        return {
            "type": "ir.actions.act_window",
            "name": _("Statement of Account"),
            "res_model": "route.visit.statement.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_visit_id": self.id},
        }

    def action_ux_collect_payment(self):
        self.ensure_one()

        if (not self._is_direct_sales_stop()) and self.remaining_due_amount <= 0 and not self.collection_skip_reason:
            self._action_mark_post_collection_stage()
            return self._get_pda_form_action()

        return {
            "type": "ir.actions.act_window",
            "name": _("Collect Payment"),
            "res_model": "route.visit.collect.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
            },
        }

    def _action_mark_collection_done(self):
        self.ensure_one()
        values = {"visit_process_state": "collection_done"}
        if hasattr(self, "collection_datetime"):
            values["collection_datetime"] = fields.Datetime.now()
        self.write(values)

    def _action_mark_post_collection_stage(self):
        self.ensure_one()
        if self._is_direct_sales_stop():
            credit_pending = bool((self.direct_stop_credit_amount or 0.0) > 0.0 and not self.direct_stop_credit_policy)
            settlement_ready = bool(self.direct_stop_settlement_ready)
            next_state = "ready_to_close" if settlement_ready and not credit_pending else "collection_done"
            values = {"visit_process_state": next_state}
            if next_state == "ready_to_close":
                values["direct_stop_settlement_reviewed"] = True
        else:
            next_state = "ready_to_close" if (self.remaining_due_amount or 0.0) <= 0.0 else "collection_done"
            values = {"visit_process_state": next_state}
        if hasattr(self, "collection_datetime"):
            values["collection_datetime"] = fields.Datetime.now()
        self.write(values)

    def action_ux_confirm_payments(self):
        self.ensure_one()
        if self._is_direct_sales_stop():
            draft_payments = self._get_direct_stop_settlement_payments(states=["draft"])
        else:
            draft_payments = self.payment_ids.filtered(lambda p: p.state == "draft")
        if not draft_payments:
            raise UserError(_("There are no draft payments to confirm."))

        draft_payments.action_confirm()
        self._action_mark_post_collection_stage()
        return self._get_pda_form_action()

    def action_ux_skip_collection(self):
        self.ensure_one()
        if not self.collection_skip_reason:
            raise UserError(_("Please enter Collection Skip Reason first."))

        self._action_mark_collection_done()
        return self._get_pda_form_action()

    def _action_finish_visit_core(self):
        self.ensure_one()

        if self._is_direct_sales_stop():
            sale_orders = self._get_direct_stop_sale_orders()
            direct_returns = self._get_direct_stop_returns()
            draft_payments = self._get_direct_stop_settlement_payments(states=["draft"])

            if not sale_orders and not self.direct_stop_skip_sale:
                raise UserError(_("Please choose Create Direct Sale or No Sale first."))

            if sale_orders.filtered(lambda o: o.state in ("draft", "sent")):
                raise UserError(_("Please confirm the Direct Sale Order before finishing the stop."))

            if self.route_enable_direct_return and not direct_returns and not self.direct_stop_skip_return:
                raise UserError(_("Please choose Create Direct Return or No Return first."))

            if draft_payments:
                raise UserError(_("Please confirm the draft settlement entries before finishing the stop."))

            if (self.direct_stop_settlement_remaining_amount or 0.0) > 0.0:
                raise UserError(_("Please settle the remaining direct-sales balance before finishing the stop."))

            if (self.direct_stop_settlement_remaining_amount or 0.0) <= 0.0 and not self.direct_stop_settlement_reviewed:
                raise UserError(_("Please open Collect Payment, review the settlement summary, then close it before finishing the stop."))

            if (self.direct_stop_credit_amount or 0.0) > 0.0 and not self.direct_stop_credit_policy:
                raise UserError(_("Please choose a return credit settlement policy before finishing the stop."))

            self.with_context(route_visit_force_write=True).write({
                "state": "done",
                "visit_process_state": "done",
                "end_datetime": fields.Datetime.now(),
            })
            return self._get_direct_stop_finish_summary_action()

        if self.visit_process_state not in ("collection_done", "ready_to_close"):
            if (
                self.visit_process_state == "reconciled"
                and (self.remaining_due_amount or 0.0) <= 0.0
                and not (self.has_pending_refill or self.refill_backorder_id)
            ):
                self._action_mark_collection_done()
            else:
                raise UserError(_("The visit is not yet ready for closing."))

        sold_lines = self.line_ids.filtered(lambda l: (l.sold_qty or 0.0) > 0)
        if sold_lines and not self.sale_order_id:
            sale_result = self.action_create_sale_order()
            if isinstance(sale_result, dict) and sale_result.get("res_model") != "sale.order":
                return sale_result

        result = self.action_end_visit()
        if isinstance(result, dict):
            return result
        if result is True and self.state == "done":
            return self._get_route_visit_finish_summary_action()
        return self._get_pda_form_action()

    def action_ux_finish_visit(self):
        return self._action_finish_visit_core()

    def action_ux_finalize_visit(self):
        return self._action_finish_visit_core()

    def _get_route_visit_finish_summary_action(self):
        self.ensure_one()
        view = self.env.ref("route_core.view_route_visit_finish_summary_wizard_form", raise_if_not_found=False)
        action = {
            "type": "ir.actions.act_window",
            "name": _("Completed Visit Summary"),
            "res_model": "route.visit.finish.summary.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
            },
        }
        if view:
            action.update({
                "view_id": view.id,
                "views": [(view.id, "form")],
            })
        return action

    def _get_direct_stop_finish_summary_action(self):
        self.ensure_one()
        return self._get_route_visit_finish_summary_action()

    def action_ux_view_sale_order(self):
        self.ensure_one()
        return self.action_view_sale_order()



    def _get_direct_stop_receipt_sale_orders(self):
        self.ensure_one()
        if not self._is_direct_sales_stop():
            return self.env["sale.order"]
        return self._get_direct_stop_sale_orders().filtered(lambda o: o.state in ("sale", "done"))

    def _get_direct_stop_receipt_returns(self):
        self.ensure_one()
        if not self._is_direct_sales_stop():
            return self.env["route.direct.return"]
        return self._get_direct_stop_returns().filtered(lambda r: r.state == "done")

    def _get_direct_stop_receipt_previous_due_lines(self):
        self.ensure_one()
        return [
            {
                "visit_ref": visit.name or "",
                "date": visit.date,
                "amount": visit.remaining_due_amount or 0.0,
            }
            for visit in self._get_direct_stop_previous_due_visits()
        ]

    def _get_direct_stop_receipt_sale_lines(self):
        self.ensure_one()
        lines = []
        for order in self._get_direct_stop_receipt_sale_orders():
            for line in order.order_line.filtered(lambda l: not l.display_type):
                barcode = getattr(line, "route_product_barcode", False) or line.product_id.barcode or line.product_id.default_code or ""
                lines.append({
                    "order_ref": order.name or "",
                    "barcode": barcode,
                    "product_name": line.product_id.display_name or line.name or "",
                    "quantity": line.product_uom_qty or 0.0,
                    "uom_name": (
                        getattr(getattr(line, "product_uom_id", False), "name", False)
                        or getattr(getattr(line, "product_uom", False), "name", False)
                        or ""
                    ),
                    "unit_price": line.price_unit or 0.0,
                    "subtotal": line.price_subtotal or 0.0,
                })
        return lines

    def _get_direct_stop_receipt_return_lines(self):
        self.ensure_one()
        lines = []
        for direct_return in self._get_direct_stop_receipt_returns():
            for line in direct_return.line_ids:
                barcode = line.route_product_barcode or line.product_id.barcode or line.product_id.default_code or ""
                lines.append({
                    "return_ref": direct_return.name or "",
                    "barcode": barcode,
                    "product_name": line.product_id.display_name or "",
                    "quantity": line.quantity or 0.0,
                    "uom_name": line.uom_id.name if line.uom_id else "",
                    "reason": dict(line._fields["return_reason"].selection).get(line.return_reason) if line.return_reason else "",
                    "unit_price": line.estimated_unit_price or 0.0,
                    "subtotal": line.estimated_amount or 0.0,
                })
        return lines

    def _get_direct_stop_receipt_payments(self):
        self.ensure_one()
        return self._get_direct_stop_settlement_payments(states=["confirmed"])

    def _get_direct_stop_receipt_summary(self):
        self.ensure_one()
        promise_payments = self._get_direct_stop_receipt_payments().filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
        latest_promise = promise_payments.sorted(
            key=lambda p: (p.payment_date or fields.Datetime.to_datetime("1900-01-01 00:00:00"), p.id or 0),
            reverse=True,
        )[:1] if promise_payments else promise_payments
        settled_amount = self.direct_stop_settlement_paid_amount or 0.0
        grand_total_due = self.direct_stop_grand_due_amount or 0.0
        immediate_remaining = max(grand_total_due - settled_amount, 0.0)
        latest_promise_status = False
        if latest_promise:
            latest_promise_status = latest_promise._get_snapshot_promise_status() if hasattr(latest_promise, "_get_snapshot_promise_status") else latest_promise.promise_status
        return {
            "previous_due": self.direct_stop_previous_due_amount or 0.0,
            "previous_due_since": self.direct_stop_previous_due_since_date,
            "current_sale": self.direct_stop_sales_total or 0.0,
            "current_return": self.direct_stop_returns_total or 0.0,
            "net_current_stop": self.direct_stop_current_net_amount or 0.0,
            "grand_total_due": grand_total_due,
            "credit_amount": self.direct_stop_credit_amount or 0.0,
            "settled_amount": settled_amount,
            "remaining_amount": self.direct_stop_settlement_remaining_amount or 0.0,
            "immediate_remaining_amount": immediate_remaining,
            "promise_amount": sum(payment.promise_amount or 0.0 for payment in promise_payments) if promise_payments else 0.0,
            "latest_promise_date": latest_promise.promise_date if latest_promise else False,
            "latest_promise_status": latest_promise_status or False,
            "sale_order_ref": ", ".join(self._get_direct_stop_receipt_sale_orders().mapped("name")) or "-",
            "return_ref": ", ".join(self._get_direct_stop_receipt_returns().mapped("name")) or "-",
        }

    def _get_direct_stop_receipt_payment_breakdown(self):
        self.ensure_one()
        payments = self._get_direct_stop_receipt_payments()
        totals = {
            "cash": 0.0,
            "bank": 0.0,
            "pos": 0.0,
            "deferred": 0.0,
            "promise": 0.0,
        }
        for payment in payments:
            mode = payment.payment_mode or "cash"
            if mode in totals:
                totals[mode] += payment.amount or 0.0
            totals["promise"] += payment.promise_amount or 0.0

        selection_map = dict(self.env["route.visit.payment"]._fields["payment_mode"].selection)
        promise_status_map = dict(self.env["route.visit.payment"]._fields["promise_status"].selection)
        promise_payments = payments.filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
        latest_promise = promise_payments.sorted(
            key=lambda p: (p.payment_date or fields.Datetime.to_datetime("1900-01-01 00:00:00"), p.id or 0),
            reverse=True,
        )[:1] if promise_payments else promise_payments
        latest_promise_status = False
        if latest_promise:
            raw_status = latest_promise._get_snapshot_promise_status() if hasattr(latest_promise, "_get_snapshot_promise_status") else latest_promise.promise_status
            latest_promise_status = promise_status_map.get(raw_status, raw_status)
        return {
            "totals": totals,
            "labels": {
                "cash": selection_map.get("cash", _("Cash")),
                "bank": selection_map.get("bank", _("Bank Transfer")),
                "pos": selection_map.get("pos", _("POS")),
                "deferred": selection_map.get("deferred", _("Deferred")),
                "promise": _("Promised Amount"),
            },
            "latest_promise_date": latest_promise.promise_date if latest_promise else False,
            "latest_promise_amount": latest_promise.promise_amount if latest_promise else 0.0,
            "latest_promise_status": latest_promise_status or False,
            "payment_count": len(payments),
        }

    def _get_consignment_receipt_payments(self):
        self.ensure_one()
        return self.payment_ids.filtered(lambda p: p.state == "confirmed").sorted(
            key=lambda p: (p.payment_date or fields.Datetime.now(), p.id),
            reverse=True,
        )

    def _get_consignment_receipt_summary(self):
        self.ensure_one()
        payments = self._get_consignment_receipt_payments()
        promise_payments = payments.filtered(lambda p: (p.promise_amount or 0.0) > 0.0)
        latest_promise = promise_payments[:1]
        line_items = self._get_consignment_receipt_line_items()
        sale_order = self._get_route_receipt_sale_order()
        sale_order_ref = self.summary_sale_order_ref or (sale_order.name if sale_order else "-")
        refill_ref = self.summary_refill_transfer_ref or (self.refill_picking_id.name or "-")
        return_refs = self.summary_return_transfer_refs or self._get_route_receipt_return_refs()
        remaining_amount = self.remaining_due_amount or 0.0
        settled_amount = sum(payments.mapped("amount")) if payments else (self.collected_amount or 0.0)
        visit_sale_amount = sum(item.get("sold_amount", 0.0) for item in line_items)
        returned_value = sum(item.get("return_amount", 0.0) for item in line_items)
        refill_value = sum(item.get("supply_value", 0.0) for item in line_items)
        current_visit_net = max((visit_sale_amount or 0.0) - (returned_value or 0.0), 0.0)

        # `outlet_current_due_amount` is already the balance that remains on the outlet
        # after any confirmed collection on this visit. Do not subtract the current
        # visit collection from it again, otherwise partial-payment visits with an
        # open promise show an incorrect zero balance after collection.
        total_outstanding_after_collection = max(self.outlet_current_due_amount or 0.0, remaining_amount)
        total_outlet_due = max(total_outstanding_after_collection + settled_amount, current_visit_net)
        previous_due = max(total_outlet_due - max(current_visit_net, 0.0), 0.0)
        raw_promise_amount = sum((getattr(payment, "effective_promise_amount", False) or payment.promise_amount or 0.0) for payment in promise_payments) if promise_payments else 0.0
        return {
            "sale_order_ref": sale_order_ref,
            "refill_ref": refill_ref,
            "return_refs": return_refs,
            "current_due": total_outlet_due,
            "total_outlet_due": total_outlet_due,
            "previous_due": previous_due,
            "settled_amount": settled_amount,
            "remaining_amount": remaining_amount,
            "current_visit_remaining": remaining_amount,
            "total_outstanding_after_collection": total_outstanding_after_collection,
            "promise_amount": min(raw_promise_amount, remaining_amount) if raw_promise_amount else 0.0,
            "latest_promise_date": latest_promise.promise_date if latest_promise else False,
            "visit_sale_amount": visit_sale_amount,
            "returned_value": returned_value,
            "current_visit_net": current_visit_net,
            "refill_value": refill_value,
            "confirmed_payment_total": sum(payments.mapped("amount")) if payments else 0.0,
        }

    def _get_consignment_receipt_line_items(self):
        self.ensure_one()
        route_map = dict(self.env["route.visit.line"]._fields["return_route"].selection)
        items_by_key = {}

        def _line_has_activity(line):
            return any([
                (line.previous_qty or 0.0),
                (line.counted_qty or 0.0),
                (line.sold_qty or 0.0),
                (line.return_qty or 0.0),
                (line.supplied_qty or 0.0),
            ])

        def _display_target_lot(line):
            # Historical visits may already contain a return-only no-lot row for a
            # tracked product while the same product has exactly one active lot row.
            # Group that display row with the lot row so the PDF remains readable
            # even before the record is reopened/normalized.
            if line.lot_id or (line.previous_qty or 0.0) or (line.counted_qty or 0.0) or (line.supplied_qty or 0.0):
                return line.lot_id
            if (line.return_qty or 0.0) <= 0:
                return line.lot_id
            product_lines = self.line_ids.filtered(lambda l: l.product_id == line.product_id and l.lot_id)
            active_lot_lines = product_lines.filtered(
                lambda l: (l.previous_qty or 0.0) > 0
                or (l.counted_qty or 0.0) > 0
                or (l.return_qty or 0.0) > 0
                or (l.supplied_qty or 0.0) > 0
            )
            if len(active_lot_lines.mapped("lot_id")) == 1:
                return active_lot_lines[:1].lot_id
            return line.lot_id

        for line in self.line_ids.filtered(lambda l: l.product_id):
            if not _line_has_activity(line):
                continue
            display_lot = _display_target_lot(line)
            key = (line.product_id.id, display_lot.id if display_lot else 0, line.return_route or "vehicle")
            if key not in items_by_key:
                lot_name = display_lot.name if display_lot else ""
                items_by_key[key] = {
                    "barcode": line.barcode or line.product_id.default_code or "",
                    "product_name": line.product_id.display_name or "",
                    "lot_name": lot_name,
                    "lot_display": (lot_name or "").replace("-", "‑") if lot_name else "",
                    "expiry_date": line.expiry_date or False,
                    "previous_qty": 0.0,
                    "display_previous_qty": 0.0,
                    "counted_qty": 0.0,
                    "sold_qty": 0.0,
                    "return_qty": 0.0,
                    "return_route": line.return_route or "vehicle",
                    "return_route_label": route_map.get(line.return_route or "vehicle", line.return_route or "vehicle"),
                    "supplied_qty": 0.0,
                    "unit_price": line.unit_price or 0.0,
                    "sold_amount": 0.0,
                    "return_amount": 0.0,
                    "supply_value": 0.0,
                }

            item = items_by_key[key]
            if not item.get("expiry_date") and line.expiry_date:
                item["expiry_date"] = line.expiry_date
            item["previous_qty"] += line.previous_qty or 0.0
            item["counted_qty"] += line.counted_qty or 0.0
            item["sold_qty"] += line.sold_qty or 0.0
            item["return_qty"] += line.return_qty or 0.0
            item["supplied_qty"] += line.supplied_qty or 0.0
            item["sold_amount"] += line.sold_amount or 0.0
            item["return_amount"] += line.return_amount or 0.0
            item["supply_value"] += line.supply_value or 0.0
            if not item["unit_price"] and line.unit_price:
                item["unit_price"] = line.unit_price or 0.0

        items = []
        for item in items_by_key.values():
            display_previous_qty = item.get("previous_qty", 0.0) or 0.0
            if display_previous_qty < 0:
                display_previous_qty = 0.0
            item["display_previous_qty"] = display_previous_qty
            items.append(item)
        return items

    def action_print_consignment_visit_receipt(self):
        self.ensure_one()
        return self.env.ref("route_core.action_report_route_visit_consignment_receipt").report_action(self)

    def _get_consignment_receipt_filename(self):
        self.ensure_one()
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", self.name or "visit").strip("-") or "visit"
        return "Consignment-Visit-Receipt-%s.pdf" % safe_name

    def _generate_consignment_receipt_attachment(self):
        self.ensure_one()
        report = self.env.ref("route_core.action_report_route_visit_consignment_receipt")
        report_ref = report.report_name or "route_core.report_route_visit_consignment_receipt"
        pdf_content, _content_type = report._render_qweb_pdf(report_ref, res_ids=self.ids)
        filename = self._get_consignment_receipt_filename()
        Attachment = self.env["ir.attachment"].sudo()
        attachment = Attachment.search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("name", "=", filename),
            ("mimetype", "=", "application/pdf"),
            ("type", "=", "binary"),
        ], limit=1)
        values = {
            "name": filename,
            "type": "binary",
            "raw": pdf_content,
            "mimetype": "application/pdf",
            "res_model": self._name,
            "res_id": self.id,
            "public": True,
            "company_id": self.company_id.id if self.company_id else False,
        }
        if attachment:
            attachment.write(values)
        else:
            attachment = Attachment.create(values)
        token = attachment.generate_access_token() or attachment.access_token or ""
        if isinstance(token, (list, tuple)):
            token = token[0] if token else ""
        return attachment, token

    def _get_consignment_receipt_public_url(self):
        self.ensure_one()
        base_url = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        if not base_url:
            raise UserError(_("Base URL is not configured. Please configure web.base.url before sending the receipt by WhatsApp."))
        attachment, token = self._generate_consignment_receipt_attachment()
        url = "%s/web/content/%s?download=true" % (base_url, attachment.id)
        if token:
            url = "%s&access_token=%s" % (url, token)
        return url

    def _build_consignment_whatsapp_message(self, pdf_url=False):
        self.ensure_one()
        summary = self._get_consignment_receipt_summary()
        currency_code = self.currency_id.name if self.currency_id else ""
        remaining_amount = summary.get("current_visit_remaining", summary.get("remaining_amount", 0.0)) or 0.0
        commission_amount = summary.get("commission_amount", 0.0) or 0.0
        lines = [
            _("Settlement Receipt"),
            _("Visit: %s") % (self.name or "-"),
            _("Outlet: %s") % (self.outlet_id.display_name if self.outlet_id else "-"),
            _("Sale Order: %s") % (summary.get("sale_order_ref") or "-"),
            _("Current Visit Sale: %.2f %s") % (summary.get("visit_sale_amount", 0.0), currency_code),
            _("Returns: %.2f %s") % (summary.get("returned_value", 0.0), currency_code),
        ]
        if commission_amount:
            lines.append(_("Category Commission: %.2f %s") % (commission_amount, currency_code))
        lines += [
            _("Net Payable: %.2f %s") % (summary.get("current_visit_net", 0.0), currency_code),
            _("Collected: %.2f %s") % (summary.get("settled_amount", 0.0), currency_code),
            _("Remaining: %.2f %s") % (remaining_amount, currency_code),
        ]
        if summary.get("promise_amount"):
            lines.append(_("Promise: %.2f %s") % (summary["promise_amount"], currency_code))
            if summary.get("latest_promise_date"):
                lines.append(_("Promise Date: %s") % summary["latest_promise_date"])
        elif remaining_amount <= 0.0:
            lines.append(_("Status: Paid in full"))
        if pdf_url:
            lines += ["", _("Receipt PDF:"), pdf_url]
        lines += ["", _("Full category details are included in the PDF.")]
        return "\n".join(lines)

    def action_print_direct_stop_settlement_receipt(self):
        self.ensure_one()
        if not self._is_direct_sales_stop():
            return self.action_print_consignment_visit_receipt()
        return self.env.ref("route_core.action_report_route_visit_settlement_receipt").report_action(self)

    def _get_direct_stop_previous_due_since_display(self):
        self.ensure_one()
        return str(self.direct_stop_previous_due_since_date) if self.direct_stop_previous_due_since_date else "0"

    def _get_direct_stop_receipt_filename(self):
        self.ensure_one()
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "-", self.name or "visit").strip("-") or "visit"
        return "Direct-Stop-Settlement-Receipt-%s.pdf" % safe_name

    def _generate_direct_stop_receipt_attachment(self):
        self.ensure_one()
        if not self._is_direct_sales_stop():
            raise UserError(_("Settlement receipt is available only for Direct Sales stops."))

        report = self.env.ref("route_core.action_report_route_visit_settlement_receipt")
        report_ref = report.report_name or "route_core.report_route_visit_settlement_receipt"
        pdf_content, _content_type = report._render_qweb_pdf(report_ref, res_ids=self.ids)
        filename = self._get_direct_stop_receipt_filename()
        Attachment = self.env["ir.attachment"].sudo()
        attachment = Attachment.search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("name", "=", filename),
            ("mimetype", "=", "application/pdf"),
            ("type", "=", "binary"),
        ], limit=1)

        values = {
            "name": filename,
            "type": "binary",
            "raw": pdf_content,
            "mimetype": "application/pdf",
            "res_model": self._name,
            "res_id": self.id,
            "public": True,
            "company_id": self.company_id.id if self.company_id else False,
        }
        if attachment:
            attachment.write(values)
        else:
            attachment = Attachment.create(values)

        token_value = attachment.generate_access_token()
        if isinstance(token_value, (list, tuple)):
            token = token_value[0] if token_value else ""
        else:
            token = token_value or attachment.access_token or ""
        return attachment, token

    def _get_direct_stop_receipt_public_url(self):
        self.ensure_one()
        base_url = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        if not base_url:
            raise UserError(_("Base URL is not configured. Please configure web.base.url before sending the receipt by WhatsApp."))
        attachment, token = self._generate_direct_stop_receipt_attachment()
        url = "%s/web/content/%s?download=true" % (base_url, attachment.id)
        if token:
            url = "%s&access_token=%s" % (url, token)
        return url

    def _route_normalize_whatsapp_phone(self, partner):
        if not partner:
            return ""
        phone = ""
        for field_name in ("mobile", "phone"):
            value = getattr(partner, field_name, False)
            if value:
                phone = str(value).strip()
                break
        return re.sub(r"\D", "", phone)

    def _get_direct_stop_credit_policy_labels(self):
        selection = []
        try:
            selection = self.env["route.visit"].fields_get(["direct_stop_credit_policy"])["direct_stop_credit_policy"].get("selection", [])
        except Exception:
            selection = []
        return dict(selection or [
            ("customer_credit", _("Customer Credit")),
            ("cash_refund", _("Cash Refund")),
            ("next_stop", _("Carry to Next Stop")),
        ])

    def _build_direct_stop_whatsapp_message(self, pdf_url=False):
        self.ensure_one()
        summary = self._get_direct_stop_receipt_summary()
        currency_code = self.currency_id.name if self.currency_id else ""
        credit_policy_map = self._get_direct_stop_credit_policy_labels()

        lines = [
            _("Settlement receipt"),
            _("Visit: %s") % (self.name or "-"),
            _("Outlet: %s") % (self.outlet_id.display_name if self.outlet_id else "-"),
            _("Sale Order: %s") % (summary.get("sale_order_ref") or "-"),
            _("Return: %s") % (summary.get("return_ref") or "-"),
            _("Total Due Now: %.2f %s") % (summary["grand_total_due"], currency_code),
            _("Collected Now: %.2f %s") % (summary["settled_amount"], currency_code),
            _("Remaining After Collection: %.2f %s") % (summary.get("immediate_remaining_amount", summary["remaining_amount"]), currency_code),
        ]

        promise_amount = summary.get("promise_amount") or 0.0
        credit_amount = summary.get("credit_amount") or 0.0

        if promise_amount:
            lines.append(_("Promise Amount: %.2f %s") % (promise_amount, currency_code))
            if summary.get("latest_promise_date"):
                lines.append(_("Promise Date: %s") % summary["latest_promise_date"])
        elif credit_amount:
            lines.append(_("Credit: %.2f %s") % (credit_amount, currency_code))
            if self.direct_stop_credit_policy:
                policy_label = credit_policy_map.get(self.direct_stop_credit_policy, self.direct_stop_credit_policy)
                lines.append(_("Credit Handling: %s") % policy_label)

        if pdf_url:
            lines += [
                "",
                _("Receipt PDF:"),
                pdf_url,
            ]

        lines += [
            "",
            _("Generated automatically by Route Core."),
        ]
        return "\n".join(lines)

    def _get_route_supervisor_resolution(self):
        self.ensure_one()
        empty_user = self.env["res.users"]
        empty_partner = self.env["res.partner"]
        result = {
            "user": empty_user,
            "partner": empty_partner,
            "phone": False,
            "reason": False,
            "status": _("No supervisor resolved"),
        }

        def _group_users(xmlid):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                return self.env["res.users"]
            users = getattr(group, "user_ids", False)
            if users is False:
                users = getattr(group, "users", self.env["res.users"])
            return users.filtered(lambda u: getattr(u, "active", True)) if users else self.env["res.users"]

        assignment = self.env["route.supervisor.assignment"]
        if "route.supervisor.assignment" in self.env:
            assignment = self.env["route.supervisor.assignment"].sudo()._get_best_assignment_for_visit(self)

        if assignment:
            selected_user = assignment.supervisor_user_id
            partner = selected_user.partner_id if selected_user else empty_partner
            phone = self._route_normalize_whatsapp_phone(partner)
            reason_parts = [_("Matched from Supervisor Assignments.")]
            reason_parts.append(
                _("Rule: %(rule)s.") % {"rule": assignment.display_name or assignment.name}
            )
            if assignment.scope_label:
                reason_parts.append(
                    _("Scope: %(scope)s.") % {"scope": assignment.scope_label}
                )
            if selected_user:
                reason_parts.append(
                    _("Selected user: %(user)s.") % {"user": selected_user.name}
                )
            if partner:
                reason_parts.append(
                    _("Contact: %(contact)s.") % {"contact": partner.display_name}
                )
            if phone:
                reason_parts.append(
                    _("WhatsApp number found: %(phone)s.") % {"phone": phone}
                )
            else:
                reason_parts.append(
                    _("No WhatsApp number is set on the assigned supervisor contact.")
                )

            result.update(
                {
                    "user": selected_user,
                    "partner": partner,
                    "phone": phone,
                    "reason": " ".join(reason_parts),
                    "status": _("Supervisor resolved") if selected_user else _("No supervisor resolved"),
                }
            )
            return result

        users = _group_users("route_core.group_route_supervisor") | _group_users("route_core.group_route_management")
        if not users:
            result["reason"] = _(
                "No active users were found in the Route Supervisor or Route Management groups, and no supervisor assignment matched this visit."
            )
            return result

        reason_parts = [_("Matched from Route Supervisor / Route Management fallback groups.")]
        selected_users = users
        if self.company_id:
            company_users = users.filtered(
                lambda u: not getattr(u, "company_ids", False) or self.company_id in u.company_ids
            )
            if company_users:
                selected_users = company_users
                reason_parts.append(
                    _("Company filter applied: %(company)s.")
                    % {"company": self.company_id.display_name}
                )
            else:
                reason_parts.append(
                    _(
                        "No company-specific fallback supervisor matched %(company)s, so the first active fallback supervisor was used."
                    )
                    % {"company": self.company_id.display_name}
                )

        selected_user = selected_users[:1]
        partner = selected_user.partner_id if selected_user else empty_partner
        phone = self._route_normalize_whatsapp_phone(partner)

        if selected_user:
            reason_parts.append(
                _("Selected user: %(user)s.") % {"user": selected_user.name}
            )
        if partner:
            reason_parts.append(
                _("Contact: %(contact)s.") % {"contact": partner.display_name}
            )
        if phone:
            reason_parts.append(
                _("WhatsApp number found: %(phone)s.") % {"phone": phone}
            )
        else:
            reason_parts.append(
                _("No WhatsApp number is set on the selected fallback supervisor contact.")
            )

        result.update(
            {
                "user": selected_user,
                "partner": partner,
                "phone": phone,
                "reason": " ".join(reason_parts),
                "status": _("Supervisor resolved") if selected_user else _("No supervisor resolved"),
            }
        )
        return result

    def _get_route_supervisor_partner(self):
        return self._get_route_supervisor_resolution()["partner"]

    def action_send_direct_stop_whatsapp_outlet(self):
        self.ensure_one()
        partner = self.partner_id or self.outlet_id.partner_id
        phone = self._route_normalize_whatsapp_phone(partner)
        if not phone:
            raise UserError(_("Outlet WhatsApp number is missing. Please set mobile or phone on the outlet contact."))
        if self._is_direct_sales_stop():
            pdf_url = self._get_direct_stop_receipt_public_url()
            message = self._build_direct_stop_whatsapp_message(pdf_url=pdf_url)
        else:
            pdf_url = self._get_consignment_receipt_public_url()
            message = self._build_consignment_whatsapp_message(pdf_url=pdf_url)
        return {
            "type": "ir.actions.act_url",
            "url": "https://wa.me/%s?text=%s" % (phone, quote(message, safe="")),
            "target": "new",
        }

    def action_send_direct_stop_whatsapp_supervisor(self):
        self.ensure_one()
        resolution = self._get_route_supervisor_resolution()
        phone = resolution["phone"]
        if not phone:
            raise UserError(
                _(
                    "Supervisor WhatsApp number is missing. Resolution details: %(details)s"
                )
                % {"details": resolution["reason"] or _("No supervisor match details are available.")}
            )
        if self._is_direct_sales_stop():
            pdf_url = self._get_direct_stop_receipt_public_url()
            message = self._build_direct_stop_whatsapp_message(pdf_url=pdf_url)
        else:
            pdf_url = self._get_consignment_receipt_public_url()
            message = self._build_consignment_whatsapp_message(pdf_url=pdf_url)
        return {
            "type": "ir.actions.act_url",
            "url": "https://wa.me/%s?text=%s" % (phone, quote(message, safe="")),
            "target": "new",
        }






