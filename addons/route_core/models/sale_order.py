from odoo import models, fields
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    route_visit_id = fields.Many2one(
        'route.visit',
        string='Route Visit',
        readonly=True,
        copy=False
    )

    def action_open_route_visit(self):
        self.ensure_one()

        if not self.route_visit_id:
            raise ValidationError('There is no Route Visit linked to this Sales Order.')

        return {
            'type': 'ir.actions.act_window',
            'name': 'Route Visit',
            'res_model': 'route.visit',
            'res_id': self.route_visit_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
