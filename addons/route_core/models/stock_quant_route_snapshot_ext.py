from odoo import api, fields, models


class StockQuantRouteSnapshotExt(models.Model):
    _inherit = "stock.quant"

    route_barcode = fields.Char(
        string="Barcode",
        related="product_id.barcode",
        readonly=True,
    )
    route_expiry_date = fields.Datetime(
        string="Expiry Date",
        related="lot_id.expiration_date",
        readonly=True,
    )
    route_alert_date = fields.Datetime(
        string="Alert Date",
        related="lot_id.alert_date",
        readonly=True,
    )
    route_product_image_128 = fields.Image(
        string="Product Image",
        related="product_id.image_128",
        readonly=True,
    )
    route_has_reservation = fields.Boolean(
        string="Has Reservation",
        compute="_compute_route_stock_flags",
        store=True,
        readonly=True,
    )
    route_available_less_than_qty = fields.Boolean(
        string="Available Less Than Quantity",
        compute="_compute_route_stock_flags",
        store=True,
        readonly=True,
    )

    @api.depends("quantity", "available_quantity", "reserved_quantity")
    def _compute_route_stock_flags(self):
        for rec in self:
            reserved_qty = rec.reserved_quantity or 0.0
            qty = rec.quantity or 0.0
            available_qty = rec.available_quantity or 0.0
            rec.route_has_reservation = reserved_qty > 0
            rec.route_available_less_than_qty = qty > 0 and available_qty < qty
