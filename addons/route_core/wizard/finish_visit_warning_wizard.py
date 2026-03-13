from odoo import models, fields
from odoo.exceptions import ValidationError


class FinishVisitWarningWizard(models.TransientModel):
    _name = 'finish.visit.warning.wizard'
    _description = 'Finish Visit Warning Wizard'

    visit_id = fields.Many2one(
        'route.visit',
        string='Visit',
        required=True
    )

    message = fields.Text(
        string='Message',
        default='No Sales Order has been created for this visit yet. You can create one now, or finish the visit anyway.',
        readonly=True
    )

    def action_create_sale_order(self):
        self.ensure_one()
        if not self.visit_id:
            raise ValidationError('No visit found.')
        return self.visit_id.action_create_sale_order()

    def action_finish_anyway(self):
        self.ensure_one()
        if not self.visit_id:
            raise ValidationError('No visit found.')

        visit = self.visit_id
        if not visit.check_in:
            raise ValidationError('You must start the visit before finishing it.')

        visit.check_out = fields.Datetime.now()
        visit.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'name': 'Visit',
            'res_model': 'route.visit',
            'res_id': visit.id,
            'view_mode': 'form',
            'target': 'current',
        }
