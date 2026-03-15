from odoo import fields, models


class RoutePlanLine(models.Model):
    _name = "route.plan.line"
    _description = "Route Plan Line"
    _order = "sequence, id"

    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    plan_id = fields.Many2one(
        "route.plan",
        string="Route Plan",
        required=True,
        ondelete="cascade",
    )
    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        ondelete="restrict",
    )
    area_id = fields.Many2one(
        "route.area",
        string="Area",
        related="outlet_id.area_id",
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        related="outlet_id.partner_id",
        store=True,
        readonly=True,
    )
    visit_id = fields.Many2one(
        "route.visit",
        string="Visit",
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("visited", "Visited"),
            ("skipped", "Skipped"),
        ],
        string="Line Status",
        default="pending",
        required=True,
    )
    note = fields.Text(string="Line Note")
