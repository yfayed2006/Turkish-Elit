from odoo import fields, models


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
