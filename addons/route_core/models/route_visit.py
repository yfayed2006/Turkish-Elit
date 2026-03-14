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
