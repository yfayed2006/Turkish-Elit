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

    visit_count = fields.Integer(
        string='Visit Count',
        compute='_compute_visit_count'
    )

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
                partner = rec.partner_id
                rec.name = partner.name or rec.name
                rec.phone = partner.phone
                rec.mobile = getattr(partner, 'mobile', False)
                rec.email = partner.email
                rec.street = partner.street
                rec.street2 = partner.street2
                rec.city = partner.city
                rec.zip = partner.zip
                rec.country_id = partner.country_id

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for rec in self:
            if rec.latitude and (rec.latitude < -90 or rec.latitude > 90):
                raise ValidationError('Latitude must be between -90 and 90.')
            if rec.longitude and (rec.longitude < -180 or rec.longitude > 180):
                raise ValidationError('Longitude must be between -180 and 180.')

    def _compute_visit_count(self):
        visit_data = self.env['route.visit'].read_group(
            [('store_id', 'in', self.ids)],
            ['store_id'],
            ['store_id']
        )
        mapped_data = {
            item['store_id'][0]: item['store_id_count']
            for item in visit_data if item.get('store_id')
        }
        for rec in self:
            rec.visit_count = mapped_data.get(rec.id, 0)

    def action_open_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Visits',
            'res_model': 'route.visit',
            'view_mode': 'list,form',
            'domain': [('store_id', '=', self.id)],
            'context': {
                'default_store_id': self.id,
                'default_route_id': False,
            },
        }
