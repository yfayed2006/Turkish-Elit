from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteChequeAccountingCompany(models.Model):
    _inherit = "res.company"

    route_cheque_accounting_enabled = fields.Boolean(
        string="Enable Route Cheque Accounting",
        default=False,
        help="When enabled, cheque follow-up can create accounting journal entries for received, cleared, bounced, and cancelled route cheques.",
    )
    route_cheque_accounting_auto_post = fields.Boolean(
        string="Auto Post Cheque Accounting",
        default=False,
        help="Automatically post cheque accounting entries when cheque status changes. Keep disabled while testing configuration, then enable when the flow is validated.",
    )
    route_cheque_accounting_posting_level = fields.Selection(
        [
            ("per_cheque", "Per Cheque"),
            ("per_allocation_line", "Per Allocation Line"),
        ],
        string="Cheque Accounting Posting Level",
        default="per_cheque",
        required=True,
        help="Per Cheque posts the visible Cheque Control amount only, which is the safest default for route operations. Per Allocation Line keeps the older detailed behavior and posts entries for each route collection allocation.",
    )
    route_cheque_accounting_journal_id = fields.Many2one(
        "account.journal",
        string="Route Cheque Journal",
        domain="[('company_id', '=', id)]",
        help="Miscellaneous journal used for route cheque received/open-due accounting entries.",
    )
    route_cheque_pending_account_id = fields.Many2one(
        "account.account",
        string="Cheques Under Collection Account",
        help="Asset/clearing account used while route cheques are received or deposited but not yet cleared by the bank.",
    )
    route_cheque_receivable_account_id = fields.Many2one(
        "account.account",
        string="Route Receivable / Open Due Account",
        help="Receivable or clearing account used to represent customer/outlet open due balances for route collections.",
    )
    route_cheque_bank_journal_id = fields.Many2one(
        "account.journal",
        string="Cleared Cheque Bank Journal",
        domain="[('company_id', '=', id), ('type', 'in', ['bank', 'cash'])]",
        help="Bank/cash journal debited when a route cheque is financially cleared.",
    )


class RouteVisitPaymentChequeFollowup(models.Model):
    _inherit = "route.visit.payment"

    cheque_followup_state = fields.Selection(
        [
            ("received", "Received"),
            ("deposited", "Under Bank Collection"),
            ("cleared", "Cleared"),
            ("bounced", "Bounced"),
            ("cancelled", "Cancelled"),
        ],
        string="Cheque Status",
        default=False,
        index=True,
        copy=False,
    )
    cheque_followup_state_label = fields.Char(
        string="Cheque Status Label",
        compute="_compute_cheque_followup_labels",
        store=False,
    )
    cheque_followup_due_label = fields.Char(
        string="Cheque Due Status",
        compute="_compute_cheque_followup_labels",
        store=False,
    )
    cheque_deposited_at = fields.Datetime(string="Sent To Bank At", copy=False)
    cheque_cleared_at = fields.Datetime(string="Cleared At", copy=False)
    cheque_bounced_at = fields.Datetime(string="Bounced At", copy=False)
    cheque_cancelled_at = fields.Datetime(string="Cheque Cancelled At", copy=False)
    cheque_followup_updated_at = fields.Datetime(string="Cheque Last Update", copy=False)
    cheque_followup_updated_by_id = fields.Many2one(
        "res.users",
        string="Cheque Updated By",
        readonly=True,
        copy=False,
    )
    cheque_followup_note = fields.Text(string="Cheque Follow-up Note", copy=False)

    cheque_custody_state = fields.Selection(
        [
            ("with_salesperson", "With Salesperson"),
            ("with_supervisor", "With Supervisor"),
            ("handed_to_accounting", "Handed to Accounting"),
            ("received_by_accounting", "Received by Accounting"),
        ],
        string="Physical Custody",
        default=False,
        index=True,
        copy=False,
        help="Tracks who physically holds the cheque before the bank/accounting lifecycle is completed.",
    )
    cheque_custody_state_label = fields.Char(
        string="Physical Custody Label",
        compute="_compute_cheque_custody_label",
        store=False,
    )
    cheque_supervisor_received_at = fields.Datetime(string="Supervisor Received At", copy=False)
    cheque_supervisor_received_by_id = fields.Many2one("res.users", string="Supervisor Received By", readonly=True, copy=False)
    cheque_handed_to_accounting_at = fields.Datetime(string="Handed to Accounting At", copy=False)
    cheque_handed_to_accounting_by_id = fields.Many2one("res.users", string="Handed to Accounting By", readonly=True, copy=False)
    cheque_accounting_received_at = fields.Datetime(string="Accounting Received At", copy=False)
    cheque_accounting_received_by_id = fields.Many2one("res.users", string="Accounting Received By", readonly=True, copy=False)

    route_cheque_is_supervisor_user = fields.Boolean(string="Is Route Cheque Supervisor User", compute="_compute_route_cheque_access_flags", store=False)
    route_cheque_is_accounting_user = fields.Boolean(string="Is Route Cheque Accounting User", compute="_compute_route_cheque_access_flags", store=False)
    route_cheque_can_supervisor_receive = fields.Boolean(string="Can Supervisor Receive Cheque", compute="_compute_route_cheque_access_flags", store=False)
    route_cheque_can_handover_accounting = fields.Boolean(string="Can Hand Over Cheque to Accounting", compute="_compute_route_cheque_access_flags", store=False)
    route_cheque_can_accountant_receive = fields.Boolean(string="Can Accountant Receive Cheque", compute="_compute_route_cheque_access_flags", store=False)
    route_cheque_can_accountant_work = fields.Boolean(string="Can Accountant Process Cheque", compute="_compute_route_cheque_access_flags", store=False)

    cash_custody_state = fields.Selection(
        [("with_salesperson", "With Salesperson"), ("handed_to_accounting", "Handed to Accounting"), ("received_by_accounting", "Received by Accounting"), ("variance", "Variance / Needs Review")],
        string="Cash Custody",
        default=False,
        index=True,
        copy=False,
        help="Tracks cash collected by the salesperson until Accounting confirms receipt.",
    )
    cash_custody_state_label = fields.Char(string="Cash Custody Label", compute="_compute_cash_custody_label", store=False)
    cash_handed_to_accounting_at = fields.Datetime(string="Cash Handed to Accounting At", copy=False)
    cash_handed_to_accounting_by_id = fields.Many2one("res.users", string="Cash Handed to Accounting By", readonly=True, copy=False)
    cash_accounting_received_at = fields.Datetime(string="Cash Accounting Received At", copy=False)
    cash_accounting_received_by_id = fields.Many2one("res.users", string="Cash Accounting Received By", readonly=True, copy=False)
    cash_handover_note = fields.Text(string="Cash Handover Note", copy=False)
    route_cash_can_handover_accounting = fields.Boolean(string="Can Hand Over Cash to Accounting", compute="_compute_route_cash_access_flags", store=False)
    route_cash_can_accountant_receive = fields.Boolean(string="Can Accountant Receive Cash", compute="_compute_route_cash_access_flags", store=False)
    route_cash_is_accounting_user = fields.Boolean(string="Is Cash Accounting User", compute="_compute_route_cash_access_flags", store=False)
    route_cash_is_salesperson_user = fields.Boolean(string="Is Cash Salesperson User", compute="_compute_route_cash_access_flags", store=False)

    cheque_financial_state = fields.Selection(
        [
            ("pending", "Pending Clearance"),
            ("cleared", "Financially Cleared"),
            ("open_due", "Open Due"),
            ("cancelled", "Cancelled"),
        ],
        string="Financial Effect",
        compute="_compute_cheque_financial_policy",
        store=True,
        index=True,
        copy=False,
    )
    cheque_financial_state_label = fields.Char(
        string="Financial Effect Label",
        compute="_compute_cheque_financial_policy",
        store=False,
    )
    cheque_collection_effect_bucket = fields.Selection(
        [
            ("pending", "Pending Clearance"),
            ("cleared", "Financially Cleared"),
            ("open_due", "Open Due"),
        ],
        string="Customer Balance Effect",
        compute="_compute_cheque_collection_effect_bucket",
        store=True,
        index=True,
        copy=False,
        help="Operational cheque effect used by filters and search panels. Bounced and cancelled cheques are grouped as Open Due because both return the amount to outlet receivable/open due.",
    )
    cheque_effective_collected_amount = fields.Monetary(
        string="Effective Collected",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
    )
    cheque_route_coverage_amount = fields.Monetary(
        string="Route Coverage",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
        help="Amount that still covers the route/customer balance before final bank clearance. Bounced or cancelled cheques do not cover the balance.",
    )
    cheque_pending_clearance_amount = fields.Monetary(
        string="Pending Bank Clearance",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
        help="Confirmed cheque amount waiting for bank deposit/clearance.",
    )
    cheque_financially_cleared_amount = fields.Monetary(
        string="Financially Cleared Amount",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
        help="Cheque amount that is finally cleared by the bank and can be treated as cash/bank collected for accounting integration.",
    )
    cheque_open_due_amount = fields.Monetary(
        string="Cheque Open Due",
        currency_field="currency_id",
        compute="_compute_cheque_financial_policy",
        store=False,
    )
    cheque_is_financially_cleared = fields.Boolean(
        string="Financially Cleared",
        compute="_compute_cheque_financial_policy",
        store=False,
    )
    cheque_needs_followup = fields.Boolean(
        string="Needs Follow-up",
        compute="_compute_cheque_financial_policy",
        store=True,
        index=True,
    )

    cheque_physical_group_key = fields.Char(
        string="Physical Cheque Group Key",
        compute="_compute_cheque_physical_group_key",
        store=True,
        index=True,
        copy=False,
        help="Technical key used to show one operational card per physical cheque while preserving detailed allocation lines in the background.",
    )
    cheque_physical_is_primary = fields.Boolean(
        string="Primary Physical Cheque Line",
        compute="_compute_cheque_physical_summary",
        search="_search_cheque_physical_is_primary",
        store=False,
        help="True only on the representative line used by Cheque Control to display one card per physical cheque.",
    )
    cheque_physical_total_amount = fields.Monetary(
        string="Physical Cheque Amount",
        currency_field="currency_id",
        compute="_compute_cheque_physical_summary",
        store=False,
        help="Total amount of all allocation lines covered by the same physical cheque.",
    )
    cheque_physical_allocation_count = fields.Integer(
        string="Allocation Lines",
        compute="_compute_cheque_physical_summary",
        store=False,
    )
    cheque_physical_display_ref = fields.Char(
        string="Physical Cheque Reference",
        compute="_compute_cheque_physical_summary",
        store=False,
    )
    cheque_physical_source_summary = fields.Char(
        string="Allocation Sources",
        compute="_compute_cheque_physical_summary",
        store=False,
    )
    cheque_physical_settlement_summary = fields.Char(
        string="Settlement Reference",
        compute="_compute_cheque_physical_summary",
        store=False,
    )
    cheque_physical_open_due_amount = fields.Monetary(
        string="Physical Cheque Open Due",
        currency_field="currency_id",
        compute="_compute_cheque_physical_summary",
        store=False,
    )

    route_cheque_accounting_enabled = fields.Boolean(
        string="Route Cheque Accounting Enabled",
        related="company_id.route_cheque_accounting_enabled",
        store=False,
        readonly=True,
    )
    route_cheque_accounting_auto_post = fields.Boolean(
        string="Auto Post Route Cheque Accounting",
        related="company_id.route_cheque_accounting_auto_post",
        store=False,
        readonly=True,
    )
    route_cheque_accounting_posting_level = fields.Selection(
        string="Cheque Accounting Posting Level",
        related="company_id.route_cheque_accounting_posting_level",
        store=False,
        readonly=True,
    )
    route_cheque_received_move_id = fields.Many2one(
        "account.move",
        string="Receipt Voucher Entry",
        readonly=True,
        copy=False,
    )
    route_cheque_cleared_move_id = fields.Many2one(
        "account.move",
        string="Cleared Accounting Entry",
        readonly=True,
        copy=False,
    )
    route_cheque_open_due_move_id = fields.Many2one(
        "account.move",
        string="Open Due Accounting Entry",
        readonly=True,
        copy=False,
    )
    route_cheque_accounting_state = fields.Selection(
        [
            ("disabled", "Accounting Disabled"),
            ("not_posted", "Not Posted"),
            ("received_posted", "Received Entry Posted"),
            ("cleared_posted", "Bank Cleared Entry Posted"),
            ("open_due_posted", "Open Due Entry Posted"),
        ],
        string="Accounting State",
        compute="_compute_route_cheque_accounting_state",
        store=False,
    )
    route_cheque_accounting_state_label = fields.Char(
        string="Accounting State Label",
        compute="_compute_route_cheque_accounting_state",
        store=False,
    )
    route_cheque_accounting_move_count = fields.Integer(
        string="Accounting Entries",
        compute="_compute_route_cheque_accounting_state",
        store=False,
    )

    def _route_user_is_route_salesperson_or_manager(self):
        user = self.env.user
        return bool(
            user.has_group("route_core.group_route_salesperson")
            or user.has_group("route_core.group_route_management")
            or user.has_group("base.group_system")
        )

    def _route_user_is_route_management_or_system(self):
        user = self.env.user
        return bool(user.has_group("route_core.group_route_management") or user.has_group("base.group_system"))

    def _route_user_can_handover_salesperson_record(self, rec):
        user = self.env.user
        if self._route_user_is_route_management_or_system():
            return True
        if not user.has_group("route_core.group_route_salesperson"):
            return False
        return bool(rec.salesperson_id and rec.salesperson_id == user)

    def _route_user_is_route_supervisor_or_manager(self):
        user = self.env.user
        return bool(
            user.has_group("route_core.group_route_supervisor")
            or user.has_group("route_core.group_route_management")
            or user.has_group("base.group_system")
        )

    def _route_user_is_route_cheque_accountant_or_manager(self):
        user = self.env.user
        # The bank/accounting lifecycle must be controlled by Accounting users.
        # Route Managers can still monitor the business flow, but they need the
        # Route Cheque Accountant role as well if they must process cheques.
        return bool(
            user.has_group("route_core.group_route_cheque_accountant")
            or user.has_group("base.group_system")
        )

    def _check_route_cheque_salesperson_user(self):
        invalid_records = self.filtered(lambda rec: not self._route_user_can_handover_salesperson_record(rec))
        if invalid_records:
            raise ValidationError(_("Only the responsible salesperson or Route Management can hand over collected cheques to Accounting."))

    def _check_route_cheque_supervisor_user(self):
        if not self._route_user_is_route_supervisor_or_manager():
            raise ValidationError(_("Only a Route Supervisor or Route Manager can monitor route cheque custody."))

    def _check_route_cheque_accounting_user(self):
        if not self._route_user_is_route_cheque_accountant_or_manager():
            raise ValidationError(_("Only a Route Cheque Accountant can process the accounting lifecycle of route cheques."))

    def _check_route_cash_salesperson_user(self):
        invalid_records = self.filtered(lambda rec: not self._route_user_can_handover_salesperson_record(rec))
        if invalid_records:
            raise ValidationError(_("Only the responsible salesperson or Route Management can hand over collected cash to Accounting."))

    def _check_route_cash_accounting_user(self):
        if not self._route_user_is_route_cheque_accountant_or_manager():
            raise ValidationError(_("Only a Route Collections Accountant can confirm cash receipt."))

    @api.depends("payment_mode", "cheque_custody_state")
    def _compute_cheque_custody_label(self):
        labels = dict(self._fields["cheque_custody_state"].selection)
        for rec in self:
            if rec.payment_mode != "cheque":
                rec.cheque_custody_state_label = False
                continue
            state = rec.cheque_custody_state or "with_salesperson"
            rec.cheque_custody_state_label = labels.get(state, state)

    @api.depends("payment_mode", "state", "cheque_custody_state", "cheque_followup_state", "route_cheque_accounting_move_count")
    def _compute_route_cheque_access_flags(self):
        is_supervisor = self._route_user_is_route_supervisor_or_manager()
        is_accounting = self._route_user_is_route_cheque_accountant_or_manager()
        for rec in self:
            is_confirmed_cheque = rec.payment_mode == "cheque" and rec.state == "confirmed"
            custody_state = rec.cheque_custody_state or "with_salesperson"
            lifecycle_state = rec.cheque_followup_state or "received"
            is_final_lifecycle = lifecycle_state in ("cleared", "bounced", "cancelled")
            can_salesperson_handover = self._route_user_can_handover_salesperson_record(rec)
            rec.route_cheque_is_supervisor_user = is_supervisor
            rec.route_cheque_is_accounting_user = is_accounting
            rec.route_cheque_can_supervisor_receive = False
            rec.route_cheque_can_handover_accounting = bool(is_confirmed_cheque and can_salesperson_handover and custody_state in (False, "with_salesperson") and not is_final_lifecycle and rec.route_cheque_accounting_move_count == 0)
            rec.route_cheque_can_accountant_receive = bool(is_confirmed_cheque and is_accounting and custody_state == "handed_to_accounting")
            rec.route_cheque_can_accountant_work = bool(is_confirmed_cheque and is_accounting and custody_state == "received_by_accounting" and lifecycle_state in (False, "received", "deposited", "cleared", "bounced", "cancelled"))

    @api.depends("payment_mode", "state", "cash_custody_state")
    def _compute_route_cash_access_flags(self):
        is_accounting = self._route_user_is_route_cheque_accountant_or_manager()
        for rec in self:
            is_confirmed_cash = rec.payment_mode == "cash" and rec.state == "confirmed"
            custody_state = rec.cash_custody_state or "with_salesperson"
            can_salesperson_handover = self._route_user_can_handover_salesperson_record(rec)
            rec.route_cash_is_salesperson_user = can_salesperson_handover
            rec.route_cash_is_accounting_user = is_accounting
            rec.route_cash_can_handover_accounting = bool(is_confirmed_cash and can_salesperson_handover and custody_state in (False, "with_salesperson"))
            rec.route_cash_can_accountant_receive = bool(is_confirmed_cash and is_accounting and custody_state == "handed_to_accounting")

    @api.depends("payment_mode", "cash_custody_state")
    def _compute_cash_custody_label(self):
        labels = dict(self._fields["cash_custody_state"].selection)
        for rec in self:
            if rec.payment_mode != "cash":
                rec.cash_custody_state_label = False
                continue
            state = rec.cash_custody_state or "with_salesperson"
            rec.cash_custody_state_label = labels.get(state, state)

    def _route_cheque_normalize_group_value(self, value):
        if not value:
            return ""
        return str(value).strip().casefold()

    def _route_cheque_physical_anchor(self):
        self.ensure_one()
        if self.settlement_visit_id:
            return "settlement", self.settlement_visit_id.id
        if self.sale_order_id:
            return "sale_order", self.sale_order_id.id
        if self.visit_id:
            return "visit", self.visit_id.id
        return "payment", self.id or 0

    def _route_cheque_physical_outlet(self):
        self.ensure_one()
        if self.settlement_visit_id and self.settlement_visit_id.outlet_id:
            return self.settlement_visit_id.outlet_id
        if self.outlet_id:
            return self.outlet_id
        if self.visit_id and self.visit_id.outlet_id:
            return self.visit_id.outlet_id
        if self.sale_order_id and self.sale_order_id.route_outlet_id:
            return self.sale_order_id.route_outlet_id
        return self.env["route.outlet"]

    @api.depends(
        "company_id",
        "currency_id",
        "payment_mode",
        "state",
        "cheque_number",
        "bank_name",
        "cheque_date",
        "settlement_visit_id",
        "settlement_visit_id.outlet_id",
        "visit_id",
        "visit_id.outlet_id",
        "sale_order_id",
        "sale_order_id.route_outlet_id",
    )
    def _compute_cheque_physical_group_key(self):
        for rec in self:
            if rec.payment_mode != "cheque" or not rec.cheque_number or not rec.bank_name or not rec.cheque_date:
                rec.cheque_physical_group_key = False
                continue

            anchor_type, anchor_id = rec._route_cheque_physical_anchor()
            outlet = rec._route_cheque_physical_outlet()
            rec.cheque_physical_group_key = "|".join(
                [
                    str(rec.company_id.id or 0),
                    str(rec.currency_id.id or 0),
                    rec._route_cheque_normalize_group_value(rec.cheque_number),
                    rec._route_cheque_normalize_group_value(rec.bank_name),
                    fields.Date.to_string(rec.cheque_date) if rec.cheque_date else "",
                    str(outlet.id or 0),
                    anchor_type,
                    str(anchor_id or 0),
                ]
            )

    def _route_cheque_physical_group_domain(self):
        self.ensure_one()
        if not self.cheque_physical_group_key:
            return [("id", "=", self.id)]
        return [
            ("payment_mode", "=", "cheque"),
            ("state", "=", "confirmed"),
            ("company_id", "=", self.company_id.id),
            ("cheque_physical_group_key", "=", self.cheque_physical_group_key),
        ]

    def _route_cheque_physical_group_records(self):
        self.ensure_one()
        if not self.cheque_physical_group_key:
            return self
        return self.search(self._route_cheque_physical_group_domain())

    def _route_cheque_physical_primary_sort_key(self):
        self.ensure_one()
        is_settlement_current_line = bool(
            self.settlement_visit_id
            and self.visit_id
            and self.visit_id.id == self.settlement_visit_id.id
        )
        return (0 if is_settlement_current_line else 1, self.id or 0)

    def _search_cheque_physical_is_primary(self, operator, value):
        if operator not in ("=", "!="):
            raise ValidationError(_("Unsupported search operator for Primary Physical Cheque Line."))

        value = bool(value)
        wants_primary = (operator == "=" and value) or (operator == "!=" and not value)
        self.env.cr.execute(
            """
            SELECT id
              FROM (
                    SELECT id,
                           row_number() OVER (
                               PARTITION BY cheque_physical_group_key
                               ORDER BY CASE
                                            WHEN settlement_visit_id IS NOT NULL
                                             AND visit_id IS NOT NULL
                                             AND visit_id = settlement_visit_id THEN 0
                                            ELSE 1
                                        END,
                                        id
                           ) AS rn
                      FROM route_visit_payment
                     WHERE payment_mode = 'cheque'
                       AND state = 'confirmed'
                       AND cheque_physical_group_key IS NOT NULL
                       AND cheque_physical_group_key != ''
                   ) ranked
             WHERE rn = 1
            UNION
            SELECT id
              FROM route_visit_payment
             WHERE payment_mode = 'cheque'
               AND state = 'confirmed'
               AND (cheque_physical_group_key IS NULL OR cheque_physical_group_key = '')
            """
        )
        primary_ids = [row[0] for row in self.env.cr.fetchall()]
        if not primary_ids:
            primary_ids = [0]
        return [("id", "in" if wants_primary else "not in", primary_ids)]

    @api.depends(
        "cheque_physical_group_key",
        "payment_mode",
        "state",
        "amount",
        "source_document_ref",
        "settlement_document_ref",
        "visit_id",
        "settlement_visit_id",
        "cheque_open_due_amount",
        "route_cheque_received_move_id",
        "route_cheque_cleared_move_id",
        "route_cheque_open_due_move_id",
    )
    def _compute_cheque_physical_summary(self):
        empty = self.browse()
        grouped_records_by_key = {}
        keys = set(rec.cheque_physical_group_key for rec in self if rec.cheque_physical_group_key)
        if keys:
            physical_records = self.search([
                ("payment_mode", "=", "cheque"),
                ("state", "=", "confirmed"),
                ("cheque_physical_group_key", "in", list(keys)),
            ])
            for payment in physical_records:
                grouped_records_by_key.setdefault(payment.cheque_physical_group_key, empty)
                grouped_records_by_key[payment.cheque_physical_group_key] |= payment

        for rec in self:
            if rec.cheque_physical_group_key:
                group_records = grouped_records_by_key.get(rec.cheque_physical_group_key, rec)
            else:
                group_records = rec

            group_records = group_records.sorted(lambda payment: payment._route_cheque_physical_primary_sort_key())
            primary = group_records[:1]
            source_refs = []
            settlement_refs = []
            for payment in group_records:
                if payment.source_document_ref and payment.source_document_ref not in source_refs:
                    source_refs.append(payment.source_document_ref)
                if payment.settlement_document_ref and payment.settlement_document_ref not in settlement_refs:
                    settlement_refs.append(payment.settlement_document_ref)

            allocation_count = len(group_records)
            source_summary = ", ".join(source_refs[:4])
            if len(source_refs) > 4:
                source_summary = _("%(sources)s + %(extra)s more") % {
                    "sources": source_summary,
                    "extra": len(source_refs) - 4,
                }

            settlement_summary = ", ".join(settlement_refs[:2])
            if len(settlement_refs) > 2:
                settlement_summary = _("%(settlements)s + %(extra)s more") % {
                    "settlements": settlement_summary,
                    "extra": len(settlement_refs) - 2,
                }

            rec.cheque_physical_is_primary = bool(rec.id and primary and rec.id == primary.id)
            rec.cheque_physical_total_amount = sum(group_records.mapped("amount")) or rec.amount or 0.0
            rec.cheque_physical_allocation_count = allocation_count
            rec.cheque_physical_display_ref = settlement_summary or (primary.source_document_ref if primary else rec.source_document_ref) or rec.source_document_ref or rec.settlement_document_ref or _("Cheque")
            rec.cheque_physical_source_summary = source_summary or rec.source_document_ref or ""
            rec.cheque_physical_settlement_summary = settlement_summary or rec.settlement_document_ref or ""
            rec.cheque_physical_open_due_amount = sum(group_records.mapped("cheque_open_due_amount")) or 0.0

    @api.depends(
        "route_cheque_accounting_enabled",
        "payment_mode",
        "state",
        "cheque_followup_state",
        "route_cheque_received_move_id.state",
        "route_cheque_cleared_move_id.state",
        "route_cheque_open_due_move_id.state",
    )
    def _compute_route_cheque_accounting_state(self):
        state_labels = dict(self._fields["route_cheque_accounting_state"].selection)
        for rec in self:
            moves = rec._route_cheque_accounting_moves()
            rec.route_cheque_accounting_move_count = len(moves)

            if not rec.route_cheque_accounting_enabled or rec.payment_mode != "cheque" or rec.state != "confirmed":
                rec.route_cheque_accounting_state = "disabled"
            else:
                followup_state = rec.cheque_followup_state or "received"
                received_posted = bool(rec.route_cheque_received_move_id and rec.route_cheque_received_move_id.state == "posted")
                cleared_posted = bool(rec.route_cheque_cleared_move_id and rec.route_cheque_cleared_move_id.state == "posted")
                open_due_posted = bool(rec.route_cheque_open_due_move_id and rec.route_cheque_open_due_move_id.state == "posted")

                if followup_state == "cleared" and received_posted and cleared_posted:
                    rec.route_cheque_accounting_state = "cleared_posted"
                elif followup_state in ("bounced", "cancelled") and received_posted and open_due_posted:
                    rec.route_cheque_accounting_state = "open_due_posted"
                elif followup_state in (False, "received", "deposited") and received_posted:
                    rec.route_cheque_accounting_state = "received_posted"
                else:
                    rec.route_cheque_accounting_state = "not_posted"

            rec.route_cheque_accounting_state_label = state_labels.get(
                rec.route_cheque_accounting_state,
                rec.route_cheque_accounting_state or "",
            )

    def _route_cheque_accounting_moves(self):
        self.ensure_one()
        moves = self.env["account.move"]
        for move in (self.route_cheque_received_move_id, self.route_cheque_cleared_move_id, self.route_cheque_open_due_move_id):
            if move:
                moves |= move
        return moves.exists()

    def _route_cheque_validate_accounting_settings(self):
        self.ensure_one()
        company = self.company_id
        if not company.route_cheque_accounting_enabled:
            raise ValidationError(_("Enable Route Cheque Accounting in Route Settings first."))
        if not company.route_cheque_accounting_journal_id:
            raise ValidationError(_("Configure Route Cheque Journal in Route Settings."))
        if not company.route_cheque_pending_account_id:
            raise ValidationError(_("Configure Cheques Under Collection Account in Route Settings."))
        if not company.route_cheque_receivable_account_id:
            raise ValidationError(_("Configure Route Receivable / Open Due Account in Route Settings."))
        return company

    def _route_cheque_get_partner(self):
        self.ensure_one()
        outlet = self.outlet_id or (self.visit_id.outlet_id if self.visit_id else False) or (self.settlement_visit_id.outlet_id if self.settlement_visit_id else False)
        return outlet.partner_id if outlet and outlet.partner_id else False

    def _route_cheque_move_ref(self, label):
        self.ensure_one()
        parts = [label]
        if self.cheque_number:
            parts.append(self.cheque_number)
        if self.source_document_ref:
            parts.append(self.source_document_ref)
        if self.settlement_document_ref and self.settlement_document_ref != self.source_document_ref:
            parts.append(self.settlement_document_ref)
        return " - ".join(parts)

    def _route_cheque_create_account_move(self, label, debit_account, credit_account, journal, amount, move_date, partner=False, ref=False):
        self.ensure_one()
        if (amount or 0.0) <= 0.0:
            return False
        if not debit_account or not credit_account or not journal:
            raise ValidationError(_("Missing accounting configuration for route cheque entry."))

        partner = partner or self._route_cheque_get_partner()
        ref = ref or self._route_cheque_move_ref(label)
        move_vals = {
            "move_type": "entry",
            "company_id": self.company_id.id,
            "journal_id": journal.id,
            "date": move_date or fields.Date.context_today(self),
            "ref": ref,
            "line_ids": [
                (0, 0, {
                    "name": ref,
                    "account_id": debit_account.id,
                    "partner_id": partner.id if partner else False,
                    "debit": amount,
                    "credit": 0.0,
                }),
                (0, 0, {
                    "name": ref,
                    "account_id": credit_account.id,
                    "partner_id": partner.id if partner else False,
                    "debit": 0.0,
                    "credit": amount,
                }),
            ],
        }
        move = self.env["account.move"].sudo().with_company(self.company_id).create(move_vals)
        move.action_post()
        return move

    def _route_cheque_accounting_group_key(self):
        self.ensure_one()
        posting_level = self.company_id.route_cheque_accounting_posting_level or "per_cheque"

        if posting_level == "per_cheque" and self.cheque_physical_group_key:
            source_key = ("physical_cheque", self.cheque_physical_group_key)
        elif self.settlement_visit_id:
            source_key = ("settlement_visit", self.settlement_visit_id.id)
        elif self.visit_id:
            source_key = ("visit", self.visit_id.id)
        elif self.sale_order_id:
            source_key = ("sale_order", self.sale_order_id.id)
        else:
            source_key = ("payment", self.id)
        return (
            self.company_id.id,
            self.currency_id.id,
            self.cheque_number or "",
            self.bank_name or "",
            self.cheque_date or False,
            source_key,
        )

    def _route_cheque_group_accounting_batches(self):
        groups = {}
        for rec in self:
            rec._ensure_cheque_followup_payment()
            groups.setdefault(rec._route_cheque_accounting_group_key(), self.browse())
            groups[rec._route_cheque_accounting_group_key()] |= rec
        return list(groups.values())

    def _route_cheque_batch_amount(self):
        if not self:
            return 0.0
        return sum(self.mapped("amount")) or 0.0

    def _route_cheque_batch_partner(self):
        partners = self.env["res.partner"]
        for rec in self:
            partner = rec._route_cheque_get_partner()
            if partner:
                partners |= partner
        # Route cheques should normally belong to a single outlet/customer.
        # If old data unexpectedly contains several partners in the same cheque
        # batch, use the first partner so receivable accounts still post safely.
        return partners[:1] if partners else False

    def _route_cheque_batch_move_ref(self, label):
        records = self.sorted(lambda rec: (rec.payment_date or fields.Datetime.now(), rec.id))
        first = records[:1]
        parts = [label]
        if first.cheque_number:
            parts.append(first.cheque_number)
        settlement_ref = first.settlement_document_ref or ""
        source_ref = first.source_document_ref or ""
        if settlement_ref:
            parts.append(settlement_ref)
        if len(records) == 1 and source_ref and source_ref != settlement_ref:
            parts.append(source_ref)
        elif len(records) > 1:
            parts.append(_("%(count)s allocations") % {"count": len(records)})
        return " - ".join(parts)

    def _route_cheque_batch_date(self, field_name=False, fallback_field="payment_date"):
        records = self.sorted(lambda rec: (getattr(rec, field_name or fallback_field, False) or getattr(rec, fallback_field, False) or fields.Datetime.now(), rec.id))
        value = False
        if field_name:
            value = next((getattr(rec, field_name, False) for rec in records if getattr(rec, field_name, False)), False)
        if not value and fallback_field:
            value = next((getattr(rec, fallback_field, False) for rec in records if getattr(rec, fallback_field, False)), False)
        return fields.Date.to_date(value) if value else fields.Date.context_today(self)

    def _route_cheque_get_shared_accounting_move(self, field_name):
        moves = self.mapped(field_name).exists()
        if not moves:
            return False
        if len(moves) > 1:
            raise ValidationError(
                _(
                    "This cheque already has multiple accounting entries for the same posting step. "
                    "It was probably posted using Per Allocation Line. Keep those detailed entries, "
                    "or reverse/correct them before posting the cheque as one grouped accounting entry."
                )
            )
        move = moves[:1]
        if move.state != "posted":
            move.action_post()
        missing_records = self.filtered(lambda rec: not getattr(rec, field_name))
        if missing_records:
            missing_records.sudo().write({field_name: move.id})
        return move

    def _route_cheque_batch_create_account_move(self, label, debit_account, credit_account, journal, amount, move_date):
        records = self.sorted(lambda rec: rec.id)
        first = records[:1]
        return first._route_cheque_create_account_move(
            label,
            debit_account,
            credit_account,
            journal,
            amount,
            move_date,
            partner=records._route_cheque_batch_partner(),
            ref=records._route_cheque_batch_move_ref(label),
        )

    def _route_cheque_ensure_received_accounting_entry_per_cheque(self):
        if not self:
            return False
        existing_move = self._route_cheque_get_shared_accounting_move("route_cheque_received_move_id")
        if existing_move:
            return existing_move

        first = self[:1]
        company = first._route_cheque_validate_accounting_settings()
        move = self._route_cheque_batch_create_account_move(
            _("Route Cheque Received"),
            company.route_cheque_pending_account_id,
            company.route_cheque_receivable_account_id,
            company.route_cheque_accounting_journal_id,
            self._route_cheque_batch_amount(),
            self._route_cheque_batch_date(fallback_field="payment_date"),
        )
        if move:
            self.sudo().write({"route_cheque_received_move_id": move.id})
        return move

    def _route_cheque_ensure_cleared_accounting_entry_per_cheque(self):
        if not self:
            return False
        existing_move = self._route_cheque_get_shared_accounting_move("route_cheque_cleared_move_id")
        if existing_move:
            return existing_move

        first = self[:1]
        company = first._route_cheque_validate_accounting_settings()
        bank_journal = company.route_cheque_bank_journal_id
        if not bank_journal:
            raise ValidationError(_("Configure Cleared Cheque Bank Journal in Route Settings."))
        bank_account = bank_journal.default_account_id
        if not bank_account:
            raise ValidationError(_("The selected Cleared Cheque Bank Journal has no default account."))

        self._route_cheque_ensure_received_accounting_entry_per_cheque()
        move = self._route_cheque_batch_create_account_move(
            _("Route Cheque Bank Cleared"),
            bank_account,
            company.route_cheque_pending_account_id,
            bank_journal,
            self._route_cheque_batch_amount(),
            self._route_cheque_batch_date(field_name="cheque_cleared_at", fallback_field="payment_date"),
        )
        if move:
            self.sudo().write({"route_cheque_cleared_move_id": move.id})
        return move

    def _route_cheque_ensure_open_due_accounting_entry_per_cheque(self, label):
        if not self:
            return False
        existing_move = self._route_cheque_get_shared_accounting_move("route_cheque_open_due_move_id")
        if existing_move:
            return existing_move

        first = self[:1]
        company = first._route_cheque_validate_accounting_settings()
        followup_state = first.cheque_followup_state or "received"
        date_field = False
        if followup_state == "bounced":
            date_field = "cheque_bounced_at"
        elif followup_state == "cancelled":
            date_field = "cheque_cancelled_at"

        self._route_cheque_ensure_received_accounting_entry_per_cheque()
        move = self._route_cheque_batch_create_account_move(
            label,
            company.route_cheque_receivable_account_id,
            company.route_cheque_pending_account_id,
            company.route_cheque_accounting_journal_id,
            self._route_cheque_batch_amount(),
            self._route_cheque_batch_date(field_name=date_field, fallback_field="payment_date"),
        )
        if move:
            self.sudo().write({"route_cheque_open_due_move_id": move.id})
        return move

    def _route_post_cheque_accounting_for_current_state_per_cheque(self):
        if not self:
            return False
        states = set((rec.cheque_followup_state or "received") for rec in self)
        if len(states) > 1:
            raise ValidationError(_("All records in one cheque accounting batch must have the same cheque follow-up status."))
        state = states.pop() if states else "received"
        if state in (False, "received", "deposited"):
            self._route_cheque_ensure_received_accounting_entry_per_cheque()
        elif state == "cleared":
            self._route_cheque_ensure_cleared_accounting_entry_per_cheque()
        elif state == "bounced":
            self._route_cheque_ensure_open_due_accounting_entry_per_cheque(_("Route Cheque Bounced"))
        elif state == "cancelled":
            self._route_cheque_ensure_open_due_accounting_entry_per_cheque(_("Route Cheque Cancelled"))
        return True

    def _route_cheque_ensure_received_accounting_entry(self):
        self.ensure_one()
        if self.route_cheque_received_move_id:
            if self.route_cheque_received_move_id.state != "posted":
                self.route_cheque_received_move_id.action_post()
            return self.route_cheque_received_move_id

        company = self._route_cheque_validate_accounting_settings()
        move = self._route_cheque_create_account_move(
            _("Route Cheque Received"),
            company.route_cheque_pending_account_id,
            company.route_cheque_receivable_account_id,
            company.route_cheque_accounting_journal_id,
            self.amount or 0.0,
            fields.Date.to_date(self.payment_date) or fields.Date.context_today(self),
        )
        if move:
            self.sudo().write({"route_cheque_received_move_id": move.id})
        return move

    def _route_cheque_ensure_cleared_accounting_entry(self):
        self.ensure_one()
        if self.route_cheque_cleared_move_id:
            if self.route_cheque_cleared_move_id.state != "posted":
                self.route_cheque_cleared_move_id.action_post()
            return self.route_cheque_cleared_move_id

        company = self._route_cheque_validate_accounting_settings()
        bank_journal = company.route_cheque_bank_journal_id
        if not bank_journal:
            raise ValidationError(_("Configure Cleared Cheque Bank Journal in Route Settings."))
        bank_account = bank_journal.default_account_id
        if not bank_account:
            raise ValidationError(_("The selected Cleared Cheque Bank Journal has no default account."))

        self._route_cheque_ensure_received_accounting_entry()
        move = self._route_cheque_create_account_move(
            _("Route Cheque Bank Cleared"),
            bank_account,
            company.route_cheque_pending_account_id,
            bank_journal,
            self.amount or 0.0,
            fields.Date.to_date(self.cheque_cleared_at) or fields.Date.context_today(self),
        )
        if move:
            self.sudo().write({"route_cheque_cleared_move_id": move.id})
        return move

    def _route_cheque_ensure_open_due_accounting_entry(self, label):
        self.ensure_one()
        if self.route_cheque_open_due_move_id:
            if self.route_cheque_open_due_move_id.state != "posted":
                self.route_cheque_open_due_move_id.action_post()
            return self.route_cheque_open_due_move_id

        company = self._route_cheque_validate_accounting_settings()
        followup_state = self.cheque_followup_state or "received"
        move_date = fields.Date.context_today(self)
        if followup_state == "bounced" and self.cheque_bounced_at:
            move_date = fields.Date.to_date(self.cheque_bounced_at)
        elif followup_state == "cancelled" and self.cheque_cancelled_at:
            move_date = fields.Date.to_date(self.cheque_cancelled_at)

        self._route_cheque_ensure_received_accounting_entry()
        move = self._route_cheque_create_account_move(
            label,
            company.route_cheque_receivable_account_id,
            company.route_cheque_pending_account_id,
            company.route_cheque_accounting_journal_id,
            self.amount or 0.0,
            move_date,
        )
        if move:
            self.sudo().write({"route_cheque_open_due_move_id": move.id})
        return move

    def _route_post_cheque_accounting_for_current_state(self):
        for batch_records in self._route_cheque_group_accounting_batches():
            first = batch_records[:1]
            posting_level = first.company_id.route_cheque_accounting_posting_level or "per_cheque"
            if posting_level == "per_cheque":
                batch_records._route_post_cheque_accounting_for_current_state_per_cheque()
                continue

            for rec in batch_records:
                state = rec.cheque_followup_state or "received"
                if state in (False, "received", "deposited"):
                    rec._route_cheque_ensure_received_accounting_entry()
                elif state == "cleared":
                    rec._route_cheque_ensure_cleared_accounting_entry()
                elif state == "bounced":
                    rec._route_cheque_ensure_open_due_accounting_entry(_("Route Cheque Bounced"))
                elif state == "cancelled":
                    rec._route_cheque_ensure_open_due_accounting_entry(_("Route Cheque Cancelled"))

    def action_route_post_cheque_accounting(self):
        self._check_route_cheque_accounting_user()
        records_for_custody = self._get_cheque_followup_batch_records()
        if records_for_custody.filtered(lambda payment: (payment.cheque_custody_state or "with_salesperson") != "received_by_accounting"):
            raise ValidationError(_("Accounting must confirm physical receipt of this cheque before posting cheque accounting entries."))
        # Cheque Control displays one card per physical cheque, while keeping the
        # allocation rows behind the scenes. Accounting must therefore post the
        # whole physical cheque group, not only the representative card line.
        records = self._get_cheque_followup_batch_records()
        records._ensure_cheque_followup_payment()
        records._route_post_cheque_accounting_for_current_state()
        return self._cheque_followup_reload_action()

    def action_route_open_cheque_accounting_moves(self):
        records = self._get_cheque_followup_batch_records() if self else self
        moves = self.env["account.move"]
        for rec in records:
            moves |= rec._route_cheque_accounting_moves()
        moves = moves.exists()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Cheque Accounting Entries"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
            "context": {"create": False},
        }
        if len(moves) == 1:
            action.update({"view_mode": "form", "res_id": moves.id})
        return action

    @api.depends("payment_mode", "state", "amount", "cheque_followup_state")
    def _compute_cheque_collection_effect_bucket(self):
        for rec in self:
            rec.cheque_collection_effect_bucket = False
            if rec.payment_mode != "cheque":
                continue

            followup_state = rec.cheque_followup_state or "received"
            amount = rec.amount or 0.0

            if rec.state != "confirmed":
                rec.cheque_collection_effect_bucket = "pending"
            elif followup_state == "cleared":
                rec.cheque_collection_effect_bucket = "cleared"
            elif followup_state in ("bounced", "cancelled") and amount:
                rec.cheque_collection_effect_bucket = "open_due"
            elif followup_state in ("bounced", "cancelled"):
                rec.cheque_collection_effect_bucket = "open_due"
            else:
                rec.cheque_collection_effect_bucket = "pending"

    @api.depends("payment_mode", "state", "amount", "cheque_followup_state")
    def _compute_cheque_financial_policy(self):
        for rec in self:
            rec.cheque_financial_state = False
            rec.cheque_financial_state_label = False
            rec.cheque_effective_collected_amount = 0.0
            rec.cheque_route_coverage_amount = 0.0
            rec.cheque_pending_clearance_amount = 0.0
            rec.cheque_financially_cleared_amount = 0.0
            rec.cheque_open_due_amount = 0.0
            rec.cheque_is_financially_cleared = False
            rec.cheque_needs_followup = False

            if rec.payment_mode != "cheque":
                continue

            followup_state = rec.cheque_followup_state or "received"
            amount = rec.amount or 0.0

            if rec.state != "confirmed":
                rec.cheque_financial_state = "pending"
                rec.cheque_financial_state_label = _("Pending Confirmation")
                continue

            if followup_state == "cleared":
                rec.cheque_financial_state = "cleared"
                rec.cheque_financial_state_label = _("Financially Cleared")
                rec.cheque_effective_collected_amount = amount
                rec.cheque_route_coverage_amount = amount
                rec.cheque_financially_cleared_amount = amount
                rec.cheque_is_financially_cleared = True
            elif followup_state == "bounced":
                rec.cheque_financial_state = "open_due"
                rec.cheque_financial_state_label = _("Bounced - Open Due")
                rec.cheque_open_due_amount = amount
                rec.cheque_needs_followup = True
            elif followup_state == "cancelled":
                rec.cheque_financial_state = "cancelled"
                rec.cheque_financial_state_label = _("Cancelled - No Collection")
                rec.cheque_open_due_amount = amount
                rec.cheque_needs_followup = True
            else:
                rec.cheque_financial_state = "pending"
                rec.cheque_financial_state_label = _("Pending Bank Clearance")
                rec.cheque_effective_collected_amount = amount
                rec.cheque_route_coverage_amount = amount
                rec.cheque_pending_clearance_amount = amount

    def _get_route_collection_covered_amount(self):
        """Operational amount that currently covers the outlet balance.

        A received/deposited cheque may close the field visit, but it remains
        pending for bank/accounting clearance. If the cheque later bounces or
        is cancelled, it no longer covers the balance and becomes open due.
        """
        self.ensure_one()
        if self.state != "confirmed":
            return 0.0
        if self.payment_mode == "cheque":
            if (self.cheque_followup_state or "received") in ("bounced", "cancelled"):
                return 0.0
            return self.cheque_route_coverage_amount or self.amount or 0.0
        return self.amount or 0.0

    def _get_route_accounting_cleared_amount(self):
        """Amount that is final for accounting/bank collection purposes."""
        self.ensure_one()
        if self.state != "confirmed":
            return 0.0
        if self.payment_mode == "cheque":
            return self.cheque_financially_cleared_amount or 0.0
        if self.payment_mode == "deferred":
            return 0.0
        return self.amount or 0.0

    def _get_route_pending_clearance_amount(self):
        self.ensure_one()
        if self.state != "confirmed" or self.payment_mode != "cheque":
            return 0.0
        return self.cheque_pending_clearance_amount or 0.0

    def _get_route_open_due_from_cheque_amount(self):
        self.ensure_one()
        if self.state != "confirmed" or self.payment_mode != "cheque":
            return 0.0
        return self.cheque_open_due_amount or 0.0

    def _get_route_financial_collected_amount(self):
        # Kept as the existing operational collection source used by visit
        # settlement screens. Use _get_route_accounting_cleared_amount() for
        # the future accounting/journal integration.
        return self._get_route_collection_covered_amount()

    def _get_route_financial_resolved_amount(self):
        self.ensure_one()
        if self.state != "confirmed":
            return 0.0
        resolved_amount = self._get_route_financial_collected_amount()
        if (self.promise_amount or 0.0) > 0.0:
            resolved_amount += self.promise_amount or 0.0
        return resolved_amount

    def _get_target_total_amount(self):
        self.ensure_one()
        if self.source_type == "direct_sale":
            return self.sale_order_id.amount_total or 0.0
        if self.visit_id and getattr(self.visit_id, "visit_execution_mode", False) == "direct_sales":
            return getattr(self.visit_id, "direct_stop_grand_due_amount", 0.0) or getattr(self.visit_id, "net_due_amount", 0.0) or 0.0
        if self.visit_id:
            return self.visit_id.net_due_amount or 0.0
        return 0.0

    def _get_target_remaining_due(self, exclude_self=False):
        self.ensure_one()
        total_amount = self._get_target_total_amount()
        confirmed_payments = self._get_confirmed_target_payments(exclude_self=exclude_self)
        resolved_amount = 0.0
        for payment in confirmed_payments:
            if hasattr(payment, "_get_route_financial_resolved_amount"):
                resolved_amount += payment._get_route_financial_resolved_amount()
            else:
                resolved_amount += payment.amount or 0.0
                if (payment.promise_amount or 0.0) > 0.0:
                    resolved_amount += payment.promise_amount or 0.0
        return max((total_amount or 0.0) - (resolved_amount or 0.0), 0.0)

    @api.depends(
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.promise_amount",
        "visit_id.payment_ids.state",
        "visit_id.payment_ids.payment_mode",
        "visit_id.payment_ids.cheque_followup_state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.promise_amount",
        "sale_order_id.direct_sale_payment_ids.state",
        "sale_order_id.direct_sale_payment_ids.payment_mode",
        "sale_order_id.direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_visit_remaining_due(self):
        for rec in self:
            rec.visit_remaining_due = rec._get_target_remaining_due() if rec._get_target_model() else 0.0

    @api.depends(
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.promise_amount",
        "visit_id.payment_ids.state",
        "visit_id.payment_ids.payment_mode",
        "visit_id.payment_ids.cheque_followup_state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.promise_amount",
        "sale_order_id.direct_sale_payment_ids.state",
        "sale_order_id.direct_sale_payment_ids.payment_mode",
        "sale_order_id.direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_remaining_due_amount(self):
        for rec in self:
            rec.remaining_due_amount = rec._get_target_remaining_due() if rec._get_target_model() else 0.0

    @api.depends(
        "state",
        "collection_type",
        "amount",
        "promise_amount",
        "promise_date",
        "due_date",
        "payment_mode",
        "cheque_followup_state",
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.promise_amount",
        "visit_id.payment_ids.state",
        "visit_id.payment_ids.payment_mode",
        "visit_id.payment_ids.cheque_followup_state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.promise_amount",
        "sale_order_id.direct_sale_payment_ids.state",
        "sale_order_id.direct_sale_payment_ids.payment_mode",
        "sale_order_id.direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_collection_filter_buckets(self):
        today = fields.Date.context_today(self)
        for rec in self:
            remaining_due = rec._get_target_remaining_due() if rec._get_target_model() else 0.0
            if rec.payment_mode == "cheque" and rec.state == "confirmed" and (rec.cheque_followup_state or "received") in ("bounced", "cancelled"):
                remaining_due = max(remaining_due, rec.amount or 0.0)

            rec.collection_due_bucket = "remaining_due" if (remaining_due or 0.0) > 0.0001 else "fully_collected"

            if rec.state != "confirmed" or (rec.promise_amount or 0.0) <= 0.0:
                rec.collection_promise_bucket = "no_promise"
            elif remaining_due <= 0.0001 and not rec._is_direct_stop_settlement_payment():
                rec.collection_promise_bucket = "closed"
            elif rec.promise_date and rec.promise_date < today:
                rec.collection_promise_bucket = "overdue"
            elif rec.promise_date and rec.promise_date == today:
                rec.collection_promise_bucket = "due_today"
            else:
                rec.collection_promise_bucket = "open"

    @api.depends(
        "promise_amount",
        "promise_date",
        "state",
        "payment_mode",
        "cheque_followup_state",
        "source_type",
        "visit_id.remaining_due_amount",
        "visit_id.payment_ids.amount",
        "visit_id.payment_ids.promise_amount",
        "visit_id.payment_ids.state",
        "visit_id.payment_ids.payment_mode",
        "visit_id.payment_ids.cheque_followup_state",
        "sale_order_id.amount_total",
        "sale_order_id.direct_sale_payment_ids.amount",
        "sale_order_id.direct_sale_payment_ids.promise_amount",
        "sale_order_id.direct_sale_payment_ids.state",
        "sale_order_id.direct_sale_payment_ids.payment_mode",
        "sale_order_id.direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_promise_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == "cancelled" or (rec.promise_amount or 0.0) <= 0:
                rec.promise_status = False
                continue

            if rec._is_direct_stop_settlement_payment():
                if rec.promise_date and rec.promise_date < today:
                    rec.promise_status = "overdue"
                elif rec.promise_date and rec.promise_date == today:
                    rec.promise_status = "due_today"
                else:
                    rec.promise_status = "open"
                continue

            remaining_due = rec._get_target_remaining_due()
            if remaining_due <= 0:
                rec.promise_status = "closed"
            elif rec.promise_date and rec.promise_date < today:
                rec.promise_status = "overdue"
            elif rec.promise_date and rec.promise_date == today:
                rec.promise_status = "due_today"
            else:
                rec.promise_status = "open"

    @api.model
    def init(self):
        """Backfill existing cheque payments after the feature is installed."""
        try:
            self.env.cr.execute(
                """
                UPDATE route_visit_payment
                   SET cheque_followup_state = 'received'
                 WHERE payment_mode = 'cheque'
                   AND (cheque_followup_state IS NULL OR cheque_followup_state = '')
                """
            )
            self.env.cr.execute(
                """
                UPDATE route_visit_payment
                   SET cheque_custody_state = 'with_salesperson'
                 WHERE payment_mode = 'cheque'
                   AND (cheque_custody_state IS NULL OR cheque_custody_state = '')
                """
            )
        except Exception:
            # Keep module upgrade safe even if the column is not ready in an unusual registry phase.
            pass

    @api.depends("payment_mode", "cheque_followup_state", "cheque_date", "cheque_custody_state")
    def _compute_cheque_followup_labels(self):
        today = fields.Date.context_today(self)
        state_labels = dict(self._fields["cheque_followup_state"].selection)
        for rec in self:
            if rec.payment_mode != "cheque":
                rec.cheque_followup_state_label = False
                rec.cheque_followup_due_label = False
                continue

            state = rec.cheque_followup_state or "received"
            rec.cheque_followup_state_label = state_labels.get(state, state)
            if state == "received" and rec.cheque_custody_state == "received_by_accounting":
                rec.cheque_followup_state_label = _("Received by Accounting")
            elif state == "received" and rec.cheque_custody_state != "received_by_accounting":
                rec.cheque_followup_state_label = _("Registered")

            if state == "cleared":
                rec.cheque_followup_due_label = _("Cleared")
            elif state == "bounced":
                rec.cheque_followup_due_label = _("Returned to Open Due")
            elif state == "cancelled":
                rec.cheque_followup_due_label = _("Cancelled - Open Due")
            elif state == "received":
                rec.cheque_followup_due_label = _("Receipt Voucher / Waiting Bank")
            elif not rec.cheque_date:
                rec.cheque_followup_due_label = _("No Cheque Date")
            elif rec.cheque_date < today:
                rec.cheque_followup_due_label = _("Overdue")
            elif rec.cheque_date == today:
                rec.cheque_followup_due_label = _("Due Today")
            else:
                rec.cheque_followup_due_label = _("Upcoming")

    def _ensure_cheque_followup_payment(self):
        for rec in self:
            if rec.payment_mode != "cheque":
                raise ValidationError(_("Cheque follow-up actions are available only for cheque payments."))
            if rec.state != "confirmed":
                raise ValidationError(_("Confirm the cheque payment before using cheque follow-up actions."))

    def _cheque_followup_reload_action(self):
        """Reload the current Odoo view after a status button updates the cheque.

        Cheque follow-up buttons are used from both the kanban/list controller and
        the form view. Returning a client reload keeps the user on the same screen
        while forcing the statusbar, visible buttons, search panel counters, and
        kanban badges to refresh immediately without a manual browser refresh.
        """
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def _validate_cheque_followup_transition(self, target_state):
        allowed_transitions = {
            "deposited": (False, "received"),
            "cleared": (False, "received", "deposited"),
            "bounced": (False, "received", "deposited"),
            "cancelled": (False, "received", "deposited", "bounced"),
        }
        for rec in self:
            current_state = rec.cheque_followup_state or "received"
            if current_state == target_state:
                continue
            if target_state in ("bounced", "cancelled") and current_state == "cleared":
                raise ValidationError(
                    _("This cheque is already financially cleared. Reset it to Received first if the cleared status was entered by mistake.")
                )
            if target_state in allowed_transitions and rec.cheque_followup_state not in allowed_transitions[target_state]:
                raise ValidationError(
                    _("Cheque status cannot be changed from %(current)s to %(target)s directly. Use Reset to Received first if this status was entered by mistake.")
                    % {
                        "current": dict(rec._fields["cheque_followup_state"].selection).get(current_state, current_state),
                        "target": dict(rec._fields["cheque_followup_state"].selection).get(target_state, target_state),
                    }
                )

    def _get_cheque_followup_batch_domain(self):
        self.ensure_one()
        if self.cheque_physical_group_key:
            return self._route_cheque_physical_group_domain()

        if not (self.cheque_number and self.bank_name and self.cheque_date):
            return [("id", "=", self.id)]

        domain = [
            ("payment_mode", "=", "cheque"),
            ("state", "=", "confirmed"),
            ("company_id", "=", self.company_id.id),
            ("cheque_number", "=", self.cheque_number),
            ("bank_name", "=", self.bank_name),
            ("cheque_date", "=", self.cheque_date),
        ]

        if self.settlement_visit_id:
            domain.append(("settlement_visit_id", "=", self.settlement_visit_id.id))
        elif self.visit_id:
            domain.extend(
                [
                    ("settlement_visit_id", "=", False),
                    ("visit_id", "=", self.visit_id.id),
                ]
            )
        elif self.sale_order_id:
            domain.extend(
                [
                    ("settlement_visit_id", "=", False),
                    ("sale_order_id", "=", self.sale_order_id.id),
                ]
            )
        else:
            domain.append(("id", "=", self.id))
        return domain

    def _get_cheque_followup_batch_records(self):
        batch_records = self.browse()
        for rec in self:
            rec._ensure_cheque_followup_payment()
            batch_records |= self.search(rec._get_cheque_followup_batch_domain())
        return batch_records

    def _write_cheque_custody_state(self, state, date_field=None, user_field=None):
        batch_records = self._get_cheque_followup_batch_records()
        batch_records._ensure_cheque_followup_payment()
        now = fields.Datetime.now()
        values = {"cheque_custody_state": state}
        if date_field:
            values[date_field] = now
        if user_field:
            values[user_field] = self.env.user.id
        batch_records.write(values)
        return self._cheque_followup_reload_action()

    def action_cheque_receive_from_salesperson(self):
        self._check_route_cheque_supervisor_user()
        return self._write_cheque_custody_state(
            "with_supervisor",
            "cheque_supervisor_received_at",
            "cheque_supervisor_received_by_id",
        )

    def action_cheque_handover_to_accounting(self):
        self._check_route_cheque_salesperson_user()
        records = self._get_cheque_followup_batch_records()
        invalid_records = records.filtered(lambda payment: (payment.cheque_custody_state or "with_salesperson") != "with_salesperson")
        if invalid_records:
            raise ValidationError(_("Only cheques that are still with the salesperson can be handed over to Accounting."))
        if records.filtered(lambda payment: (payment.cheque_followup_state or "received") in ("cleared", "bounced", "cancelled") or payment.route_cheque_accounting_move_count):
            raise ValidationError(_("Finalized or posted cheques cannot be handed over again."))
        return self._write_cheque_custody_state(
            "handed_to_accounting",
            "cheque_handed_to_accounting_at",
            "cheque_handed_to_accounting_by_id",
        )

    def action_cheque_accounting_receive(self):
        self._check_route_cheque_accounting_user()
        records = self._get_cheque_followup_batch_records()
        invalid_records = records.filtered(lambda payment: (payment.cheque_custody_state or "with_salesperson") != "handed_to_accounting")
        if invalid_records:
            raise ValidationError(_("This cheque must be handed over directly by the salesperson before Accounting can confirm receipt."))
        return self._write_cheque_custody_state(
            "received_by_accounting",
            "cheque_accounting_received_at",
            "cheque_accounting_received_by_id",
        )

    def _write_cash_custody_state(self, state, date_field=None, user_field=None):
        records = self.filtered(lambda rec: rec.payment_mode == "cash")
        if not records:
            raise ValidationError(_("Cash handover actions are available only for cash payments."))
        invalid_records = records.filtered(lambda rec: rec.state != "confirmed")
        if invalid_records:
            raise ValidationError(_("Confirm the cash collection before using handover actions."))
        now = fields.Datetime.now()
        values = {"cash_custody_state": state}
        if date_field:
            values[date_field] = now
        if user_field:
            values[user_field] = self.env.user.id
        records.write(values)
        return self._cheque_followup_reload_action()

    def action_cash_handover_to_accounting(self):
        self._check_route_cash_salesperson_user()
        records = self.filtered(lambda rec: rec.payment_mode == "cash")
        invalid_records = records.filtered(lambda payment: (payment.cash_custody_state or "with_salesperson") != "with_salesperson")
        if invalid_records:
            raise ValidationError(_("Only cash that is still with the salesperson can be handed over to Accounting."))
        return records._write_cash_custody_state("handed_to_accounting", "cash_handed_to_accounting_at", "cash_handed_to_accounting_by_id")

    def action_cash_accounting_receive(self):
        self._check_route_cash_accounting_user()
        records = self.filtered(lambda rec: rec.payment_mode == "cash")
        invalid_records = records.filtered(lambda payment: (payment.cash_custody_state or "with_salesperson") != "handed_to_accounting")
        if invalid_records:
            raise ValidationError(_("This cash collection must be handed over by the salesperson before Accounting can confirm receipt."))
        return records._write_cash_custody_state("received_by_accounting", "cash_accounting_received_at", "cash_accounting_received_by_id")

    def _write_cheque_followup_state(self, state, date_field=None):
        self._check_route_cheque_accounting_user()
        requested_records = self
        batch_records = requested_records._get_cheque_followup_batch_records()
        batch_records._ensure_cheque_followup_payment()
        invalid_records = batch_records.filtered(lambda payment: (payment.cheque_custody_state or "with_salesperson") != "received_by_accounting")
        if invalid_records:
            raise ValidationError(_("Accounting must confirm physical receipt of this cheque before changing its bank lifecycle status."))
        batch_records._validate_cheque_followup_transition(state)
        now = fields.Datetime.now()
        values = {
            "cheque_followup_state": state,
            "cheque_followup_updated_at": now,
            "cheque_followup_updated_by_id": self.env.user.id,
        }
        if date_field:
            values[date_field] = now
        batch_records.write(values)

        auto_records = batch_records.filtered(
            lambda payment: payment.company_id.route_cheque_accounting_enabled
            and payment.company_id.route_cheque_accounting_auto_post
        )
        if auto_records:
            auto_records._route_post_cheque_accounting_for_current_state()
        return self._cheque_followup_reload_action()

    def action_cheque_mark_deposited(self):
        return self._write_cheque_followup_state("deposited", "cheque_deposited_at")

    def action_cheque_mark_cleared(self):
        return self._write_cheque_followup_state("cleared", "cheque_cleared_at")

    def action_cheque_mark_bounced(self):
        return self._write_cheque_followup_state("bounced", "cheque_bounced_at")

    def action_cheque_mark_cancelled(self):
        return self._write_cheque_followup_state("cancelled", "cheque_cancelled_at")

    def action_cheque_reset_received(self):
        self._check_route_cheque_accounting_user()
        batch_records = self._get_cheque_followup_batch_records()
        for payment in batch_records:
            if payment._route_cheque_accounting_moves():
                raise ValidationError(_("This cheque already has accounting entries. Reverse or correct the accounting entries before resetting the cheque status."))
        batch_records.write(
            {
                "cheque_followup_state": "received",
                "cheque_followup_updated_at": fields.Datetime.now(),
                "cheque_followup_updated_by_id": self.env.user.id,
                "cheque_deposited_at": False,
                "cheque_cleared_at": False,
                "cheque_bounced_at": False,
                "cheque_cancelled_at": False,
            }
        )
        return self._cheque_followup_reload_action()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("payment_mode") == "cheque" and not vals.get("cheque_followup_state"):
                vals["cheque_followup_state"] = "received"
            if vals.get("payment_mode") == "cheque" and not vals.get("cheque_custody_state"):
                vals["cheque_custody_state"] = "with_salesperson"
            if vals.get("payment_mode") == "cash" and not vals.get("cash_custody_state"):
                vals["cash_custody_state"] = "with_salesperson"
            elif vals.get("payment_mode") and vals.get("payment_mode") != "cheque":
                vals["cheque_followup_state"] = False
        records = super().create(vals_list)
        records.filtered(lambda rec: rec.payment_mode == "cheque" and not rec.cheque_followup_state).with_context(
            bypass_cheque_followup_post_create=True
        ).write({"cheque_followup_state": "received"})
        records.filtered(lambda rec: rec.payment_mode == "cheque" and not rec.cheque_custody_state).with_context(
            bypass_cheque_followup_post_create=True
        ).write({"cheque_custody_state": "with_salesperson"})
        records.filtered(lambda rec: rec.payment_mode == "cash" and not rec.cash_custody_state).with_context(
            bypass_cheque_followup_post_create=True
        ).write({"cash_custody_state": "with_salesperson"})
        return records

    def write(self, vals):
        values = dict(vals)
        if values.get("payment_mode") == "cheque" and not values.get("cheque_followup_state"):
            values["cheque_followup_state"] = "received"
        if values.get("payment_mode") == "cheque" and not values.get("cheque_custody_state"):
            values["cheque_custody_state"] = "with_salesperson"
        if values.get("payment_mode") == "cash" and not values.get("cash_custody_state"):
            values["cash_custody_state"] = "with_salesperson"
        elif values.get("payment_mode") and values.get("payment_mode") != "cheque":
            values.update(
                {
                    "cheque_followup_state": False,
                    "cheque_deposited_at": False,
                    "cheque_cleared_at": False,
                    "cheque_bounced_at": False,
                    "cheque_cancelled_at": False,
                    "cheque_followup_note": False,
                    "cheque_custody_state": False,
                    "cheque_supervisor_received_at": False,
                    "cheque_supervisor_received_by_id": False,
                    "cheque_handed_to_accounting_at": False,
                    "cheque_handed_to_accounting_by_id": False,
                    "cheque_accounting_received_at": False,
                    "cheque_accounting_received_by_id": False,
                }
            )
        if values.get("payment_mode") and values.get("payment_mode") != "cash":
            values.update({"cash_custody_state": False, "cash_handed_to_accounting_at": False, "cash_handed_to_accounting_by_id": False, "cash_accounting_received_at": False, "cash_accounting_received_by_id": False, "cash_handover_note": False})
        return super().write(values)


class RouteVisitChequeFinancialPolicy(models.Model):
    _inherit = "route.visit"

    def _route_sum_financial_collected_amount(self, payments):
        total = 0.0
        for payment in payments:
            if hasattr(payment, "_get_route_financial_collected_amount"):
                total += payment._get_route_financial_collected_amount()
            elif payment.state == "confirmed":
                total += payment.amount or 0.0
        return total

    def _route_sum_financial_resolved_amount(self, payments):
        total = 0.0
        for payment in payments:
            if hasattr(payment, "_get_route_financial_resolved_amount"):
                total += payment._get_route_financial_resolved_amount()
            elif payment.state == "confirmed":
                total += payment.amount or 0.0
                if (payment.promise_amount or 0.0) > 0.0:
                    total += payment.promise_amount or 0.0
        return total

    def _get_direct_stop_settlement_cash_amount(self, states=None):
        self.ensure_one()
        payments = self._get_direct_stop_settlement_payments(states=states)
        return self._route_sum_financial_collected_amount(payments) if payments else 0.0

    def _get_direct_stop_settlement_resolved_amount(self, states=None):
        self.ensure_one()
        payments = self._get_direct_stop_settlement_payments(states=states)
        return self._route_sum_financial_resolved_amount(payments) if payments else 0.0

    @api.depends(
        "visit_execution_mode",
        "direct_stop_skip_sale",
        "direct_stop_skip_return",
        "direct_stop_credit_policy",
        "name",
        "direct_stop_return_ids.state",
        "direct_stop_return_ids.amount_total",
        "payment_ids.state",
        "payment_ids.amount",
        "payment_ids.promise_amount",
        "payment_ids.payment_mode",
        "payment_ids.cheque_followup_state",
        "settlement_payment_ids.state",
        "settlement_payment_ids.amount",
        "settlement_payment_ids.promise_amount",
        "settlement_payment_ids.payment_mode",
        "settlement_payment_ids.cheque_followup_state",
    )
    def _compute_direct_stop_summary(self):
        for rec in self:
            orders = rec.direct_stop_order_ids.filtered(lambda o: o.state not in ("cancel",)) if rec.direct_stop_order_ids else rec.direct_stop_order_ids
            if rec.id and hasattr(rec, "_get_direct_stop_active_returns"):
                active_returns = rec._get_direct_stop_active_returns()
            elif rec.id and hasattr(rec, "_get_direct_stop_returns"):
                active_returns = rec._get_direct_stop_returns()
            else:
                active_returns = rec.direct_stop_return_ids.filtered(lambda r: r.state != "cancel") if rec.direct_stop_return_ids else rec.direct_stop_return_ids
            previous_due_visits = rec._get_direct_stop_previous_due_visits() if rec.id else self.env["route.visit"]
            settlement_payments = rec._get_direct_stop_settlement_payments() if rec.id else self.env["route.visit.payment"]

            rec.direct_stop_order_count = len(orders)
            rec.direct_stop_return_count = len(active_returns)
            rec.direct_stop_sales_total = sum(orders.filtered(lambda o: o.state in ("sale", "done")).mapped("amount_total"))
            rec.direct_stop_returns_total = sum(active_returns.mapped("amount_total"))
            rec.direct_stop_previous_due_amount = sum(previous_due_visits.mapped("remaining_due_amount")) if previous_due_visits else 0.0
            rec.direct_stop_previous_due_since_date = min(previous_due_visits.mapped("date")) if previous_due_visits else False
            rec.direct_stop_current_net_amount = (rec.direct_stop_sales_total or 0.0) - (rec.direct_stop_returns_total or 0.0)

            gross_due = (rec.direct_stop_previous_due_amount or 0.0) + (rec.direct_stop_current_net_amount or 0.0)
            rec.direct_stop_grand_due_amount = max(gross_due, 0.0)
            rec.direct_stop_credit_amount = max(-gross_due, 0.0)

            confirmed_payments = settlement_payments.filtered(lambda p: p.state == "confirmed") if settlement_payments else settlement_payments
            draft_payments = settlement_payments.filtered(lambda p: p.state == "draft") if settlement_payments else settlement_payments
            confirmed_collected_amount = rec._route_sum_financial_collected_amount(confirmed_payments) if confirmed_payments else 0.0
            confirmed_resolved_amount = rec._get_direct_stop_settlement_resolved_amount(states=["confirmed"]) if rec.id else confirmed_collected_amount
            rec.direct_stop_settlement_paid_amount = confirmed_collected_amount
            rec.direct_stop_settlement_remaining_amount = max((rec.direct_stop_grand_due_amount or 0.0) - (confirmed_resolved_amount or 0.0), 0.0)

            if rec.direct_stop_order_count:
                rec.direct_stop_sale_status = "yes"
            elif rec.direct_stop_skip_sale:
                rec.direct_stop_sale_status = "no"
            else:
                rec.direct_stop_sale_status = "pending"

            if rec.direct_stop_return_count:
                rec.direct_stop_return_status = "yes"
            elif rec.direct_stop_skip_return:
                rec.direct_stop_return_status = "no"
            else:
                rec.direct_stop_return_status = "pending"

            credit_ready = (rec.direct_stop_credit_amount or 0.0) <= 0.0 or bool(rec.direct_stop_credit_policy)
            sale_answer_complete = rec.direct_stop_sale_status != "pending"
            return_answer_complete = (not rec.route_enable_direct_return) or rec.direct_stop_return_status != "pending"
            rec.direct_stop_settlement_ready = (
                rec.visit_execution_mode != "direct_sales"
                or (
                    sale_answer_complete
                    and return_answer_complete
                    and not draft_payments
                    and (rec.direct_stop_settlement_remaining_amount or 0.0) <= 0.0
                    and credit_ready
                )
            )

    @api.depends(
        "visit_execution_mode",
        "payment_ids.state",
        "payment_ids.amount",
        "payment_ids.promise_amount",
        "payment_ids.payment_mode",
        "payment_ids.cheque_followup_state",
        "settlement_payment_ids.state",
        "settlement_payment_ids.amount",
        "settlement_payment_ids.promise_amount",
        "settlement_payment_ids.payment_mode",
        "settlement_payment_ids.cheque_followup_state",
        "line_ids.sold_amount",
        "line_ids.return_amount",
        "line_ids.route_net_payable_amount",
        "direct_stop_grand_due_amount",
    )
    def _compute_payment_totals(self):
        Payment = self.env["route.visit.payment"]
        for rec in self:
            if hasattr(rec, "_is_direct_sales_stop") and rec._is_direct_sales_stop():
                net_due = getattr(rec, "direct_stop_grand_due_amount", 0.0) or 0.0
                confirmed_payments = rec._get_direct_stop_settlement_payments(states=["confirmed"]) if rec.id and hasattr(rec, "_get_direct_stop_settlement_payments") else Payment
                total_collected = rec._route_sum_financial_collected_amount(confirmed_payments) if confirmed_payments else 0.0
                resolved_amount = rec._get_direct_stop_settlement_resolved_amount(states=["confirmed"]) if rec.id and hasattr(rec, "_get_direct_stop_settlement_resolved_amount") else total_collected
                remaining_amount = max((net_due or 0.0) - (resolved_amount or 0.0), 0.0)
            else:
                if hasattr(rec, "_get_route_consignment_financial_amounts"):
                    amounts = rec._get_route_consignment_financial_amounts()
                    net_due = amounts.get("net_payable_amount", 0.0)
                else:
                    total_sales = sum((line.sold_amount or 0.0) for line in rec.line_ids) if rec.line_ids else 0.0
                    total_returns = sum((line.return_amount or 0.0) for line in rec.line_ids) if rec.line_ids else 0.0
                    net_due = max((total_sales or 0.0) - (total_returns or 0.0), 0.0)
                confirmed_payments = rec.payment_ids.filtered(lambda p: p.state == "confirmed") if rec.payment_ids else rec.payment_ids
                total_collected = rec._route_sum_financial_collected_amount(confirmed_payments) if confirmed_payments else 0.0
                remaining_amount = max((net_due or 0.0) - (total_collected or 0.0), 0.0)

            rec.net_due_amount = net_due
            rec.collected_amount = total_collected
            rec.remaining_due_amount = remaining_amount


class SaleOrderChequeFinancialPolicy(models.Model):
    _inherit = "sale.order"

    def _get_route_payment_confirmed_amount(self, exclude_payment=None):
        self.ensure_one()
        payments = self.direct_sale_payment_ids.filtered(lambda p: p.state == "confirmed")
        if exclude_payment:
            payments = payments.filtered(lambda p: p.id != exclude_payment.id)
        total = 0.0
        for payment in payments:
            if hasattr(payment, "_get_route_financial_collected_amount"):
                total += payment._get_route_financial_collected_amount()
            else:
                total += payment.amount or 0.0
        return total

    @api.depends(
        "amount_total",
        "direct_sale_payment_ids.amount",
        "direct_sale_payment_ids.state",
        "direct_sale_payment_ids.payment_mode",
        "direct_sale_payment_ids.cheque_followup_state",
    )
    def _compute_direct_sale_payment_summary(self):
        for order in self:
            active_payments = order.direct_sale_payment_ids.filtered(lambda p: p.state != "cancelled")
            confirmed_payments = active_payments.filtered(lambda p: p.state == "confirmed")
            collected_amount = 0.0
            for payment in confirmed_payments:
                if hasattr(payment, "_get_route_financial_collected_amount"):
                    collected_amount += payment._get_route_financial_collected_amount()
                else:
                    collected_amount += payment.amount or 0.0
            order.direct_sale_payment_count = len(active_payments)
            order.direct_sale_collected_amount = collected_amount
            order.direct_sale_remaining_due = order._get_route_payment_remaining_due()
