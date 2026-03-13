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

    store_count = fields.Integer(
        string='Store Count',
        compute='_compute_store_count',
        store=True
    )

    visit_count = fields.Integer(
        string='Visit Count',
        compute='_compute_visit_count'
    )

    @api.depends('line_ids')
    def _compute_store_count(self):
        for rec in self:
            rec.store_count = len(rec.line_ids)

    def _compute_visit_count(self):
        visit_data = self.env['route.visit'].read_group(
            [('route_id', 'in', self.ids)],
            ['route_id'],
            ['route_id']
        )
        mapped_data = {
            item['route_id'][0]: item['route_id_count']
            for item in visit_data if item.get('route_id')
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
            'domain': [('route_id', '=', self.id)],
            'context': {
                'default_route_id': self.id,
                'default_user_id': self.user_id.id,
            },
        }

    def action_generate_visits(self):
        RouteVisit = self.env['route.visit']
        today = fields.Date.context_today(self)

        for rec in self:
            for line in rec.line_ids.filtered(lambda l: l.store_id and l.active):
                existing_visit = RouteVisit.search([
                    ('route_id', '=', rec.id),
                    ('route_line_id', '=', line.id),
                    ('store_id', '=', line.store_id.id),
                    ('visit_date', '=', today),
                ], limit=1)

                if not existing_visit:
                    RouteVisit.create({
                        'route_id': rec.id,
                        'route_line_id': line.id,
                        'store_id': line.store_id.id,
                        'user_id': rec.user_id.id or self.env.user.id,
                        'visit_date': today,
                        'state': 'planned',
                    })

        return self.action_open_visits()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('route.route') or 'NEW'
        return super().create(vals_list)
