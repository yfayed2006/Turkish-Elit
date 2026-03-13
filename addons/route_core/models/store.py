from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RouteStore(models.Model):
    _name = 'route.store'
    _description = 'Store'
    _order = 'sequence, name'

    name = fields.Char(string='Store Name', required=True)
    code = fields.Char(string='Store Code', copy=False)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        help='Linked customer/contact in Odoo'
    )

    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')

    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')

    latitude = fields.Float(string='Latitude', digits=(10, 6))
    longitude = fields.Float(string='Longitude', digits=(10, 6))

    visit_day = fields.Selection([
        ('sat', 'Saturday'),
        ('sun', 'Sunday'),
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
    ], string='Visit Day')

    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Store code must be unique.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('route.store') or 'NEW'
        return super().create(vals_list)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            if rec.partner_id:
                rec.name = rec.partner_id.name or rec.name
                rec.phone = rec.partner_id.phone
                rec.mobile = rec.partner_id.mobile
                rec.email = rec.partner_id.email
                rec.street = rec.partner_id.street
                rec.street2 = rec.partner_id.street2
                rec.city = rec.partner_id.city
                rec.zip = rec.partner_id.zip
                rec.country_id = rec.partner_id.country_id

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for rec in self:
            if rec.latitude and (rec.latitude < -90 or rec.latitude > 90):
                raise ValidationError('Latitude must be between -90 and 90.')
            if rec.longitude and (rec.longitude < -180 or rec.longitude > 180):
                raise ValidationError('Longitude must be between -180 and 180.')
