from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteSalespersonDeduction(models.Model):
    _name = "route.salesperson.deduction"
    _description = "Salesperson Monthly Deduction"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "month_date desc, salesperson_id, id desc"

    name = fields.Char(string="Deduction Reference", required=True, copy=False, readonly=True, default="New", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, readonly=True, default=lambda self: self.env.company)
    ledger_id = fields.Many2one("route.salesperson.shortage", string="Monthly Ledger", required=True, ondelete="cascade", index=True, tracking=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", related="ledger_id.salesperson_id", store=True, readonly=True)
    month_date = fields.Date(string="Month", related="ledger_id.month_date", store=True, readonly=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("executed", "Executed"),
        ("cancelled", "Cancelled"),
    ], string="Execution Status", default="draft", required=True, tracking=True)
    line_ids = fields.One2many("route.salesperson.shortage.line", "deduction_record_id", string="Deduction Lines", copy=False)
    note = fields.Text(string="Notes")
    approved_on = fields.Datetime(string="Approved On", readonly=True, copy=False, tracking=True)
    approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False, tracking=True)
    executed_on = fields.Datetime(string="Executed On", readonly=True, copy=False, tracking=True)
    executed_by_id = fields.Many2one("res.users", string="Executed By", readonly=True, copy=False, tracking=True)

    line_count = fields.Integer(string="Lines", compute="_compute_totals")
    total_shortage_qty = fields.Float(string="Total Deduction Qty", compute="_compute_totals")
    total_shortage_amount = fields.Float(string="Total Deduction Amount", compute="_compute_totals")

    _sql_constraints = [
        (
            "route_salesperson_deduction_ledger_unique",
            "unique(ledger_id)",
            "Only one deduction record is allowed for each monthly shortage ledger.",
        ),
    ]

    @api.depends("line_ids", "line_ids.shortage_qty", "line_ids.shortage_amount")
    def _compute_totals(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)
            rec.total_shortage_qty = sum(rec.line_ids.mapped("shortage_qty"))
            rec.total_shortage_amount = sum(rec.line_ids.mapped("shortage_amount"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.salesperson.deduction") or "New"
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if rec.state == "executed":
                continue
            if not rec.line_ids:
                raise UserError(_("You cannot approve an empty deduction record."))
            rec.write({
                "state": "approved",
                "approved_on": fields.Datetime.now(),
                "approved_by_id": self.env.user.id,
            })
        return True

    def action_mark_executed(self):
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(_("Cancelled deduction records cannot be executed."))
            if not rec.line_ids:
                raise UserError(_("You cannot execute an empty deduction record."))
            values = {
                "state": "executed",
                "executed_on": fields.Datetime.now(),
                "executed_by_id": self.env.user.id,
            }
            if not rec.approved_on:
                values.update({
                    "approved_on": fields.Datetime.now(),
                    "approved_by_id": self.env.user.id,
                })
            rec.write(values)
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == "executed":
                raise UserError(_("Executed deduction records cannot be reset to draft."))
            rec.write({
                "state": "draft",
                "approved_on": False,
                "approved_by_id": False,
                "executed_on": False,
                "executed_by_id": False,
            })
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "executed":
                raise UserError(_("Executed deduction records cannot be cancelled."))
            rec.write({"state": "cancelled"})
        return True

    def action_open_monthly_ledger(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Salesperson Shortage Ledger"),
            "res_model": "route.salesperson.shortage",
            "res_id": self.ledger_id.id,
            "view_mode": "form",
            "target": "current",
        }
