from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RouteVisit(models.Model):
    _inherit = "route.visit"

    ux_stage = fields.Selection(
        [
            ("arrival", "Arrival"),
            ("load_balance", "Load Balance"),
            ("count", "Count Shelf"),
            ("reconcile", "Reconcile"),
            ("refill", "Refill"),
            ("collection", "Collection"),
            ("ready_to_close", "Ready to Close"),
            ("done", "Done"),
        ],
        string="Workflow Stage",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_primary_action = fields.Selection(
        [
            ("start_visit", "Start Visit"),
            ("load_previous_balance", "Load Previous Balance"),
            ("scan_shelf", "Scan Shelf"),
            ("reconcile_count", "Reconcile Count"),
            ("generate_refill", "Generate Refill Proposal"),
            ("collect_payment", "Collect Payment"),
            ("confirm_payments", "Confirm Payments"),
            ("finalize_visit", "Finalize Visit"),
            ("finish_visit", "Finish Visit"),
            ("none", "No Action"),
        ],
        string="Primary Action",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_stage_title = fields.Char(
        string="Stage Title",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_stage_help = fields.Char(
        string="Stage Help",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_scan_barcode = fields.Boolean(
        string="Can Scan Barcode",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_create_sale_order = fields.Boolean(
        string="Can Create Sale Order",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_view_sale_order = fields.Boolean(
        string="Can View Sale Order",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_generate_refill = fields.Boolean(
        string="Can Generate Refill",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_open_pending_refill = fields.Boolean(
        string="Can Open Pending Refill",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_collect_payment = fields.Boolean(
        string="Can Collect Payment",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_confirm_payments = fields.Boolean(
        string="Can Confirm Payments",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_skip_collection = fields.Boolean(
        string="Can Skip Collection",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_open_payments = fields.Boolean(
        string="Can Open Payments",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_finish_visit = fields.Boolean(
        string="Can Finish Visit",
        compute="_compute_ux_workflow",
        store=False,
    )

    @api.depends(
        "state",
        "visit_process_state",
        "sale_order_id",
        "sale_order_count",
        "sold_total_qty",
        "payment_ids.state",
        "collection_skip_reason",
        "remaining_due_amount",
        "has_pending_refill",
        "has_refill",
        "no_refill",
        "refill_backorder_id",
        "refill_datetime",
    )
    def _compute_ux_workflow(self):
        for rec in self:
            draft_payments = rec.payment_ids.filtered(lambda p: p.state == "draft")
            confirmed_payments = rec.payment_ids.filtered(lambda p: p.state == "confirmed")

            # المهم هنا:
            # refill يعتبر "تم" فقط إذا تم تنفيذ step التوليد فعليًا
            refill_generated = bool(rec.refill_datetime or rec.no_refill)

            collection_ready = bool(
                draft_payments or confirmed_payments or rec.collection_skip_reason
            )

            rec.ux_can_scan_barcode = rec.state == "in_progress" and rec.visit_process_state in (
                "checked_in",
                "counting",
            )

            rec.ux_can_create_sale_order = False
            rec.ux_can_view_sale_order = bool(rec.sale_order_id or rec.sale_order_count)

            rec.ux_can_generate_refill = bool(
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and not refill_generated
            )

            rec.ux_can_open_pending_refill = bool(
                rec.has_pending_refill or rec.refill_backorder_id
            )

            rec.ux_can_collect_payment = bool(
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and refill_generated
            )

            rec.ux_can_confirm_payments = bool(
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and bool(draft_payments)
            )

            rec.ux_can_skip_collection = bool(
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and refill_generated
            )

            rec.ux_can_open_payments = bool(
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and refill_generated
            )

            rec.ux_can_finish_visit = bool(
                rec.state == "in_progress"
                and (
                    rec.visit_process_state in ("collection_done", "ready_to_close")
                    or (
                        rec.visit_process_state == "reconciled"
                        and refill_generated
                        and collection_ready
                    )
                )
            )

            if rec.state in ("done", "cancel") or rec.visit_process_state in ("done", "cancelled"):
                rec.ux_stage = "done"
                rec.ux_primary_action = "none"
                rec.ux_stage_title = "Visit Completed"
                rec.ux_stage_help = "This visit is already finalized."
                continue

            if rec.state == "draft":
                rec.ux_stage = "arrival"
                rec.ux_primary_action = "start_visit"
                rec.ux_stage_title = "Start the visit"
                rec.ux_stage_help = "Begin the stop when the representative reaches the outlet."
                continue

            if rec.state == "in_progress" and rec.visit_process_state == "pending":
                rec.ux_stage = "load_balance"
                rec.ux_primary_action = "load_previous_balance"
                rec.ux_stage_title = "Load previous shelf balance"
                rec.ux_stage_help = "Bring the previous outlet stock into the visit before counting sales."
                continue

            if rec.visit_process_state == "checked_in":
                rec.ux_stage = "count"
                rec.ux_primary_action = "scan_shelf"
                rec.ux_stage_title = "Scan shelf stock"
                rec.ux_stage_help = "Use Scan Barcode to record shelf quantities, then continue when counting is complete."
                continue

            if rec.visit_process_state == "counting":
                rec.ux_stage = "reconcile"
                rec.ux_primary_action = "reconcile_count"
                rec.ux_stage_title = "Reconcile counted stock"
                rec.ux_stage_help = "After finishing the shelf count, confirm reconciliation to calculate sold quantities and auto-create the sale order."
                continue

            if rec.visit_process_state == "reconciled":
                if not refill_generated:
                    rec.ux_stage = "refill"
                    rec.ux_primary_action = "generate_refill"
                    rec.ux_stage_title = "Generate refill proposal"
                    rec.ux_stage_help = "Calculate the suggested supply from vehicle stock and the remaining pending refill."
                    continue

                if draft_payments:
                    rec.ux_stage = "collection"
                    rec.ux_primary_action = "confirm_payments"
                    rec.ux_stage_title = "Confirm collected payments"
                    rec.ux_stage_help = "Review the entered payment lines and confirm them before closing the visit."
                    continue

                if not confirmed_payments and not rec.collection_skip_reason:
                    rec.ux_stage = "collection"
                    rec.ux_primary_action = "collect_payment"
                    rec.ux_stage_title = "Collect payment or skip collection"
                    rec.ux_stage_help = "Add a payment line or enter a Collection Skip Reason to continue."
                    continue

                rec.ux_stage = "ready_to_close"
                rec.ux_primary_action = "finalize_visit"
                rec.ux_stage_title = "Finish visit"
                rec.ux_stage_help = "Settlement is ready. Update balances and complete the visit."
                continue

            if rec.visit_process_state == "collection_done":
                rec.ux_stage = "ready_to_close"
                rec.ux_primary_action = "finalize_visit"
                rec.ux_stage_title = "Finish visit"
                rec.ux_stage_help = "Payments are complete. Update balances and close the visit."
                continue

            if rec.visit_process_state == "ready_to_close":
                rec.ux_stage = "ready_to_close"
                rec.ux_primary_action = "finalize_visit"
                rec.ux_stage_title = "Finish visit"
                rec.ux_stage_help = "The visit is ready to close."
                continue

            rec.ux_stage = "arrival"
            rec.ux_primary_action = "start_visit"
            rec.ux_stage_title = "Start the visit"
            rec.ux_stage_help = "Begin the visit to continue the workflow."

    def action_ux_start_visit(self):
        self.ensure_one()
        return self.action_start_visit()

    def action_ux_load_previous_balance(self):
        self.ensure_one()
        return self.action_load_previous_balance()

    def action_ux_scan_shelf(self):
        self.ensure_one()
        return self.action_open_scan_wizard()

    def action_ux_reconcile_count(self):
        self.ensure_one()

        self.action_set_reconciled()

        if self.visit_process_state == "reconciled" and self.sold_total_qty > 0 and not self.sale_order_id:
            self.action_create_sale_order()

        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_ux_create_sale_order(self):
        self.ensure_one()
        return self.action_view_sale_order() if self.sale_order_id else self.action_create_sale_order()

    def action_ux_generate_refill(self):
        self.ensure_one()
        self.action_generate_refill_proposal()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_ux_open_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit Payments"),
            "res_model": "route.visit.payment",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
                "default_payment_date": fields.Date.context_today(self),
            },
        }

    def action_ux_collect_payment(self):
        self.ensure_one()
        return self.action_ux_open_payments()

    def action_ux_confirm_payments(self):
        self.ensure_one()
        draft_payments = self.payment_ids.filtered(lambda p: p.state == "draft")
        if not draft_payments:
            raise UserError(_("There are no draft payments to confirm."))
        self.action_confirm_all_payments()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_ux_skip_collection(self):
        self.ensure_one()
        if not self.collection_skip_reason:
            raise UserError(_("Please enter Collection Skip Reason first."))
        self.action_skip_collection()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def _action_finish_visit_core(self):
        self.ensure_one()

        if self.visit_process_state == "reconciled":
            if self.sold_total_qty > 0 and not self.sale_order_id:
                self.action_create_sale_order()

            if not self.refill_datetime and not self.no_refill:
                self.action_generate_refill_proposal()

            draft_payments = self.payment_ids.filtered(lambda p: p.state == "draft")
            confirmed_payments = self.payment_ids.filtered(lambda p: p.state == "confirmed")

            if draft_payments:
                self.action_confirm_all_payments()
            elif confirmed_payments:
                self.write({
                    "visit_process_state": "collection_done",
                    "collection_datetime": fields.Datetime.now(),
                })
            elif self.collection_skip_reason:
                self.action_skip_collection()
            else:
                raise UserError(_(
                    "Before finishing the visit, either:\n"
                    "- add/confirm payment(s), or\n"
                    "- enter a Collection Skip Reason."
                ))

            self.flush_recordset()

        if self.visit_process_state == "collection_done":
            self.action_update_outlet_balance()

        if self.visit_process_state == "ready_to_close":
            return self.action_set_done_process()

        raise UserError(_(
            "The visit is not yet ready for closing.\n"
            "Current process state: %s"
        ) % (self.visit_process_state or "-"))

    def action_ux_finish_visit(self):
        return self._action_finish_visit_core()

    def action_ux_finalize_visit(self):
        return self._action_finish_visit_core()

    def action_ux_view_sale_order(self):
        self.ensure_one()
        return self.action_view_sale_order()
