from odoo import models, fields


class RouteLine(models.Model):
    _name = 'route.line'
    _description = 'Route Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)

    route_id = fields.Many2one(
        'route.route',
        string='Route',
        required=True,
        ondelete='cascade'
    )

    store_id = fields.Many2one(
        'route.store',
        string='Store',
        required=True
    )

    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')

    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='store_id.partner_id',
        store=True,
        readonly=True
    )

    phone = fields.Char(
        string='Phone',
        related='store_id.phone',
        store=True,
        readonly=True
    )

    city = fields.Char(
        string='City',
        related='store_id.city',
        store=True,
        readonly=True
    )
