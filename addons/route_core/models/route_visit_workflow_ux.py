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
            ("generate_refill", "Generate Refill Proposal"),
            ("confirm_refill", "Confirm Refill"),
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
        "collection_skip_reason",
        "has_pending_refill",
        "has_refill",
        "no_refill",
        "refill_backorder_id",
        "refill_datetime",
        "returns_step_done",
        "refill_picking_id",
        "refill_picking_count",
    )
    def _compute_ux_workflow(self):
        for rec in self:
            rec.ux_can_scan_barcode = (
                rec.state == "in_progress"
                and rec.visit_process_state in ("checked_in", "counting")
            )

            rec.ux_can_scan_returns = (
                rec.state == "in_progress"
                and rec.visit_process_state == "counting"
                and not rec.returns_step_done
            )
            rec.ux_can_no_returns = rec.ux_can_scan_returns

            rec.ux_can_create_sale_order = False
            rec.ux_can_view_sale_order = bool(rec.sale_order_id or rec.sale_order_count)

            rec.ux_can_generate_refill = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and not (rec.refill_datetime or rec.has_refill or rec.no_refill)
            )

            rec.ux_can_confirm_refill = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and bool(rec.refill_datetime or rec.has_refill or rec.no_refill)
                and not rec.refill_picking_id
            )

            rec.ux_can_view_refill_transfer = bool(rec.refill_picking_id or rec.refill_picking_count)

            rec.ux_can_open_pending_refill = bool(
                rec.has_pending_refill or rec.refill_backorder_id
            )

            rec.ux_can_collect_payment = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and (
                    bool(rec.refill_picking_id)
                    or not (rec.refill_datetime or rec.has_refill or rec.no_refill)
                )
            )
            rec.ux_can_confirm_payments = (
                rec.state == "in_progress"
                and rec.visit_process_state == "reconciled"
                and bool(rec.payment_ids.filtered(lambda p: p.state == "draft"))
            )
            rec.ux_can_skip_collection = rec.ux_can_collect_payment
            rec.ux_can_open_payments = rec.ux_can_collect_payment

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

            elif rec.visit_process_state == "checked_in":
                rec.ux_stage = "count"
                rec.ux_primary_action = "scan_shelf"
                rec.ux_stage_title = "Scan shelf stock"
                rec.ux_stage_help = "Scan the current shelf quantities."

            elif rec.visit_process_state == "counting" and not rec.returns_step_done:
                rec.ux_stage = "returns"
                rec.ux_primary_action = "returns_step"
                rec.ux_stage_title = "Returns step"
                rec.ux_stage_help = "Either scan returns or choose No Returns."

            elif rec.visit_process_state == "counting" and rec.returns_step_done:
                rec.ux_stage = "reconcile"
                rec.ux_primary_action = "reconcile_count"
                rec.ux_stage_title = "Reconcile counted stock"
                rec.ux_stage_help = "Confirm reconciliation."

            elif rec.visit_process_state == "reconciled" and not (
                rec.refill_datetime or rec.has_refill or rec.no_refill
            ):
                rec.ux_stage = "refill"
                rec.ux_primary_action = "generate_refill"
                rec.ux_stage_title = "Generate refill proposal"
                rec.ux_stage_help = "Generate the suggested refill."

            elif (
                rec.visit_process_state == "reconciled"
                and bool(rec.refill_datetime or rec.has_refill or rec.no_refill)
                and not rec.refill_picking_id
            ):
                rec.ux_stage = "refill"
                rec.ux_primary_action = "confirm_refill"
                rec.ux_stage_title = "Confirm refill transfer"
                rec.ux_stage_help = "Create the internal transfer from van to outlet."

            elif (
                rec.visit_process_state == "reconciled"
                and not rec.payment_ids.filtered(lambda p: p.state == "confirmed")
                and not rec.collection_skip_reason
            ):
                rec.ux_stage = "collection"
                rec.ux_primary_action = "collect_payment"
                rec.ux_stage_title = "Collect payment"
                rec.ux_stage_help = "Add a payment or skip collection."

            elif rec.visit_process_state in ("collection_done", "ready_to_close"):
                rec.ux_stage = "ready_to_close"
                rec.ux_primary_action = "finalize_visit"
                rec.ux_stage_title = "Finish visit"
                rec.ux_stage_help = "Close the visit."

            else:
                rec.ux_stage = "done"
                rec.ux_primary_action = "none"
                rec.ux_stage_title = "Visit completed"
                rec.ux_stage_help = "No action required."

    def action_ux_start_visit(self):
        self.ensure_one()
        return self.action_start_visit()

    def action_ux_load_previous_balance(self):
        self.ensure_one()
        return self.action_load_previous_balance()

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

        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_ux_generate_refill(self):
        self.ensure_one()
        self.action_generate_refill_proposal()

        if not self.refill_datetime:
            self.write({"refill_datetime": fields.Datetime.now()})

        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_ux_confirm_refill(self):
        self.ensure_one()
        self.action_confirm_refill_transfer()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit"),
            "res_model": "route.visit",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_ux_view_refill_transfer(self):
        self.ensure_one()
        return self.action_view_refill_transfer()

    def action_ux_open_payments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Visit Payment"),
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
