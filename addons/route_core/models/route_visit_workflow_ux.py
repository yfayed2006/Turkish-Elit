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
            ("settlement", "Settlement"),
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
            ("finalize_visit", "Finalize Visit"),
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

    ux_can_create_sale_order = fields.Boolean(
        string="Can Create Sale Order",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_scan_barcode = fields.Boolean(
        string="Can Scan Barcode",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_view_sale_order = fields.Boolean(
        string="Can View Sale Order",
        compute="_compute_ux_workflow",
        store=False,
    )

    ux_can_open_pending_refill = fields.Boolean(
        string="Can Open Pending Refill",
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
        "refill_backorder_id",
    )
    def _compute_ux_workflow(self):
        for rec in self:
            rec.ux_can_scan_barcode = rec.state == "in_progress" and rec.visit_process_state in (
                "checked_in",
                "counting",
            )
            rec.ux_can_create_sale_order = bool(
                rec.state == "in_progress"
                and rec.sold_total_qty > 0
                and not rec.sale_order_id
            )
            rec.ux_can_view_sale_order = bool(rec.sale_order_id or rec.sale_order_count)
            rec.ux_can_open_pending_refill = bool(
                rec.has_pending_refill or rec.refill_backorder_id
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
                rec.ux_stage_help = "After finishing the shelf count, confirm reconciliation to calculate sold quantities."
                continue

            if rec.visit_process_state in ("reconciled", "collection_done", "ready_to_close"):
                rec.ux_stage = "settlement"
                rec.ux_primary_action = "finalize_visit"
                rec.ux_stage_title = "Finalize settlement"
                rec.ux_stage_help = (
                    "Review refill, payment, and outlet balance, then complete the visit in one guided step."
                )
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
        return self.action_set_reconciled()

    def action_ux_finalize_visit(self):
        self.ensure_one()

        if self.visit_process_state == "reconciled":
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
                    "Before finalizing the visit, either:\n"
                    "- add/confirm payment(s), or\n"
                    "- enter a Collection Skip Reason."
                ))

            self.flush_recordset()

        if self.visit_process_state == "collection_done":
            self.action_update_outlet_balance()

        if self.visit_process_state == "ready_to_close":
            return self.action_set_done_process()

        raise UserError(_(
            "The visit is not yet ready for finalization.\n"
            "Current process state: %s"
        ) % (self.visit_process_state or "-"))

    def action_ux_create_sale_order(self):
        self.ensure_one()
        return self.action_create_sale_order()

    def action_ux_view_sale_order(self):
        self.ensure_one()
        return self.action_view_sale_order()
