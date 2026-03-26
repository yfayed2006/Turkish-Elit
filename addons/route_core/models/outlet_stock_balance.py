from odoo import api, fields, models
from odoo.exceptions import ValidationError


class OutletStockBalance(models.Model):
    _name = "outlet.stock.balance"
    _description = "Outlet Stock Balance"
    _order = "outlet_id, product_id"
    _rec_name = "product_id"

    outlet_id = fields.Many2one(
        "route.outlet",
        string="Outlet",
        required=True,
        ondelete="cascade",
        index=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        ondelete="restrict",
        index=True,
    )

    barcode = fields.Char(
        string="Barcode",
        related="product_id.barcode",
        store=True,
        readonly=True,
    )

    qty = fields.Float(string="Quantity", default=0.0, required=True)

    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        default=0.0,
    )

    last_visit_id = fields.Many2one(
        "route.visit",
        string="Last Visit",
        ondelete="set null",
    )

    last_updated_at = fields.Datetime(
        string="Last Updated At",
        default=fields.Datetime.now,
    )

    lot_names = fields.Char(
        string="Lot / Serial",
        compute="_compute_lot_tracking_info",
        readonly=True,
    )

    nearest_expiry_date = fields.Date(
        string="Expiry Date",
        compute="_compute_lot_tracking_info",
        readonly=True,
    )

    nearest_alert_date = fields.Date(
        string="Alert Date",
        compute="_compute_lot_tracking_info",
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "outlet_product_unique",
            "unique(outlet_id, product_id)",
            "Only one stock balance record is allowed per outlet and product.",
        ),
    ]

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.outlet_id.display_name} - {rec.product_id.display_name}"
            result.append((rec.id, name))
        return result

    @api.depends("outlet_id", "product_id")
    def _compute_lot_tracking_info(self):
        Quant = self.env["stock.quant"]
        for rec in self:
            rec.lot_names = False
            rec.nearest_expiry_date = False
            rec.nearest_alert_date = False

            if not rec.outlet_id or not rec.product_id:
                continue

            stock_location_field = rec.outlet_id._fields.get("stock_location_id")
            location = stock_location_field and rec.outlet_id.stock_location_id or False
            if not location:
                continue

            quants = Quant.search([
                ("location_id", "child_of", location.id),
                ("product_id", "=", rec.product_id.id),
                ("quantity", ">", 0),
                ("lot_id", "!=", False),
            ])

            lots = quants.mapped("lot_id")
            if not lots:
                continue

            unique_lots = lots.sorted(lambda lot: (lot.name or "", lot.id))
            rec.lot_names = ", ".join(dict.fromkeys(unique_lots.mapped("name")))

            expiry_dates = []
            alert_dates = []
            for lot in unique_lots:
                if lot.expiration_date:
                    expiry_dates.append(fields.Date.to_date(lot.expiration_date))
                if lot.alert_date:
                    alert_dates.append(fields.Date.to_date(lot.alert_date))

            if expiry_dates:
                rec.nearest_expiry_date = min(expiry_dates)
            if alert_dates:
                rec.nearest_alert_date = min(alert_dates)

    @api.onchange("product_id")
    def _onchange_product_id_set_unit_price(self):
        for rec in self:
            if rec.product_id:
                rec.unit_price = rec.product_id.lst_price or 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("last_updated_at", fields.Datetime.now())

            product_id = vals.get("product_id")
            if product_id and not vals.get("unit_price"):
                product = self.env["product.product"].browse(product_id)
                vals["unit_price"] = product.lst_price or 0.0

        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals or {})
        vals["last_updated_at"] = fields.Datetime.now()

        if vals.get("product_id") and not vals.get("unit_price"):
            product = self.env["product.product"].browse(vals["product_id"])
            vals["unit_price"] = product.lst_price or 0.0

        return super().write(vals)

    @api.constrains("qty", "unit_price")
    def _check_non_negative_qty_and_price(self):
        for rec in self:
            if rec.qty < 0:
                raise ValidationError("Quantity cannot be negative.")
            if rec.unit_price < 0:
                raise ValidationError("Unit Price cannot be negative.")
