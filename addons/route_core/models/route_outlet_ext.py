from odoo import fields, models


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    code = fields.Char(string="Outlet Code", index=True)
    barcode = fields.Char(string="Outlet Barcode", index=True)
    default_commission_rate = fields.Float(string="Default Commission %", default=20.0)
    active_stock_tracking = fields.Boolean(string="Active Stock Tracking", default=True)

    last_visit_id = fields.Many2one(
        "route.visit",
        string="Last Visit",
        ondelete="set null",
    )

    last_settlement_date = fields.Datetime(string="Last Settlement Date")
