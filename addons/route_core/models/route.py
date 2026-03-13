from odoo import models, fields, api


class RouteRoute(models.Model):
    _name = 'route.route'
    _description = 'Route'
    _order = 'name'

    name = fields.Char(string='Route Name', required=True)
    code = fields.Char(string='Route Code', copy=False, readonly=True)
    active = fields.Boolean(string='Active', default=True)

    user_id = fields.Many2one(
        'res.users',
        string='Salesperson'
    )

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

    line_ids = fields.One2many(
        'route.line',
        'route_id',
        string='Stores'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('route.route') or 'NEW'
        return super().create(vals_list)
