from odoo import _, api, fields, models


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    code = fields.Char(string="Outlet Code", index=True)
    barcode = fields.Char(string="Outlet Barcode", index=True)
    default_commission_rate = fields.Float(string="Default Commission %", default=20.0)
    active_stock_tracking = fields.Boolean(string="Active Stock Tracking", default=True)
    direct_sale_pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Direct Sale Pricelist",
        ondelete="set null",
        help="Optional pricelist used for this outlet when operation mode is Direct Sale.",
    )

    last_visit_id = fields.Many2one(
        "route.visit",
        string="Last Visit",
        ondelete="set null",
    )

    last_settlement_date = fields.Datetime(string="Last Settlement Date")



    route_financial_open_due_amount = fields.Monetary(
        string="Open Due",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_effective_collected_amount = fields.Monetary(
        string="Effective Collected",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
        help="Operational amount currently covering the outlet balance. Bounced/cancelled cheques are excluded by their financial policy.",
    )
    route_financial_open_promise_amount = fields.Monetary(
        string="Open Promise Amount",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_bank_pos_pending_amount = fields.Monetary(
        string="Bank/POS Pending Confirmation",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_bank_pos_verified_not_posted_amount = fields.Monetary(
        string="Bank/POS Confirmed Not Posted",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_bank_pos_followup_amount = fields.Monetary(
        string="Bank/POS Follow-up",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_cheque_pending_amount = fields.Monetary(
        string="Cheque Pending Clearance",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_cheque_open_due_amount = fields.Monetary(
        string="Cheque Open Due",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_cheque_cleared_amount = fields.Monetary(
        string="Cheque Cleared",
        currency_field="currency_id",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_open_item_count = fields.Integer(
        string="Financial Items",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_profile_state = fields.Selection(
        [
            ("clear", "Financially Clear"),
            ("watch", "Pending Review"),
            ("attention", "Needs Follow-up"),
        ],
        string="Financial Profile Status",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )
    route_financial_profile_label = fields.Char(
        string="Financial Profile Label",
        compute="_compute_route_outlet_financial_profile",
        store=False,
    )

    @api.depends(
        "current_due_amount",
        "total_collected_amount",
        "payment_ids",
        "payment_ids.amount",
        "payment_ids.state",
        "payment_ids.payment_mode",
        "payment_ids.collection_type",
        "payment_ids.promise_amount",
        "payment_ids.promise_date",
        "payment_ids.due_date",
        "payment_ids.reference",
        "payment_ids.bank_name",
        "payment_ids.cheque_number",
        "payment_ids.cheque_date",
    )
    def _compute_route_outlet_financial_profile(self):
        for outlet in self:
            confirmed_payments = outlet.payment_ids.filtered(lambda payment: payment.state == "confirmed")

            open_due_amount = outlet.current_due_amount or 0.0
            effective_collected_amount = 0.0
            open_promise_amount = 0.0
            bank_pos_pending_amount = 0.0
            bank_pos_verified_not_posted_amount = 0.0
            bank_pos_followup_amount = 0.0
            cheque_pending_amount = 0.0
            cheque_open_due_amount = 0.0
            cheque_cleared_amount = 0.0

            for payment in confirmed_payments:
                amount = payment.amount or 0.0
                if hasattr(payment, "_get_route_financial_collected_amount"):
                    effective_collected_amount += payment._get_route_financial_collected_amount() or 0.0
                elif payment.payment_mode != "deferred":
                    effective_collected_amount += amount

                promise_status = getattr(payment, "promise_status", False)
                remaining_due = getattr(payment, "remaining_due_amount", 0.0) or 0.0
                if (
                    payment.collection_type in ("defer_date", "next_visit")
                    or (payment.promise_amount or 0.0) > 0.0
                    or promise_status in ("open", "due_today", "overdue")
                ):
                    if promise_status != "closed" and (remaining_due > 0.0 or (payment.promise_amount or 0.0) > 0.0):
                        open_promise_amount += (
                            getattr(payment, "effective_promise_amount", 0.0)
                            or payment.promise_amount
                            or remaining_due
                            or 0.0
                        )

                if payment.payment_mode in ("bank", "pos"):
                    verification_state = getattr(payment, "electronic_verification_state", False) or "reported"
                    accounting_state = getattr(payment, "route_electronic_accounting_state", False) or "pending_verification"
                    if accounting_state == "posted":
                        continue
                    if accounting_state == "verified_not_posted":
                        bank_pos_verified_not_posted_amount += amount
                    elif accounting_state == "followup" or verification_state == "rejected":
                        bank_pos_followup_amount += amount
                    else:
                        bank_pos_pending_amount += amount

                if payment.payment_mode == "cheque":
                    cheque_pending_amount += getattr(payment, "cheque_pending_clearance_amount", 0.0) or 0.0
                    cheque_open_due_amount += getattr(payment, "cheque_open_due_amount", 0.0) or 0.0
                    cheque_cleared_amount += getattr(payment, "cheque_financially_cleared_amount", 0.0) or 0.0

            open_item_count = 0
            for value in (
                open_due_amount,
                open_promise_amount,
                bank_pos_pending_amount,
                bank_pos_verified_not_posted_amount,
                bank_pos_followup_amount,
                cheque_pending_amount,
                cheque_open_due_amount,
            ):
                if (value or 0.0) > 0.0:
                    open_item_count += 1

            if open_due_amount > 0.0 or cheque_open_due_amount > 0.0 or bank_pos_followup_amount > 0.0:
                profile_state = "attention"
                profile_label = _("Needs Follow-up")
            elif bank_pos_pending_amount > 0.0 or bank_pos_verified_not_posted_amount > 0.0 or cheque_pending_amount > 0.0 or open_promise_amount > 0.0:
                profile_state = "watch"
                profile_label = _("Pending Review")
            else:
                profile_state = "clear"
                profile_label = _("Financially Clear")

            outlet.route_financial_open_due_amount = open_due_amount
            outlet.route_financial_effective_collected_amount = effective_collected_amount
            outlet.route_financial_open_promise_amount = open_promise_amount
            outlet.route_financial_bank_pos_pending_amount = bank_pos_pending_amount
            outlet.route_financial_bank_pos_verified_not_posted_amount = bank_pos_verified_not_posted_amount
            outlet.route_financial_bank_pos_followup_amount = bank_pos_followup_amount
            outlet.route_financial_cheque_pending_amount = cheque_pending_amount
            outlet.route_financial_cheque_open_due_amount = cheque_open_due_amount
            outlet.route_financial_cheque_cleared_amount = cheque_cleared_amount
            outlet.route_financial_open_item_count = open_item_count
            outlet.route_financial_profile_state = profile_state
            outlet.route_financial_profile_label = profile_label

    def action_open_financial_profile(self):
        self.ensure_one()
        view = self.env.ref("route_core.view_route_outlet_financial_profile_form", raise_if_not_found=False)
        context = self._get_pda_clean_action_context(route_outlet_back_id=self.id) if hasattr(self, "_get_pda_clean_action_context") else dict(self.env.context or {})
        context.update({"create": 0, "edit": 0, "delete": 0})
        action = {
            "type": "ir.actions.act_window",
            "name": _("Outlet Financial Profile"),
            "res_model": "route.outlet",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": context,
        }
        if view:
            action["views"] = [(view.id, "form")]
        return action

    def action_view_bank_pos_payments(self):
        self.ensure_one()
        action = self.action_view_payments()
        action["name"] = _("Bank/POS Payments")
        action["domain"] = [("outlet_id", "=", self.id), ("payment_mode", "in", ["bank", "pos"])]
        return action

    def action_view_cheque_payments(self):
        self.ensure_one()
        action = self.action_view_payments()
        action["name"] = _("Cheque Payments")
        action["domain"] = [("outlet_id", "=", self.id), ("payment_mode", "=", "cheque")]
        return action

    @api.onchange("partner_id", "outlet_operation_mode")
    def _onchange_direct_sale_pricelist(self):
        for record in self:
            if record.outlet_operation_mode != "direct_sale":
                record.direct_sale_pricelist_id = False
                continue
            if not record.direct_sale_pricelist_id and record.partner_id and record.partner_id.property_product_pricelist:
                record.direct_sale_pricelist_id = record.partner_id.property_product_pricelist

    @api.onchange("outlet_operation_mode")
    def _onchange_outlet_setup_mode(self):
        for record in self:
            if record.outlet_operation_mode != "consignment" and "stock_location_id" in record._fields:
                record.stock_location_id = False
