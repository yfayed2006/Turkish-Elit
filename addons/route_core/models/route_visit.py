from odoo import models, fields, api


class RouteVisit(models.Model):
    _name = 'route.visit'
    _description = 'Route Visit'
    _order = 'visit_date desc, id desc'

    name = fields.Char(
        string='Visit Reference',
        compute='_compute_name',
        store=True
    )

    route_id = fields.Many2one(
        'route.route',
        string='Route',
        required=True
    )

    route_line_id = fields.Many2one(
        'route.line',
        string='Route Line',
        domain="[('route_id', '=', route_id)]"
    )

    store_id = fields.Many2one(
        'route.store',
        string='Store',
        required=True
    )

    user_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        required=True,
        default=lambda self: self.env.user
    )

    visit_date = fields.Date(
        string='Visit Date',
        required=True,
        default=fields.Date.context_today
    )

    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('missed', 'Missed'),
    ], string='Status', default='planned', required=True)

    check_in = fields.Datetime(string='Check In')
    check_out = fields.Datetime(string='Check Out')

    duration_minutes = fields.Float(
        string='Duration (Minutes)',
        compute='_compute_duration_minutes',
        store=True
    )

    notes = fields.Text(string='Notes')
    active = fields.Boolean(string='Active', default=True)

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

    @api.depends('route_id', 'store_id', 'visit_date')
    def _compute_name(self):
        for rec in self:
            route_name = rec.route_id.name or 'Route'
            store_name = rec.store_id.name or 'Store'
            date_text = rec.visit_date or ''
            rec.name = f'{route_name} - {store_name} - {date_text}'

    @api.depends('check_in', 'check_out')
    def _compute_duration_minutes(self):
        for rec in self:
            rec.duration_minutes = 0.0
            if rec.check_in and rec.check_out:
                delta = rec.check_out - rec.check_in
                rec.duration_minutes = delta.total_seconds() / 60.0

    @api.onchange('route_line_id')
    def _onchange_route_line_id(self):
        for rec in self:
            if rec.route_line_id:
                rec.route_id = rec.route_line_id.route_id
                rec.store_id = rec.route_line_id.store_id

    @api.onchange('route_id')
    def _onchange_route_id(self):
        for rec in self:
            if rec.route_line_id and rec.route_line_id.route_id != rec.route_id:
                rec.route_line_id = False

    def action_start_visit(self):
        for rec in self:
            rec.state = 'in_progress'
            rec.check_in = fields.Datetime.now()

    def action_finish_visit(self):
        for rec in self:
            rec.state = 'done'
            if not rec.check_in:
                rec.check_in = fields.Datetime.now()
            rec.check_out = fields.Datetime.now()

    def action_mark_missed(self):
        for rec in self:
            rec.state = 'missed'
