from odoo import models, fields, api
from odoo.exceptions import ValidationError


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
        store=True,
        digits=(16, 2)
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

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        readonly=True,
        copy=False
    )

    sale_order_count = fields.Integer(
        string='Sales Order Count',
        compute='_compute_sale_order_count'
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
                rec.duration_minutes = round(delta.total_seconds() / 60.0, 2)

    def _compute_sale_order_count(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0

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

    @api.constrains('check_in', 'check_out')
    def _check_check_out_after_check_in(self):
        for rec in self:
            if rec.check_in and rec.check_out and rec.check_out < rec.check_in:
                raise ValidationError('Check Out cannot be earlier than Check In.')

    def action_start_visit(self):
        for rec in self:
            rec.state = 'in_progress'
            rec.check_in = fields.Datetime.now()
            rec.check_out = False

    def action_finish_visit(self):
        self.ensure_one()

        if not self.check_in:
            raise ValidationError('You must start the visit before finishing it.')

        if not self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Finish Visit Warning',
                'res_model': 'finish.visit.warning.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_visit_id': self.id,
                },
            }

        self.check_out = fields.Datetime.now()
        self.state = 'done'

    def action_mark_missed(self):
        for rec in self:
            rec.state = 'missed'

    def action_create_sale_order(self):
        self.ensure_one()

        if not self.store_id.partner_id:
            raise ValidationError('This store does not have a linked customer.')

        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Sales Order',
                'res_model': 'sale.order',
                'res_id': self.sale_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        sale_order = self.env['sale.order'].create({
            'partner_id': self.store_id.partner_id.id,
            'user_id': self.user_id.id,
            'origin': self.name,
            'note': f'Created from Route Visit: {self.name}',
            'route_visit_id': self.id,
        })

        self.sale_order_id = sale_order.id

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Order',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_sale_order(self):
        self.ensure_one()

        if not self.sale_order_id:
            raise ValidationError('There is no Sales Order linked to this visit yet.')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Order',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
