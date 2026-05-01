from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RouteVisitEndWizard(models.TransientModel):
    _name = "route.visit.end.wizard"
    _description = "Route Visit End Wizard"

    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        required=True,
        readonly=True,
    )
    reason = fields.Text(
        string="Completion Note / No Sale Reason",
    )
    has_sale_qty = fields.Boolean(
        string="Has Sale Quantity",
        compute="_compute_finish_context",
        store=False,
    )
    has_operational_activity = fields.Boolean(
        string="Has Operational Activity",
        compute="_compute_finish_context",
        store=False,
    )
    reason_required = fields.Boolean(
        string="Reason Required",
        compute="_compute_finish_context",
        store=False,
    )
    finish_hint = fields.Text(
        string="Finish Guidance",
        compute="_compute_finish_context",
        store=False,
    )

    @api.depends(
        "visit_id",
        "visit_id.sale_order_id",
        "visit_id.refill_picking_id",
        "visit_id.line_ids.sold_qty",
        "visit_id.line_ids.supplied_qty",
        "visit_id.line_ids.return_qty",
        "visit_id.line_ids.counted_qty",
    )
    def _compute_finish_context(self):
        for wizard in self:
            visit = wizard.visit_id.sudo()
            lines = visit.line_ids.sudo() if visit else self.env["route.visit.line"]

            has_sale_qty = any((line.sold_qty or 0.0) > 0.0 for line in lines)
            has_refill_qty = any((line.supplied_qty or 0.0) > 0.0 for line in lines)
            has_return_qty = any((line.return_qty or 0.0) > 0.0 for line in lines)
            has_count_qty = any((line.counted_qty or 0.0) > 0.0 for line in lines)

            has_refill_document = bool(getattr(visit, "refill_picking_id", False))
            has_sale_document = bool(getattr(visit, "sale_order_id", False))

            has_operational_activity = bool(
                has_sale_qty
                or has_refill_qty
                or has_return_qty
                or has_count_qty
                or has_refill_document
                or has_sale_document
            )

            wizard.has_sale_qty = has_sale_qty
            wizard.has_operational_activity = has_operational_activity
            wizard.reason_required = not has_operational_activity

            if has_sale_qty and not has_sale_document:
                wizard.finish_hint = _(
                    "Sold quantities were recorded. Create the sale order before finishing this visit."
                )
            elif has_operational_activity:
                wizard.finish_hint = _(
                    "This visit has operational activity such as counting, refill, return, or linked documents. "
                    "You can finish the visit without a no-sale reason."
                )
            else:
                wizard.finish_hint = _(
                    "No sale or operational activity was recorded. Please enter a reason before finishing the visit."
                )

    def _get_return_action(self):
        self.ensure_one()

        plan_line = self.env["route.plan.line"].search(
            [("visit_id", "=", self.visit_id.id)],
            limit=1,
        )

        if plan_line and plan_line.plan_id:
            plan = plan_line.plan_id

            remaining_lines = plan.line_ids.filtered(
                lambda line: line.state == "pending"
            )

            if remaining_lines:
                action = self.env.ref("route_core.action_route_plan").read()[0]
                action["res_id"] = plan.id
                action["views"] = [(False, "form")]
                return action

            return self.env.ref("route_core.action_route_plan").read()[0]

        return self.env.ref("route_core.action_route_visit").read()[0]

    def _ensure_visit_can_finish(self):
        self.ensure_one()

        if not self.visit_id:
            raise UserError(_("No visit found."))

        visit = self.visit_id.sudo()
        if visit.state == "cancel" or visit.visit_process_state == "cancel":
            raise UserError(_("Cancelled visits cannot be ended."))

        if visit.visit_process_state == "done" and visit.state == "done":
            return visit

        allowed_process_states = {
            "reconciled",
            "collection_done",
            "ready_to_close",
        }
        if visit.state != "in_progress" and visit.visit_process_state not in allowed_process_states:
            raise UserError(_("Only active visits that reached the finish step can be ended."))

        return visit

    def action_create_sale_order(self):
        self.ensure_one()
        visit = self._ensure_visit_can_finish()

        if not self.has_sale_qty:
            raise UserError(_("There are no sold quantities to create a sale order."))

        return visit.action_create_sale_order()

    def action_end_without_sale(self):
        self.ensure_one()
        visit = self._ensure_visit_can_finish()

        if self.has_sale_qty and not visit.sale_order_id:
            raise UserError(_("Sold quantities exist. Please create the sale order before finishing the visit."))

        clean_reason = (self.reason or "").strip()
        if self.reason_required and not clean_reason:
            raise UserError(_("Please enter a reason before ending the visit without sale."))

        values = {
            "state": "done",
            "visit_process_state": "done",
            "end_datetime": fields.Datetime.now(),
        }
        if clean_reason:
            values["no_sale_reason"] = clean_reason

        visit.with_context(route_visit_force_write=True).write(values)

        if hasattr(visit, "_sync_shortages_from_visit"):
            visit._sync_shortages_from_visit()

        return self._get_return_action()

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}

        return self._get_return_action()

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
