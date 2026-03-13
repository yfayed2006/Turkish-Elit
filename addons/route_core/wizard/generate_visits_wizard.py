from odoo import models, fields, api
from odoo.exceptions import ValidationError


class GenerateVisitsWizard(models.TransientModel):
    _name = 'generate.visits.wizard'
    _description = 'Generate Visits Wizard'

    route_id = fields.Many2one(
        'route.route',
        string='Route',
        required=True
    )

    visit_date = fields.Date(
        string='Visit Date',
        required=True,
        default=fields.Date.context_today
    )

    @api.onchange('route_id')
    def _onchange_route_id(self):
        for rec in self:
            if rec.route_id and not rec.visit_date:
                rec.visit_date = fields.Date.context_today(self)

    def _get_day_code_from_date(self, date_value):
        weekday_map = {
            0: 'mon',
            1: 'tue',
            2: 'wed',
            3: 'thu',
            4: 'fri',
            5: 'sat',
            6: 'sun',
        }
        return weekday_map.get(date_value.weekday())

    def action_generate(self):
        self.ensure_one()

        if not self.route_id.visit_day:
            raise ValidationError(
                f'Please set Visit Day for route "{self.route_id.name}" first.'
            )

        selected_day_code = self._get_day_code_from_date(self.visit_date)

        if self.route_id.visit_day != selected_day_code:
            raise ValidationError(
                f'The selected date does not match the Visit Day of route "{self.route_id.name}".'
            )

        RouteVisit = self.env['route.visit']

        for line in self.route_id.line_ids.filtered(lambda l: l.store_id and l.active):
            existing_visit = RouteVisit.search([
                ('route_id', '=', self.route_id.id),
                ('route_line_id', '=', line.id),
                ('store_id', '=', line.store_id.id),
                ('visit_date', '=', self.visit_date),
            ], limit=1)

            if not existing_visit:
                RouteVisit.create({
                    'route_id': self.route_id.id,
                    'route_line_id': line.id,
                    'store_id': line.store_id.id,
                    'user_id': self.route_id.user_id.id or self.env.user.id,
                    'visit_date': self.visit_date,
                    'state': 'planned',
                })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Visits',
            'res_model': 'route.visit',
            'view_mode': 'list,form',
            'domain': [
                ('route_id', '=', self.route_id.id),
                ('visit_date', '=', self.visit_date),
            ],
            'context': {
                'default_route_id': self.route_id.id,
                'default_user_id': self.route_id.user_id.id,
                'default_visit_date': self.visit_date,
            },
        }
