from odoo import _, api, fields, models, tools


class RouteCustodyAccountingWorkQueue(models.Model):
    _name = "route.custody.accounting.work.queue"
    _description = "Route Accounting Work Queue"
    _auto = False
    _rec_name = "name"
    _order = "is_company_summary desc, total_work_count desc, last_activity_at desc, salesperson_id"

    name = fields.Char(string="Salesperson", compute="_compute_name", store=False)
    is_company_summary = fields.Boolean(string="Company Summary", readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    last_activity_at = fields.Datetime(string="Last Custody Activity", readonly=True)
    workflow_state = fields.Selection(
        [
            ("followup", "Open Follow-up"),
            ("electronic_pending", "Bank/POS Pending Confirmation"),
            ("waiting_receipt", "Waiting Accounting Receipt"),
            ("received_not_posted", "Received / Verified Not Posted"),
            ("bank_pending", "Bank Pending"),
            ("with_salesperson", "With Salesperson"),
            ("clear", "No Open Work"),
        ],
        string="Work Priority",
        readonly=True,
    )

    cash_with_salesperson_amount = fields.Monetary(string="Cash With Salespeople", currency_field="currency_id", readonly=True)
    cash_with_salesperson_count = fields.Integer(string="Cash Lines With Salespeople", readonly=True)
    cheque_with_salesperson_amount = fields.Monetary(string="Cheques With Salespeople", currency_field="currency_id", readonly=True)
    cheque_with_salesperson_count = fields.Integer(string="Cheques With Salespeople", readonly=True)

    cash_waiting_receipt_amount = fields.Monetary(string="Cash Waiting Receipt", currency_field="currency_id", readonly=True)
    cash_waiting_receipt_count = fields.Integer(string="Cash Waiting Receipt Lines", readonly=True)
    cheque_waiting_receipt_amount = fields.Monetary(string="Cheques Waiting Receipt", currency_field="currency_id", readonly=True)
    cheque_waiting_receipt_count = fields.Integer(string="Cheques Waiting Receipt", readonly=True)

    cash_received_not_posted_amount = fields.Monetary(string="Cash Received Not Posted", currency_field="currency_id", readonly=True)
    cash_received_not_posted_count = fields.Integer(string="Cash Received Not Posted Lines", readonly=True)
    cheque_received_not_posted_amount = fields.Monetary(string="Cheques Received Not Posted", currency_field="currency_id", readonly=True)
    cheque_received_not_posted_count = fields.Integer(string="Cheques Received Not Posted", readonly=True)

    electronic_pending_amount = fields.Monetary(string="Bank/POS Pending Confirmation", currency_field="currency_id", readonly=True)
    electronic_pending_count = fields.Integer(string="Bank/POS Pending Confirmation", readonly=True)
    electronic_verified_not_posted_amount = fields.Monetary(string="Bank/POS Confirmed Not Posted", currency_field="currency_id", readonly=True)
    electronic_verified_not_posted_count = fields.Integer(string="Bank/POS Confirmed Not Posted", readonly=True)
    electronic_rejected_amount = fields.Monetary(string="Bank/POS Follow-up", currency_field="currency_id", readonly=True)
    electronic_rejected_count = fields.Integer(string="Bank/POS Follow-up", readonly=True)

    bank_pending_amount = fields.Monetary(string="Bank Pending Cheques", currency_field="currency_id", readonly=True)
    bank_pending_count = fields.Integer(string="Bank Pending Cheques", readonly=True)
    bounced_followup_amount = fields.Monetary(string="Bounced Cheques", currency_field="currency_id", readonly=True)
    bounced_followup_count = fields.Integer(string="Bounced Cheques", readonly=True)
    cancelled_followup_amount = fields.Monetary(string="Cancelled Cheques", currency_field="currency_id", readonly=True)
    cancelled_followup_count = fields.Integer(string="Cancelled Cheques", readonly=True)
    open_followup_amount = fields.Monetary(string="Open Follow-up Amount", currency_field="currency_id", readonly=True)
    open_followup_count = fields.Integer(string="Open Follow-up Items", readonly=True)

    total_with_salesperson_amount = fields.Monetary(string="Total With Salespeople", currency_field="currency_id", readonly=True)
    total_waiting_receipt_amount = fields.Monetary(string="Total Waiting Receipt", currency_field="currency_id", readonly=True)
    total_received_not_posted_amount = fields.Monetary(string="Total Received / Verified Not Posted", currency_field="currency_id", readonly=True)
    total_work_amount = fields.Monetary(string="Total Work Amount", currency_field="currency_id", readonly=True)
    total_work_count = fields.Integer(string="Open Work Items", readonly=True)

    @api.depends("salesperson_id", "is_company_summary")
    def _compute_name(self):
        for rec in self:
            if rec.is_company_summary:
                rec.name = _("Accounting Overview")
            else:
                rec.name = rec.salesperson_id.display_name if rec.salesperson_id else _("Unassigned Salesperson")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW route_custody_accounting_work_queue AS (
                WITH cash_base AS (
                    SELECT
                        MIN(p.id) AS min_id,
                        p.company_id AS company_id,
                        p.currency_id AS currency_id,
                        p.salesperson_id AS salesperson_id,
                        MAX(p.payment_date) AS last_activity_at,
                        COALESCE(SUM(CASE WHEN COALESCE(p.cash_custody_state, 'with_salesperson') = 'with_salesperson' THEN p.amount ELSE 0 END), 0) AS cash_with_salesperson_amount,
                        COUNT(*) FILTER (WHERE COALESCE(p.cash_custody_state, 'with_salesperson') = 'with_salesperson') AS cash_with_salesperson_count,
                        COALESCE(SUM(CASE WHEN p.cash_custody_state = 'handed_to_accounting' THEN p.amount ELSE 0 END), 0) AS cash_waiting_receipt_amount,
                        COUNT(*) FILTER (WHERE p.cash_custody_state = 'handed_to_accounting') AS cash_waiting_receipt_count,
                        COALESCE(SUM(CASE WHEN p.cash_custody_state = 'received_by_accounting' AND (p.route_cash_receipt_move_id IS NULL OR COALESCE(cash_move.state, '') != 'posted') THEN p.amount ELSE 0 END), 0) AS cash_received_not_posted_amount,
                        COUNT(*) FILTER (WHERE p.cash_custody_state = 'received_by_accounting' AND (p.route_cash_receipt_move_id IS NULL OR COALESCE(cash_move.state, '') != 'posted')) AS cash_received_not_posted_count
                    FROM route_visit_payment p
                    LEFT JOIN account_move cash_move ON cash_move.id = p.route_cash_receipt_move_id
                    WHERE p.state = 'confirmed'
                      AND p.payment_mode = 'cash'
                    GROUP BY p.company_id, p.currency_id, p.salesperson_id
                ),
                cheque_physical AS (
                    SELECT
                        MIN(p.id) AS min_id,
                        p.company_id AS company_id,
                        p.currency_id AS currency_id,
                        p.salesperson_id AS salesperson_id,
                        COALESCE(NULLIF(p.cheque_physical_group_key, ''), 'payment:' || p.id::varchar) AS physical_key,
                        MAX(p.payment_date) AS last_activity_at,
                        COALESCE(MAX(NULLIF(p.cheque_custody_state, '')), 'with_salesperson') AS cheque_custody_state,
                        COALESCE(MAX(NULLIF(p.cheque_followup_state, '')), 'received') AS cheque_followup_state,
                        SUM(p.amount) AS amount,
                        BOOL_OR(COALESCE(received_move.state, '') = 'posted') AS received_posted,
                        BOOL_OR(COALESCE(cleared_move.state, '') = 'posted') AS cleared_posted,
                        BOOL_OR(COALESCE(open_due_move.state, '') = 'posted') AS open_due_posted
                    FROM route_visit_payment p
                    LEFT JOIN account_move received_move ON received_move.id = p.route_cheque_received_move_id
                    LEFT JOIN account_move cleared_move ON cleared_move.id = p.route_cheque_cleared_move_id
                    LEFT JOIN account_move open_due_move ON open_due_move.id = p.route_cheque_open_due_move_id
                    WHERE p.state = 'confirmed'
                      AND p.payment_mode = 'cheque'
                    GROUP BY p.company_id, p.currency_id, p.salesperson_id, COALESCE(NULLIF(p.cheque_physical_group_key, ''), 'payment:' || p.id::varchar)
                ),
                cheque_base AS (
                    SELECT
                        MIN(min_id) AS min_id,
                        company_id,
                        currency_id,
                        salesperson_id,
                        MAX(last_activity_at) AS last_activity_at,
                        COALESCE(SUM(amount) FILTER (WHERE cheque_custody_state = 'with_salesperson'), 0) AS cheque_with_salesperson_amount,
                        COUNT(*) FILTER (WHERE cheque_custody_state = 'with_salesperson') AS cheque_with_salesperson_count,
                        COALESCE(SUM(amount) FILTER (WHERE cheque_custody_state = 'handed_to_accounting'), 0) AS cheque_waiting_receipt_amount,
                        COUNT(*) FILTER (WHERE cheque_custody_state = 'handed_to_accounting') AS cheque_waiting_receipt_count,
                        COALESCE(SUM(amount) FILTER (WHERE cheque_custody_state = 'received_by_accounting' AND NOT received_posted), 0) AS cheque_received_not_posted_amount,
                        COUNT(*) FILTER (WHERE cheque_custody_state = 'received_by_accounting' AND NOT received_posted) AS cheque_received_not_posted_count,
                        COALESCE(SUM(amount) FILTER (WHERE cheque_custody_state = 'received_by_accounting' AND cheque_followup_state = 'deposited'), 0) AS bank_pending_amount,
                        COUNT(*) FILTER (WHERE cheque_custody_state = 'received_by_accounting' AND cheque_followup_state = 'deposited') AS bank_pending_count,
                        COALESCE(SUM(amount) FILTER (WHERE cheque_followup_state = 'bounced'), 0) AS bounced_followup_amount,
                        COUNT(*) FILTER (WHERE cheque_followup_state = 'bounced') AS bounced_followup_count,
                        COALESCE(SUM(amount) FILTER (WHERE cheque_followup_state = 'cancelled'), 0) AS cancelled_followup_amount,
                        COUNT(*) FILTER (WHERE cheque_followup_state = 'cancelled') AS cancelled_followup_count
                    FROM cheque_physical
                    GROUP BY company_id, currency_id, salesperson_id
                ),
                electronic_base AS (
                    SELECT
                        MIN(p.id) AS min_id,
                        p.company_id AS company_id,
                        p.currency_id AS currency_id,
                        p.salesperson_id AS salesperson_id,
                        MAX(p.payment_date) AS last_activity_at,
                        COALESCE(SUM(CASE WHEN COALESCE(p.electronic_verification_state, 'reported') = 'reported' AND (p.route_electronic_receipt_move_id IS NULL OR COALESCE(electronic_move.state, '') != 'posted') THEN p.amount ELSE 0 END), 0) AS electronic_pending_amount,
                        COUNT(*) FILTER (WHERE COALESCE(p.electronic_verification_state, 'reported') = 'reported' AND (p.route_electronic_receipt_move_id IS NULL OR COALESCE(electronic_move.state, '') != 'posted')) AS electronic_pending_count,
                        COALESCE(SUM(CASE WHEN p.electronic_verification_state = 'verified' AND (p.route_electronic_receipt_move_id IS NULL OR COALESCE(electronic_move.state, '') != 'posted') THEN p.amount ELSE 0 END), 0) AS electronic_verified_not_posted_amount,
                        COUNT(*) FILTER (WHERE p.electronic_verification_state = 'verified' AND (p.route_electronic_receipt_move_id IS NULL OR COALESCE(electronic_move.state, '') != 'posted')) AS electronic_verified_not_posted_count,
                        COALESCE(SUM(CASE WHEN p.electronic_verification_state = 'rejected' THEN p.amount ELSE 0 END), 0) AS electronic_rejected_amount,
                        COUNT(*) FILTER (WHERE p.electronic_verification_state = 'rejected') AS electronic_rejected_count
                    FROM route_visit_payment p
                    LEFT JOIN account_move electronic_move ON electronic_move.id = p.route_electronic_receipt_move_id
                    WHERE p.state = 'confirmed'
                      AND p.payment_mode IN ('bank', 'pos')
                    GROUP BY p.company_id, p.currency_id, p.salesperson_id
                ),
                keys AS (
                    SELECT company_id, currency_id, salesperson_id FROM cash_base
                    UNION
                    SELECT company_id, currency_id, salesperson_id FROM cheque_base
                    UNION
                    SELECT company_id, currency_id, salesperson_id FROM electronic_base
                ),
                combined AS (
                    SELECT
                        LEAST(
                            COALESCE(c.min_id, 2147483647),
                            COALESCE(q.min_id, 2147483647),
                            COALESCE(e.min_id, 2147483647)
                        ) AS id,
                        k.company_id AS company_id,
                        k.currency_id AS currency_id,
                        k.salesperson_id AS salesperson_id,
                        GREATEST(
                            COALESCE(c.last_activity_at, '1970-01-01'::timestamp),
                            COALESCE(q.last_activity_at, '1970-01-01'::timestamp),
                            COALESCE(e.last_activity_at, '1970-01-01'::timestamp)
                        ) AS last_activity_at,
                        COALESCE(c.cash_with_salesperson_amount, 0) AS cash_with_salesperson_amount,
                        COALESCE(c.cash_with_salesperson_count, 0) AS cash_with_salesperson_count,
                        COALESCE(q.cheque_with_salesperson_amount, 0) AS cheque_with_salesperson_amount,
                        COALESCE(q.cheque_with_salesperson_count, 0) AS cheque_with_salesperson_count,
                        COALESCE(c.cash_waiting_receipt_amount, 0) AS cash_waiting_receipt_amount,
                        COALESCE(c.cash_waiting_receipt_count, 0) AS cash_waiting_receipt_count,
                        COALESCE(q.cheque_waiting_receipt_amount, 0) AS cheque_waiting_receipt_amount,
                        COALESCE(q.cheque_waiting_receipt_count, 0) AS cheque_waiting_receipt_count,
                        COALESCE(c.cash_received_not_posted_amount, 0) AS cash_received_not_posted_amount,
                        COALESCE(c.cash_received_not_posted_count, 0) AS cash_received_not_posted_count,
                        COALESCE(q.cheque_received_not_posted_amount, 0) AS cheque_received_not_posted_amount,
                        COALESCE(q.cheque_received_not_posted_count, 0) AS cheque_received_not_posted_count,
                        COALESCE(e.electronic_pending_amount, 0) AS electronic_pending_amount,
                        COALESCE(e.electronic_pending_count, 0) AS electronic_pending_count,
                        COALESCE(e.electronic_verified_not_posted_amount, 0) AS electronic_verified_not_posted_amount,
                        COALESCE(e.electronic_verified_not_posted_count, 0) AS electronic_verified_not_posted_count,
                        COALESCE(e.electronic_rejected_amount, 0) AS electronic_rejected_amount,
                        COALESCE(e.electronic_rejected_count, 0) AS electronic_rejected_count,
                        COALESCE(q.bank_pending_amount, 0) AS bank_pending_amount,
                        COALESCE(q.bank_pending_count, 0) AS bank_pending_count,
                        COALESCE(q.bounced_followup_amount, 0) AS bounced_followup_amount,
                        COALESCE(q.bounced_followup_count, 0) AS bounced_followup_count,
                        COALESCE(q.cancelled_followup_amount, 0) AS cancelled_followup_amount,
                        COALESCE(q.cancelled_followup_count, 0) AS cancelled_followup_count
                    FROM keys k
                    LEFT JOIN cash_base c
                      ON c.company_id = k.company_id
                     AND c.currency_id = k.currency_id
                     AND COALESCE(c.salesperson_id, 0) = COALESCE(k.salesperson_id, 0)
                    LEFT JOIN cheque_base q
                      ON q.company_id = k.company_id
                     AND q.currency_id = k.currency_id
                     AND COALESCE(q.salesperson_id, 0) = COALESCE(k.salesperson_id, 0)
                    LEFT JOIN electronic_base e
                      ON e.company_id = k.company_id
                     AND e.currency_id = k.currency_id
                     AND COALESCE(e.salesperson_id, 0) = COALESCE(k.salesperson_id, 0)
                ),
                raw_rows AS (
                    SELECT
                        id,
                        FALSE AS is_company_summary,
                        company_id,
                        currency_id,
                        salesperson_id,
                        last_activity_at,
                        cash_with_salesperson_amount,
                        cash_with_salesperson_count,
                        cheque_with_salesperson_amount,
                        cheque_with_salesperson_count,
                        cash_waiting_receipt_amount,
                        cash_waiting_receipt_count,
                        cheque_waiting_receipt_amount,
                        cheque_waiting_receipt_count,
                        cash_received_not_posted_amount,
                        cash_received_not_posted_count,
                        cheque_received_not_posted_amount,
                        cheque_received_not_posted_count,
                        electronic_pending_amount,
                        electronic_pending_count,
                        electronic_verified_not_posted_amount,
                        electronic_verified_not_posted_count,
                        electronic_rejected_amount,
                        electronic_rejected_count,
                        bank_pending_amount,
                        bank_pending_count,
                        bounced_followup_amount,
                        bounced_followup_count,
                        cancelled_followup_amount,
                        cancelled_followup_count
                    FROM combined
                    WHERE id IS NOT NULL
                      AND id != 2147483647

                    UNION ALL

                    SELECT
                        -company_id AS id,
                        TRUE AS is_company_summary,
                        company_id,
                        currency_id,
                        NULL::integer AS salesperson_id,
                        MAX(last_activity_at) AS last_activity_at,
                        COALESCE(SUM(cash_with_salesperson_amount), 0) AS cash_with_salesperson_amount,
                        COALESCE(SUM(cash_with_salesperson_count), 0) AS cash_with_salesperson_count,
                        COALESCE(SUM(cheque_with_salesperson_amount), 0) AS cheque_with_salesperson_amount,
                        COALESCE(SUM(cheque_with_salesperson_count), 0) AS cheque_with_salesperson_count,
                        COALESCE(SUM(cash_waiting_receipt_amount), 0) AS cash_waiting_receipt_amount,
                        COALESCE(SUM(cash_waiting_receipt_count), 0) AS cash_waiting_receipt_count,
                        COALESCE(SUM(cheque_waiting_receipt_amount), 0) AS cheque_waiting_receipt_amount,
                        COALESCE(SUM(cheque_waiting_receipt_count), 0) AS cheque_waiting_receipt_count,
                        COALESCE(SUM(cash_received_not_posted_amount), 0) AS cash_received_not_posted_amount,
                        COALESCE(SUM(cash_received_not_posted_count), 0) AS cash_received_not_posted_count,
                        COALESCE(SUM(cheque_received_not_posted_amount), 0) AS cheque_received_not_posted_amount,
                        COALESCE(SUM(cheque_received_not_posted_count), 0) AS cheque_received_not_posted_count,
                        COALESCE(SUM(electronic_pending_amount), 0) AS electronic_pending_amount,
                        COALESCE(SUM(electronic_pending_count), 0) AS electronic_pending_count,
                        COALESCE(SUM(electronic_verified_not_posted_amount), 0) AS electronic_verified_not_posted_amount,
                        COALESCE(SUM(electronic_verified_not_posted_count), 0) AS electronic_verified_not_posted_count,
                        COALESCE(SUM(electronic_rejected_amount), 0) AS electronic_rejected_amount,
                        COALESCE(SUM(electronic_rejected_count), 0) AS electronic_rejected_count,
                        COALESCE(SUM(bank_pending_amount), 0) AS bank_pending_amount,
                        COALESCE(SUM(bank_pending_count), 0) AS bank_pending_count,
                        COALESCE(SUM(bounced_followup_amount), 0) AS bounced_followup_amount,
                        COALESCE(SUM(bounced_followup_count), 0) AS bounced_followup_count,
                        COALESCE(SUM(cancelled_followup_amount), 0) AS cancelled_followup_amount,
                        COALESCE(SUM(cancelled_followup_count), 0) AS cancelled_followup_count
                    FROM combined
                    WHERE id IS NOT NULL
                      AND id != 2147483647
                    GROUP BY company_id, currency_id
                )
                SELECT
                    id,
                    is_company_summary,
                    company_id,
                    currency_id,
                    salesperson_id,
                    last_activity_at,
                    cash_with_salesperson_amount,
                    cash_with_salesperson_count,
                    cheque_with_salesperson_amount,
                    cheque_with_salesperson_count,
                    cash_waiting_receipt_amount,
                    cash_waiting_receipt_count,
                    cheque_waiting_receipt_amount,
                    cheque_waiting_receipt_count,
                    cash_received_not_posted_amount,
                    cash_received_not_posted_count,
                    cheque_received_not_posted_amount,
                    cheque_received_not_posted_count,
                    electronic_pending_amount,
                    electronic_pending_count,
                    electronic_verified_not_posted_amount,
                    electronic_verified_not_posted_count,
                    electronic_rejected_amount,
                    electronic_rejected_count,
                    bank_pending_amount,
                    bank_pending_count,
                    bounced_followup_amount,
                    bounced_followup_count,
                    cancelled_followup_amount,
                    cancelled_followup_count,
                    (bounced_followup_amount + cancelled_followup_amount + electronic_rejected_amount) AS open_followup_amount,
                    (bounced_followup_count + cancelled_followup_count + electronic_rejected_count) AS open_followup_count,
                    (cash_with_salesperson_amount + cheque_with_salesperson_amount) AS total_with_salesperson_amount,
                    (cash_waiting_receipt_amount + cheque_waiting_receipt_amount) AS total_waiting_receipt_amount,
                    (cash_received_not_posted_amount + cheque_received_not_posted_amount + electronic_verified_not_posted_amount) AS total_received_not_posted_amount,
                    (
                        cash_with_salesperson_amount + cheque_with_salesperson_amount
                        + cash_waiting_receipt_amount + cheque_waiting_receipt_amount
                        + cash_received_not_posted_amount + cheque_received_not_posted_amount
                        + electronic_pending_amount + electronic_verified_not_posted_amount + electronic_rejected_amount
                        + bank_pending_amount + bounced_followup_amount + cancelled_followup_amount
                    ) AS total_work_amount,
                    (
                        cash_with_salesperson_count + cheque_with_salesperson_count
                        + cash_waiting_receipt_count + cheque_waiting_receipt_count
                        + cash_received_not_posted_count + cheque_received_not_posted_count
                        + electronic_pending_count + electronic_verified_not_posted_count + electronic_rejected_count
                        + bank_pending_count + bounced_followup_count + cancelled_followup_count
                    ) AS total_work_count,
                    CASE
                        WHEN (bounced_followup_count + cancelled_followup_count + electronic_rejected_count) > 0 THEN 'followup'
                        WHEN electronic_pending_count > 0 THEN 'electronic_pending'
                        WHEN (cash_waiting_receipt_count + cheque_waiting_receipt_count) > 0 THEN 'waiting_receipt'
                        WHEN (cash_received_not_posted_count + cheque_received_not_posted_count + electronic_verified_not_posted_count) > 0 THEN 'received_not_posted'
                        WHEN bank_pending_count > 0 THEN 'bank_pending'
                        WHEN (cash_with_salesperson_count + cheque_with_salesperson_count) > 0 THEN 'with_salesperson'
                        ELSE 'clear'
                    END AS workflow_state
                FROM raw_rows
                WHERE id IS NOT NULL
            )
            """
        )

    def _base_payment_domain(self):
        self.ensure_one()
        domain = [
            ("state", "=", "confirmed"),
            ("payment_mode", "in", ["cash", "cheque", "bank", "pos"]),
            ("route_custody_is_primary", "=", True),
        ]
        if self.salesperson_id and not self.is_company_summary:
            domain.append(("salesperson_id", "=", self.salesperson_id.id))
        elif not self.is_company_summary:
            domain.append(("salesperson_id", "=", False))
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        return domain

    def _open_payment_action(self, name, domain, extra_context=None):
        action = self.env["ir.actions.act_window"]._for_xml_id("route_core.action_route_accounting_collections_custody")
        action.update(
            {
                "name": name,
                "domain": domain,
                "context": {
                    "create": 0,
                    "edit": 0,
                    "delete": 0,
                    "route_accounting_custody_monitor_mode": True,
                    "route_accounting_custody_actions_mode": True,
                    **(extra_context or {}),
                },
            }
        )
        return action

    def _open_payment_records(self, name, records, extra_context=None):
        ids = records.ids or [0]
        return self._open_payment_action(name, [("id", "in", ids)], extra_context=extra_context)

    def _work_payments(self):
        self.ensure_one()
        return self.env["route.visit.payment"].search(self._base_payment_domain())

    def action_open_all_work(self):
        self.ensure_one()
        return self._open_payment_action(
            _("Accounting Work Queue - %s") % (self.name,),
            self._base_payment_domain() + [("route_custody_monitor_open_visible", "=", True)],
        )

    def action_open_with_salesperson(self):
        self.ensure_one()
        return self._open_payment_action(
            _("Custody With Salesperson - %s") % (self.name,),
            self._base_payment_domain() + [("route_custody_with_salesperson_visible", "=", True)],
            {"search_default_filter_custody_with_salesperson": 1},
        )

    def _base_bank_pos_domain(self, verification_state=None):
        self.ensure_one()
        domain = [
            ("state", "=", "confirmed"),
            ("payment_mode", "in", ["bank", "pos"]),
            ("electronic_is_primary", "=", True),
        ]
        if verification_state == "reported":
            domain += ["|", ("electronic_verification_state", "=", False), ("electronic_verification_state", "=", "reported")]
        elif verification_state:
            domain.append(("electronic_verification_state", "=", verification_state))
        if self.salesperson_id and not self.is_company_summary:
            domain.append(("salesperson_id", "=", self.salesperson_id.id))
        elif not self.is_company_summary:
            domain.append(("salesperson_id", "=", False))
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        return domain

    def action_open_electronic_verification(self):
        self.ensure_one()
        return self._open_payment_action(
            _("Bank/POS Payments Pending Confirmation - %s") % (self.name,),
            self._base_bank_pos_domain("reported"),
            {"search_default_filter_electronic_pending": 1},
        )

    def action_open_waiting_receipt(self):
        self.ensure_one()
        return self._open_payment_action(
            _("Waiting Accounting Receipt - %s") % (self.name,),
            self._base_payment_domain()
            + [
                "|",
                "&",
                ("payment_mode", "=", "cash"),
                ("cash_custody_state", "=", "handed_to_accounting"),
                "&",
                ("payment_mode", "=", "cheque"),
                ("cheque_custody_state", "=", "handed_to_accounting"),
            ],
            {"search_default_filter_custody_handed_accounting": 1},
        )

    def action_open_received_not_posted(self):
        self.ensure_one()
        payments = self._work_payments().filtered(
            lambda payment: (
                payment.payment_mode == "cash"
                and payment.cash_custody_state == "received_by_accounting"
                and (not payment.route_cash_receipt_move_id or payment.route_cash_receipt_move_id.state != "posted")
            )
            or (
                payment.payment_mode == "cheque"
                and payment.cheque_custody_state == "received_by_accounting"
                and (not payment.route_cheque_received_move_id or payment.route_cheque_received_move_id.state != "posted")
            )
            or (
                payment.payment_mode in ("bank", "pos")
                and (payment.electronic_verification_state or "reported") == "verified"
                and (not payment.route_electronic_receipt_move_id or payment.route_electronic_receipt_move_id.state != "posted")
            )
        )
        return self._open_payment_records(
            _("Received / Verified Not Posted - %s") % (self.name,),
            payments,
            {"search_default_filter_custody_received_accounting": 1},
        )

    def action_open_bank_pending(self):
        self.ensure_one()
        return self._open_payment_action(
            _("Bank Pending Cheques - %s") % (self.name,),
            self._base_payment_domain()
            + [
                ("payment_mode", "=", "cheque"),
                ("cheque_custody_state", "=", "received_by_accounting"),
                ("cheque_followup_state", "=", "deposited"),
            ],
            {"search_default_filter_cheque": 1, "search_default_filter_deposited": 1},
        )

    def action_open_followup(self):
        self.ensure_one()
        payments = self._work_payments().filtered(
            lambda payment: (
                payment.payment_mode == "cheque"
                and (
                    payment.cheque_followup_state in ("bounced", "cancelled")
                    or payment.cheque_collection_effect_bucket == "open_due"
                )
            )
            or (
                payment.payment_mode in ("bank", "pos")
                and payment.electronic_verification_state == "rejected"
            )
        )
        return self._open_payment_records(
            _("Follow-up - %s") % (self.name,),
            payments,
            {"search_default_filter_needs_followup": 1},
        )

