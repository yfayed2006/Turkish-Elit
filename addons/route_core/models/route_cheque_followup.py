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
            ("deposited", "Deposited"),
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
    cheque_deposited_at = fields.Datetime(string="Deposited At", copy=False)
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
        string="Cheque Effect",
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
        string="Received Accounting Entry",
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

        # In real route usage a direct-stop settlement may create several allocation
        # payment rows that share the same cheque number/bank/date. Those rows are
        # operational allocations, not separate cheque amounts. For the default
        # App-Store-friendly mode we must never sum all allocations into one bank
        # posting because that can overstate the physical cheque amount. Therefore,
        # Per Cheque posts the selected Cheque Control record amount only. The older
        # detailed grouping remains available under Per Allocation Line.
        if posting_level == "per_cheque":
            source_key = ("cheque_control_record", self.id)
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
        first = self[:1]
        posting_level = first.company_id.route_cheque_accounting_posting_level or "per_cheque"
        if posting_level == "per_cheque":
            return first.amount or 0.0
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
        # Accounting posting must use the selected Cheque Control record(s), not the
        # operational follow-up batch. The follow-up batch is still useful for
        # status synchronization, but using it for accounting can sum unrelated
        # allocation lines and create an overstated journal entry.
        self._ensure_cheque_followup_payment()
        self._route_post_cheque_accounting_for_current_state()
        return self._cheque_followup_reload_action()

    def action_route_open_cheque_accounting_moves(self):
        moves = self.env["account.move"]
        for rec in self:
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
        except Exception:
            # Keep module upgrade safe even if the column is not ready in an unusual registry phase.
            pass

    @api.depends("payment_mode", "cheque_followup_state", "cheque_date")
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

            if state == "cleared":
                rec.cheque_followup_due_label = _("Cleared")
            elif state == "bounced":
                rec.cheque_followup_due_label = _("Bounced")
            elif state == "cancelled":
                rec.cheque_followup_due_label = _("Cancelled")
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

    def _write_cheque_followup_state(self, state, date_field=None):
        requested_records = self
        batch_records = requested_records._get_cheque_followup_batch_records()
        batch_records._ensure_cheque_followup_payment()
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

        # Auto-post only the record(s) the user acted on. This keeps accounting
        # aligned with the visible Cheque Amount and prevents a direct-stop batch
        # from posting the sum of all allocation lines.
        auto_records = requested_records.filtered(
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
            elif vals.get("payment_mode") and vals.get("payment_mode") != "cheque":
                vals["cheque_followup_state"] = False
        records = super().create(vals_list)
        records.filtered(lambda rec: rec.payment_mode == "cheque" and not rec.cheque_followup_state).with_context(
            bypass_cheque_followup_post_create=True
        ).write({"cheque_followup_state": "received"})
        return records

    def write(self, vals):
        values = dict(vals)
        if values.get("payment_mode") == "cheque" and not values.get("cheque_followup_state"):
            values["cheque_followup_state"] = "received"
        elif values.get("payment_mode") and values.get("payment_mode") != "cheque":
            values.update(
                {
                    "cheque_followup_state": False,
                    "cheque_deposited_at": False,
                    "cheque_cleared_at": False,
                    "cheque_bounced_at": False,
                    "cheque_cancelled_at": False,
                    "cheque_followup_note": False,
                }
            )
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
