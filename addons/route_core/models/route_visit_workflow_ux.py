from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"


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

    ux_can_create_direct_sale = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_direct_sale_orders = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_direct_sale_payments = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_create_direct_return = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_direct_returns = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_skip_direct_sale = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_skip_direct_return = fields.Boolean(compute="_compute_ux_workflow", store=False)
    ux_can_open_direct_stop_settlement = fields.Boolean(compute="_compute_ux_workflow", store=False)

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
        "route_operation_mode",
        "route_enable_direct_sale",
        "route_enable_direct_return",
        "outlet_operation_mode",
        "sale_order_id",
        "sale_order_count",
        "direct_stop_order_ids.state",
        "direct_stop_order_ids.amount_total",
        "direct_stop_return_ids.state",
        "direct_stop_return_ids.amount_total",
        "direct_stop_skip_sale",
        "direct_stop_skip_return",
        "direct_stop_sale_status",
        "direct_stop_return_status",
        "direct_stop_credit_amount",
        "direct_stop_credit_policy",
        "direct_stop_settlement_ready",
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
            rec.ux_can_create_direct_sale = bool(direct_sales_stop and rec.route_enable_direct_sale and rec.direct_stop_sale_status == "pending")
            rec.ux_can_open_direct_sale_orders = bool(direct_sales_stop and rec.route_enable_direct_sale and rec.direct_stop_order_count)
            rec.ux_can_open_direct_sale_payments = bool(direct_sales_stop and (rec.payment_ids or rec.remaining_due_amount > 0))
            rec.ux_can_create_direct_return = bool(direct_sales_stop and rec.route_enable_direct_return and rec.direct_stop_sale_status != "pending" and rec.direct_stop_return_status == "pending")
            rec.ux_can_open_direct_returns = bool(direct_sales_stop and rec.route_enable_direct_return and rec.direct_stop_return_count)
            rec.ux_can_skip_direct_sale = bool(direct_sales_stop and rec.state == "in_progress" and rec.direct_stop_sale_status == "pending")
            rec.ux_can_skip_direct_return = bool(direct_sales_stop and rec.state == "in_progress" and rec.direct_stop_sale_status != "pending" and rec.direct_stop_return_status == "pending")
            rec.ux_can_open_direct_stop_settlement = bool(direct_sales_stop and rec.state == "in_progress" and rec.direct_stop_sale_status != "pending" and rec.direct_stop_return_status != "pending")
            rec.ux_can_finish_visit = False

            if direct_sales_stop:
                has_draft_direct_stop_payments = bool(rec.payment_ids.filtered(lambda p: p.state == "draft"))
                if rec.state == "draft":
                    rec.ux_stage = "arrival"
                    rec.ux_primary_action = "start_visit"
                    rec.ux_stage_title = _("Start direct sales stop")
                    rec.ux_stage_help = _("Begin the direct sales stop.")
                elif rec.state == "in_progress":
                    if rec.direct_stop_sale_status == "pending":
                        rec.ux_stage = "arrival"
                        rec.ux_primary_action = "none"
                        rec.ux_stage_title = _("Sales decision")
                        rec.ux_stage_help = _("Do you want to create a direct sale order for this stop?")
                    elif rec.direct_stop_return_status == "pending":
                        rec.ux_stage = "returns"
                        rec.ux_primary_action = "none"
                        rec.ux_stage_title = _("Return decision")
                        rec.ux_stage_help = _("Is there a direct return for this stop?")
                    elif not rec.direct_stop_settlement_ready:
                        rec.ux_stage = "collection"
                        if has_draft_direct_stop_payments:
                            rec.ux_primary_action = "confirm_payments"
                        elif (rec.remaining_due_amount or 0.0) > 0.0:
                            rec.ux_primary_action = "collect_payment"
                        else:
                            rec.ux_primary_action = "none"
                        rec.ux_stage_title = _("Financial settlement")
                        rec.ux_stage_help = _("Review sales, returns, net due, then settle payment or choose a return credit settlement.")
                    else:
                        rec.ux_stage = "ready_to_close"
                        rec.ux_primary_action = "finish_visit"
                        rec.ux_stage_title = _("Ready to finish")
                        rec.ux_stage_help = _("The stop is financially settled and can now be finished.")
                        rec.ux_can_finish_visit = True
                else:
                    rec.ux_stage = "done"
                    rec.ux_primary_action = "none"
                    rec.ux_stage_title = _("Stop completed")
                    rec.ux_stage_help = _("No action required.")
                continue

            rec.ux_can_scan_barcode = (
                rec.state == "in_progress"
                and rec.visit_process_state in ("checked_in", "counting")
                and has_lines
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
                rec.ux_stage_help = _("Add a full payment, partial payment, deferment, or carry forward. Use Skip Collection below only when collection is not possible.")

            elif rec.visit_process_state in ("collection_done", "ready_to_close"):
                rec.ux_stage = "ready_to_close"
                rec.ux_primary_action = "finish_visit"
                rec.ux_stage_title = _("Finish visit")
                rec.ux_stage_help = _("Close the visit.")

            else:
                rec.ux_stage = "done"
                rec.ux_primary_action = "none"
                rec.ux_stage_title = _("Visit completed")
                rec.ux_stage_help = _("No action required.")

    def _get_pda_form_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("PDA Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("route_core.view_route_visit_pda_form").id,
            "target": "current",
            "context": {
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

    def action_ux_create_direct_sale(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        if not self.route_enable_direct_sale:
            raise UserError(_("Direct Sale is disabled in Route Settings."))
        self.direct_stop_skip_sale = False
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
                "route_visit_name": self.name,
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
            "domain": [("route_order_mode", "=", "direct_sale"), ("origin", "=", self.name)],
            "context": {"search_default_route_order_mode": "direct_sale", "create": 0},
        }

    def action_ux_open_direct_sale_payments(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        return {
            "type": "ir.actions.act_window",
            "name": _("Financial Settlement"),
            "res_model": "route.visit.payment",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("visit_id", "=", self.id)],
            "context": {
                "default_visit_id": self.id,
                "search_default_visit_id": self.id,
                "create": 0,
            },
        }

    def action_ux_create_direct_return(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        if not self.route_enable_direct_return:
            raise UserError(_("Direct Return is disabled in Route Settings."))
        self.direct_stop_skip_return = False
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
                "default_visit_id": self.id,
                "route_visit_id": self.id,
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
        return {
            "type": "ir.actions.act_window",
            "name": _("Direct Returns"),
            "res_model": "route.direct.return",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("visit_id", "=", self.id)],
        }

    def action_ux_skip_direct_sale(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        self.direct_stop_skip_sale = True
        return self._get_pda_form_action()

    def action_ux_skip_direct_return(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        self.direct_stop_skip_return = True
        return self._get_pda_form_action()

    def action_ux_open_direct_stop_settlement(self):
        self.ensure_one()
        self._ensure_direct_sales_stop()
        return self.action_ux_open_payments()

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
        self.action_load_previous_balance()
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
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit Payments"),
            "res_model": "route.visit.payment",
            "view_mode": "list,form",
            "target": "current",
            "domain": [("visit_id", "=", self.id)],
            "context": {
                "default_visit_id": self.id,
                "search_default_visit_id": self.id,
            },
        }

    def action_ux_collect_payment(self):
        self.ensure_one()

        if self._is_direct_sales_stop() and self.remaining_due_amount <= 0:
            return self._get_pda_form_action()

        if self.remaining_due_amount <= 0 and not self.collection_skip_reason:
            self._action_mark_collection_done()
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

    def action_ux_confirm_payments(self):
        self.ensure_one()
        draft_payments = self.payment_ids.filtered(lambda p: p.state == "draft")
        if not draft_payments:
            raise UserError(_("There are no draft payments to confirm."))

        draft_payments.action_confirm()
        if self._is_direct_sales_stop():
            self.write({"visit_process_state": "collection_done"})
        else:
            self._action_mark_collection_done()
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
            if self.direct_stop_sale_status == "pending":
                raise UserError(_("Please answer the sales decision first."))
            if self.direct_stop_return_status == "pending":
                raise UserError(_("Please answer the return decision first."))
            if self.payment_ids.filtered(lambda p: p.state == "draft"):
                raise UserError(_("Please confirm the draft settlement payment before finishing the stop."))
            if (self.remaining_due_amount or 0.0) > 0.0:
                raise UserError(_("Please settle the remaining amount before finishing the stop."))
            if (self.direct_stop_credit_amount or 0.0) > 0.0 and not self.direct_stop_credit_policy:
                raise UserError(_("Please choose how to settle the return credit before finishing the stop."))
            self.with_context(route_visit_force_write=True).write({
                "state": "done",
                "visit_process_state": "done",
                "end_datetime": fields.Datetime.now(),
            })
            return self._get_pda_form_action()

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
        return self._get_pda_form_action()

    def action_ux_finish_visit(self):
        return self._action_finish_visit_core()

    def action_ux_finalize_visit(self):
        return self._action_finish_visit_core()

    def action_ux_view_sale_order(self):
        self.ensure_one()
        return self.action_view_sale_order()


