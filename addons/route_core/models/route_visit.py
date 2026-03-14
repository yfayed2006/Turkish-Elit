from odoo import fields, models


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _order = "id desc"

    name = fields.Char(string="Visit Reference", required=True)
    date = fields.Date(string="Visit Date")
    notes = fields.Text(string="Notes")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
    )
    user_id = fields.Many2one("res.users", string="Salesperson")
    partner_id = fields.Many2one("res.partner", string="Customer")

    def action_start_visit(self):
        for rec in self:
            rec.state = "in_progress"

    def action_end_visit(self):
        for rec in self:
            rec.state = "done"

    def action_cancel_visit(self):
        for rec in self:
            rec.state = "cancel"

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"
