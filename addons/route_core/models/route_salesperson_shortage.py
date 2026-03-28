from odoo import _, api, fields, models
from odoo.exceptions import UserError


class RouteSalespersonShortage(models.Model):
    _name = "route.salesperson.shortage"
    _description = "Salesperson Shortage Ledger"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "month_date desc, salesperson_id, id desc"

    name = fields.Char(string="Ledger Reference", required=True, copy=False, readonly=True, default="New", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, readonly=True, default=lambda self: self.env.company)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", required=True, tracking=True)
    month_date = fields.Date(string="Month", required=True, tracking=True)
    state = fields.Selection([
        ("open", "Open"),
        ("under_review", "Under Review"),
        ("settled", "Settled"),
    ], string="Status", default="open", required=True, tracking=True)
    line_ids = fields.One2many("route.salesperson.shortage.line", "ledger_id", string="Shortage Lines", copy=False)
    note = fields.Text(string="Notes")
    settled_on = fields.Datetime(string="Settled On", readonly=True, copy=False, tracking=True)
    settled_by_id = fields.Many2one("res.users", string="Settled By", readonly=True, copy=False, tracking=True)

    line_count = fields.Integer(string="Lines", compute="_compute_totals")
    pending_line_count = fields.Integer(string="Pending Lines", compute="_compute_totals")
    finalized_line_count = fields.Integer(string="Finalized Lines", compute="_compute_totals")
    deduction_line_count = fields.Integer(string="Deduction Lines", compute="_compute_totals")
    waived_line_count = fields.Integer(string="Waived Lines", compute="_compute_totals")
    settled_line_count = fields.Integer(string="Admin Settled Lines", compute="_compute_totals")
    total_shortage_qty = fields.Float(string="Total Shortage Qty", compute="_compute_totals")
    total_shortage_amount = fields.Float(string="Total Shortage Amount", compute="_compute_totals")
    pending_amount = fields.Float(string="Pending Amount", compute="_compute_totals")
    finalized_amount = fields.Float(string="Finalized Amount", compute="_compute_totals")

    _sql_constraints = [
        (
            "route_salesperson_shortage_unique_month",
            "unique(company_id, salesperson_id, month_date)",
            "Only one salesperson shortage ledger is allowed for each salesperson and month.",
        ),
    ]

    @api.depends(
        "line_ids",
        "line_ids.shortage_qty",
        "line_ids.shortage_amount",
        "line_ids.settlement_decision",
        "line_ids.is_finalized",
    )
    def _compute_totals(self):
        for rec in self:
            finalized = rec.line_ids.filtered("is_finalized")
            pending = rec.line_ids - finalized
            rec.line_count = len(rec.line_ids)
            rec.pending_line_count = len(pending)
            rec.finalized_line_count = len(finalized)
            rec.deduction_line_count = len(finalized.filtered(lambda line: line.settlement_decision == "deduct"))
            rec.waived_line_count = len(finalized.filtered(lambda line: line.settlement_decision == "waive"))
            rec.settled_line_count = len(finalized.filtered(lambda line: line.settlement_decision == "settle_admin"))
            rec.total_shortage_qty = sum(rec.line_ids.mapped("shortage_qty"))
            rec.total_shortage_amount = sum(rec.line_ids.mapped("shortage_amount"))
            rec.pending_amount = sum(pending.mapped("shortage_amount"))
            rec.finalized_amount = sum(finalized.mapped("shortage_amount"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("route.salesperson.shortage") or "New"
        return super().create(vals_list)

    @api.model
    def _month_start(self, date_value):
        if not date_value:
            date_value = fields.Date.context_today(self)
        return date_value.replace(day=1)

    @api.model
    def _get_or_create_monthly_ledger(self, salesperson, month_date, company):
        ledger = self.search([
            ("salesperson_id", "=", salesperson.id),
            ("month_date", "=", month_date),
            ("company_id", "=", company.id),
        ], limit=1)
        if ledger:
            return ledger
        return self.create({
            "salesperson_id": salesperson.id,
            "month_date": month_date,
            "company_id": company.id,
            "note": _("Monthly shortage ledger generated from vehicle closing reconciliations."),
        })

    def action_start_review(self):
        self.write({"state": "under_review"})
        return True

    def action_finalize_settlement(self):
        for rec in self:
            pending = rec.line_ids.filtered(lambda line: line.settlement_decision == "pending")
            if pending:
                raise UserError(_("Please choose a settlement decision for all shortage lines before settling the monthly ledger."))
            now = fields.Datetime.now()
            rec.line_ids.write({
                "is_finalized": True,
                "finalized_on": now,
                "finalized_by_id": self.env.user.id,
            })
            rec.write({
                "state": "settled",
                "settled_on": now,
                "settled_by_id": self.env.user.id,
            })
        return True

    def action_reopen(self):
        self.write({
            "state": "under_review",
            "settled_on": False,
            "settled_by_id": False,
        })
        self.mapped("line_ids").write({
            "is_finalized": False,
            "finalized_on": False,
            "finalized_by_id": False,
        })
        return True


class RouteSalespersonShortageLine(models.Model):
    _name = "route.salesperson.shortage.line"
    _description = "Salesperson Shortage Ledger Line"
    _order = "shortage_date desc, id desc"

    ledger_id = fields.Many2one("route.salesperson.shortage", string="Shortage Ledger", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one("res.company", string="Company", related="ledger_id.company_id", store=True, readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", related="ledger_id.salesperson_id", store=True, readonly=True)
    shortage_date = fields.Date(string="Shortage Date", required=True, readonly=True)
    closing_id = fields.Many2one("route.vehicle.closing", string="Vehicle Closing", required=True, readonly=True, ondelete="cascade")
    closing_line_id = fields.Many2one("route.vehicle.closing.line", string="Closing Line", required=True, readonly=True, ondelete="cascade")
    plan_id = fields.Many2one("route.plan", string="Route Plan", readonly=True)
    vehicle_id = fields.Many2one("route.vehicle", string="Vehicle", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", required=True, readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UoM", readonly=True)
    lot_id = fields.Many2one("stock.lot", string="Lot/Serial Number", readonly=True)
    variance_reason = fields.Selection(selection=lambda self: self.env["route.vehicle.closing.line"]._fields["variance_reason"].selection, string="Variance Reason", readonly=True)
    reconciliation_action = fields.Selection(selection=lambda self: self.env["route.vehicle.closing.line"]._fields["reconciliation_action"].selection, string="Reconciliation Action", readonly=True)
    review_note = fields.Char(string="Review Note", readonly=True)
    shortage_qty = fields.Float(string="Shortage Qty", digits="Product Unit of Measure", readonly=True)
    unit_price = fields.Float(string="Unit Price", digits="Product Price", readonly=True)
    shortage_amount = fields.Float(string="Shortage Amount", digits="Product Price", readonly=True)
    settlement_decision = fields.Selection([
        ("pending", "Pending"),
        ("deduct", "Deduct from Salesperson"),
        ("settle_admin", "Admin Settlement"),
        ("waive", "Waive / Ignore"),
    ], string="Settlement Decision", default="pending", required=True)
    settlement_note = fields.Char(string="Settlement Note")
    is_finalized = fields.Boolean(string="Finalized", default=False, readonly=True, copy=False)
    finalized_on = fields.Datetime(string="Finalized On", readonly=True, copy=False)
    finalized_by_id = fields.Many2one("res.users", string="Finalized By", readonly=True, copy=False)
    settlement_status = fields.Selection([
        ("pending", "Pending"),
        ("deduct", "Approved Deduction"),
        ("settled", "Admin Settled"),
        ("waived", "Waived"),
    ], string="Settlement Status", compute="_compute_settlement_status")

    _sql_constraints = [
        (
            "route_salesperson_shortage_line_closing_line_unique",
            "unique(closing_line_id)",
            "Each vehicle closing line can create only one salesperson shortage line.",
        ),
    ]

    @api.depends("is_finalized", "settlement_decision")
    def _compute_settlement_status(self):
        for rec in self:
            if not rec.is_finalized or rec.settlement_decision == "pending":
                rec.settlement_status = "pending"
            elif rec.settlement_decision == "deduct":
                rec.settlement_status = "deduct"
            elif rec.settlement_decision == "settle_admin":
                rec.settlement_status = "settled"
            else:
                rec.settlement_status = "waived"

    def action_finalize_lines(self):
        for rec in self:
            if rec.settlement_decision == "pending":
                raise UserError(_("Please choose a settlement decision before finalizing this shortage line."))
            rec.write({
                "is_finalized": True,
                "finalized_on": fields.Datetime.now(),
                "finalized_by_id": self.env.user.id,
            })
        return True

    def action_reopen_lines(self):
        self.write({
            "is_finalized": False,
            "finalized_on": False,
            "finalized_by_id": False,
        })
        return True
