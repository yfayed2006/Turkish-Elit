from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Visit Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )
    date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Salesperson",
        required=True,
        default=lambda self: self.env.user,
    )
    notes = fields.Text(string="Notes")
    no_sale_reason = fields.Text(
        string="Reason for Ending Without Sale",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    start_datetime = fields.Datetime(
        string="Start DateTime",
        readonly=True,
    )
    end_datetime = fields.Datetime_
