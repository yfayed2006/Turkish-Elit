from odoo import fields, models


class RouteVisit(models.Model):
    _name = "route.visit"
    _description = "Route Visit"
    _order = "id desc"

    name = fields.Char(string="Visit Reference", required=True)
    date = fields.Date(string="Visit Date")
    partner_id = fields.Many2one("res.partner", string="Customer")
    user_id = fields.Many2one("res.users", string="Salesperson")
    notes = fields.Text(string="Notes")
