from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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

    def _write_cheque_followup_state(self, state, date_field=None):
        self._ensure_cheque_followup_payment()
        now = fields.Datetime.now()
        values = {
            "cheque_followup_state": state,
            "cheque_followup_updated_at": now,
            "cheque_followup_updated_by_id": self.env.user.id,
        }
        if date_field:
            values[date_field] = now
        self.write(values)
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
        self._ensure_cheque_followup_payment()
        self.write(
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
