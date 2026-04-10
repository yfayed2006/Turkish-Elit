from odoo import api, fields, models


class RouteOutlet(models.Model):
    _inherit = "route.outlet"

    code = fields.Char(string="Outlet Code", index=True)
    barcode = fields.Char(string="Outlet Barcode", index=True)
    default_commission_rate = fields.Float(string="Default Commission %", default=20.0)
    active_stock_tracking = fields.Boolean(string="Active Stock Tracking", default=True)
    direct_sale_pricelist_id = fields.Many2one(
        "product.pricelist",
        string="Direct Sale Pricelist",
        ondelete="set null",
        help="Optional pricelist used for this outlet when operation mode is Direct Sale.",
    )

    last_visit_id = fields.Many2one(
        "route.visit",
        string="Last Visit",
        ondelete="set null",
    )

    last_settlement_date = fields.Datetime(string="Last Settlement Date")

    @api.onchange("partner_id", "outlet_operation_mode")
    def _onchange_direct_sale_pricelist(self):
        for record in self:
            if record.outlet_operation_mode != "direct_sale":
                record.direct_sale_pricelist_id = False
                continue
            if not record.direct_sale_pricelist_id and record.partner_id and record.partner_id.property_product_pricelist:
                record.direct_sale_pricelist_id = record.partner_id.property_product_pricelist

    @api.onchange("outlet_operation_mode")
    def _onchange_outlet_setup_mode(self):
        for record in self:
            if record.outlet_operation_mode != "consignment" and "stock_location_id" in record._fields:
                record.stock_location_id = False
