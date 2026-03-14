from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    store_code = fields.Char(string="Store Code")

    visit_order = fields.Integer(string="Visit Order")

    credit_limit_store = fields.Float(string="Store Credit Limit")

    gps_radius = fields.Integer(string="GPS Radius (meters)", default=50)
