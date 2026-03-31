from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    route_enable_lot_serial_tracking = fields.Boolean(
        string="Enable Lot/Serial Workflow",
        default=True,
        help="If disabled, Route Core hides route lot/serial fields and skips route-level lot checks.",
    )

    route_enable_expiry_tracking = fields.Boolean(
        string="Enable Expiry Workflow",
        default=True,
        help="If disabled, Route Core hides expiry fields and expiry-specific route logic.",
    )

    route_require_related_contact_for_direct_sale = fields.Boolean(
        string="Require Related Contact for Direct Sale Outlet",
        default=True,
        help="If enabled, direct sale outlets must have a related customer/contact.",
    )

    return_damaged_location_id = fields.Many2one(
        "stock.location",
        string="Return Damaged Location",
        domain="[('usage', '=', 'internal')]",
        help="Internal stock location used for damaged returned products from route visits.",
    )

    return_near_expiry_location_id = fields.Many2one(
        "stock.location",
        string="Return Near Expiry Location",
        domain="[('usage', '=', 'internal')]",
        help="Internal stock location used for near expiry returned products from route visits.",
    )
