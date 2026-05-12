# -*- coding: utf-8 -*-
"""Compatibility extension for Route Core Bank/POS custody flow.

This file intentionally keeps the Bank/POS verification fields separate from
route_cheque_followup.py so upgrades do not fail when XML views already refer to
these fields. It extends route.visit.payment only and is safe for generic use.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RouteVisitPaymentElectronicControl(models.Model):
    _inherit = "route.visit.payment"

    electronic_verification_state = fields.Selection(
        [
            ("reported", "Reported by Salesperson"),
            ("verified", "Verified by Accounting"),
            ("rejected", "Needs Follow-up"),
        ],
        string="Bank/POS Verification",
        default=False,
        index=True,
        copy=False,
        help="Used for Bank Transfer and POS payments. Reported payments are visible to Accounting for verification before receipt voucher posting.",
    )
    electronic_verification_state_label = fields.Char(
        string="Bank/POS Verification Label",
        compute="_compute_electronic_verification_state_label",
        store=False,
    )
    electronic_verification_note = fields.Text(string="Bank/POS Confirmation Note", copy=False)
    electronic_verified_at = fields.Datetime(string="Bank/POS Confirmed At", copy=False)
    electronic_verified_by_id = fields.Many2one("res.users", string="Bank/POS Confirmed By", readonly=True, copy=False)
    electronic_rejected_at = fields.Datetime(string="Bank/POS Follow-up At", copy=False)
    electronic_rejected_by_id = fields.Many2one("res.users", string="Bank/POS Follow-up By", readonly=True, copy=False)

    electronic_group_key = fields.Char(
        string="Bank/POS Group Key",
        compute="_compute_electronic_group_key",
        store=True,
        index=True,
        copy=False,
        help="Technical key used to show one Bank/POS card for one reported electronic payment while preserving allocation lines.",
    )
    electronic_is_primary = fields.Boolean(
        string="Primary Bank/POS Payment Line",
        compute="_compute_electronic_is_primary",
        search="_search_electronic_is_primary",
        store=False,
    )
    electronic_payment_total_amount = fields.Monetary(
        string="Electronic Payment Total",
        currency_field="currency_id",
        compute="_compute_electronic_payment_summary",
        store=False,
        help="Total amount of all allocation lines covered by the same Bank/POS payment reference.",
    )
    electronic_payment_allocation_count = fields.Integer(
        string="Electronic Payment Allocations",
        compute="_compute_electronic_payment_summary",
        store=False,
    )
    electronic_payment_display_ref = fields.Char(
        string="Electronic Payment Reference",
        compute="_compute_electronic_payment_summary",
        store=False,
    )
    electronic_payment_source_summary = fields.Char(
        string="Payment Covers",
        compute="_compute_electronic_payment_summary",
        store=False,
    )
    electronic_payment_settlement_summary = fields.Char(
        string="Settlement Visits",
        compute="_compute_electronic_payment_summary",
        store=False,
    )
    electronic_payment_area_summary = fields.Char(
        string="Areas",
        compute="_compute_electronic_payment_summary",
        store=False,
    )
    route_electronic_show_accounting_actions = fields.Boolean(
        string="Show Bank/POS Accounting Actions",
        compute="_compute_route_electronic_context_flags",
        store=False,
    )

    route_electronic_receipt_move_id = fields.Many2one(
        "account.move",
        string="Bank/POS Receipt Voucher Entry",
        readonly=True,
        copy=False,
    )
    route_electronic_accounting_state = fields.Selection(
        [
            ("disabled", "Accounting Disabled"),
            ("pending_verification", "Pending Bank/POS Confirmation"),
            ("verified_not_posted", "Bank/POS Confirmed Not Posted"),
            ("followup", "Bank/POS Follow-up"),
            ("posted", "Receipt Entry Posted"),
        ],
        string="Bank/POS Accounting State",
        compute="_compute_route_electronic_accounting_state",
        store=False,
    )
    route_electronic_accounting_state_label = fields.Char(
        string="Bank/POS Accounting State Label",
        compute="_compute_route_electronic_accounting_state",
        store=False,
    )
    route_electronic_accounting_move_count = fields.Integer(
        string="Bank/POS Accounting Entries",
        compute="_compute_route_electronic_accounting_state",
        store=False,
    )
    route_electronic_can_accountant_verify = fields.Boolean(
        string="Can Confirm Bank/POS Payment",
        compute="_compute_route_electronic_access_flags",
        store=False,
    )
    route_electronic_can_accountant_reject = fields.Boolean(
        string="Can Mark Bank/POS for Follow-up",
        compute="_compute_route_electronic_access_flags",
        store=False,
    )
    route_electronic_can_post_receipt = fields.Boolean(
        string="Can Post Bank/POS Receipt Voucher",
        compute="_compute_route_electronic_access_flags",
        store=False,
    )

    @api.depends("payment_mode", "electronic_verification_state")
    def _compute_electronic_verification_state_label(self):
        labels = dict(self._fields["electronic_verification_state"].selection)
        for rec in self:
            if rec.payment_mode not in ("bank", "pos"):
                rec.electronic_verification_state_label = False
                continue
            state = rec.electronic_verification_state or "reported"
            rec.electronic_verification_state_label = labels.get(state, state)

    def _route_electronic_normalize_group_value(self, value):
        normalizer = getattr(self, "_route_cheque_normalize_group_value", False)
        if normalizer:
            return normalizer(value)
        return (value or "").strip().lower()

    @api.depends(
        "company_id",
        "currency_id",
        "payment_mode",
        "state",
        "reference",
        "bank_name",
        "pos_terminal",
        "payment_date",
        "settlement_visit_id",
        "visit_id",
        "sale_order_id",
        "salesperson_id",
    )
    def _compute_electronic_group_key(self):
        for rec in self:
            if rec.payment_mode not in ("bank", "pos") or rec.state != "confirmed":
                rec.electronic_group_key = False
                continue
            if rec.settlement_visit_id:
                anchor_type = "settlement"
                anchor_id = rec.settlement_visit_id.id
            elif rec.visit_id:
                anchor_type = "visit"
                anchor_id = rec.visit_id.id
            elif rec.sale_order_id:
                anchor_type = "sale_order"
                anchor_id = rec.sale_order_id.id
            else:
                anchor_type = "payment"
                anchor_id = rec.id or 0
            rec.electronic_group_key = "|".join(
                [
                    str(rec.company_id.id or 0),
                    str(rec.currency_id.id or 0),
                    rec.payment_mode or "",
                    str(rec.salesperson_id.id or 0),
                    rec._route_electronic_normalize_group_value(rec.reference),
                    rec._route_electronic_normalize_group_value(rec.bank_name),
                    rec._route_electronic_normalize_group_value(rec.pos_terminal),
                    anchor_type,
                    str(anchor_id or 0),
                    fields.Datetime.to_string(rec.payment_date) if rec.payment_date else "",
                ]
            )

    def _route_electronic_group_domain(self):
        self.ensure_one()
        if self.payment_mode not in ("bank", "pos") or self.state != "confirmed":
            return [("id", "=", self.id)]
        if self.electronic_group_key:
            return [
                ("payment_mode", "in", ["bank", "pos"]),
                ("state", "=", "confirmed"),
                ("company_id", "=", self.company_id.id),
                ("electronic_group_key", "=", self.electronic_group_key),
            ]
        return [("id", "=", self.id)]

    def _route_electronic_group_records(self):
        self.ensure_one()
        return self.search(self._route_electronic_group_domain())

    @api.depends_context("route_accounting_custody_actions_mode")
    def _compute_route_electronic_context_flags(self):
        show_actions = bool(self.env.context.get("route_accounting_custody_actions_mode"))
        for rec in self:
            rec.route_electronic_show_accounting_actions = show_actions

    @api.depends(
        "electronic_group_key",
        "payment_mode",
        "state",
        "amount",
        "reference",
        "bank_name",
        "pos_terminal",
        "payment_date",
        "source_document_ref",
        "settlement_document_ref",
        "settlement_visit_id",
        "visit_id",
        "sale_order_id",
        "area_id",
    )
    def _compute_electronic_payment_summary(self):
        for rec in self:
            if rec.payment_mode in ("bank", "pos") and rec.state == "confirmed":
                group_records = rec._route_electronic_group_records()
            else:
                group_records = rec

            group_records = group_records.sorted(lambda payment: (payment.payment_date or fields.Datetime.now(), payment.id))
            primary = group_records[:1]
            total_amount = sum(group_records.mapped("amount")) or rec.amount or 0.0
            source_refs = []
            settlement_refs = []
            area_names = []
            for payment in group_records:
                if payment.source_document_ref and payment.source_document_ref not in source_refs:
                    source_refs.append(payment.source_document_ref)
                if payment.settlement_document_ref and payment.settlement_document_ref not in settlement_refs:
                    settlement_refs.append(payment.settlement_document_ref)
                if payment.area_id and payment.area_id.display_name not in area_names:
                    area_names.append(payment.area_id.display_name)

            source_summary = ", ".join(source_refs[:4])
            if len(source_refs) > 4:
                source_summary = _("%(sources)s + %(extra)s more") % {
                    "sources": source_summary,
                    "extra": len(source_refs) - 4,
                }

            settlement_summary = ", ".join(settlement_refs[:3])
            if len(settlement_refs) > 3:
                settlement_summary = _("%(settlements)s + %(extra)s more") % {
                    "settlements": settlement_summary,
                    "extra": len(settlement_refs) - 3,
                }

            area_summary = ", ".join(area_names[:3])
            if len(area_names) > 3:
                area_summary = _("%(areas)s + %(extra)s more") % {
                    "areas": area_summary,
                    "extra": len(area_names) - 3,
                }

            mode_label = _("Bank Transfer") if rec.payment_mode == "bank" else _("POS Payment")
            reference = rec.reference or (primary.reference if primary else False) or rec.source_document_ref or rec.settlement_document_ref or ""
            rec.electronic_payment_total_amount = total_amount
            rec.electronic_payment_allocation_count = len(group_records)
            rec.electronic_payment_display_ref = ("%s %s" % (mode_label, reference)).strip()
            rec.electronic_payment_source_summary = source_summary or rec.source_document_ref or ""
            rec.electronic_payment_settlement_summary = settlement_summary or rec.settlement_document_ref or ""
            rec.electronic_payment_area_summary = area_summary or (rec.area_id.display_name if rec.area_id else "")

    def _get_electronic_batch_records(self):
        batch_records = self.env["route.visit.payment"]
        for rec in self:
            if rec.payment_mode in ("bank", "pos"):
                batch_records |= rec._route_electronic_group_records()
            else:
                batch_records |= rec
        return batch_records.exists()

    def _route_electronic_primary_ids_sql(self, accounting_visible=False, verification_states=None, salesperson_id=False):
        params = []
        where_extra = ""
        if verification_states:
            where_extra += " AND COALESCE(p.electronic_verification_state, 'reported') IN %s"
            params.append(tuple(verification_states))
        if salesperson_id:
            where_extra += " AND p.salesperson_id = %s"
            params.append(salesperson_id)
        if accounting_visible:
            where_extra += """
                AND COALESCE(p.electronic_verification_state, 'reported') IN ('reported', 'verified', 'rejected')
                AND (
                    p.route_electronic_receipt_move_id IS NULL
                    OR COALESCE(electronic_move.state, '') != 'posted'
                    OR COALESCE(p.electronic_verification_state, 'reported') = 'rejected'
                )
            """
        self.env.cr.execute(
            """
            SELECT id
              FROM (
                    SELECT p.id,
                           ROW_NUMBER() OVER (
                               PARTITION BY COALESCE(NULLIF(p.electronic_group_key, ''), 'payment:' || p.id::varchar)
                               ORDER BY p.payment_date DESC NULLS LAST, p.id DESC
                           ) AS rn
                      FROM route_visit_payment p
                      LEFT JOIN account_move electronic_move ON electronic_move.id = p.route_electronic_receipt_move_id
                     WHERE p.state = 'confirmed'
                       AND p.payment_mode IN ('bank', 'pos')
                       {where_extra}
                   ) ranked
             WHERE rn = 1
            """.format(where_extra=where_extra),
            params,
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def _search_electronic_is_primary(self, operator, value):
        if operator not in ("=", "!="):
            raise ValidationError(_("Unsupported search operator for Bank/POS primary payment."))
        primary_ids = self._route_electronic_primary_ids_sql()
        truthy = bool(value)
        if (operator == "=" and truthy) or (operator == "!=" and not truthy):
            return [("id", "in", primary_ids or [0])]
        return ["!", ("id", "in", primary_ids or [0])]

    @api.depends("payment_mode", "state", "electronic_group_key")
    def _compute_electronic_is_primary(self):
        primary_ids = set(self._route_electronic_primary_ids_sql()) if self else set()
        for rec in self:
            rec.electronic_is_primary = bool(rec.id and rec.id in primary_ids)

    def _route_electronic_accounting_moves(self):
        self.ensure_one()
        moves = self.env["account.move"]
        if self.route_electronic_receipt_move_id:
            moves |= self.route_electronic_receipt_move_id
        return moves.exists()

    @api.depends(
        "route_cheque_accounting_enabled",
        "payment_mode",
        "state",
        "electronic_verification_state",
        "route_electronic_receipt_move_id.state",
    )
    def _compute_route_electronic_accounting_state(self):
        state_labels = dict(self._fields["route_electronic_accounting_state"].selection)
        for rec in self:
            moves = rec._route_electronic_accounting_moves() if rec.payment_mode in ("bank", "pos") else self.env["account.move"]
            rec.route_electronic_accounting_move_count = len(moves)
            if not rec.route_cheque_accounting_enabled or rec.payment_mode not in ("bank", "pos") or rec.state != "confirmed":
                rec.route_electronic_accounting_state = "disabled"
                rec.route_electronic_accounting_state_label = False
                continue
            verification_state = rec.electronic_verification_state or "reported"
            receipt_posted = bool(rec.route_electronic_receipt_move_id and rec.route_electronic_receipt_move_id.state == "posted")
            if receipt_posted:
                rec.route_electronic_accounting_state = "posted"
            elif verification_state == "verified":
                rec.route_electronic_accounting_state = "verified_not_posted"
            elif verification_state == "rejected":
                rec.route_electronic_accounting_state = "followup"
            else:
                rec.route_electronic_accounting_state = "pending_verification"
            rec.route_electronic_accounting_state_label = state_labels.get(
                rec.route_electronic_accounting_state,
                rec.route_electronic_accounting_state or "",
            )

    @api.depends(
        "payment_mode",
        "state",
        "electronic_verification_state",
        "route_electronic_accounting_state",
        "route_electronic_accounting_move_count",
    )
    def _compute_route_electronic_access_flags(self):
        checker = getattr(self, "_route_user_is_route_cheque_accountant_or_manager", False)
        is_accounting = checker() if checker else self.env.user.has_group("account.group_account_user")
        for rec in self:
            is_electronic = rec.payment_mode in ("bank", "pos") and rec.state == "confirmed"
            verification_state = rec.electronic_verification_state or "reported"
            posted = rec.route_electronic_accounting_state == "posted"
            rec.route_electronic_can_accountant_verify = bool(is_electronic and is_accounting and not posted and verification_state in (False, "reported", "rejected"))
            rec.route_electronic_can_accountant_reject = bool(is_electronic and is_accounting and not posted and verification_state in (False, "reported"))
            rec.route_electronic_can_post_receipt = bool(is_electronic and is_accounting and not posted and verification_state == "verified")

    def _route_electronic_validate_accounting_settings(self):
        self.ensure_one()
        company = self.company_id
        if not company.route_cheque_accounting_enabled:
            raise ValidationError(_("Enable Route Collection Accounting in Route Settings first."))
        if not company.route_cheque_receivable_account_id:
            raise ValidationError(_("Configure Route Receivable / Open Due Account in Route Settings."))
        if not company.route_cheque_bank_journal_id:
            raise ValidationError(_("Configure a bank/cash journal in Cleared Cheque Bank Journal. It is also used for Bank Transfer and POS receipt voucher entries."))
        if not company.route_cheque_bank_journal_id.default_account_id:
            raise ValidationError(_("The selected bank/cash journal has no default account."))
        return company

    def _route_electronic_get_partner(self):
        self.ensure_one()
        outlet = self.outlet_id or (self.visit_id.outlet_id if self.visit_id else False) or (self.settlement_visit_id.outlet_id if self.settlement_visit_id else False)
        return outlet.partner_id if outlet and outlet.partner_id else False

    def _route_electronic_batch_amount(self):
        return sum(self.mapped("amount")) or 0.0

    def _route_electronic_batch_date(self):
        records = self.sorted(lambda rec: (rec.electronic_verified_at or rec.payment_date or fields.Datetime.now(), rec.id))
        value = next((rec.electronic_verified_at for rec in records if rec.electronic_verified_at), False)
        if not value:
            value = next((rec.payment_date for rec in records if rec.payment_date), False)
        return fields.Date.to_date(value) if value else fields.Date.context_today(self)

    def _route_electronic_batch_move_ref(self):
        records = self.sorted(lambda rec: (rec.payment_date or fields.Datetime.now(), rec.id))
        first = records[:1]
        mode_label = _("Bank Transfer") if first.payment_mode == "bank" else _("POS")
        parts = [_("Route Bank/POS Receipt"), mode_label]
        if first.reference:
            parts.append(first.reference)
        if first.settlement_document_ref:
            parts.append(first.settlement_document_ref)
        if len(records) > 1:
            parts.append(_("%(count)s allocations") % {"count": len(records)})
        return " - ".join(parts)

    def _route_electronic_get_shared_accounting_move(self):
        moves = self.mapped("route_electronic_receipt_move_id").exists()
        if not moves:
            return False
        if len(moves) > 1:
            raise ValidationError(_("This Bank/POS payment batch already has multiple receipt voucher entries. Review the entries before posting again."))
        move = moves[:1]
        if move.state != "posted":
            move.action_post()
        missing_records = self.filtered(lambda rec: not rec.route_electronic_receipt_move_id)
        if missing_records:
            missing_records.sudo().write({"route_electronic_receipt_move_id": move.id})
        return move

    def _route_electronic_ensure_receipt_accounting_entry(self):
        if not self:
            return False
        existing_move = self._route_electronic_get_shared_accounting_move()
        if existing_move:
            return existing_move
        records = self.sorted(lambda rec: rec.id)
        first = records[:1]
        company = first._route_electronic_validate_accounting_settings()
        journal = company.route_cheque_bank_journal_id
        bank_account = journal.default_account_id
        receivable_account = company.route_cheque_receivable_account_id
        amount = records._route_electronic_batch_amount()
        if (amount or 0.0) <= 0.0:
            raise ValidationError(_("Bank/POS receipt voucher amount must be greater than zero."))
        ref = records._route_electronic_batch_move_ref()
        credit_groups = {}
        for payment in records:
            payment_amount = payment.amount or 0.0
            if payment_amount <= 0.0:
                continue
            partner = payment._route_electronic_get_partner()
            key = partner.id if partner else 0
            credit_groups.setdefault(key, {"partner": partner, "amount": 0.0})
            credit_groups[key]["amount"] += payment_amount
        line_vals = [
            (0, 0, {
                "name": ref,
                "account_id": bank_account.id,
                "partner_id": False,
                "debit": amount,
                "credit": 0.0,
            })
        ]
        for group in credit_groups.values():
            credit_amount = group["amount"] or 0.0
            if credit_amount <= 0.0:
                continue
            partner = group["partner"]
            line_vals.append(
                (0, 0, {
                    "name": ref,
                    "account_id": receivable_account.id,
                    "partner_id": partner.id if partner else False,
                    "debit": 0.0,
                    "credit": credit_amount,
                })
            )
        move = self.env["account.move"].sudo().with_company(first.company_id).create(
            {
                "move_type": "entry",
                "company_id": first.company_id.id,
                "journal_id": journal.id,
                "date": records._route_electronic_batch_date(),
                "ref": ref,
                "line_ids": line_vals,
            }
        )
        move.action_post()
        records.sudo().write({"route_electronic_receipt_move_id": move.id})
        return move

    def action_electronic_mark_verified(self):
        checker = getattr(self, "_check_route_cash_accounting_user", False)
        if checker:
            checker()
        records = self._get_electronic_batch_records()
        records.write(
            {
                "electronic_verification_state": "verified",
                "electronic_verified_at": fields.Datetime.now(),
                "electronic_verified_by_id": self.env.user.id,
            }
        )
        reloader = getattr(self, "_cheque_followup_reload_action", False)
        return reloader() if reloader else {"type": "ir.actions.client", "tag": "reload"}

    def action_electronic_mark_rejected(self):
        checker = getattr(self, "_check_route_cash_accounting_user", False)
        if checker:
            checker()
        records = self._get_electronic_batch_records()
        for payment in records:
            if payment.route_electronic_receipt_move_id and payment.route_electronic_receipt_move_id.state == "posted":
                raise ValidationError(_("This Bank/POS payment already has a posted receipt voucher entry. Reverse or correct the entry before marking it for follow-up."))
        records.write(
            {
                "electronic_verification_state": "rejected",
                "electronic_rejected_at": fields.Datetime.now(),
                "electronic_rejected_by_id": self.env.user.id,
            }
        )
        reloader = getattr(self, "_cheque_followup_reload_action", False)
        return reloader() if reloader else {"type": "ir.actions.client", "tag": "reload"}

    def action_route_post_electronic_receipt_accounting(self):
        checker = getattr(self, "_check_route_cash_accounting_user", False)
        if checker:
            checker()
        records = self._get_electronic_batch_records()
        invalid_records = records.filtered(lambda payment: (payment.electronic_verification_state or "reported") != "verified")
        if invalid_records:
            raise ValidationError(_("Accounting must confirm this Bank/POS payment before posting the receipt voucher entry."))
        records._route_electronic_ensure_receipt_accounting_entry()
        reloader = getattr(self, "_cheque_followup_reload_action", False)
        return reloader() if reloader else {"type": "ir.actions.client", "tag": "reload"}

    def action_route_open_electronic_accounting_moves(self):
        records = self._get_electronic_batch_records() if self else self
        moves = self.env["account.move"]
        for rec in records:
            moves |= rec._route_electronic_accounting_moves()
        moves = moves.exists()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Bank/POS Receipt Voucher Entries"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
            "context": {"create": False},
        }
        if len(moves) == 1:
            action.update({"view_mode": "form", "res_id": moves.id})
        return action

    def action_open_custody_details(self):
        self.ensure_one()
        if self.payment_mode in ("bank", "pos"):
            records = self._route_electronic_group_records()
            title = _("Bank/POS Payment Details")
            return {
                "type": "ir.actions.act_window",
                "name": title,
                "res_model": "route.visit.payment",
                "view_mode": "list,form",
                "domain": [("id", "in", records.ids)],
                "context": {"create": 0, "edit": 0, "delete": 0},
                "target": "current",
            }
        return super().action_open_custody_details()


    def _route_custody_primary_ids_sql(self, accounting_visible=False, custody_states=None, salesperson_id=False):
        """Include Bank Transfer/POS cards in the same custody helpers used by menus.

        Cash and cheque keep their physical custody behavior from route_cheque_followup.py.
        Bank/POS payments are not physical custody, but they are still salesperson-reported
        values that Accounting must confirm and post, so they need to appear in My Custody,
        Custody Monitor, and Accounting Work Queue until their workflow is complete.
        """
        primary_ids = []
        super_method = getattr(super(), "_route_custody_primary_ids_sql", False)
        if super_method:
            primary_ids.extend(
                super_method(
                    accounting_visible=accounting_visible,
                    custody_states=custody_states,
                    salesperson_id=salesperson_id,
                )
            )

        electronic_ids = []
        if custody_states:
            if "with_salesperson" in custody_states:
                electronic_ids = self._route_electronic_primary_ids_sql(
                    verification_states=("reported", "rejected"),
                    salesperson_id=salesperson_id,
                )
        elif accounting_visible:
            electronic_ids = self._route_electronic_primary_ids_sql(
                accounting_visible=True,
                salesperson_id=salesperson_id,
            )
        else:
            electronic_ids = self._route_electronic_primary_ids_sql(salesperson_id=salesperson_id)

        primary_ids.extend(electronic_ids or [])
        return list(dict.fromkeys(primary_ids))

    @api.depends(
        "payment_mode",
        "state",
        "cash_custody_is_primary",
        "cheque_physical_is_primary",
        "cash_custody_state",
        "cheque_custody_state",
        "cheque_followup_state",
        "route_cash_accounting_state",
        "route_cheque_accounting_state",
        "electronic_is_primary",
        "electronic_verification_state",
        "route_electronic_accounting_state",
        "route_electronic_receipt_move_id.state",
    )
    def _compute_route_custody_flags(self):
        super()._compute_route_custody_flags()
        for rec in self:
            if rec.payment_mode not in ("bank", "pos"):
                continue
            verification_state = rec.electronic_verification_state or "reported"
            accounting_state = rec.route_electronic_accounting_state or "pending_verification"
            is_primary = bool(rec.electronic_is_primary and rec.state == "confirmed")
            is_posted = accounting_state == "posted"
            rec.route_custody_is_primary = is_primary
            rec.route_custody_with_salesperson_visible = bool(
                is_primary
                and not is_posted
                and verification_state in ("reported", "rejected")
            )
            rec.route_custody_accounting_visible = bool(
                is_primary
                and not is_posted
                and verification_state in ("reported", "verified", "rejected")
            )
            rec.route_custody_accounting_todo_visible = rec.route_custody_accounting_visible
            rec.route_custody_monitor_open_visible = rec.route_custody_accounting_visible

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("payment_mode") in ("bank", "pos") and not vals.get("electronic_verification_state"):
                vals["electronic_verification_state"] = "reported"
        return super().create(vals_list)

    def write(self, vals):
        values = dict(vals)
        if values.get("payment_mode") in ("bank", "pos") and not values.get("electronic_verification_state"):
            values["electronic_verification_state"] = "reported"
        if values.get("payment_mode") and values.get("payment_mode") not in ("bank", "pos"):
            values.update(
                {
                    "electronic_verification_state": False,
                    "electronic_verification_note": False,
                    "electronic_verified_at": False,
                    "electronic_verified_by_id": False,
                    "electronic_rejected_at": False,
                    "electronic_rejected_by_id": False,
                    "route_electronic_receipt_move_id": False,
                }
            )
        return super().write(values)
