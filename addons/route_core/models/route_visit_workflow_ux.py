from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

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
            ("returns_step", "Additional Returns"),
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

    ux_can_finish_visit = fields.Boolean(compute="_compute_ux_workflow", store=False)

    @api.depends(
        "state",
        "visit_process_state",
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
        "line_ids.product_id",
        "line_ids.previous_qty",
        "line_ids.counted_qty",
        "line_ids.supplied_qty",
        "line_ids.return_qty",
    )
    def _compute_ux_workflow(self):
        for rec in self:
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

            rec.ux_can_create_sale_order = False
            rec.ux_can_view_sale_order = bool(rec.sale_order_id or rec.sale_order_count)

            rec.ux_can_confirm_return_transfers = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and has_return_qty
                and not has_return_transfers
            )

            rec.ux_can_view_return_transfers = has_return_transfers

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

            rec.ux_can_view_refill_transfer = bool(
                rec.refill_picking_id or rec.refill_picking_count
            )

            rec.ux_can_open_pending_refill = bool(
                rec.has_pending_refill or rec.refill_backorder_id
            )

            rec.ux_can_collect_payment = (
                can_enter_collection
                and not rec.ux_can_open_pending_refill
                and not has_draft_payments
                and not rec.collection_skip_reason
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
                rec.state == "in_progress"
                and rec.visit_process_state in ("collection_done", "ready_to_close")
            )

            if rec.state == "draft":
                rec.ux_stage = "arrival"
                rec.ux_primary_action = "start_visit"
                rec.ux_stage_title = "Start the visit"
                rec.ux_stage_help = "Begin the visit."

            elif rec.state == "in_progress" and rec.visit_process_state == "pending":
                rec.ux_stage = "load_balance"
                rec.ux_primary_action = "load_previous_balance"
                rec.ux_stage_title = "Load previous balance"
                rec.ux_stage_help = "Load previous shelf quantities."

            elif load_balance_required:
                rec.ux_stage = "load_balance"
                rec.ux_primary_action = "load_previous_balance"
                rec.ux_stage_title = "Load previous balance"
                rec.ux_stage_help = "Load previous shelf quantities before counting."

            elif rec.visit_process_state == "checked_in":
                rec.ux_stage = "count"
                rec.ux_primary_action = "scan_shelf"
                rec.ux_stage_title = "Scan shelf stock"
                rec.ux_stage_help = "Scan the current shelf quantities."

            elif rec.visit_process_state == "counting" and not rec.returns_step_done:
                rec.ux_stage = "returns"
                rec.ux_primary_action = "returns_step"
                rec.ux_stage_title = "Additional Returns"
                rec.ux_stage_help = "Do you have any additional returns not recorded during shelf counting? Choose No Additional Returns or Add Additional Returns."

            elif rec.visit_process_state == "counting" and rec.returns_step_done:
                rec.ux_stage = "reconcile"
                rec.ux_primary_action = "reconcile_count"
                rec.ux_stage_title = "Reconcile counted stock"
                rec.ux_stage_help = "Confirm reconciliation."

            elif (
                rec.visit_process_state == "reconciled"
                and has_return_qty
                and not has_return_transfers
            ):
                rec.ux_stage = "return_transfer"
                rec.ux_primary_action = "confirm_return_transfers"
                rec.ux_stage_title = "Confirm return transfers"
                rec.ux_stage_help = "Create the internal transfers for returned products."

            elif (
                rec.visit_process_state == "reconciled"
                and not rec.refill_datetime
                and (not has_return_qty or has_return_transfers)
            ):
                rec.ux_stage = "refill"
                rec.ux_primary_action = "generate_refill"
                rec.ux_stage_title = "Generate refill proposal"
                rec.ux_stage_help = "Generate the suggested refill."

            elif (
                rec.visit_process_state == "reconciled"
                and (not has_return_qty or has_return_transfers)
                and bool(rec.refill_datetime)
                and has_supplied_qty
                and not rec.refill_picking_id
            ):
                rec.ux_stage = "refill"
                rec.ux_primary_action = "confirm_refill"
                rec.ux_stage_title = "Confirm refill transfer"
                rec.ux_stage_help = "Create the internal transfer from van to outlet."

            elif rec.ux_can_open_pending_refill:
                rec.ux_stage = "refill"
                rec.ux_primary_action = "open_pending_refill"
                rec.ux_stage_title = "Open pending refill"
                rec.ux_stage_help = "There is a pending refill/backorder that must be reviewed first."

            elif can_enter_collection and has_draft_payments:
                rec.ux_stage = "collection"
                rec.ux_primary_action = "confirm_payments"
                rec.ux_stage_title = "Confirm payments"
                rec.ux_stage_help = "Review and confirm the drafted payment decisions."

            elif (
                can_enter_collection
                and not has_confirmed_payments
                and not rec.collection_skip_reason
                and not rec.ux_can_open_pending_refill
            ):
                rec.ux_stage = "collection"
                rec.ux_primary_action = "collect_payment"
                rec.ux_stage_title = "Collect payment"
                rec.ux_stage_help = "Add a full payment, partial payment, deferment, or carry forward."

            elif rec.visit_process_state in ("collection_done", "ready_to_close"):
                rec.ux_stage = "ready_to_close"
                rec.ux_primary_action = "finish_visit"
                rec.ux_stage_title = "Finish visit"
                rec.ux_stage_help = "Close the visit."

            else:
                rec.ux_stage = "done"
                rec.ux_primary_action = "none"
                rec.ux_stage_title = "Visit completed"
                rec.ux_stage_help = "No action required."

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

    def action_ux_start_visit(self):
        self.ensure_one()
        self.action_start_visit()
        return self._get_pda_form_action()

    def action_ux_load_previous_balance(self):
        self.ensure_one()
        self.action_load_previous_balance()
        return self._get_pda_form_action()

    def action_ux_scan_shelf(self):
        self.ensure_one()
        return self.action_open_scan_wizard()

    def action_ux_returns_step(self):
        self.ensure_one()
        return self._action_open_returns_scan_wizard()

    def action_ux_no_returns(self):
        self.ensure_one()
        return self._action_mark_no_returns()

    def action_ux_reconcile_count(self):
        self.ensure_one()
        self.action_set_reconciled()

        if (
            self.visit_process_state == "reconciled"
            and self.sold_total_qty > 0
            and not self.sale_order_id
        ):
            self.action_create_sale_order()

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
        self.action_generate_refill_proposal()

        if not self.refill_datetime:
            self.write({"refill_datetime": fields.Datetime.now()})

        return self._get_pda_form_action()

    def action_ux_confirm_refill(self):
        self.ensure_one()
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

        if self.remaining_due_amount <= 0 and not self.collection_skip_reason:
            raise UserError(_("There is no remaining due amount to collect on this visit."))

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

    def action_ux_confirm_payments(self):
        self.ensure_one()
        draft_payments = self.payment_ids.filtered(lambda p: p.state == "draft")
        if not draft_payments:
            raise UserError(_("There are no draft payments to confirm."))

        self.action_confirm_all_payments()

        return self._get_pda_form_action()

    def action_ux_skip_collection(self):
        self.ensure_one()
        if not self.collection_skip_reason:
            raise UserError(_("Please enter Collection Skip Reason first."))

        self.action_skip_collection()

        return self._get_pda_form_action()

    def _action_finish_visit_core(self):
        self.ensure_one()

        if self.visit_process_state == "collection_done":
            self.action_update_outlet_balance()

        if self.visit_process_state == "ready_to_close":
            return self.action_set_done_process()

        raise UserError(_("The visit is not yet ready for closing."))

    def action_ux_finish_visit(self):
        return self._action_finish_visit_core()

    def action_ux_finalize_visit(self):
        return self._action_finish_visit_core()

    def action_ux_view_sale_order(self):
        self.ensure_one()
        return self.action_view_sale_order()
