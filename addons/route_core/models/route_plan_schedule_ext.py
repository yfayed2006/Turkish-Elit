from odoo import fields, models


class RoutePlan(models.Model):
    _inherit = "route.plan"

    weekly_schedule_id = fields.Many2one(
        "route.weekly.schedule",
        string="Weekly Schedule",
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )
